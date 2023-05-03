import random
import time

MB = 1024**2


def alloc(size):
    return "X" * MB * size


def test_a():
    x = ""
    for size in [20, 100, 200, 500]:
        x = alloc(size)  # noqa: unused-variable
        time.sleep(0.2)


def test_b():
    x = ""
    for _ in range(10):
        x = "X" * MB * random.randint(0, 50)  # noqa: unused-variable
        time.sleep(0.2)
