import shutil

import click
from importlib import resources
from pathlib import Path


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
