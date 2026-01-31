import json
import yaml
from datetime import datetime
from pathlib import Path

KANBAN_DIR = ".kanban"
BOARD_FILE = "board.json"


def load_config(project_dir: Path) -> dict:
    """Load kanban.yaml from project directory."""
    config_path = project_dir / "kanban.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"No kanban.yaml found in {project_dir}")

    with open(config_path) as f:
        return yaml.safe_load(f)


def init_board(project_dir: Path) -> dict:
    """Initialize board.json from kanban.yaml."""
    config = load_config(project_dir)

    board = {
        "project": config["project"],
        "design_doc": config.get("design_doc", ""),
        "tasks": [],
    }

    for task in config["tasks"]:
        board["tasks"].append({
            "id": task["id"],
            "name": task["name"],
            "phase": task["phase"],
            "deps": task.get("deps", []),
            "section": task.get("section", ""),
            "verify": task["verify"],
            "commit": task["commit"],
            "status": "pending",
        })

    return board


def get_board_path(project_dir: Path) -> Path:
    return project_dir / KANBAN_DIR / BOARD_FILE


def save_board(project_dir: Path, board: dict) -> None:
    """Save board state to .kanban/board.json."""
    board_path = get_board_path(project_dir)
    board_path.parent.mkdir(exist_ok=True)
    with open(board_path, "w") as f:
        json.dump(board, f, indent=2)


def load_board(project_dir: Path) -> dict:
    """Load board state from .kanban/board.json."""
    board_path = get_board_path(project_dir)
    if not board_path.exists():
        return init_board(project_dir)
    with open(board_path) as f:
        return json.load(f)


def get_task_status(board: dict, task_id: str) -> str:
    """Get status of a task by ID."""
    for task in board["tasks"]:
        if task["id"] == task_id:
            return task["status"]
    return "unknown"


def are_deps_met(board: dict, task: dict) -> bool:
    """Check if all dependencies are completed."""
    for dep_id in task.get("deps", []):
        if get_task_status(board, dep_id) != "completed":
            return False
    return True


def is_blocked_by_failure(board: dict, task: dict) -> bool:
    """Check if task is blocked by a failed dependency (transitive)."""
    visited = set()

    def check(t):
        if t["id"] in visited:
            return False
        visited.add(t["id"])
        for dep_id in t.get("deps", []):
            dep = next((x for x in board["tasks"] if x["id"] == dep_id), None)
            if dep:
                if dep["status"] == "failed":
                    return True
                if check(dep):
                    return True
        return False

    return check(task)


def get_next_task(board: dict) -> dict | None:
    """Get next available task (pending, deps met, not blocked)."""
    for task in board["tasks"]:
        if task["status"] == "pending":
            if are_deps_met(board, task) and not is_blocked_by_failure(board, task):
                return task
    return None


def get_task(board: dict, task_id: str) -> dict | None:
    """Get a task by ID."""
    for task in board["tasks"]:
        if task["id"] == task_id:
            return task
    return None


def start_task(board: dict, task_id: str) -> None:
    """Mark task as in_progress."""
    task = get_task(board, task_id)
    if not task:
        raise ValueError(f"Task {task_id} not found")
    task["status"] = "in_progress"
    task["started_at"] = datetime.now().isoformat()


def complete_task(board: dict, task_id: str, tokens: dict = None) -> None:
    """Mark task as completed."""
    task = get_task(board, task_id)
    if not task:
        raise ValueError(f"Task {task_id} not found")
    task["status"] = "completed"
    task["completed_at"] = datetime.now().isoformat()
    if tokens:
        task["tokens"] = tokens


def fail_task(board: dict, task_id: str, reason: str = "unknown") -> None:
    """Mark task as failed."""
    task = get_task(board, task_id)
    if not task:
        raise ValueError(f"Task {task_id} not found")
    task["status"] = "failed"
    task["failed_at"] = datetime.now().isoformat()
    task["failure_reason"] = reason


def reset_task(board: dict, task_id: str) -> None:
    """Reset task to pending."""
    task = get_task(board, task_id)
    if not task:
        raise ValueError(f"Task {task_id} not found")
    task["status"] = "pending"
    for key in ["started_at", "completed_at", "failed_at", "failure_reason", "tokens"]:
        task.pop(key, None)
