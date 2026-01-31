# jacks-kanban

CLI tool to orchestrate Claude Code through kanban tasks. Each task runs in a fresh Claude session to avoid context window exhaustion.

## Installation

```bash
pip install -e .
```

## Quick Start

```bash
cd your-project
kanban init                    # Creates kanban.yaml + .kanban/
# Edit kanban.yaml with your tasks
kanban status                  # See board overview
kanban run --loop              # Execute tasks until done/failure
kanban run --watch             # With tmux dashboard
```

## Usage Guide

### 1. Design your project

Start a conversation with Claude and design your project. Have it produce a `DESIGN.md` with sections for each feature.

### 2. Generate tasks

Ask Claude to read `docs/task-schema.md` and break your design into kanban tasks. It will output `kanban.yaml` content following the schema.

### 3. Initialize

```bash
cd your-project
kanban init          # creates kanban.yaml template + .kanban/
```

Then replace the template `kanban.yaml` with the tasks Claude generated.

### 4. Run

```bash
# Run one task at a time
kanban run

# Run all tasks until one fails or all complete
kanban run --loop

# Run with a tmux dashboard showing progress + Claude's log
kanban run --watch
```

### 5. Monitor and manage

```bash
kanban status        # board overview (completed/pending/failed counts)
kanban show 1.1      # details on a specific task
kanban dashboard -w  # live-refreshing dashboard
kanban sync          # re-check verify commands against codebase
kanban reset 1.1     # reset a failed task to retry it
kanban reset --all   # reset everything
```

### Key concept

Each task runs in a **fresh Claude session** with a prompt that tells Claude to:

1. Read the relevant section of your `DESIGN.md`
2. Write a failing test first (TDD)
3. Implement the code
4. Run the verify command
5. Commit if it passes

This avoids context window exhaustion — each task gets a clean context window rather than accumulating tokens from previous tasks.

## Commands

| Command | Description |
|---------|-------------|
| `kanban init` | Initialize project with `kanban.yaml` template and `.kanban/` directory |
| `kanban status` | Show board overview with task counts |
| `kanban show <id>` | Show details of a specific task |
| `kanban run` | Run one task |
| `kanban run --loop` | Run tasks until done or failure |
| `kanban run --watch` | Run with tmux dashboard |
| `kanban sync` | Re-run verify commands and sync board state with codebase |
| `kanban reset [id]` | Reset a task to pending |
| `kanban reset --all` | Reset all tasks to pending |
| `kanban dashboard` | Show status display |
| `kanban dashboard -w` | Live-refreshing status display |
| `kanban stream-log` | Format `claude.log` stream for display (pipe stdin) |

## Task Sizing

Each task must complete in a single Claude session without context compaction:
- One file or one small feature
- Under 300 lines of code
- 1-3 verification attempts
- Fast verify command (under 10 seconds)

See `docs/task-schema.md` for the full schema.
