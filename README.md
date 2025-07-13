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

## Running tests

This repository uses `pytest` for unit testing. Install `pytest` and run the test suite with:

```bash
pip install pytest
pytest
```

