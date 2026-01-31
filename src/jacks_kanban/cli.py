import os
import shutil
import time

import click
from importlib import resources
from pathlib import Path

from jacks_kanban.board import load_board, save_board, get_next_task, get_task, reset_task
from jacks_kanban.runner import run_loop, run_task
from jacks_kanban.sync import sync_board
from jacks_kanban.stream_log import process_stream
from jacks_kanban.dashboard import render_dashboard


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


@main.command()
@click.option("--loop", "-l", is_flag=True, help="Keep running until failure or done")
@click.option("--watch", "-w", is_flag=True, help="Run with tmux dashboard")
@click.option("--max", "max_tasks", type=int, help="Max tasks to run")
def run(loop, watch, max_tasks):
    """Run kanban tasks."""
    project_dir = Path.cwd()

    if watch:
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


@main.command("stream-log")
def stream_log():
    """Format claude.log stream for display. Pipe stdin."""
    process_stream()


@main.command()
@click.option("--watch", "-w", is_flag=True, help="Refresh every 2 seconds")
def dashboard(watch):
    """Show live dashboard."""
    project_dir = Path.cwd()

    if watch:
        try:
            while True:
                render_dashboard(project_dir)
                time.sleep(2)
        except KeyboardInterrupt:
            pass
    else:
        render_dashboard(project_dir)


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


if __name__ == "__main__":
    main()
