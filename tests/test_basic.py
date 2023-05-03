import time

import pytest


def test_0():
    time.sleep(1)


def test_1():
    x = [1] * 100  # noqa: unused-variable
    time.sleep(1)


x = []


@pytest.mark.parametrize("size", [1 << x for x in range(10, 30, 4)])
def test_mem(size):
    global x
    x = [1 for _ in range(size)]
    time.sleep(1)
