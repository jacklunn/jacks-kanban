# jacks-kanban Build Plan

A CLI tool that orchestrates Claude Code to execute tasks from a kanban board. Each task runs in a fresh Claude session to avoid context window exhaustion.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  User's Project                                                 │
│  ├── kanban.yaml          # Task definitions (user edits)       │
│  ├── DESIGN.md            # Design doc Claude reads             │
│  └── .kanban/                                                   │
│      ├── board.json       # Runtime state (gitignored)          │
│      ├── claude.log       # Claude output (gitignored)          │
│      └── work.log         # Activity log (gitignored)           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  jacks-kanban (installed globally via pip)                      │
│                                                                 │
│  kanban init      → creates kanban.yaml template + .kanban/     │
│  kanban status    → show board overview                         │
│  kanban run       → execute one task                            │
│  kanban run --loop → execute until failure or completion        │
│  kanban run --watch → loop with tmux dashboard                  │
│  kanban sync      → sync board.json with codebase state         │
│  kanban show <id> → show task details                           │
│  kanban reset     → reset task(s) to pending                    │
└─────────────────────────────────────────────────────────────────┘
```

## Core Loop

```
while tasks available:
    1. Load kanban.yaml → find next task (pending + deps met)
    2. Mark task "in_progress" in board.json
    3. Build prompt:
       - Task details (id, name, verify command, commit message)
       - Section reference from design doc
       - TDD instructions
    4. Run: claude -p "$prompt" --output-format stream-json > claude.log
    5. Parse claude.log for SUCCESS/FAILED + token usage
    6. Update board.json (complete/fail + tokens)
    7. If success and loop mode: continue
       If failure: stop
```

## File Structure

```
jacks-kanban/
├── pyproject.toml
├── README.md
├── src/jacks_kanban/
│   ├── __init__.py
│   ├── cli.py              # Click-based CLI entry point
│   ├── board.py            # YAML loading, board.json management
│   ├── runner.py           # Task execution loop
│   ├── sync.py             # Sync board with codebase
│   ├── dashboard.py        # Live status display
│   ├── stream_log.py       # Format claude.log for viewing
│   └── templates/
│       ├── kanban.yaml     # Starter template
│       └── gitignore       # For .kanban/
├── tests/
│   ├── __init__.py
│   ├── test_board.py
│   ├── test_runner.py
│   └── test_sync.py
└── docs/
    └── task-schema.md      # Schema doc for Claude to generate tasks
```

---

## Phase 0: Project Setup

### Unit 0.1: [DONE] Initialize Python package

Create the basic package structure with pyproject.toml.

**Files to create:**
- `pyproject.toml`
- `src/jacks_kanban/__init__.py`
- `README.md`

**pyproject.toml:**
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "jacks-kanban"
version = "0.1.0"
description = "CLI tool to orchestrate Claude Code through kanban tasks"
requires-python = ">=3.11"
dependencies = [
    "click>=8.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov",
]

[project.scripts]
kanban = "jacks_kanban.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/jacks_kanban"]
```

**Verify:** `pip install -e . && kanban --help`

---

### Unit 0.2: [DONE] Create templates directory

Create the starter templates that `kanban init` will copy.

**Files to create:**
- `src/jacks_kanban/templates/kanban.yaml`
- `src/jacks_kanban/templates/gitignore`

**kanban.yaml template:**
```yaml
# Project configuration
project: MyProject
design_doc: DESIGN.md  # The design doc Claude reads for context

# Optional additional context files
context_files: []

# Phase definitions
phases:
  0: "Setup"
  1: "Core"
  2: "Features"

# Task definitions
tasks:
  - id: "0.1"
    name: "Example task"
    phase: 0
    deps: []
    section: "## Section Name"  # Section header in design_doc
    verify: "echo 'replace with real verify command'"
    commit: "feat: example commit message"
```

**gitignore template:**
```
board.json
claude.log
work.log
```

**Verify:** `test -f src/jacks_kanban/templates/kanban.yaml`

---

### Unit 0.3: [DONE] Create test infrastructure

Set up pytest and basic test structure.

**Files to create:**
- `tests/__init__.py`
- `tests/conftest.py`

**conftest.py:**
```python
import pytest
import tempfile
from pathlib import Path

@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory."""
    return tmp_path

@pytest.fixture
def sample_kanban_yaml():
    """Return sample kanban.yaml content."""
    return """
project: TestProject
design_doc: DESIGN.md
phases:
  0: Setup
  1: Core
tasks:
  - id: "0.1"
    name: "First task"
    phase: 0
    deps: []
    section: "## Setup"
    verify: "test -f setup.txt"
    commit: "feat: setup"
  - id: "0.2"
    name: "Second task"
    phase: 0
    deps: ["0.1"]
    section: "## Setup Part 2"
    verify: "test -f setup2.txt"
    commit: "feat: setup 2"
  - id: "1.1"
    name: "Core task"
    phase: 1
    deps: ["0.2"]
    section: "## Core"
    verify: "test -f core.txt"
    commit: "feat: core"
"""
```

**Verify:** `pytest --collect-only`

---

## Phase 1: Board Management

### Unit 1.1: [DONE] Load kanban.yaml

Create board.py with function to load and validate kanban.yaml.

**Files to create:**
- `src/jacks_kanban/board.py`
- `tests/test_board.py`

**Test:**
```python
def test_load_config(tmp_project, sample_kanban_yaml):
    config_file = tmp_project / "kanban.yaml"
    config_file.write_text(sample_kanban_yaml)
    
    config = load_config(tmp_project)
    
    assert config["project"] == "TestProject"
    assert len(config["tasks"]) == 3
```

**Implementation:**
```python
import yaml
from pathlib import Path

def load_config(project_dir: Path) -> dict:
    """Load kanban.yaml from project directory."""
    config_path = project_dir / "kanban.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"No kanban.yaml found in {project_dir}")
    
    with open(config_path) as f:
        return yaml.safe_load(f)
```

**Verify:** `pytest tests/test_board.py::test_load_config -v`

---

### Unit 1.2: [DONE] Initialize board.json

Create function to generate board.json from kanban.yaml config.

**Test:**
```python
def test_init_board(tmp_project, sample_kanban_yaml):
    config_file = tmp_project / "kanban.yaml"
    config_file.write_text(sample_kanban_yaml)
    
    board = init_board(tmp_project)
    
    assert board["project"] == "TestProject"
    assert len(board["tasks"]) == 3
    assert all(t["status"] == "pending" for t in board["tasks"])
```

