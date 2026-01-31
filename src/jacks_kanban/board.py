import yaml
from pathlib import Path


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
