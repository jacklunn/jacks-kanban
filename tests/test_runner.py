from pathlib import Path

from jacks_kanban.board import init_board, get_next_task
from jacks_kanban.runner import build_prompt, execute_claude, parse_claude_log, run_task


def test_build_prompt():
    task = {
        "id": "1.1",
        "name": "Create model",
        "section": "## Models > User",
        "verify": "pytest tests/test_models.py -v",
        "commit": "feat: add User model",
    }
    design_doc = "DESIGN.md"

    prompt = build_prompt(task, design_doc)

    assert "1.1" in prompt
    assert "Create model" in prompt
    assert "## Models > User" in prompt
    assert "pytest tests/test_models.py" in prompt
    assert "DESIGN.md" in prompt
    assert "TDD" in prompt


def test_build_prompt_includes_commit_message():
    task = {
        "id": "0.1",
        "name": "Setup project",
        "section": "## Setup",
        "verify": "test -f setup.txt",
        "commit": "feat: initial setup",
    }

    prompt = build_prompt(task, "DESIGN.md")

    assert "feat: initial setup" in prompt


def test_execute_claude_captures_log(tmp_path, mocker):
    # Mock subprocess to avoid actually calling claude
    mock_run = mocker.patch("jacks_kanban.runner.subprocess.run")
    mock_run.return_value.returncode = 0

    log_file = tmp_path / "claude.log"

    returncode = execute_claude("test prompt", log_file, project_dir=tmp_path)

    assert returncode == 0
    mock_run.assert_called_once()
    call_args = mock_run.call_args
    cmd = call_args[0][0]
    assert "claude" in cmd
    assert "--output-format" in cmd
    assert "stream-json" in cmd
    assert "-p" in cmd
    assert call_args[1]["cwd"] == tmp_path


def test_execute_claude_returns_nonzero_on_failure(tmp_path, mocker):
    mock_run = mocker.patch("jacks_kanban.runner.subprocess.run")
    mock_run.return_value.returncode = 1

    log_file = tmp_path / "claude.log"

    returncode = execute_claude("test prompt", log_file, project_dir=tmp_path)

    assert returncode == 1


def test_parse_log_success(tmp_path):
    log_content = '{"type":"system","subtype":"init","model":"claude-sonnet-4-20250514"}\n{"type":"assistant","message":{"content":[{"type":"text","text":"Working on it..."}]}}\n{"type":"result","is_error":false,"result":"Done","duration_ms":5000,"total_cost_usd":0.01,"num_turns":3,"usage":{"input_tokens":1000,"output_tokens":500,"cache_read_input_tokens":200,"cache_creation_input_tokens":100}}'

    log_file = tmp_path / "claude.log"
    log_file.write_text(log_content)

    result, tokens = parse_claude_log(log_file)

    assert result == "SUCCESS"
    assert tokens["cost_usd"] == 0.01
    assert tokens["input_tokens"] == 1000
    assert tokens["output_tokens"] == 500
    assert tokens["cache_read_input_tokens"] == 200
    assert tokens["cache_creation_input_tokens"] == 100
    assert tokens["duration_ms"] == 5000
    assert tokens["num_turns"] == 3


def test_parse_log_failure(tmp_path):
    log_content = '{"type":"result","is_error":true,"result":"Test failed"}'

    log_file = tmp_path / "claude.log"
    log_file.write_text(log_content)

    result, tokens = parse_claude_log(log_file)

    assert result.startswith("FAILED")
    assert "Test failed" in result


def test_parse_log_no_result(tmp_path):
    log_content = '{"type":"system","subtype":"init","model":"claude-sonnet-4-20250514"}\n{"type":"assistant","message":{"content":[{"type":"text","text":"Working..."}]}}'

    log_file = tmp_path / "claude.log"
    log_file.write_text(log_content)

    result, tokens = parse_claude_log(log_file)

    assert result.startswith("FAILED")
    assert tokens == {}


def test_parse_log_handles_blank_lines_and_invalid_json(tmp_path):
    log_content = '\n\nnot valid json\n{"type":"result","is_error":false,"result":"OK","duration_ms":1000,"total_cost_usd":0.05,"num_turns":1,"usage":{"input_tokens":500,"output_tokens":250,"cache_read_input_tokens":0,"cache_creation_input_tokens":0}}\n'

    log_file = tmp_path / "claude.log"
    log_file.write_text(log_content)

    result, tokens = parse_claude_log(log_file)

    assert result == "SUCCESS"
    assert tokens["cost_usd"] == 0.05


def test_run_task_updates_board_on_success(tmp_path, sample_kanban_yaml, mocker):
    Path(tmp_path / "kanban.yaml").write_text(sample_kanban_yaml)
    Path(tmp_path / ".kanban").mkdir()

    mocker.patch("jacks_kanban.runner.execute_claude", return_value=0)
    mocker.patch(
        "jacks_kanban.runner.parse_claude_log",
        return_value=("SUCCESS", {"cost_usd": 0.01}),
    )

    board = init_board(tmp_path)
    task = get_next_task(board)

    success = run_task(tmp_path, board, task)

    assert success is True
    assert board["tasks"][0]["status"] == "completed"
    assert board["tasks"][0]["tokens"]["cost_usd"] == 0.01


def test_run_task_updates_board_on_failure(tmp_path, sample_kanban_yaml, mocker):
    Path(tmp_path / "kanban.yaml").write_text(sample_kanban_yaml)
    Path(tmp_path / ".kanban").mkdir()

    mocker.patch("jacks_kanban.runner.execute_claude", return_value=1)
    mocker.patch(
        "jacks_kanban.runner.parse_claude_log",
        return_value=("FAILED:Test failed", {}),
    )

    board = init_board(tmp_path)
    task = get_next_task(board)

    success = run_task(tmp_path, board, task)

    assert success is False
    assert board["tasks"][0]["status"] == "failed"
    assert board["tasks"][0]["failure_reason"] == "Test failed"