**Implementation in board.py:**
```python
def init_board(project_dir: Path) -> dict:
    """Initialize board.json from kanban.yaml."""
    config = load_config(project_dir)
    
    board = {
        "project": config["project"],
        "design_doc": config.get("design_doc", ""),
        "tasks": []
    }
    
    for task in config["tasks"]:
        board["tasks"].append({
            "id": task["id"],
            "name": task["name"],
            "phase": task["phase"],
            "deps": task.get("deps", []),
            "section": task.get("section", ""),
            "verify": task["verify"],
            "commit": task["commit"],
            "status": "pending",
        })
    
    return board
```

**Verify:** `pytest tests/test_board.py::test_init_board -v`

---

### Unit 1.3: [DONE] Save and load board.json

Add functions to persist and load board state.

**Test:**
```python
def test_save_and_load_board(tmp_project, sample_kanban_yaml):
    config_file = tmp_project / "kanban.yaml"
    config_file.write_text(sample_kanban_yaml)
    kanban_dir = tmp_project / ".kanban"
    kanban_dir.mkdir()
    
    board = init_board(tmp_project)
    board["tasks"][0]["status"] = "completed"
    
    save_board(tmp_project, board)
    loaded = load_board(tmp_project)
    
    assert loaded["tasks"][0]["status"] == "completed"
```

**Implementation:**
```python
import json

KANBAN_DIR = ".kanban"
BOARD_FILE = "board.json"

def get_board_path(project_dir: Path) -> Path:
    return project_dir / KANBAN_DIR / BOARD_FILE

def save_board(project_dir: Path, board: dict) -> None:
    """Save board state to .kanban/board.json."""
    board_path = get_board_path(project_dir)
    board_path.parent.mkdir(exist_ok=True)
    with open(board_path, "w") as f:
        json.dump(board, f, indent=2)

def load_board(project_dir: Path) -> dict:
    """Load board state from .kanban/board.json."""
    board_path = get_board_path(project_dir)
    if not board_path.exists():
        return init_board(project_dir)
    with open(board_path) as f:
        return json.load(f)
```

**Verify:** `pytest tests/test_board.py::test_save_and_load_board -v`

---

### Unit 1.4: [DONE] Get next available task

Find the next task that is pending and has all dependencies met.

**Test:**
```python
def test_get_next_task(tmp_project, sample_kanban_yaml):
    config_file = tmp_project / "kanban.yaml"
    config_file.write_text(sample_kanban_yaml)
    
    board = init_board(tmp_project)
    
    # First task should be available
    task = get_next_task(board)
    assert task["id"] == "0.1"
    
    # After completing 0.1, 0.2 should be available
    board["tasks"][0]["status"] = "completed"
    task = get_next_task(board)
    assert task["id"] == "0.2"

def test_get_next_task_blocked_by_failure(tmp_project, sample_kanban_yaml):
    config_file = tmp_project / "kanban.yaml"
    config_file.write_text(sample_kanban_yaml)
    
    board = init_board(tmp_project)
    board["tasks"][0]["status"] = "failed"
    
    # No task available when blocked by failure
    task = get_next_task(board)
    assert task is None
```

**Implementation:**
```python
def get_task_status(board: dict, task_id: str) -> str:
    """Get status of a task by ID."""
    for task in board["tasks"]:
        if task["id"] == task_id:
            return task["status"]
    return "unknown"

def are_deps_met(board: dict, task: dict) -> bool:
    """Check if all dependencies are completed."""
    for dep_id in task.get("deps", []):
        if get_task_status(board, dep_id) != "completed":
            return False
    return True

def is_blocked_by_failure(board: dict, task: dict) -> bool:
    """Check if task is blocked by a failed dependency (transitive)."""
    visited = set()
    
    def check(t):
        if t["id"] in visited:
            return False
        visited.add(t["id"])
        for dep_id in t.get("deps", []):
            dep = next((x for x in board["tasks"] if x["id"] == dep_id), None)
            if dep:
                if dep["status"] == "failed":
                    return True
                if check(dep):
                    return True
        return False
    
    return check(task)

def get_next_task(board: dict) -> dict | None:
    """Get next available task (pending, deps met, not blocked)."""
    for task in board["tasks"]:
        if task["status"] == "pending":
            if are_deps_met(board, task) and not is_blocked_by_failure(board, task):
                return task
    return None
```

**Verify:** `pytest tests/test_board.py::test_get_next_task tests/test_board.py::test_get_next_task_blocked_by_failure -v`

---

### Unit 1.5: [DONE] Task state transitions

Add functions to start, complete, and fail tasks.

**Test:**
```python
def test_start_task(tmp_project, sample_kanban_yaml):
    config_file = tmp_project / "kanban.yaml"
    config_file.write_text(sample_kanban_yaml)
    
    board = init_board(tmp_project)
    start_task(board, "0.1")
    
    assert board["tasks"][0]["status"] == "in_progress"
    assert "started_at" in board["tasks"][0]

def test_complete_task(tmp_project, sample_kanban_yaml):
    config_file = tmp_project / "kanban.yaml"
    config_file.write_text(sample_kanban_yaml)
    
    board = init_board(tmp_project)
    start_task(board, "0.1")
    complete_task(board, "0.1", tokens={"cost_usd": 0.01})
    
    assert board["tasks"][0]["status"] == "completed"
    assert "completed_at" in board["tasks"][0]
    assert board["tasks"][0]["tokens"]["cost_usd"] == 0.01

def test_fail_task(tmp_project, sample_kanban_yaml):
    config_file = tmp_project / "kanban.yaml"
    config_file.write_text(sample_kanban_yaml)
    
    board = init_board(tmp_project)
    start_task(board, "0.1")
    fail_task(board, "0.1", reason="Test failed")
    
    assert board["tasks"][0]["status"] == "failed"
    assert board["tasks"][0]["failure_reason"] == "Test failed"
```

**Implementation:**
```python
from datetime import datetime

def get_task(board: dict, task_id: str) -> dict | None:
    """Get a task by ID."""
    for task in board["tasks"]:
        if task["id"] == task_id:
            return task
    return None

def start_task(board: dict, task_id: str) -> None:
    """Mark task as in_progress."""
    task = get_task(board, task_id)
    if not task:
        raise ValueError(f"Task {task_id} not found")
    task["status"] = "in_progress"
    task["started_at"] = datetime.now().isoformat()

def complete_task(board: dict, task_id: str, tokens: dict = None) -> None:
    """Mark task as completed."""
    task = get_task(board, task_id)
    if not task:
        raise ValueError(f"Task {task_id} not found")
    task["status"] = "completed"
    task["completed_at"] = datetime.now().isoformat()
    if tokens:
        task["tokens"] = tokens

def fail_task(board: dict, task_id: str, reason: str = "unknown") -> None:
    """Mark task as failed."""
    task = get_task(board, task_id)
    if not task:
        raise ValueError(f"Task {task_id} not found")
    task["status"] = "failed"
    task["failed_at"] = datetime.now().isoformat()
    task["failure_reason"] = reason

def reset_task(board: dict, task_id: str) -> None:
    """Reset task to pending."""
    task = get_task(board, task_id)
    if not task:
        raise ValueError(f"Task {task_id} not found")
    task["status"] = "pending"
    for key in ["started_at", "completed_at", "failed_at", "failure_reason", "tokens"]:
        task.pop(key, None)
```

