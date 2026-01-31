from pathlib import Path
from io import StringIO
from unittest.mock import patch

from jacks_kanban.dashboard import render_dashboard
from jacks_kanban.board import init_board, save_board, start_task, complete_task, fail_task


def test_render_dashboard_all_pending(tmp_path, sample_kanban_yaml):
    """Test dashboard renders correctly with all tasks pending."""
    Path(tmp_path / "kanban.yaml").write_text(sample_kanban_yaml)
    Path(tmp_path / ".kanban").mkdir()

    output = StringIO()
    with patch("sys.stdout", output):
        render_dashboard(tmp_path)

    text = output.getvalue()
    assert "TestProject" in text
    assert "0/3" in text
    assert "0%" in text


def test_render_dashboard_mixed_states(tmp_path, sample_kanban_yaml):
    """Test dashboard renders correctly with mixed task states."""
    Path(tmp_path / "kanban.yaml").write_text(sample_kanban_yaml)
    Path(tmp_path / ".kanban").mkdir()

    board = init_board(tmp_path)
    complete_task(board, "0.1")
    start_task(board, "0.2")
    save_board(tmp_path, board)

    output = StringIO()
    with patch("sys.stdout", output):
        render_dashboard(tmp_path)

    text = output.getvalue()
    assert "TestProject" in text
    assert "1/3" in text
    assert "33%" in text
    # Should show current in-progress task
    assert "0.2" in text


def test_render_dashboard_all_completed(tmp_path, sample_kanban_yaml):
    """Test dashboard renders correctly with all tasks completed."""
    Path(tmp_path / "kanban.yaml").write_text(sample_kanban_yaml)
    Path(tmp_path / ".kanban").mkdir()

    board = init_board(tmp_path)
    complete_task(board, "0.1")
    complete_task(board, "0.2")
    complete_task(board, "1.1")
    save_board(tmp_path, board)

    output = StringIO()
    with patch("sys.stdout", output):
        render_dashboard(tmp_path)

    text = output.getvalue()
    assert "3/3" in text
    assert "100%" in text


def test_render_dashboard_with_failed(tmp_path, sample_kanban_yaml):
    """Test dashboard renders correctly with a failed task."""
    Path(tmp_path / "kanban.yaml").write_text(sample_kanban_yaml)
    Path(tmp_path / ".kanban").mkdir()

    board = init_board(tmp_path)
    start_task(board, "0.1")
    fail_task(board, "0.1", reason="Tests failed")
    save_board(tmp_path, board)

    output = StringIO()
    with patch("sys.stdout", output):
        render_dashboard(tmp_path)

    text = output.getvalue()
    assert "TestProject" in text
    # Failed count should be 1
    assert "1" in text


def test_render_dashboard_shows_next_task(tmp_path, sample_kanban_yaml):
    """Test dashboard shows next available task when nothing is in progress."""
    Path(tmp_path / "kanban.yaml").write_text(sample_kanban_yaml)
    Path(tmp_path / ".kanban").mkdir()

    output = StringIO()
    with patch("sys.stdout", output):
        render_dashboard(tmp_path)

    text = output.getvalue()
    # Next task should be 0.1 (first pending with deps met)
    assert "0.1" in text
    assert "First task" in text
