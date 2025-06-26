# learning

Learning environment

This repository includes a simple command-line calculator located in `src/calculator.py`.

## Running the calculator

Run the calculator interactively by executing:

```bash
python src/calculator.py
```

You can either supply the numbers and operation when prompted or provide them as command-line arguments:

```bash
python src/calculator.py 3 5 -o add
```

No additional dependencies are required since the script only uses Python's standard library.

## Todo List

A small helper script `src/todo.py` lets you keep track of tasks in a file called `tasks.txt` at the repository root.
Use it to add new items or display the current list:

```bash
python src/todo.py add "Buy groceries"
python src/todo.py list
```
