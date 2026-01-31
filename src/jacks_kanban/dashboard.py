from pathlib import Path
from datetime import datetime

from jacks_kanban.board import load_board, get_next_task

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def render_dashboard(project_dir: Path, config_file: str = "kanban.yaml"):
    """Render the dashboard display."""
    board = load_board(project_dir, config_file)
    tasks = board["tasks"]

    counts = {"pending": 0, "in_progress": 0, "completed": 0, "failed": 0}
    for task in tasks:
        counts[task["status"]] = counts.get(task["status"], 0) + 1

    total = len(tasks)
    pct = counts["completed"] / total if total > 0 else 0
    bar_width = 40
    filled = int(bar_width * pct)
    bar = f"{GREEN}{'█' * filled}{DIM}{'░' * (bar_width - filled)}{RESET}"

    # Clear and render
    print("\033[2J\033[H", end="")
    print(f"{BOLD}{CYAN}{'=' * 60}{RESET}")
    print(f"{BOLD}  {board['project']} - Dashboard{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 60}{RESET}")
    print()
    print(f"  Progress: {bar} {counts['completed']}/{total} ({pct*100:.0f}%)")
    print()
    print(f"  {GREEN}✓ Completed:{RESET}   {counts['completed']:3d}")
    print(f"  {YELLOW}◆ In Progress:{RESET} {counts['in_progress']:3d}")
    print(f"  {DIM}○ Pending:{RESET}     {counts['pending']:3d}")
    print(f"  {RED}✗ Failed:{RESET}      {counts['failed']:3d}")
    print()

    # Current/next task
    current = next((t for t in tasks if t["status"] == "in_progress"), None)
    if current:
        print(f"  {YELLOW}▶ Current:{RESET} [{current['id']}] {current['name']}")
    else:
        next_task = get_next_task(board)
        if next_task:
            print(f"  {DIM}Next:{RESET} [{next_task['id']}] {next_task['name']}")

    print()
    print(f"{DIM}  Updated: {datetime.now().strftime('%H:%M:%S')}{RESET}")
