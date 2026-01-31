import json
import yaml
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
