from pathlib import Path

from click.testing import CliRunner
from jacks_kanban.cli import main
from jacks_kanban.board import init_board, save_board, start_task, complete_task, fail_task


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


def test_status_shows_counts(tmp_path, sample_kanban_yaml):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("kanban.yaml").write_text(sample_kanban_yaml)
        Path(".kanban").mkdir()

        result = runner.invoke(main, ["status"])

        assert result.exit_code == 0
        assert "TestProject" in result.output
        assert "Pending" in result.output
        assert "Completed" in result.output
        assert "In Progress" in result.output
        assert "Failed" in result.output
        # All 3 tasks are pending
        assert "3" in result.output
        # Next task should be shown
        assert "0.1" in result.output
        assert "First task" in result.output


def test_status_with_mixed_states(tmp_path, sample_kanban_yaml):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("kanban.yaml").write_text(sample_kanban_yaml)
        Path(".kanban").mkdir()

        # Set up mixed states
        board = init_board(Path.cwd())
        complete_task(board, "0.1")
        start_task(board, "0.2")
        save_board(Path.cwd(), board)

        result = runner.invoke(main, ["status"])

        assert result.exit_code == 0
        assert "TestProject" in result.output
        # Next available task should be shown (0.2 is in_progress, 1.1 deps not met)
        # No next task available since 0.2 is in_progress and 1.1 is blocked
        assert "Completed" in result.output


def test_status_no_next_task(tmp_path, sample_kanban_yaml):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("kanban.yaml").write_text(sample_kanban_yaml)
        Path(".kanban").mkdir()

        # Complete all tasks
        board = init_board(Path.cwd())
        complete_task(board, "0.1")
        complete_task(board, "0.2")
        complete_task(board, "1.1")
        save_board(Path.cwd(), board)

        result = runner.invoke(main, ["status"])

        assert result.exit_code == 0
        assert "Next" not in result.output


def test_init_does_not_overwrite_existing_kanban_yaml(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("kanban.yaml").write_text("project: Existing")
        result = runner.invoke(main, ["init"])
        assert result.exit_code == 0
        assert Path("kanban.yaml").read_text() == "project: Existing"
        assert "already exists" in result.output
