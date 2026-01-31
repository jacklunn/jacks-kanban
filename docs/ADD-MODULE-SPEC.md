# Add-Module Feature Specification

This document specifies the multi-module support feature for jacks-kanban. Use this to implement the feature in a fresh Claude Code session.

## Overview

Allow users to manage multiple kanban boards within a single project. Each module gets its own `kanban-{name}.yaml` config and `.kanban/{name}-board.json` state file.

## Commands to Implement

### 1. Global `--board` flag

Add a global option to specify which board file to use:

```bash
kanban --board kanban-auth.yaml status
kanban --board kanban-auth.yaml run --loop
kanban -b kanban-auth.yaml sync
```

### 2. `kanban add-module <name>`

Create a new module board:

```bash
kanban add-module auth
kanban add-module auth --design docs/auth-design.md
```

### 3. `kanban list-modules`

List all kanban modules in the project:

```bash
kanban list-modules
```

---

## Implementation Details

### File: `src/jacks_kanban/cli.py`

#### Update main group to accept --board flag:

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

#### Add add-module command:

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
        kanban --board kanban-auth.yaml run --loop
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
    template = f'''# {name.title()} Module
project: {name.title()}Module
design_doc: {design_doc or f"docs/{name}-design.md"}

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
'''
    
    config_path.write_text(template)
    click.echo(f"Created {config_file}")
    click.echo()
    click.echo("Next steps:")
    click.echo(f"  1. Create your design doc: {design_doc or f'docs/{name}-design.md'}")
    click.echo(f"  2. Generate tasks using Claude (see docs/task-schema.md)")
    click.echo(f"  3. Paste generated tasks into {config_file}")
    click.echo(f"  4. Run: kanban --board {config_file} run --loop")
```

#### Add list-modules command:

```python
@main.command("list-modules")
def list_modules():
    """List all kanban modules in the project."""
    import json
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

### File: `src/jacks_kanban/board.py`

#### Update load_config to accept config filename:

```python
def load_config(project_dir: Path, config_file: str = "kanban.yaml") -> dict:
    """Load kanban YAML from project directory."""
    config_path = project_dir / config_file
    if not config_path.exists():
        raise FileNotFoundError(f"No {config_file} found in {project_dir}")
    
    with open(config_path) as f:
        return yaml.safe_load(f)
```

#### Update get_board_path to derive board filename from config:

```python
def get_board_path(project_dir: Path, config_file: str = "kanban.yaml") -> Path:
    """Get board.json path for a given config file.
    
    Mapping:
        kanban.yaml -> .kanban/board.json
        kanban-auth.yaml -> .kanban/auth-board.json
        kanban-billing.yaml -> .kanban/billing-board.json
    """
    base = Path(config_file).stem  # "kanban" or "kanban-auth"
    if base == "kanban":
        board_name = "board.json"
    else:
        # Extract module name: "kanban-auth" -> "auth"
        module = base.replace("kanban-", "")
        board_name = f"{module}-board.json"
    return project_dir / KANBAN_DIR / board_name
```

#### Update load_board and save_board signatures:

```python
def load_board(project_dir: Path, config_file: str = "kanban.yaml") -> dict:
    """Load board state from .kanban/{module}-board.json."""
    board_path = get_board_path(project_dir, config_file)
    if not board_path.exists():
        return init_board(project_dir, config_file)
    with open(board_path) as f:
        return json.load(f)

def save_board(project_dir: Path, board: dict, config_file: str = "kanban.yaml") -> None:
    """Save board state to .kanban/{module}-board.json."""
    board_path = get_board_path(project_dir, config_file)
    board_path.parent.mkdir(exist_ok=True)
    with open(board_path, "w") as f:
        json.dump(board, f, indent=2)

def init_board(project_dir: Path, config_file: str = "kanban.yaml") -> dict:
    """Initialize board from kanban YAML config."""
    config = load_config(project_dir, config_file)
    
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

### Update all CLI commands to use context

Every command that uses `load_board` or `save_board` needs to:

1. Add `@click.pass_context` decorator
2. Get board_file from context: `board_file = ctx.obj.get("board_file", "kanban.yaml")`
3. Pass it to board functions: `load_board(project_dir, board_file)`

Commands to update:
- `status`
- `show`
- `reset`
- `run`
- `sync`
- `dashboard`

Example pattern:

```python
@main.command()
@click.pass_context
def status(ctx):
    """Show board status overview."""
    project_dir = Path.cwd()
    board_file = ctx.obj.get("board_file", "kanban.yaml")
    board = load_board(project_dir, board_file)
    # ... rest unchanged
