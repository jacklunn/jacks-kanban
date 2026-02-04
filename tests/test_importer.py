"""Tests for the plan importer module."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from jacks_kanban.importer import (
    build_import_prompt,
    extract_yaml_from_response,
    load_task_schema,
)


class TestBuildImportPrompt:
    """Tests for build_import_prompt function."""

    def test_includes_plan_content(self):
        """Plan content should be included in the prompt."""
        plan = "# My Project\n\nThis is my plan."
        prompt = build_import_prompt(plan)
        assert "# My Project" in prompt
        assert "This is my plan." in prompt

    def test_includes_project_name_when_provided(self):
        """Project name should be included when specified."""
        prompt = build_import_prompt("plan content", project_name="TestProject")
        assert "project: TestProject" in prompt

    def test_includes_design_doc_path_when_provided(self):
        """Design doc path should be included when specified."""
        prompt = build_import_prompt("plan content", design_doc_path="docs/design.md")
        assert "design_doc: docs/design.md" in prompt

    def test_includes_task_sizing_rules(self):
        """Prompt should include task sizing guidance."""
        prompt = build_import_prompt("plan content")
        assert "300 lines" in prompt or "single Claude session" in prompt

    def test_requests_yaml_output(self):
        """Prompt should request YAML output format."""
        prompt = build_import_prompt("plan content")
        assert "YAML" in prompt


class TestExtractYamlFromResponse:
    """Tests for extract_yaml_from_response function."""

    def test_extracts_from_code_fence(self):
        """Should extract YAML from markdown code fences."""
        response = """Here's the config:

```yaml
project: Test
tasks:
  - id: "0.1"
```

That's all!"""
        result = extract_yaml_from_response(response)
        assert result.startswith("project: Test")
        assert "tasks:" in result
        assert "```" not in result

    def test_handles_raw_yaml(self):
        """Should handle raw YAML without code fences."""
        response = """project: Test
design_doc: DESIGN.md

tasks:
  - id: "0.1"
    name: First task"""
        result = extract_yaml_from_response(response)
        assert result.startswith("project: Test")
        assert "tasks:" in result

    def test_handles_yaml_with_leading_comment(self):
        """Should handle YAML that starts with a comment."""
        response = """# Project config
project: Test
tasks:
  - id: "0.1" """
        result = extract_yaml_from_response(response)
        assert "# Project config" in result
        assert "project: Test" in result

    def test_finds_project_line_in_mixed_content(self):
        """Should find project: line even with preceding text."""
        response = """Sure, here's the kanban config:

project: MyProject
design_doc: docs/plan.md

tasks:
  - id: "0.1"
    name: Setup"""
        result = extract_yaml_from_response(response)
        assert result.startswith("project: MyProject")

    def test_handles_code_fence_without_yaml_marker(self):
        """Should extract from code fence without yaml language marker."""
        response = """```
project: Test
tasks: []
```"""
        result = extract_yaml_from_response(response)
        assert "project: Test" in result


class TestLoadTaskSchema:
    """Tests for load_task_schema function."""

    def test_returns_string(self):
        """Should return a non-empty string."""
        schema = load_task_schema()
        assert isinstance(schema, str)
        assert len(schema) > 0

    def test_includes_schema_content(self):
        """Should include key schema elements."""
        schema = load_task_schema()
        # Should mention key fields
        assert "id" in schema.lower()
        assert "verify" in schema.lower()


class TestImportPlanCLI:
    """Tests for the import-plan CLI command."""

    def test_command_exists(self):
        """The import-plan command should be registered."""
        from click.testing import CliRunner
        from jacks_kanban.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["import-plan", "--help"])
        assert result.exit_code == 0
        assert "plan document" in result.output.lower() or "PLAN_FILE" in result.output

    def test_requires_plan_file_argument(self):
        """Should require a plan file argument."""
        from click.testing import CliRunner
        from jacks_kanban.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["import-plan"])
        assert result.exit_code != 0

    def test_shows_output_option(self):
        """Should show --output option in help."""
        from click.testing import CliRunner
        from jacks_kanban.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["import-plan", "--help"])
        assert "--output" in result.output or "-o" in result.output

    def test_shows_project_option(self):
        """Should show --project option in help."""
        from click.testing import CliRunner
        from jacks_kanban.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["import-plan", "--help"])
        assert "--project" in result.output or "-p" in result.output

    def test_file_not_found_error(self):
        """Should error on non-existent plan file."""
        from click.testing import CliRunner
        from jacks_kanban.cli import main

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["import-plan", "nonexistent.md"])
            assert result.exit_code != 0


class TestImportPlanIntegration:
    """Integration tests for import_plan function (mocked Claude)."""

    def test_import_plan_with_mocked_claude(self, tmp_path):
        """Should process plan file and return YAML."""
        from jacks_kanban.importer import import_plan

        # Create a test plan file
        plan_file = tmp_path / "plan.md"
        plan_file.write_text("""# Test Project

## Phase 1: Setup
Create the project structure.

## Phase 2: Core
Implement core features.
""")

        mock_yaml = """project: TestProject
design_doc: plan.md

phases:
  0: "Setup"
  1: "Core"

tasks:
  - id: "0.1"
    name: Create project structure
    phase: 0
    deps: []
    section: "## Phase 1: Setup"
    verify: "test -d src"
    commit: "chore: initial project structure"
"""

        with patch('jacks_kanban.importer.execute_claude_import') as mock_execute:
            mock_execute.return_value = (mock_yaml, {"input_tokens": 100, "output_tokens": 50, "cost_usd": 0.001})

            yaml_content, tokens = import_plan(
                plan_path=plan_file,
                project_dir=tmp_path,
                project_name="TestProject",
            )

            assert "project: TestProject" in yaml_content
            assert "tasks:" in yaml_content
            assert tokens["cost_usd"] == 0.001

    def test_import_plan_writes_output_file(self, tmp_path):
        """Should write to output file when specified."""
        from jacks_kanban.importer import import_plan

        plan_file = tmp_path / "plan.md"
        plan_file.write_text("# My Plan")

        output_file = tmp_path / "kanban-test.yaml"

        mock_yaml = "project: Test\ntasks: []"

        with patch('jacks_kanban.importer.execute_claude_import') as mock_execute:
            mock_execute.return_value = (mock_yaml, {})

            import_plan(
                plan_path=plan_file,
                project_dir=tmp_path,
                output_path=output_file,
            )

            assert output_file.exists()
            assert "project: Test" in output_file.read_text()

    def test_import_plan_infers_project_name_from_heading(self, tmp_path):
        """Should infer project name from first heading."""
        from jacks_kanban.importer import import_plan, build_import_prompt

        plan_file = tmp_path / "plan.md"
        plan_file.write_text("# Awesome Project\n\nDescription here.")

        with patch('jacks_kanban.importer.execute_claude_import') as mock_execute:
            mock_execute.return_value = ("project: Test\ntasks: []", {})

            import_plan(
                plan_path=plan_file,
                project_dir=tmp_path,
            )

            # Check the prompt that was built
            call_args = mock_execute.call_args[0][0]
            assert "Awesome Project" in call_args
