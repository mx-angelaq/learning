import json
from pathlib import Path

import pytest

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from todo import add_task, complete_task


def test_add_task(tmp_path: Path):
    file_path = tmp_path / "tasks.json"
    task = add_task(file_path, "Write tests")

    with file_path.open() as f:
        data = json.load(f)

    assert data == [task]
    assert task["description"] == "Write tests"
    assert task["completed"] is False
    assert task["id"] == 1


def test_complete_task(tmp_path: Path):
    file_path = tmp_path / "tasks.json"
    initial = [{"id": 1, "description": "Test", "completed": False}]
    with file_path.open("w") as f:
        json.dump(initial, f)

    updated = complete_task(file_path, 1)
    assert updated is True

    with file_path.open() as f:
        data = json.load(f)

    assert data[0]["completed"] is True
