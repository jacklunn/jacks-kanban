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

## Workflow

1. Design your project with Claude → produce DESIGN.md
2. Ask Claude to break it into tasks → generates kanban.yaml content
3. Run `kanban run --loop` → Claude executes tasks one by one

## Commands

- `kanban init` - Initialize project
- `kanban status` - Show board overview
- `kanban show <id>` - Show task details
- `kanban run` - Run one task
- `kanban run --loop` - Run until done/failure
- `kanban run --watch` - Run with tmux dashboard
- `kanban sync` - Sync board with codebase
- `kanban reset [id]` - Reset task(s)
- `kanban dashboard` - Live status display

## Task Sizing

Each task must complete in a single Claude session without context compaction:
- One file or one small feature
- Under 300 lines of code
- 1-3 verification attempts
- Fast verify command (under 10 seconds)

See `docs/task-schema.md` for the full schema.
