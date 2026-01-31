# Kanban Task Generation Schema

Use this document when asking Claude to generate tasks from a design document.

## Critical Constraint

Each task MUST be completable by Claude in a **single session without context compaction**. 

This is the entire point of the system. If a task is too large, Claude's context window fills up, compaction occurs, context is lost, and the task fails.

### Task Sizing Rules

A properly-sized task:
- Creates/modifies **1-2 files** max
- Produces **under 300 lines of code**
- Has **one clear objective** (one model, one function, one endpoint)
- Completes in **1-3 verification attempts**
- Has a **fast verify command** (under 10 seconds)

If a task feels like two things, make it two tasks.

### Examples

❌ Too big:
- "Implement storage backends" (multiple backends = multiple tasks)
- "Create models and tests" (split: create model, then create tests)
- "Build the CLI with all commands" (each command is a task)

✅ Right size:
- "Create PhotoMetadata pydantic model"
- "Add S3 upload method to StorageBackend"  
- "Implement `sync status` CLI command"

## YAML Format

```yaml
# Project configuration
project: MyProject
design_doc: DESIGN.md  # The design doc Claude reads for context

# Optional additional context files
context_files: []

# Phase definitions
phases:
  0: "Setup"
  1: "Core"
  2: "Features"
  3: "Integration"

# Task definitions
tasks:
  - id: "0.1"           # phase.sequence
    name: Short name
    phase: 0
    deps: []            # task ids this depends on
    section: "## Section Name > Subsection"  # pointer into design doc
    verify: "shell command that exits 0 on success"
    commit: "conventional commit message"

  - id: "1.1"
    name: Create Foo model
    phase: 1
    deps: ["0.1"]
    section: "## Data Models > Foo"
    verify: "python -c 'from myproject.models import Foo'"
    commit: "feat(models): add Foo model"
```

## Field Descriptions

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique identifier, format: `phase.sequence` (e.g., "1.1", "2.3") |
| `name` | Yes | Short, descriptive name (shown in status) |
| `phase` | Yes | Phase number (for grouping/display) |
| `deps` | No | Array of task IDs that must complete first |
| `section` | No | Section header in design_doc for Claude to read |
| `verify` | Yes | Shell command that exits 0 when task is complete |
| `commit` | Yes | Git commit message (conventional commits recommended) |

## Verify Command Patterns

Each task needs a verify command that:
- Exits 0 if the task is complete
- Exits non-zero if incomplete
- Runs fast (under 10 seconds)
- Tests the specific deliverable, not the whole project

### Common Patterns

```yaml
# File/directory exists
verify: "test -f src/foo/bar.py"
verify: "test -d src/mypackage"

# Python import works
verify: "python -c 'from myproject.models import Foo'"

# Specific test passes
verify: "pytest tests/test_foo.py::test_specific_function -v"

# CLI command exists
verify: "myproject --help | grep 'subcommand'"

# Multiple checks (all must pass)
verify: "test -f src/foo.py && python -c 'from myproject import Foo'"

# grep for specific content
verify: "grep 'class MyModel' src/models.py"

# JSON/YAML validation
verify: "python -c 'import yaml; yaml.safe_load(open(\"config.yaml\"))'"
```

## Dependencies

- Use `deps` to specify what must complete first
- Keep dependency chains short where possible  
- Phase 0 tasks typically have no dependencies
- Later phases depend on earlier phase completion
- Avoid circular dependencies

### Dependency Example

```yaml
tasks:
  - id: "0.1"
    name: "Create package structure"
    deps: []  # No deps - can start immediately
    
  - id: "1.1"
    name: "Create User model"
    deps: ["0.1"]  # Needs package structure first
    
  - id: "1.2"
    name: "Create Post model"
    deps: ["0.1"]  # Also needs package, but NOT 1.1
    
  - id: "2.1"
    name: "Create API endpoint"
    deps: ["1.1", "1.2"]  # Needs both models
```

## Section References

The `section` field tells Claude where to find implementation details in your design doc.

Format: `"## Heading > Subheading > Sub-subheading"`

```yaml
# If your DESIGN.md has:
# ## Data Models
# ### User
# ...content...

section: "## Data Models > User"
```

Claude will read that section for context before implementing.

## Phase Organization

Organize phases by dependency order and logical grouping:

```yaml
phases:
  0: "Project Setup"      # Package structure, dependencies, test infra
  1: "Core Models"        # Data structures, schemas
  2: "Data Layer"         # Database, repositories  
  3: "Business Logic"     # Services, use cases
  4: "API Layer"          # Routes, endpoints
  5: "CLI"                # Command-line interface
  6: "Integration"        # Glue code, main.py wiring
  7: "Documentation"      # README, deployment docs
```

## Commit Message Convention

Use conventional commits for clear history:

```yaml
commit: "feat(models): add User model"
commit: "feat(api): add /users endpoint"
commit: "test(models): add User model tests"
commit: "fix(auth): handle expired tokens"
commit: "chore: add pytest dependency"
commit: "docs: add API documentation"
```

## Generation Prompt

When asking Claude to generate tasks, use this prompt template:

---

**Prompt:**

```
I have a design document for [PROJECT NAME]. Please generate a kanban.yaml file following the task schema.

Requirements:
1. Each task must be completable in a single Claude session without context compaction
2. Tasks should produce under 300 lines of code
3. Use TDD approach: many tasks will be "write test" then "implement"
4. Include fast verify commands for each task
5. Keep dependency chains short
6. Follow conventional commit messages

Here is the design document:

[PASTE DESIGN.md CONTENT]

Here is the task schema for reference:

[PASTE THIS SCHEMA DOCUMENT]
```

---

## Validation Checklist

Before running tasks, verify your kanban.yaml:

- [ ] Each task has a unique ID
- [ ] All referenced deps exist
- [ ] No circular dependencies
- [ ] Verify commands are fast (<10s)
- [ ] Verify commands test specific deliverables
- [ ] Section references match design doc headings
- [ ] Tasks are small (1-2 files, <300 lines)
- [ ] Commit messages follow conventions