**Verify:** `pytest tests/test_board.py::test_start_task tests/test_board.py::test_complete_task tests/test_board.py::test_fail_task -v`

---

## Phase 2: CLI Commands

### Unit 2.1: [DONE] CLI entry point with init command

Create the Click-based CLI with `kanban init` command.

**Files to create:**
- `src/jacks_kanban/cli.py`
- `tests/test_cli.py`

**Test:**
```python
from click.testing import CliRunner
from jacks_kanban.cli import main

def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "kanban" in result.output.lower()

def test_init_creates_files(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["init"])
        assert result.exit_code == 0
        assert Path("kanban.yaml").exists()
        assert Path(".kanban").is_dir()
```

**Implementation:**
```python
import click
import shutil
from pathlib import Path
from importlib import resources

@click.group()
def main():
    """jacks-kanban: Orchestrate Claude Code through kanban tasks."""
    pass

@main.command()
def init():
    """Initialize a new kanban project."""
    project_dir = Path.cwd()
    
    # Copy template kanban.yaml
    if not (project_dir / "kanban.yaml").exists():
        template = resources.files("jacks_kanban.templates").joinpath("kanban.yaml")
        with resources.as_file(template) as src:
            shutil.copy(src, project_dir / "kanban.yaml")
        click.echo("Created kanban.yaml")
    else:
        click.echo("kanban.yaml already exists")
    
    # Create .kanban directory
    kanban_dir = project_dir / ".kanban"
    kanban_dir.mkdir(exist_ok=True)
    
    # Copy .gitignore for .kanban
    gitignore_path = kanban_dir / ".gitignore"
    if not gitignore_path.exists():
        template = resources.files("jacks_kanban.templates").joinpath("gitignore")
        with resources.as_file(template) as src:
            shutil.copy(src, gitignore_path)
    
    click.echo("Created .kanban/")
    click.echo("\nEdit kanban.yaml to define your tasks, then run: kanban status")

if __name__ == "__main__":
    main()
```

**Verify:** `pytest tests/test_cli.py::test_cli_help tests/test_cli.py::test_init_creates_files -v`

---

### Unit 2.2: [DONE] Status command

Add `kanban status` to show board overview.

**Test:**
```python
def test_status_shows_counts(tmp_path, sample_kanban_yaml):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("kanban.yaml").write_text(sample_kanban_yaml)
        Path(".kanban").mkdir()
        
        result = runner.invoke(main, ["status"])
        
        assert result.exit_code == 0
        assert "TestProject" in result.output
        assert "Pending" in result.output
```

**Implementation in cli.py:**
```python
from jacks_kanban.board import load_board, get_next_task

@main.command()
def status():
    """Show board status overview."""
    project_dir = Path.cwd()
    board = load_board(project_dir)
    
    counts = {"pending": 0, "in_progress": 0, "completed": 0, "failed": 0}
    for task in board["tasks"]:
        counts[task["status"]] = counts.get(task["status"], 0) + 1
    
    total = len(board["tasks"])
    
    click.echo("=" * 50)
    click.echo(f"  {board['project']}")
    click.echo("=" * 50)
    click.echo(f"  Completed:   {counts['completed']:3d} / {total}")
    click.echo(f"  In Progress: {counts['in_progress']:3d}")
    click.echo(f"  Pending:     {counts['pending']:3d}")
    click.echo(f"  Failed:      {counts['failed']:3d}")
    click.echo("=" * 50)
    
    next_task = get_next_task(board)
    if next_task:
        click.echo(f"\nNext: [{next_task['id']}] {next_task['name']}")
```

**Verify:** `pytest tests/test_cli.py::test_status_shows_counts -v`

---

### Unit 2.3: [DONE] Show command

Add `kanban show <task_id>` to display task details.

**Test:**
```python
def test_show_task(tmp_path, sample_kanban_yaml):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("kanban.yaml").write_text(sample_kanban_yaml)
        Path(".kanban").mkdir()
        
        result = runner.invoke(main, ["show", "0.1"])
        
        assert result.exit_code == 0
        assert "First task" in result.output
        assert "pending" in result.output
```

**Implementation:**
```python
@main.command()
@click.argument("task_id")
def show(task_id):
    """Show details of a specific task."""
    project_dir = Path.cwd()
    board = load_board(project_dir)
    
    task = get_task(board, task_id)
    if not task:
        click.echo(f"Task {task_id} not found", err=True)
        raise SystemExit(1)
    
    click.echo(f"Task: {task['id']} - {task['name']}")
    click.echo(f"Phase: {task['phase']}")
    click.echo(f"Status: {task['status']}")
    click.echo(f"Section: {task.get('section', 'N/A')}")
    click.echo(f"Dependencies: {task.get('deps', [])}")
    click.echo(f"Verify: {task['verify']}")
    click.echo(f"Commit: {task['commit']}")
    if task.get("failure_reason"):
        click.echo(f"Failure: {task['failure_reason']}")
```

**Verify:** `pytest tests/test_cli.py::test_show_task -v`

---

### Unit 2.4: [DONE] Reset command

Add `kanban reset [task_id]` to reset tasks.

**Test:**
```python
def test_reset_task(tmp_path, sample_kanban_yaml):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("kanban.yaml").write_text(sample_kanban_yaml)
        Path(".kanban").mkdir()
        
        # First complete a task
        board = init_board(Path.cwd())
        complete_task(board, "0.1")
        save_board(Path.cwd(), board)
        
        # Reset it
        result = runner.invoke(main, ["reset", "0.1"])
        assert result.exit_code == 0
        
        # Verify reset
        board = load_board(Path.cwd())
        task = get_task(board, "0.1")
        assert task["status"] == "pending"
```

**Implementation:**
```python
@main.command()
@click.argument("task_id", required=False)
@click.option("--all", "reset_all", is_flag=True, help="Reset all tasks")
def reset(task_id, reset_all):
    """Reset task(s) to pending state."""
    project_dir = Path.cwd()
    board = load_board(project_dir)
    
    if reset_all:
        for task in board["tasks"]:
            reset_task(board, task["id"])
        save_board(project_dir, board)
        click.echo(f"Reset all {len(board['tasks'])} tasks to pending")
    elif task_id:
        reset_task(board, task_id)
        save_board(project_dir, board)
        click.echo(f"Reset task {task_id} to pending")
    else:
        click.echo("Specify a task_id or use --all", err=True)
        raise SystemExit(1)
```

