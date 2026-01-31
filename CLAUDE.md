# jacks-kanban

## Build Workflow

This project is being built incrementally from `BUILD-PLAN.md`. Each unit of work runs in a fresh Claude context to avoid context exhaustion.

### How to find the next task

1. Read `BUILD-PLAN.md`
2. Find the first unit header that is NOT marked `[DONE]`
3. That is your current unit — implement it

### Unit completion checklist

For each unit:
1. Write tests first (TDD)
2. Implement the code
3. Run the verify command specified in the unit
4. Commit the implementation with the appropriate message
5. Mark the unit `[DONE]` in `BUILD-PLAN.md` (e.g., change `### Unit 0.1:` to `### Unit 0.1: [DONE]`)
6. Commit the BUILD-PLAN.md update
7. Ask the user to clear context before starting the next unit

### Conventions

- Use `uv` for Python package management
- Use TDD methodology
- Use `tmux` to start any servers
- Maintain `TODO.md` with completed, in-progress, and pending tasks
- Fix root causes, never write workaround scripts
