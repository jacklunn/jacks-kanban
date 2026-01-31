from pathlib import Path

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
        assert Path(".kanban/.gitignore").exists()


def test_init_does_not_overwrite_existing_kanban_yaml(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("kanban.yaml").write_text("project: Existing")
        result = runner.invoke(main, ["init"])
        assert result.exit_code == 0
        assert Path("kanban.yaml").read_text() == "project: Existing"
        assert "already exists" in result.output