**Verify:** `pytest tests/test_cli.py::test_reset_task -v`

---

## Phase 3: Runner

### Unit 3.1: [DONE] Build prompt from task

Create runner.py with function to build the Claude prompt.

**Files to create:**
- `src/jacks_kanban/runner.py`
- `tests/test_runner.py`

**Test:**
```python
def test_build_prompt():
    task = {
        "id": "1.1",
        "name": "Create model",
        "section": "## Models > User",
        "verify": "pytest tests/test_models.py -v",
        "commit": "feat: add User model",
    }
    design_doc = "DESIGN.md"
    
    prompt = build_prompt(task, design_doc)
    
    assert "1.1" in prompt
    assert "Create model" in prompt
    assert "## Models > User" in prompt
    assert "pytest tests/test_models.py" in prompt
    assert "DESIGN.md" in prompt
    assert "TDD" in prompt
```

**Implementation:**
```python
def build_prompt(task: dict, design_doc: str) -> str:
    """Build the prompt for Claude to execute a task."""
    return f"""You are implementing a single task from the build plan.

## Your Task
- **ID**: {task['id']}
- **Name**: {task['name']}
- **Section**: {task['section']}

## Instructions

1. Read the section "{task['section']}" in `{design_doc}`
2. Write the failing test FIRST (TDD approach)
3. Implement the minimal code to make the test pass
4. Run the verification command: `{task['verify']}`
5. If tests pass, commit with: `git add -A && git commit -m "{task['commit']}"`

## Rules
- This is ONE task only - do not continue to other tasks
- Follow TDD strictly: test first, then implement
- Keep implementation minimal - only what's needed to pass the test
- The design doc has all the details you need

Begin now."""
```

**Verify:** `pytest tests/test_runner.py::test_build_prompt -v`

---

### Unit 3.2: [DONE] Execute Claude and capture output

Add function to run Claude CLI and capture stream-json output.

**Test:**
```python
def test_execute_claude_captures_log(tmp_path, mocker):
    # Mock subprocess to avoid actually calling claude
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.returncode = 0
    
    log_file = tmp_path / "claude.log"
    
    execute_claude("test prompt", log_file, project_dir=tmp_path)
    
    mock_run.assert_called_once()
    call_args = mock_run.call_args
    assert "claude" in call_args[0][0]
    assert "--output-format" in call_args[0][0]
```

**Implementation:**
```python
import subprocess
from pathlib import Path

def execute_claude(prompt: str, log_file: Path, project_dir: Path) -> int:
    """Execute Claude CLI and capture output to log file."""
    cmd = [
        "claude",
        "-p", prompt,
        "--output-format", "stream-json",
        "--verbose",
        "--allowedTools", "Read,Write,Edit,MultiEdit,Bash,Glob,Grep",
    ]
    
    with open(log_file, "w") as f:
        result = subprocess.run(
            cmd,
            stdout=f,
            stderr=subprocess.STDOUT,
            cwd=project_dir,
        )
    
    return result.returncode
```

**Verify:** `pytest tests/test_runner.py::test_execute_claude_captures_log -v`

---

### Unit 3.3: [DONE] Parse Claude log for result

Extract SUCCESS/FAILED and token usage from claude.log.

**Test:**
```python
def test_parse_log_success(tmp_path):
    log_content = '''{"type":"system","subtype":"init","model":"claude-sonnet-4-20250514"}
{"type":"assistant","message":{"content":[{"type":"text","text":"Working on it..."}]}}
{"type":"result","is_error":false,"result":"Done","duration_ms":5000,"total_cost_usd":0.01,"num_turns":3,"usage":{"input_tokens":1000,"output_tokens":500,"cache_read_input_tokens":200,"cache_creation_input_tokens":100}}'''
    
    log_file = tmp_path / "claude.log"
    log_file.write_text(log_content)
    
    result, tokens = parse_claude_log(log_file)
    
    assert result == "SUCCESS"
    assert tokens["cost_usd"] == 0.01
    assert tokens["input_tokens"] == 1000
    assert tokens["output_tokens"] == 500

def test_parse_log_failure(tmp_path):
    log_content = '''{"type":"result","is_error":true,"result":"Test failed"}'''
    
    log_file = tmp_path / "claude.log"
    log_file.write_text(log_content)
    
    result, tokens = parse_claude_log(log_file)
    
    assert result.startswith("FAILED")
```

**Implementation:**
```python
import json

def parse_claude_log(log_file: Path) -> tuple[str, dict]:
    """Parse claude.log and extract result + token usage."""
    result = "FAILED:No result found"
    tokens = {}
    
    with open(log_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                if d.get("type") == "result":
                    usage = d.get("usage", {})
                    tokens = {
                        "input_tokens": usage.get("input_tokens", 0),
                        "output_tokens": usage.get("output_tokens", 0),
                        "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0),
                        "cache_creation_input_tokens": usage.get("cache_creation_input_tokens", 0),
                        "cost_usd": d.get("total_cost_usd", 0),
                        "duration_ms": d.get("duration_ms", 0),
                        "num_turns": d.get("num_turns", 0),
                    }
                    
                    if d.get("is_error"):
                        result = f"FAILED:{d.get('result', 'Unknown error')[:100]}"
                    else:
                        result = "SUCCESS"
            except json.JSONDecodeError:
                pass
    
    return result, tokens
```

**Verify:** `pytest tests/test_runner.py::test_parse_log_success tests/test_runner.py::test_parse_log_failure -v`

---

### Unit 3.4: [DONE] Run single task

Combine prompt building, execution, and result parsing.

**Test:**
```python
def test_run_task_updates_board(tmp_path, sample_kanban_yaml, mocker):
    Path(tmp_path / "kanban.yaml").write_text(sample_kanban_yaml)
    Path(tmp_path / ".kanban").mkdir()
    
    # Mock execute_claude to simulate success
    mocker.patch("jacks_kanban.runner.execute_claude", return_value=0)
    mocker.patch("jacks_kanban.runner.parse_claude_log", return_value=("SUCCESS", {"cost_usd": 0.01}))
    
    board = init_board(tmp_path)
    task = get_next_task(board)
    
    success = run_task(tmp_path, board, task)
    
    assert success is True
    assert board["tasks"][0]["status"] == "completed"
```

