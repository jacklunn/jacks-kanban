import os
import shutil
import time

import click
from importlib import resources
from pathlib import Path

from jacks_kanban.board import load_board, load_config, save_board, get_board_path, get_next_task, get_task, reset_task
from jacks_kanban.runner import run_loop, run_task
from jacks_kanban.sync import sync_board
from jacks_kanban.stream_log import process_stream
from jacks_kanban.dashboard import render_dashboard
from jacks_kanban.importer import import_plan


@click.group()
@click.option("--board", "-b", "board_file", type=click.Path(),
              help="Path to kanban YAML file (default: kanban.yaml)")
@click.pass_context
def main(ctx, board_file):
    """jacks-kanban: Orchestrate Claude Code through kanban tasks."""
    ctx.ensure_object(dict)
    ctx.obj["board_file"] = board_file or "kanban.yaml"


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


@main.command()
@click.pass_context
def status(ctx):
    """Show board status overview."""
    project_dir = Path.cwd()
    board_file = ctx.obj.get("board_file", "kanban.yaml")
    board = load_board(project_dir, board_file)

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


@main.command()
@click.argument("task_id")
@click.pass_context
def show(ctx, task_id):
    """Show details of a specific task."""
    project_dir = Path.cwd()
    board_file = ctx.obj.get("board_file", "kanban.yaml")
    board = load_board(project_dir, board_file)

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


@main.command()
@click.argument("task_id", required=False)
@click.option("--all", "reset_all", is_flag=True, help="Reset all tasks")
@click.pass_context
def reset(ctx, task_id, reset_all):
    """Reset task(s) to pending state."""
    project_dir = Path.cwd()
    board_file = ctx.obj.get("board_file", "kanban.yaml")
    board = load_board(project_dir, board_file)

    if reset_all:
        for task in board["tasks"]:
            reset_task(board, task["id"])
        save_board(project_dir, board, board_file)
        click.echo(f"Reset all {len(board['tasks'])} tasks to pending")
    elif task_id:
        reset_task(board, task_id)
        save_board(project_dir, board, board_file)
        click.echo(f"Reset task {task_id} to pending")
    else:
        click.echo("Specify a task_id or use --all", err=True)
        raise SystemExit(1)


@main.command()
@click.pass_context
def sync(ctx):
    """Sync board with codebase state."""
    project_dir = Path.cwd()
    board_file = ctx.obj.get("board_file", "kanban.yaml")
    board = load_board(project_dir, board_file)

    click.echo("Syncing board with codebase...")
    changes = sync_board(project_dir, board)

    if changes:
        save_board(project_dir, board, board_file)
        click.echo(f"\nUpdated {len(changes)} task(s):")
        for change in changes:
            click.echo(f"  {change}")
    else:
        click.echo("No changes needed")


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

    def log_callback(event, task):
        if event == "start":
            click.echo(f"▶ Starting [{task['id']}]: {task['name']}")
        elif event == "complete":
            click.echo(f"✓ Completed [{task['id']}]")
        elif event == "fail":
            click.echo(f"✗ Failed [{task['id']}]")

    if loop or max_tasks:
        completed = run_loop(project_dir, config_file=board_file, max_tasks=max_tasks, callback=log_callback)
        click.echo(f"\nCompleted {completed} task(s)")
    else:
        # Run single task
        board = load_board(project_dir, board_file)
        task = get_next_task(board)
        if not task:
            click.echo("No tasks available")
            return
        log_callback("start", task)
        success = run_task(project_dir, board, task, config_file=board_file)
        log_callback("complete" if success else "fail", task)


@main.command("stream-log")
def stream_log():
    """Format claude.log stream for display. Pipe stdin."""
    process_stream()


@main.command()
@click.option("--watch", "-w", is_flag=True, help="Refresh every 2 seconds")
@click.pass_context
def dashboard(ctx, watch):
    """Show live dashboard."""
    project_dir = Path.cwd()
    board_file = ctx.obj.get("board_file", "kanban.yaml")

    if watch:
        try:
            while True:
                render_dashboard(project_dir, board_file)
                time.sleep(2)
        except KeyboardInterrupt:
            pass
    else:
        render_dashboard(project_dir, board_file)


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


@main.command("import-plan")
@click.argument("plan_file", type=click.Path(exists=True))
@click.option("--output", "-o", "output_file", type=click.Path(),
              help="Write output to this file instead of stdout")
@click.option("--project", "-p", "project_name",
              help="Project name for the generated config")
@click.option("--append", "-a", "append_to", type=click.Path(exists=True),
              help="Append generated tasks to an existing kanban file")
def import_plan_cmd(plan_file, output_file, project_name, append_to):
    """Convert a plan document into kanban tasks using Claude.

    Reads a plan/design document and uses Claude to generate properly
    formatted kanban.yaml task definitions.

    \b
    Examples:
        # Output to stdout for review
        kanban import-plan docs/my-design.md

        # Save directly to a file
        kanban import-plan docs/my-design.md --output kanban-feature.yaml

        # Specify project name
        kanban import-plan docs/auth-design.md -p AuthModule -o kanban-auth.yaml

        # Append tasks to existing board
        kanban import-plan docs/new-features.md --append kanban.yaml
    """
    project_dir = Path.cwd()
    plan_path = Path(plan_file)

    output_path = Path(output_file) if output_file else None
    append_path = Path(append_to) if append_to else None

    click.echo(f"Importing plan from {plan_file}...", err=True)
    click.echo("(This calls Claude to analyze and convert the document)", err=True)
    click.echo("", err=True)

    try:
        yaml_content, tokens = import_plan(
            plan_path=plan_path,
            project_dir=project_dir,
            project_name=project_name,
            output_path=output_path,
            append_to=append_path,
        )

        if output_path:
            click.echo(f"Wrote {output_path}", err=True)
        elif append_path:
            click.echo(f"Appended tasks to {append_path}", err=True)
        else:
            # Output to stdout
            click.echo(yaml_content)

        # Show token usage
        if tokens:
            cost = tokens.get("cost_usd", 0)
            click.echo("", err=True)
            click.echo(f"Tokens: {tokens.get('input_tokens', 0)} in / {tokens.get('output_tokens', 0)} out | Cost: ${cost:.4f}", err=True)

    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    except Exception as e:
        click.echo(f"Error during import: {e}", err=True)
        raise SystemExit(1)


def launch_watch_mode(project_dir: Path, board_file: str = "kanban.yaml", max_tasks: int = None):
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
    loop_cmd = f"kanban --board {board_file} run --loop"
    if max_tasks:
        loop_cmd += f" --max {max_tasks}"
    os.system(f"tmux send-keys -t {session_name}:0.0 '{loop_cmd}' C-m")

    # Attach
    os.system(f"tmux attach-session -t {session_name}")


if __name__ == "__main__":
    main()
