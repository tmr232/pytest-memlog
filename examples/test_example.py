import time

import pytest

MB = 1024 ** 2
@pytest.mark.memlog
def test_memory_usage_logged():
    list([1] * (20 * MB))
    list([1] * (100 * MB))
    list([1] * (200 * MB))

def test_ignored():
    time.sleep(10)