**Implementation:**
```python
from jacks_kanban.board import start_task, complete_task, fail_task, save_board

def run_task(project_dir: Path, board: dict, task: dict) -> bool:
    """Run a single task and update board state."""
    kanban_dir = project_dir / ".kanban"
    log_file = kanban_dir / "claude.log"
    
    # Mark started
    start_task(board, task["id"])
    save_board(project_dir, board)
    
    # Build and execute
    prompt = build_prompt(task, board.get("design_doc", "DESIGN.md"))
    execute_claude(prompt, log_file, project_dir)
    
    # Parse result
    result, tokens = parse_claude_log(log_file)
    
    if result == "SUCCESS":
        complete_task(board, task["id"], tokens)
        save_board(project_dir, board)
        return True
    else:
        reason = result.replace("FAILED:", "")
        fail_task(board, task["id"], reason)
        save_board(project_dir, board)
        return False
```

**Verify:** `pytest tests/test_runner.py::test_run_task_updates_board -v`

---

### Unit 3.5: [DONE] Task loop

Implement the main loop that runs tasks until done or failure.

**Test:**
```python
def test_run_loop_stops_on_failure(tmp_path, sample_kanban_yaml, mocker):
    Path(tmp_path / "kanban.yaml").write_text(sample_kanban_yaml)
    Path(tmp_path / ".kanban").mkdir()
    
    # First task succeeds, second fails
    results = [("SUCCESS", {}), ("FAILED:error", {})]
    mocker.patch("jacks_kanban.runner.execute_claude", return_value=0)
    mocker.patch("jacks_kanban.runner.parse_claude_log", side_effect=results)
    
    completed = run_loop(tmp_path, max_tasks=10)
    
    assert completed == 1  # Only first task completed
```

**Implementation:**
```python
from jacks_kanban.board import load_board, get_next_task

def run_loop(project_dir: Path, max_tasks: int = None, callback=None) -> int:
    """Run tasks in a loop until done, failure, or max_tasks reached."""
    completed = 0
    
    while True:
        if max_tasks and completed >= max_tasks:
            break
        
        board = load_board(project_dir)
        task = get_next_task(board)
        
        if not task:
            break
        
        if callback:
            callback("start", task)
        
        success = run_task(project_dir, board, task)
        
        if callback:
            callback("complete" if success else "fail", task)
        
        if success:
            completed += 1
        else:
            break
    
    return completed
```

**Verify:** `pytest tests/test_runner.py::test_run_loop_stops_on_failure -v`

---

### Unit 3.6: [DONE] Run command in CLI

Add `kanban run` command with --loop and --watch options.

**Test:**
```python
def test_run_command(tmp_path, sample_kanban_yaml, mocker):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("kanban.yaml").write_text(sample_kanban_yaml)
        Path(".kanban").mkdir()
        
        mocker.patch("jacks_kanban.runner.run_task", return_value=True)
        
        result = runner.invoke(main, ["run"])
        
        assert result.exit_code == 0
```

**Implementation in cli.py:**
```python
from jacks_kanban.runner import run_loop, run_task
from jacks_kanban.board import load_board, get_next_task, save_board
import os

@main.command()
@click.option("--loop", "-l", is_flag=True, help="Keep running until failure or done")
@click.option("--watch", "-w", is_flag=True, help="Run with tmux dashboard")
@click.option("--max", "max_tasks", type=int, help="Max tasks to run")
def run(loop, watch, max_tasks):
    """Run kanban tasks."""
    project_dir = Path.cwd()
    
    if watch:
        # Launch tmux session
        launch_watch_mode(project_dir, max_tasks)
        return
    
    def log_callback(event, task):
        if event == "start":
            click.echo(f"▶ Starting [{task['id']}]: {task['name']}")
        elif event == "complete":
            click.echo(f"✓ Completed [{task['id']}]")
        elif event == "fail":
            click.echo(f"✗ Failed [{task['id']}]")
    
    if loop or max_tasks:
        completed = run_loop(project_dir, max_tasks=max_tasks, callback=log_callback)
        click.echo(f"\nCompleted {completed} task(s)")
    else:
        # Run single task
        board = load_board(project_dir)
        task = get_next_task(board)
        if not task:
            click.echo("No tasks available")
            return
        log_callback("start", task)
        success = run_task(project_dir, board, task)
        log_callback("complete" if success else "fail", task)

def launch_watch_mode(project_dir: Path, max_tasks: int = None):
    """Launch tmux with dashboard."""
    session_name = "kanban"
    kanban_dir = project_dir / ".kanban"
    
    # Kill existing session
    os.system(f"tmux kill-session -t {session_name} 2>/dev/null")
    
    # Create new session
    os.system(f"tmux new-session -d -s {session_name} -c {project_dir}")
    os.system(f"tmux split-window -v -p 30 -t {session_name}")
    
    # Bottom pane: stream log
    os.system(f"tmux send-keys -t {session_name}:0.1 'tail -f {kanban_dir}/claude.log | kanban stream-log' C-m")
    
    # Top pane: run loop
    loop_cmd = "kanban run --loop"
    if max_tasks:
        loop_cmd += f" --max {max_tasks}"
    os.system(f"tmux send-keys -t {session_name}:0.0 '{loop_cmd}' C-m")
    
    # Attach
    os.system(f"tmux attach-session -t {session_name}")
```

**Verify:** `pytest tests/test_cli.py::test_run_command -v`

---

## Phase 4: Sync and Utilities

### Unit 4.1: [DONE] Sync command

Add `kanban sync` to verify tasks against codebase.

**Files to create:**
- `src/jacks_kanban/sync.py`

**Test:**
```python
def test_sync_marks_completed(tmp_path, sample_kanban_yaml):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("kanban.yaml").write_text(sample_kanban_yaml)
        Path(".kanban").mkdir()
        
        # Create file that makes first task pass
        Path("setup.txt").touch()
        
        result = runner.invoke(main, ["sync"])
        
        assert result.exit_code == 0
        board = load_board(Path.cwd())
        assert board["tasks"][0]["status"] == "completed"
```

**Implementation:**
```python
# sync.py
import subprocess
from pathlib import Path
from datetime import datetime

def run_verify(verify_cmd: str, project_dir: Path) -> bool:
    """Run verification command, return True if passes."""
    try:
        result = subprocess.run(
            verify_cmd,
            shell=True,
            cwd=project_dir,
            capture_output=True,
            timeout=60,
        )
        return result.returncode == 0
    except:
        return False

def sync_board(project_dir: Path, board: dict) -> list[str]:
    """Sync board with codebase state. Returns list of changes."""
    changes = []
    
    for task in board["tasks"]:
        if task["status"] in ["pending", "in_progress", "failed"]:
            if run_verify(task["verify"], project_dir):
                old_status = task["status"]
                task["status"] = "completed"
                task["completed_at"] = datetime.now().isoformat()
                task.pop("failure_reason", None)
                changes.append(f"[{task['id']}] {old_status} -> completed")
    
    return changes
```

