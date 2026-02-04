"""Plan document to kanban tasks converter using Claude."""

import json
import re
import subprocess
import tempfile
from importlib import resources
from pathlib import Path


def load_task_schema() -> str:
    """Load the task-schema.md content from docs/."""
    # Try loading from package resources first
    try:
        schema = resources.files("jacks_kanban").parent.parent / "docs" / "task-schema.md"
        if schema.exists():
            return schema.read_text()
    except Exception:
        pass

    # Fall back to relative path from cwd
    schema_path = Path("docs/task-schema.md")
    if schema_path.exists():
        return schema_path.read_text()

    # Return minimal inline schema if file not found
    return """
## Task Schema (minimal)

Each task in kanban.yaml should have:
- id: "phase.sequence" (e.g., "0.1", "1.2")
- name: Short descriptive name
- phase: Phase number (integer)
- deps: List of task IDs this depends on
- section: Section reference in design doc
- verify: Shell command that exits 0 on success
- commit: Conventional commit message
"""


def build_import_prompt(plan_content: str, project_name: str = None, design_doc_path: str = None) -> str:
    """Build the prompt for Claude to convert a plan into kanban tasks."""
    task_schema = load_task_schema()

    project_line = f'project: {project_name}' if project_name else 'project: MyProject  # Update this'
    design_line = f'design_doc: {design_doc_path}' if design_doc_path else 'design_doc: DESIGN.md  # Update this'

    return f"""You are converting a plan document into kanban.yaml tasks.

## Task Schema Reference

{task_schema}

## Critical Rules

1. Each task MUST be completable in a single Claude session (~200K context)
2. Tasks should produce under 300 lines of code
3. Use TDD: separate "write test" and "implement" tasks where appropriate
4. Verify commands must be fast (<10 seconds) and specific
5. Keep dependency chains short
6. Follow conventional commit messages

## Output Format

Output ONLY valid YAML content that can be pasted directly into a kanban.yaml file.
Start with the project configuration, then phases, then tasks.
Do not include any explanation before or after the YAML.
Do not wrap in markdown code fences.

Start the output exactly like this:
```
{project_line}
{design_line}

phases:
  0: "Setup"
  ...

tasks:
  - id: "0.1"
    ...
```

## Plan Document to Convert

{plan_content}

Generate the kanban.yaml content now:"""


def execute_claude_import(prompt: str, project_dir: Path) -> tuple[str, dict]:
    """Execute Claude to convert plan and return the output."""
    cmd = [
        "claude",
        "-p", prompt,
        "--output-format", "stream-json",
    ]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
        log_file = Path(f.name)

    try:
        with open(log_file, "w") as f:
            result = subprocess.run(
                cmd,
                stdout=f,
                stderr=subprocess.STDOUT,
                cwd=project_dir,
            )

        # Parse the log to extract the assistant's response
        output_text = ""
        tokens = {}

        with open(log_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    if d.get("type") == "assistant":
                        content = d.get("message", {}).get("content", [])
                        for item in content:
                            if item.get("type") == "text":
                                output_text += item.get("text", "")
                    elif d.get("type") == "result":
                        usage = d.get("usage", {})
                        tokens = {
                            "input_tokens": usage.get("input_tokens", 0),
                            "output_tokens": usage.get("output_tokens", 0),
                            "cost_usd": d.get("total_cost_usd", 0),
                        }
                except json.JSONDecodeError:
                    pass

        return output_text, tokens
    finally:
        log_file.unlink(missing_ok=True)


def extract_yaml_from_response(response: str) -> str:
    """Extract YAML content from Claude's response.

    Handles cases where the response might include markdown code fences
    or other surrounding text.
    """
    # Remove markdown code fences if present
    yaml_match = re.search(r'```(?:yaml)?\s*\n(.*?)```', response, re.DOTALL)
    if yaml_match:
        return yaml_match.group(1).strip()

    # If the response starts with 'project:' or '#', assume it's raw YAML
    lines = response.strip().split('\n')
    if lines and (lines[0].startswith('project:') or lines[0].startswith('#')):
        return response.strip()

    # Try to find where YAML starts (look for 'project:' line)
    for i, line in enumerate(lines):
        if line.startswith('project:'):
            return '\n'.join(lines[i:]).strip()

    # Return as-is if no patterns match
    return response.strip()


def import_plan(
    plan_path: Path,
    project_dir: Path,
    project_name: str = None,
    output_path: Path = None,
    append_to: Path = None,
) -> tuple[str, dict]:
    """Convert a plan document to kanban tasks.

    Args:
        plan_path: Path to the plan/design document
        project_dir: Project directory for running Claude
        project_name: Optional project name for the output
        output_path: Optional path to write output file
        append_to: Optional path to append tasks to existing file

    Returns:
        Tuple of (yaml_content, token_usage)
    """
    # Read the plan document
    plan_content = plan_path.read_text()

    # Use plan filename as design_doc reference
    design_doc_path = str(plan_path.relative_to(project_dir)) if plan_path.is_relative_to(project_dir) else plan_path.name

    # Infer project name from plan if not provided
    if not project_name:
        # Try to extract from first heading
        heading_match = re.search(r'^#\s+(.+)$', plan_content, re.MULTILINE)
        if heading_match:
            project_name = heading_match.group(1).strip()

    # Build prompt and execute
    prompt = build_import_prompt(plan_content, project_name, design_doc_path)
    response, tokens = execute_claude_import(prompt, project_dir)

    # Extract YAML from response
    yaml_content = extract_yaml_from_response(response)

    # Handle output
    if output_path:
        output_path.write_text(yaml_content)
    elif append_to:
        # Append tasks section to existing file
        existing = append_to.read_text()
        # Extract just the tasks from generated content
        tasks_match = re.search(r'^tasks:\s*\n(.*)', yaml_content, re.MULTILINE | re.DOTALL)
        if tasks_match:
            tasks_section = tasks_match.group(0)
            # Append to existing file
            with open(append_to, 'a') as f:
                f.write('\n\n# === Imported tasks ===\n')
                f.write(tasks_section)

    return yaml_content, tokens
