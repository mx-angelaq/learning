# learning

Learning environment

This repository includes two command-line utilities:
- A simple calculator located in `src/calculator.py`.
- A basic to-do list manager located in `src/todo.py`.

## Running the calculator

Run the calculator interactively by executing:

```bash
python src/calculator.py
```

You can either supply the numbers and operation when prompted or provide them as command-line arguments:

```bash
python src/calculator.py 3 5 -o add
```

import argparse
import json
from pathlib import Path

class ToDoList:
    """Simple to-do list manager backed by a JSON file."""

    def __init__(self, path: Path | None = None):
        self.path = path or Path(__file__).resolve().parent.parent / "todo_data.json"
        self.tasks: list[dict] = []
        self.load()

    def load(self) -> None:
        if self.path.exists():
            try:
                with self.path.open("r", encoding="utf-8") as f:
                    self.tasks = json.load(f)
            except json.JSONDecodeError:
                self.tasks = []
        else:
            self.tasks = []

    def save(self) -> None:
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(self.tasks, f, indent=2)

    def add_task(self, text: str) -> None:
        self.tasks.append({"text": text, "completed": False})
        self.save()

    def complete_task(self, index: int) -> None:
        if 0 <= index < len(self.tasks):
            self.tasks[index]["completed"] = True
            self.save()
        else:
            raise IndexError("Task index out of range")

    def list_tasks(self) -> list[dict]:
        return self.tasks

def main() -> None:
    parser = argparse.ArgumentParser(description="Simple command-line to-do list")
    subparsers = parser.add_subparsers(dest="command")

    add_parser = subparsers.add_parser("add", help="Add a new task")
    add_parser.add_argument("text", help="Task description")

    subparsers.add_parser("list", help="List tasks")

    done_parser = subparsers.add_parser("done", help="Mark a task as completed")
    done_parser.add_argument("index", type=int, help="Task number as shown in the list")

    args = parser.parse_args()

    todo = ToDoList()

    if args.command == "add":
        todo.add_task(args.text)
        print(f'Added task: {args.text}')
    elif args.command == "list":
        tasks = todo.list_tasks()
        if not tasks:
            print("No tasks found.")
        else:
            for i, task in enumerate(tasks, start=1):
                mark = "[x]" if task.get("completed") else "[ ]"
                print(f"{i}. {mark} {task.get('text')}")
    elif args.command == "done":
        try:
            todo.complete_task(args.index - 1)
            print(f"Completed task #{args.index}")
        except IndexError:
            print("Invalid task number")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()

