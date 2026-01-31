from jacks_kanban.runner import build_prompt


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
