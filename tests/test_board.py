from jacks_kanban.board import load_config, init_board


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


def test_load_config_missing_file(tmp_project):
    """load_config raises FileNotFoundError when kanban.yaml doesn't exist."""
    import pytest

    with pytest.raises(FileNotFoundError):
        load_config(tmp_project)
