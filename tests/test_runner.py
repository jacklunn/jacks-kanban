from jacks_kanban.runner import build_prompt, execute_claude


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
