from jacks_kanban.board import load_config, init_board, save_board, load_board, get_next_task


def test_load_config(tmp_project, sample_kanban_yaml):
    config_file = tmp_project / "kanban.yaml"
    config_file.write_text(sample_kanban_yaml)

    config = load_config(tmp_project)

    assert config["project"] == "TestProject"
    assert len(config["tasks"]) == 3


def test_init_board(tmp_project, sample_kanban_yaml):
    config_file = tmp_project / "kanban.yaml"
    config_file.write_text(sample_kanban_yaml)

    board = init_board(tmp_project)

    assert board["project"] == "TestProject"
    assert len(board["tasks"]) == 3
    assert all(t["status"] == "pending" for t in board["tasks"])


def test_save_and_load_board(tmp_project, sample_kanban_yaml):
    config_file = tmp_project / "kanban.yaml"
    config_file.write_text(sample_kanban_yaml)
    kanban_dir = tmp_project / ".kanban"
    kanban_dir.mkdir()

    board = init_board(tmp_project)
    board["tasks"][0]["status"] = "completed"

    save_board(tmp_project, board)
    loaded = load_board(tmp_project)

    assert loaded["tasks"][0]["status"] == "completed"


def test_load_board_initializes_when_missing(tmp_project, sample_kanban_yaml):
    """load_board falls back to init_board when board.json doesn't exist."""
    config_file = tmp_project / "kanban.yaml"
    config_file.write_text(sample_kanban_yaml)

    board = load_board(tmp_project)

    assert board["project"] == "TestProject"
    assert all(t["status"] == "pending" for t in board["tasks"])


def test_get_next_task(tmp_project, sample_kanban_yaml):
    config_file = tmp_project / "kanban.yaml"
    config_file.write_text(sample_kanban_yaml)

    board = init_board(tmp_project)

    # First task should be available (no deps)
    task = get_next_task(board)
    assert task["id"] == "0.1"

    # After completing 0.1, 0.2 should be available
    board["tasks"][0]["status"] = "completed"
    task = get_next_task(board)
    assert task["id"] == "0.2"


def test_get_next_task_blocked_by_failure(tmp_project, sample_kanban_yaml):
    config_file = tmp_project / "kanban.yaml"
    config_file.write_text(sample_kanban_yaml)

    board = init_board(tmp_project)
    board["tasks"][0]["status"] = "failed"

    # No task available when blocked by failure
    task = get_next_task(board)
    assert task is None


def test_load_config_missing_file(tmp_project):
    """load_config raises FileNotFoundError when kanban.yaml doesn't exist."""
    import pytest

    with pytest.raises(FileNotFoundError):
        load_config(tmp_project)
