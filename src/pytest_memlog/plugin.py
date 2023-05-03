"""
New design is needed!

As a session fixture, we should have a process that constantly logs the memory
of the test process.

As each test starts or stops, the process gets notified, so it can log accordingly.

Marks with arguments can be used to trigger test-failure on extreme memory usage.

Pytest flags & config can be used to:
    1. Set measurement interval
    2. Log measurements to file


## Possible Marks & Flags

Global:
- Disable/Enable
- Log path
- Default log or ignore test
- Interval

Per Test:
- Limit memory
- Log / ignore test

## Extra output (optional!):

- Output per-test max memory usage


## Plotting ideas

- Plot the entire graph, with different colors per-test.
- draw per-graph max-memory plot to find outliers

References:

- [Parse human-friendly memory sizes](https://github.com/xolox/python-humanfriendly)
- [pytest.Item docs](https://docs.pytest.org/en/latest/reference/reference.html#pytest.Item)
- [Pytest hook to add fixtures based on marks](https://docs.pytest.org/en/latest/reference/reference.html#_pytest.hookspec.pytest_collection_modifyitems)
- [SO answer on adding fixture by mark](https://stackoverflow.com/a/50607635/3337893)
- [Adding custom markers](https://docs.pytest.org/en/7.1.x/example/markers.html#custom-marker-and-command-line-option-to-control-test-runs)
- [SO getting marks in a fixture](https://stackoverflow.com/a/61379477/3337893)
"""
import time
from pathlib import Path
from typing import Optional

import pytest

from pytest_memlog.formatting import format_memory, parse_memory_string
from pytest_memlog.memlog import Memlog


@pytest.fixture(scope="session", autouse=True)
def memlog_session(request: pytest.FixtureRequest):
    # If memlog is disabled, don't do anything.
    if not request.config.getoption("memlog"):
        yield None
        return

    logpath = request.config.getoption("memlog-path")
    interval = request.config.getoption("memlog-interval")
    warmup = request.config.getoption("memlog-warmup")

    with Memlog(logpath=logpath, interval=interval) as ml:
        # Allow memlog to capture a baseline before starting the tests.
        time.sleep(warmup)
        yield ml


@pytest.fixture(autouse=True)
def memlog_me(request: pytest.FixtureRequest, memlog_session: Optional[Memlog]):
    if memlog_session is None:
        yield
        return

    memlog_session.begin_test(request.node.nodeid)

    try:
        yield
    finally:
        max_rss = memlog_session.end_test()

        memory_limit_marker = request.node.get_closest_marker("limit_memory")
        if memory_limit_marker:
            memory_limit = parse_memory_string(memory_limit_marker.args[0])
            if max_rss > memory_limit:
                pytest.fail(
                    f"Memory usage ({format_memory(max_rss)} "
                    f"exceeds memory limit ({format_memory(memory_limit)})."
                )


def pytest_addoption(parser):
    parser.addoption(
        "--memlog",
        dest="memlog",
        action="store_true",
        help="Disable memlog.",
    )

    parser.addoption(
        "--memlog-path",
        dest="memlog-path",
        action="store",
        metavar="FILEPATH",
        help="Path to store the memlog JSON log.",
        default="memlog.json",
        type=Path,
    )

    parser.addoption(
        "--memlog-interval",
        dest="memlog-interval",
        action="store",
        metavar="SECONDS",
        default=0.1,
        help="Interval between memory samples.",
        type=float,
    )

    parser.addoption(
        "--memlog-warmup",
        dest="memlog-warmup",
        action="store",
        metavar="SECONDS",
        default=0,
        help="Time to wait between starting the memlog process and the first test.",
        type=float,
    )


def pytest_configure(config):
    # register an additional marker
    config.addinivalue_line(
        "markers",
        "limit_memory(memory): mark the test to fail if exceeding the memory limit.",
    )