**CLI in cli.py:**
```python
from jacks_kanban.sync import sync_board

@main.command()
def sync():
    """Sync board with codebase state."""
    project_dir = Path.cwd()
    board = load_board(project_dir)
    
    click.echo("Syncing board with codebase...")
    changes = sync_board(project_dir, board)
    
    if changes:
        save_board(project_dir, board)
        click.echo(f"\nUpdated {len(changes)} task(s):")
        for change in changes:
            click.echo(f"  {change}")
    else:
        click.echo("No changes needed")
```

**Verify:** `pytest tests/test_cli.py::test_sync_marks_completed -v`

---

### Unit 4.2: [DONE] Stream-log command

Add `kanban stream-log` for piping claude.log.

**Test:**
```python
def test_stream_log_parses_json(tmp_path):
    runner = CliRunner()
    log_line = '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Write","input":{"file_path":"test.py"}}]}}'
    
    result = runner.invoke(main, ["stream-log"], input=log_line)
    
    assert "Write" in result.output
    assert "test.py" in result.output
```

**Implementation:**
```python
# stream_log.py (copy existing, make it work as CLI command)
import json
import sys
import click

@main.command("stream-log")
def stream_log():
    """Format claude.log stream for display. Pipe stdin."""
    GREEN = "\033[32m"
    DIM = "\033[2m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    RESET = "\033[0m"
    
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            msg_type = d.get("type", "")
            
            if msg_type == "assistant":
                content = d.get("message", {}).get("content", [])
                for item in content:
                    if item.get("type") == "tool_use":
                        name = item.get("name", "")
                        inp = item.get("input", {})
                        if name in ["Read", "Write", "Edit", "MultiEdit"]:
                            click.echo(f"  {GREEN}->{RESET} {name}: {inp.get('file_path', '')}")
                        elif name == "Bash":
                            click.echo(f"  {GREEN}->{RESET} Bash: {inp.get('command', '')[:80]}")
                        else:
                            click.echo(f"  {GREEN}->{RESET} {name}")
            
            elif msg_type == "result":
                is_error = d.get("is_error", False)
                duration = d.get("duration_ms", 0) // 1000
                cost = d.get("total_cost_usd", 0)
                status = f"{RED}FAILED{RESET}" if is_error else f"{GREEN}SUCCESS{RESET}"
                click.echo(f"\n{BOLD}Result: {status}{RESET}")
                click.echo(f"{DIM}  {duration}s | ${cost:.4f}{RESET}")
        
        except json.JSONDecodeError:
            pass
```

**Verify:** `pytest tests/test_cli.py::test_stream_log_parses_json -v`

---

### Unit 4.3: [DONE] Dashboard command

Add `kanban dashboard` for live status display.

**Files to create:**
- `src/jacks_kanban/dashboard.py`

**Implementation:**
```python
# dashboard.py
import click
from pathlib import Path
from datetime import datetime
from jacks_kanban.board import load_board, get_next_task

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

def render_dashboard(project_dir: Path):
    """Render the dashboard display."""
    board = load_board(project_dir)
    tasks = board["tasks"]
    
    counts = {"pending": 0, "in_progress": 0, "completed": 0, "failed": 0}
    for task in tasks:
        counts[task["status"]] = counts.get(task["status"], 0) + 1
    
    total = len(tasks)
    pct = counts["completed"] / total if total > 0 else 0
    bar_width = 40
    filled = int(bar_width * pct)
    bar = f"{GREEN}{'█' * filled}{DIM}{'░' * (bar_width - filled)}{RESET}"
    
    # Clear and render
    print("\033[2J\033[H", end="")
    print(f"{BOLD}{CYAN}{'=' * 60}{RESET}")
    print(f"{BOLD}  {board['project']} - Dashboard{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 60}{RESET}")
    print()
    print(f"  Progress: {bar} {counts['completed']}/{total} ({pct*100:.0f}%)")
    print()
    print(f"  {GREEN}✓ Completed:{RESET}   {counts['completed']:3d}")
    print(f"  {YELLOW}◆ In Progress:{RESET} {counts['in_progress']:3d}")
    print(f"  {DIM}○ Pending:{RESET}     {counts['pending']:3d}")
    print(f"  {RED}✗ Failed:{RESET}      {counts['failed']:3d}")
    print()
    
    # Current/next task
    current = next((t for t in tasks if t["status"] == "in_progress"), None)
    if current:
        print(f"  {YELLOW}▶ Current:{RESET} [{current['id']}] {current['name']}")
    else:
        next_task = get_next_task(board)
        if next_task:
            print(f"  {DIM}Next:{RESET} [{next_task['id']}] {next_task['name']}")
    
    print()
    print(f"{DIM}  Updated: {datetime.now().strftime('%H:%M:%S')}{RESET}")
```

**CLI:**
```python
from jacks_kanban.dashboard import render_dashboard

@main.command()
@click.option("--watch", "-w", is_flag=True, help="Refresh every 2 seconds")
def dashboard(watch):
    """Show live dashboard."""
    import time
    project_dir = Path.cwd()
    
    if watch:
        while True:
            render_dashboard(project_dir)
            time.sleep(2)
    else:
        render_dashboard(project_dir)
```

**Verify:** `kanban dashboard` (manual test)

---

## Phase 5: Documentation

### Unit 5.1: [DONE] Create task-schema.md

The schema doc for Claude to generate tasks.

**Files to create:**
- `docs/task-schema.md`

**Content:** (Copy the schema we developed earlier in this conversation)

**Verify:** `test -f docs/task-schema.md`

---

### Unit 5.2: [DONE] Create README.md

**Content:**
```markdown
# jacks-kanban

CLI tool to orchestrate Claude Code through kanban tasks. Each task runs in a fresh Claude session to avoid context window exhaustion.

## Installation

```bash
pip install -e .
```

## Quick Start

```bash
cd your-project
kanban init                    # Creates kanban.yaml + .kanban/
# Edit kanban.yaml with your tasks
kanban status                  # See board overview
kanban run --loop              # Execute tasks until done/failure
kanban run --watch             # With tmux dashboard
```

## Workflow

1. Design your project with Claude → produce DESIGN.md
2. Ask Claude to break it into tasks → generates kanban.yaml content
3. Run `kanban run --loop` → Claude executes tasks one by one

## Commands

- `kanban init` - Initialize project
- `kanban status` - Show board overview
- `kanban show <id>` - Show task details
- `kanban run` - Run one task
- `kanban run --loop` - Run until done/failure
- `kanban run --watch` - Run with tmux dashboard
- `kanban sync` - Sync board with codebase
- `kanban reset [id]` - Reset task(s)
- `kanban dashboard` - Live status display

## Task Sizing

Each task must complete in a single Claude session without context compaction:
- One file or one small feature
- Under 300 lines of code
- 1-3 verification attempts
- Fast verify command (under 10 seconds)

See `docs/task-schema.md` for the full schema.
```

