"""Simple JSON-based task management utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict


def _load_tasks(file_path: Path) -> List[Dict]:
    if file_path.exists():
        with file_path.open("r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def _save_tasks(file_path: Path, tasks: List[Dict]) -> None:
    with file_path.open("w", encoding="utf-8") as f:
        json.dump(tasks, f)


def add_task(file_path: str | Path, description: str) -> Dict:
    """Add a new task with the given description and return it."""
    path = Path(file_path)
    tasks = _load_tasks(path)
    next_id = max((task.get("id", 0) for task in tasks), default=0) + 1
    task = {"id": next_id, "description": description, "completed": False}
    tasks.append(task)
    _save_tasks(path, tasks)
    return task


def complete_task(file_path: str | Path, task_id: int) -> bool:
    """Mark the task with the given ID as completed.

    Returns True if the task was found and updated, False otherwise.
    """
    path = Path(file_path)
    tasks = _load_tasks(path)
    updated = False
    for task in tasks:
        if task.get("id") == task_id:
            task["completed"] = True
            updated = True
            break
    if updated:
        _save_tasks(path, tasks)
    return updated
