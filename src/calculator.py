# Simple calculator module


def add(x, y):
    """Return the sum of x and y."""
    return x + y


def subtract(x, y):
    """Return the difference of x and y."""
    return x - y


def multiply(x, y):
    """Return the product of x and y."""
    return x * y


def divide(x, y):
    """Return the quotient of x and y."""
    if y == 0:
        raise ValueError("Cannot divide by zero")
    return x / y


def main():
    """Run the calculator interactively or via command line arguments."""
    import argparse

    parser = argparse.ArgumentParser(description="Simple command-line calculator")
    parser.add_argument("x", type=float, nargs="?", help="first number")
    parser.add_argument("y", type=float, nargs="?", help="second number")
    parser.add_argument(
        "-o",
        "--operation",
        choices=["add", "sub", "mul", "div"],
        help="operation to perform",
    )

    args = parser.parse_args()

    if args.x is None:
        args.x = float(input("Enter first number: "))
    if args.y is None:
        args.y = float(input("Enter second number: "))
    if args.operation is None:
        args.operation = input("Enter operation (add, sub, mul, div): ").strip()

    operations = {
        "add": add,
        "sub": subtract,
        "mul": multiply,
        "div": divide,
    }

    func = operations.get(args.operation)
    if func is None:
        print(f"Unknown operation: {args.operation}")
        return

    try:
        result = func(args.x, args.y)
    except Exception as exc:
        print(f"Error: {exc}")
        return

    print(f"Result: {result}")


if __name__ == "__main__":
    main()