**Verify:** `test -f README.md`

---

## Phase 6: Multi-Module Support

This phase adds support for managing multiple modules within a single project. Each module gets its own kanban YAML and board file, allowing independent task execution.

### Unit 6.1: [DONE] Support --board flag in all commands

Allow specifying which board file to use via `--board` flag.

**Test:**
```python
def test_status_with_board_flag(tmp_path, sample_kanban_yaml):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("kanban-auth.yaml").write_text(sample_kanban_yaml.replace("TestProject", "AuthModule"))
        Path(".kanban").mkdir()
        
        result = runner.invoke(main, ["status", "--board", "kanban-auth.yaml"])
        
        assert result.exit_code == 0
        assert "AuthModule" in result.output
```

**Implementation:**

Add to cli.py at the group level:
```python
@click.group()
@click.option("--board", "-b", "board_file", type=click.Path(), 
              help="Path to kanban YAML file (default: kanban.yaml)")
@click.pass_context
def main(ctx, board_file):
    """jacks-kanban: Orchestrate Claude Code through kanban tasks."""
    ctx.ensure_object(dict)
    ctx.obj["board_file"] = board_file or "kanban.yaml"
```

Update board.py to accept optional config path:
```python
def load_config(project_dir: Path, config_file: str = "kanban.yaml") -> dict:
    """Load kanban YAML from project directory."""
    config_path = project_dir / config_file
    if not config_path.exists():
        raise FileNotFoundError(f"No {config_file} found in {project_dir}")
    
    with open(config_path) as f:
        return yaml.safe_load(f)

def get_board_path(project_dir: Path, config_file: str = "kanban.yaml") -> Path:
    """Get board.json path for a given config file."""
    # kanban-auth.yaml -> .kanban/auth-board.json
    base = Path(config_file).stem  # "kanban-auth"
    if base == "kanban":
        board_name = "board.json"
    else:
        # Extract module name: "kanban-auth" -> "auth"
        module = base.replace("kanban-", "").replace("kanban", "")
        board_name = f"{module}-board.json" if module else "board.json"
    return project_dir / KANBAN_DIR / board_name
```

**Verify:** `pytest tests/test_cli.py::test_status_with_board_flag -v`

---

### Unit 6.2: [DONE] Add-module command

Add `kanban add-module <name>` to create a new module board.

**Test:**
```python
def test_add_module_creates_files(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path(".kanban").mkdir()
        
        result = runner.invoke(main, ["add-module", "auth"])
        
        assert result.exit_code == 0
        assert Path("kanban-auth.yaml").exists()
        
def test_add_module_with_design_doc(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path(".kanban").mkdir()
        Path("docs").mkdir()
        Path("docs/auth-design.md").write_text("# Auth Design")
        
        result = runner.invoke(main, ["add-module", "auth", "--design", "docs/auth-design.md"])
        
        assert result.exit_code == 0
        config = yaml.safe_load(Path("kanban-auth.yaml").read_text())
        assert config["design_doc"] == "docs/auth-design.md"
```

**Implementation in cli.py:**
```python
@main.command("add-module")
@click.argument("name")
@click.option("--design", "-d", "design_doc", type=click.Path(),
              help="Path to design document for this module")
def add_module(name, design_doc):
    """Create a new module board.
    
    Creates kanban-<name>.yaml with a starter template.
    The board state will be stored in .kanban/<name>-board.json.
    
    Example:
        kanban add-module auth
        kanban add-module auth --design docs/auth-design.md
    
    Then run with:
        kanban run --board kanban-auth.yaml --loop
    """
    project_dir = Path.cwd()
    config_file = f"kanban-{name}.yaml"
    config_path = project_dir / config_file
    
    if config_path.exists():
        click.echo(f"{config_file} already exists", err=True)
        raise SystemExit(1)
    
    # Create .kanban if needed
    kanban_dir = project_dir / ".kanban"
    kanban_dir.mkdir(exist_ok=True)
    
    # Generate template
    template = f"""# {name.title()} Module
project: {name.title()}Module
design_doc: {design_doc or f'docs/{name}-design.md'}

# Phase definitions
phases:
  0: "Setup"
  1: "Core"
  2: "Integration"

# Task definitions
# Generate these by asking Claude to break down your design doc.
# See docs/task-schema.md for the schema.
tasks:
  - id: "0.1"
    name: "Example: Add {name} dependencies"
    phase: 0
    deps: []
    section: "## Setup"
    verify: "echo 'Replace with real verify command'"
    commit: "chore({name}): add dependencies"
"""
    
    config_path.write_text(template)
    click.echo(f"Created {config_file}")
    click.echo(f"")
    click.echo(f"Next steps:")
    click.echo(f"  1. Create your design doc: {design_doc or f'docs/{name}-design.md'}")
    click.echo(f"  2. Generate tasks using Claude (see docs/task-schema.md)")
    click.echo(f"  3. Paste generated tasks into {config_file}")
    click.echo(f"  4. Run: kanban run --board {config_file} --loop")
```

**Verify:** `pytest tests/test_cli.py::test_add_module_creates_files tests/test_cli.py::test_add_module_with_design_doc -v`

---

### Unit 6.3: [DONE] List-modules command

Add `kanban list-modules` to show all module boards.

**Test:**
```python
def test_list_modules(tmp_path, sample_kanban_yaml):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path(".kanban").mkdir()
        Path("kanban.yaml").write_text(sample_kanban_yaml)
        Path("kanban-auth.yaml").write_text(sample_kanban_yaml.replace("TestProject", "AuthModule"))
        Path("kanban-billing.yaml").write_text(sample_kanban_yaml.replace("TestProject", "BillingModule"))
        
        result = runner.invoke(main, ["list-modules"])
        
        assert result.exit_code == 0
        assert "kanban.yaml" in result.output
        assert "kanban-auth.yaml" in result.output
        assert "kanban-billing.yaml" in result.output
```

**Implementation:**
```python
@main.command("list-modules")
def list_modules():
    """List all kanban modules in the project."""
    project_dir = Path.cwd()
    
    # Find all kanban*.yaml files
    configs = sorted(project_dir.glob("kanban*.yaml"))
    
    if not configs:
        click.echo("No kanban modules found.")
        click.echo("Run 'kanban init' or 'kanban add-module <name>' to create one.")
        return
    
    click.echo("Kanban modules:\n")
    
    for config_path in configs:
        try:
            config = load_config(project_dir, config_path.name)
            board_path = get_board_path(project_dir, config_path.name)
            
            # Count tasks by status
            if board_path.exists():
                with open(board_path) as f:
                    board = json.load(f)
                tasks = board["tasks"]
                completed = sum(1 for t in tasks if t["status"] == "completed")
                total = len(tasks)
                status = f"{completed}/{total} complete"
            else:
                total = len(config.get("tasks", []))
                status = f"{total} tasks (not started)"
            
            click.echo(f"  {config_path.name}")
            click.echo(f"    Project: {config.get('project', 'Unknown')}")
            click.echo(f"    Design:  {config.get('design_doc', 'N/A')}")
            click.echo(f"    Status:  {status}")
            click.echo()
        except Exception as e:
            click.echo(f"  {config_path.name} (error: {e})")
            click.echo()
```

