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

## Managing your to-do list

Add a new task:

```bash
python src/todo.py add "Buy milk"
```

List existing tasks:

```bash
python src/todo.py list
```

Mark a task as completed using the number from the list:

```bash
python src/todo.py done 1
```

Both scripts rely only on Python's standard library, so no additional dependencies are required.
