import subprocess
from datetime import datetime
from pathlib import Path


def run_verify(verify_cmd: str, project_dir: Path) -> bool:
    """Run verification command, return True if passes."""
    try:
        result = subprocess.run(
            verify_cmd,
            shell=True,
            cwd=project_dir,
            capture_output=True,
            timeout=60,
        )
        return result.returncode == 0
    except Exception:
        return False


def sync_board(project_dir: Path, board: dict) -> list[str]:
    """Sync board with codebase state. Returns list of changes."""
    changes = []

    for task in board["tasks"]:
        if task["status"] in ["pending", "in_progress", "failed"]:
            if run_verify(task["verify"], project_dir):
                old_status = task["status"]
                task["status"] = "completed"
                task["completed_at"] = datetime.now().isoformat()
                task.pop("failure_reason", None)
                changes.append(f"[{task['id']}] {old_status} -> completed")

    return changes
