from pathlib import Path


def build_prompt(task: dict, design_doc: str) -> str:
    """Build the prompt for Claude to execute a task."""
    return f"""You are implementing a single task from the build plan.

## Your Task
- **ID**: {task['id']}
- **Name**: {task['name']}
- **Section**: {task['section']}

## Instructions

1. Read the section "{task['section']}" in `{design_doc}`
2. Write the failing test FIRST (TDD approach)
3. Implement the minimal code to make the test pass
4. Run the verification command: `{task['verify']}`
5. If tests pass, commit with: `git add -A && git commit -m "{task['commit']}"`

## Rules
- This is ONE task only - do not continue to other tasks
- Follow TDD strictly: test first, then implement
- Keep implementation minimal - only what's needed to pass the test
- The design doc has all the details you need

Begin now."""