**Verify:** `pytest tests/test_cli.py::test_list_modules -v`

---

### Unit 6.4: [DONE] Run command with --board

Update run command to use the --board flag from context.

**Test:**
```python
def test_run_with_board_flag(tmp_path, sample_kanban_yaml, mocker):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("kanban-auth.yaml").write_text(sample_kanban_yaml.replace("TestProject", "AuthModule"))
        Path(".kanban").mkdir()
        
        mocker.patch("jacks_kanban.runner.run_task", return_value=True)
        
        result = runner.invoke(main, ["--board", "kanban-auth.yaml", "run"])
        
        assert result.exit_code == 0
        # Verify it used the right board
        assert Path(".kanban/auth-board.json").exists()
```

**Implementation:**

Update all commands to get board_file from context:
```python
@main.command()
@click.pass_context
def status(ctx):
    """Show board status overview."""
    project_dir = Path.cwd()
    board_file = ctx.obj.get("board_file", "kanban.yaml")
    board = load_board(project_dir, board_file)
    # ... rest of implementation

@main.command()
@click.option("--loop", "-l", is_flag=True, help="Keep running until failure or done")
@click.option("--watch", "-w", is_flag=True, help="Run with tmux dashboard")
@click.option("--max", "max_tasks", type=int, help="Max tasks to run")
@click.pass_context
def run(ctx, loop, watch, max_tasks):
    """Run kanban tasks."""
    project_dir = Path.cwd()
    board_file = ctx.obj.get("board_file", "kanban.yaml")
    
    if watch:
        launch_watch_mode(project_dir, board_file, max_tasks)
        return
    
    # ... rest uses board_file
```

Update `launch_watch_mode` to pass board file:
```python
def launch_watch_mode(project_dir: Path, board_file: str, max_tasks: int = None):
    """Launch tmux with dashboard."""
    session_name = "kanban"
    kanban_dir = project_dir / ".kanban"
    
    os.system(f"tmux kill-session -t {session_name} 2>/dev/null")
    os.system(f"tmux new-session -d -s {session_name} -c {project_dir}")
    os.system(f"tmux split-window -v -p 30 -t {session_name}")
    
    # Bottom pane: stream log  
    os.system(f"tmux send-keys -t {session_name}:0.1 'tail -f {kanban_dir}/claude.log | kanban stream-log' C-m")
    
    # Top pane: run loop with board flag
    loop_cmd = f"kanban --board {board_file} run --loop"
    if max_tasks:
        loop_cmd += f" --max {max_tasks}"
    os.system(f"tmux send-keys -t {session_name}:0.0 '{loop_cmd}' C-m")
    
    os.system(f"tmux attach-session -t {session_name}")
```

**Verify:** `pytest tests/test_cli.py::test_run_with_board_flag -v`

---

### Unit 6.5: [DONE] Sync and reset with --board

Ensure sync and reset commands also respect the --board flag.

**Test:**
```python
def test_sync_with_board_flag(tmp_path, sample_kanban_yaml):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("kanban-auth.yaml").write_text(sample_kanban_yaml)
        Path(".kanban").mkdir()
        Path("setup.txt").touch()  # Makes first task pass
        
        result = runner.invoke(main, ["--board", "kanban-auth.yaml", "sync"])
        
        assert result.exit_code == 0
        assert Path(".kanban/auth-board.json").exists()
```

**Implementation:**

Update sync and reset commands:
```python
@main.command()
@click.pass_context
def sync(ctx):
    """Sync board with codebase state."""
    project_dir = Path.cwd()
    board_file = ctx.obj.get("board_file", "kanban.yaml")
    board = load_board(project_dir, board_file)
    
    click.echo(f"Syncing {board_file} with codebase...")
    changes = sync_board(project_dir, board)
    
    if changes:
        save_board(project_dir, board, board_file)
        click.echo(f"\nUpdated {len(changes)} task(s):")
        for change in changes:
            click.echo(f"  {change}")
    else:
        click.echo("No changes needed")

@main.command()
@click.argument("task_id", required=False)
@click.option("--all", "reset_all", is_flag=True, help="Reset all tasks")
@click.pass_context
def reset(ctx, task_id, reset_all):
    """Reset task(s) to pending state."""
    project_dir = Path.cwd()
    board_file = ctx.obj.get("board_file", "kanban.yaml")
    board = load_board(project_dir, board_file)
    
    # ... rest of implementation, then:
    save_board(project_dir, board, board_file)
```

**Verify:** `pytest tests/test_cli.py::test_sync_with_board_flag -v`

---

## Phase 6 Usage Examples

Once Phase 6 is complete, the multi-module workflow looks like:

### Creating a New Module

```bash
cd ~/projects/MiniBrain

# Create the module
kanban add-module auth --design docs/auth-design.md

# This creates:
#   kanban-auth.yaml     (edit this with your tasks)
#   .kanban/auth-board.json (created on first run)
```

### Generating Tasks

```bash
# Chat with Claude, paste your design doc + task-schema.md
# Claude generates YAML task definitions
# Paste into kanban-auth.yaml
```

### Running the Module

```bash
# Check status
kanban --board kanban-auth.yaml status

# Run tasks
kanban --board kanban-auth.yaml run --loop

# Or with dashboard
kanban --board kanban-auth.yaml run --watch

# Sync if you made manual changes
kanban --board kanban-auth.yaml sync
```

### Listing All Modules

```bash
kanban list-modules

# Output:
# Kanban modules:
#
#   kanban.yaml
#     Project: MiniBrain History System
#     Design:  minibrain-history-build-plan.md
#     Status:  85/85 complete
#
#   kanban-auth.yaml
#     Project: AuthModule  
#     Design:  docs/auth-design.md
#     Status:  12/24 complete
```

---

## Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| 0 | 3 | Project setup, templates, tests |
| 1 | 5 | Board management (load, save, next, transitions) |
| 2 | 4 | CLI commands (init, status, show, reset) |
| 3 | 6 | Runner (prompt, execute, parse, loop, run command) |
| 4 | 3 | Sync, stream-log, dashboard |
| 5 | 2 | Documentation |
| 6 | 5 | Multi-module support (--board flag, add-module, list-modules) |

**Total: 28 tasks**

Each task is sized to complete in a single Claude session.
