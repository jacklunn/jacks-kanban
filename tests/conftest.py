import pytest
from pathlib import Path


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory."""
    return tmp_path


@pytest.fixture
def sample_kanban_yaml():
    """Return sample kanban.yaml content."""
    return """
project: TestProject
design_doc: DESIGN.md
phases:
  0: Setup
  1: Core
tasks:
  - id: "0.1"
    name: "First task"
    phase: 0
    deps: []
    section: "## Setup"
    verify: "test -f setup.txt"
    commit: "feat: setup"
  - id: "0.2"
    name: "Second task"
    phase: 0
    deps: ["0.1"]
    section: "## Setup Part 2"
    verify: "test -f setup2.txt"
    commit: "feat: setup 2"
  - id: "1.1"
    name: "Core task"
    phase: 1
    deps: ["0.2"]
    section: "## Core"
    verify: "test -f core.txt"
    commit: "feat: core"
"""
