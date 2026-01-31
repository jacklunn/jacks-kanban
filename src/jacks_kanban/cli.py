import shutil

import click
from importlib import resources
from pathlib import Path

from jacks_kanban.board import load_board, save_board, get_next_task, get_task, reset_task


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


if __name__ == "__main__":
    main()
