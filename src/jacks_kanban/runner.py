import json
import subprocess
from pathlib import Path


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
