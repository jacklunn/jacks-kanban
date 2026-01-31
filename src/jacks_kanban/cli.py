import shutil

import click
from importlib import resources
from pathlib import Path

from jacks_kanban.board import load_board, get_next_task


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


if __name__ == "__main__":
    main()
