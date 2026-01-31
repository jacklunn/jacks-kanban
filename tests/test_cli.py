from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner
from jacks_kanban.cli import main
from jacks_kanban.board import init_board, save_board, load_board, get_task, start_task, complete_task, fail_task, reset_task


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


def test_show_task(tmp_path, sample_kanban_yaml):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("kanban.yaml").write_text(sample_kanban_yaml)
        Path(".kanban").mkdir()

        result = runner.invoke(main, ["show", "0.1"])

        assert result.exit_code == 0
        assert "First task" in result.output
        assert "pending" in result.output
        assert "0.1" in result.output
        assert "Setup" in result.output
        assert "test -f setup.txt" in result.output
        assert "feat: setup" in result.output


def test_show_task_not_found(tmp_path, sample_kanban_yaml):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("kanban.yaml").write_text(sample_kanban_yaml)
        Path(".kanban").mkdir()

        result = runner.invoke(main, ["show", "99.99"])

        assert result.exit_code == 1
        assert "not found" in result.output


def test_show_task_with_failure_reason(tmp_path, sample_kanban_yaml):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("kanban.yaml").write_text(sample_kanban_yaml)
        Path(".kanban").mkdir()

        board = init_board(Path.cwd())
        start_task(board, "0.1")
        fail_task(board, "0.1", reason="Tests did not pass")
        save_board(Path.cwd(), board)

        result = runner.invoke(main, ["show", "0.1"])

        assert result.exit_code == 0
        assert "failed" in result.output
        assert "Tests did not pass" in result.output


def test_reset_task(tmp_path, sample_kanban_yaml):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("kanban.yaml").write_text(sample_kanban_yaml)
        Path(".kanban").mkdir()

        # First complete a task
        board = init_board(Path.cwd())
        complete_task(board, "0.1")
        save_board(Path.cwd(), board)

        # Reset it
        result = runner.invoke(main, ["reset", "0.1"])
        assert result.exit_code == 0
        assert "0.1" in result.output
        assert "pending" in result.output

        # Verify reset
        board = load_board(Path.cwd())
        task = get_task(board, "0.1")
        assert task["status"] == "pending"


def test_reset_all_tasks(tmp_path, sample_kanban_yaml):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("kanban.yaml").write_text(sample_kanban_yaml)
        Path(".kanban").mkdir()

        # Complete some tasks
        board = init_board(Path.cwd())
        complete_task(board, "0.1")
        complete_task(board, "0.2")
        start_task(board, "1.1")
        save_board(Path.cwd(), board)

        # Reset all
        result = runner.invoke(main, ["reset", "--all"])
        assert result.exit_code == 0
        assert "3" in result.output

        # Verify all reset
        board = load_board(Path.cwd())
        for task in board["tasks"]:
            assert task["status"] == "pending"


def test_reset_no_args(tmp_path, sample_kanban_yaml):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("kanban.yaml").write_text(sample_kanban_yaml)
        Path(".kanban").mkdir()

        result = runner.invoke(main, ["reset"])
        assert result.exit_code == 1


def test_run_command(tmp_path, sample_kanban_yaml):
    """Test kanban run executes a single task successfully."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("kanban.yaml").write_text(sample_kanban_yaml)
        Path(".kanban").mkdir()

        with patch("jacks_kanban.cli.run_task", return_value=True):
            result = runner.invoke(main, ["run"])

        assert result.exit_code == 0
        assert "0.1" in result.output
        assert "First task" in result.output


def test_run_command_no_tasks(tmp_path, sample_kanban_yaml):
    """Test kanban run when all tasks are completed."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("kanban.yaml").write_text(sample_kanban_yaml)
        Path(".kanban").mkdir()

        board = init_board(Path.cwd())
        complete_task(board, "0.1")
        complete_task(board, "0.2")
        complete_task(board, "1.1")
        save_board(Path.cwd(), board)

        result = runner.invoke(main, ["run"])

        assert result.exit_code == 0
        assert "No tasks available" in result.output


def test_run_command_loop(tmp_path, sample_kanban_yaml):
    """Test kanban run --loop calls run_loop."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("kanban.yaml").write_text(sample_kanban_yaml)
        Path(".kanban").mkdir()

        with patch("jacks_kanban.cli.run_loop", return_value=3) as mock_loop:
            result = runner.invoke(main, ["run", "--loop"])

        assert result.exit_code == 0
        assert "3" in result.output
        mock_loop.assert_called_once()


def test_run_command_max(tmp_path, sample_kanban_yaml):
    """Test kanban run --max passes max_tasks to run_loop."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("kanban.yaml").write_text(sample_kanban_yaml)
        Path(".kanban").mkdir()

        with patch("jacks_kanban.cli.run_loop", return_value=2) as mock_loop:
            result = runner.invoke(main, ["run", "--max", "2"])

        assert result.exit_code == 0
        mock_loop.assert_called_once()
        _, kwargs = mock_loop.call_args
        assert kwargs.get("max_tasks") == 2


def test_run_command_watch(tmp_path, sample_kanban_yaml):
    """Test kanban run --watch calls launch_watch_mode."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("kanban.yaml").write_text(sample_kanban_yaml)
        Path(".kanban").mkdir()

        with patch("jacks_kanban.cli.launch_watch_mode") as mock_watch:
            result = runner.invoke(main, ["run", "--watch"])

        assert result.exit_code == 0
        mock_watch.assert_called_once()
