import yaml
from pathlib import Path


def load_config(project_dir: Path) -> dict:
    """Load kanban.yaml from project directory."""
    config_path = project_dir / "kanban.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"No kanban.yaml found in {project_dir}")

    with open(config_path) as f:
        return yaml.safe_load(f)
