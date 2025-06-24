# Simple command-line todo list manager

import argparse
from pathlib import Path

TASKS_FILE = Path(__file__).resolve().parent.parent / "tasks.txt"


def add_task(description: str) -> None:
    """Append a task description to the tasks file."""
    with open(TASKS_FILE, "a", encoding="utf-8") as f:
        f.write(description.strip() + "\n")


def list_tasks() -> list[str]:
    """Return the list of tasks from the tasks file."""
    if not TASKS_FILE.exists():
        return []
    with open(TASKS_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def main() -> None:
    """Handle command-line arguments for adding and listing tasks."""
    parser = argparse.ArgumentParser(description="Simple todo list manager")
    subparsers = parser.add_subparsers(dest="command")

    add_parser = subparsers.add_parser("add", help="Add a new task")
    add_parser.add_argument("description", help="task description")

    subparsers.add_parser("list", help="List existing tasks")

    args = parser.parse_args()

    if args.command == "add":
        add_task(args.description)
        print("Task added.")
    elif args.command == "list":
        tasks = list_tasks()
        if not tasks:
            print("No tasks found.")
        else:
            for idx, task in enumerate(tasks, 1):
                print(f"{idx}. {task}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