```

### Update runner.py

Update `run_loop` and `run_task` to accept config_file parameter:

```python
def run_task(project_dir: Path, board: dict, task: dict, config_file: str = "kanban.yaml") -> bool:
    """Run a single task and update board state."""
    # ... implementation uses save_board(project_dir, board, config_file)

def run_loop(project_dir: Path, config_file: str = "kanban.yaml", max_tasks: int = None, callback=None) -> int:
    """Run tasks in a loop until done, failure, or max_tasks reached."""
    # ... uses load_board(project_dir, config_file)
```

### Update launch_watch_mode

```python
def launch_watch_mode(project_dir: Path, board_file: str, max_tasks: int = None):
    """Launch tmux with dashboard."""
    session_name = "kanban"
    kanban_dir = project_dir / ".kanban"
    
    os.system(f"tmux kill-session -t {session_name} 2>/dev/null")
    os.system(f"tmux new-session -d -s {session_name} -c {project_dir}")
    os.system(f"tmux split-window -v -p 30 -t {session_name}")
    
    os.system(f"tmux send-keys -t {session_name}:0.1 'tail -f {kanban_dir}/claude.log | kanban stream-log' C-m")
    
    loop_cmd = f"kanban --board {board_file} run --loop"
    if max_tasks:
        loop_cmd += f" --max {max_tasks}"
    os.system(f"tmux send-keys -t {session_name}:0.0 '{loop_cmd}' C-m")
    
    os.system(f"tmux attach-session -t {session_name}")
```

---

## Tests

### File: `tests/test_cli.py`

Add these tests:

```python
def test_add_module_creates_files(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path(".kanban").mkdir()
        
        result = runner.invoke(main, ["add-module", "auth"])
        
        assert result.exit_code == 0
        assert Path("kanban-auth.yaml").exists()
        content = Path("kanban-auth.yaml").read_text()
        assert "AuthModule" in content


def test_add_module_with_design_doc(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path(".kanban").mkdir()
        Path("docs").mkdir()
        Path("docs/auth-design.md").write_text("# Auth Design")
        
        result = runner.invoke(main, ["add-module", "auth", "--design", "docs/auth-design.md"])
        
        assert result.exit_code == 0
        content = Path("kanban-auth.yaml").read_text()
        assert "docs/auth-design.md" in content


def test_add_module_already_exists(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path(".kanban").mkdir()
        Path("kanban-auth.yaml").write_text("existing")
        
        result = runner.invoke(main, ["add-module", "auth"])
        
        assert result.exit_code == 1
        assert "already exists" in result.output


def test_list_modules(tmp_path, sample_kanban_yaml):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path(".kanban").mkdir()
        Path("kanban.yaml").write_text(sample_kanban_yaml)
        Path("kanban-auth.yaml").write_text(sample_kanban_yaml.replace("TestProject", "AuthModule"))
        
        result = runner.invoke(main, ["list-modules"])
        
        assert result.exit_code == 0
        assert "kanban.yaml" in result.output
        assert "kanban-auth.yaml" in result.output
        assert "AuthModule" in result.output


def test_status_with_board_flag(tmp_path, sample_kanban_yaml):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("kanban-auth.yaml").write_text(sample_kanban_yaml.replace("TestProject", "AuthModule"))
        Path(".kanban").mkdir()
        
        result = runner.invoke(main, ["--board", "kanban-auth.yaml", "status"])
        
        assert result.exit_code == 0
        assert "AuthModule" in result.output


def test_board_path_mapping():
    """Test that config files map to correct board paths."""
    from jacks_kanban.board import get_board_path
    from pathlib import Path
    
    project = Path("/tmp/test")
    
    assert get_board_path(project, "kanban.yaml").name == "board.json"
    assert get_board_path(project, "kanban-auth.yaml").name == "auth-board.json"
    assert get_board_path(project, "kanban-billing.yaml").name == "billing-board.json"
```

---

## Verification Commands

After implementation, verify with:

```bash
# Run all new tests
pytest tests/test_cli.py::test_add_module_creates_files -v
pytest tests/test_cli.py::test_add_module_with_design_doc -v
pytest tests/test_cli.py::test_add_module_already_exists -v
pytest tests/test_cli.py::test_list_modules -v
pytest tests/test_cli.py::test_status_with_board_flag -v
pytest tests/test_cli.py::test_board_path_mapping -v

# Manual verification
kanban add-module test-feature
cat kanban-test-feature.yaml
kanban list-modules
kanban --board kanban-test-feature.yaml status
```

---

## Usage After Implementation

```bash
# In an existing project with .kanban/
cd ~/projects/MiniBrain

# Create a new module
kanban add-module auth --design docs/auth-design.md

# Edit kanban-auth.yaml with your tasks (or generate with Claude)

# Run the module
kanban --board kanban-auth.yaml run --loop

# Check all modules
kanban list-modules
```
