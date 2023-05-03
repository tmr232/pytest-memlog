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
import json
import multiprocessing
import multiprocessing.connection
import os
import re
import sys
import time
from pathlib import Path
from typing import List, Optional

import attrs
import psutil
import pytest


# TODO: Consider switching to standard dataclasses to reduce library dependencies.
@attrs.frozen
class BeginTest:
    name: str


@attrs.frozen
class EndTest:
    pass


@attrs.frozen
class MaxRss:
    max_rss: int


@attrs.frozen
class Close:
    pass


if sys.platform != "win32":
    _Connection = multiprocessing.connection.Connection
else:
    _Connection = multiprocessing.connection.PipeConnection


def memlog(
    pid: int,
    conn: _Connection,
    interval: float = 0.1,
    logpath: Optional[Path] = None,
) -> None:
    process = psutil.Process(pid)

    log = []
    max_rss = 0
    name = ""
    while True:
        rss = process.memory_info().rss
        log.append(
            {
                "rss": rss,
                "time": time.monotonic(),
                "name": name,
            }
        )

        # Maintain the maximum value seen
        max_rss = max(max_rss, rss)

        if conn.poll():
            command = conn.recv()

            if isinstance(command, BeginTest):
                # We measure max-memory on a per-test basis.
                max_rss = 0
                name = command.name
            elif isinstance(command, EndTest):
                # No test == no name
                name = ""
                # Report the test memory usage
                conn.send(MaxRss(max_rss))
            elif isinstance(command, Close):
                break
            else:
                # This should never happen
                raise RuntimeError(f"Unsupported command: {command!r}")

        time.sleep(interval)

    if logpath:
        with logpath.open("w") as f:
            json.dump(log, f, indent=4)


class Memlog:
    conn: _Connection
    process: multiprocessing.Process

    def __init__(self, interval: float = 0.1, logpath: Optional[Path] = None):
        self.conn, child_conn = multiprocessing.Pipe(True)
        self.process = multiprocessing.Process(
            target=memlog,
            kwargs={
                "pid": os.getpid(),
                "conn": child_conn,
                "interval": interval,
                "logpath": logpath,
            },
        )

    def begin_test(self, name: str) -> None:
        self.conn.send(BeginTest(name=name))

    def end_test(self) -> int:
        self.conn.send(EndTest())

        response = self.conn.recv()
        assert isinstance(response, MaxRss)

        return response.max_rss

    def __enter__(self):
        self.process.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # We use a Close command instead of closing the pipe because closing the pipe
        # causes a BrokenPipeError, and handling a Close command is cleaner.
        self.conn.send(Close())
        self.process.join()
        return False


@pytest.fixture(scope="session")
def memlog_session(request: pytest.FixtureRequest):
    # If memlog is disabled, don't do anything.
    if not request.config.getoption("memlog"):
        yield None
        return

    logpath = request.config.getoption("memlog-path")
    interval = request.config.getoption("memlog-interval")

    with Memlog(logpath=logpath, interval=interval) as ml:
        yield ml


MEM_RE = re.compile(
    r"""
    (?P<number>\d+\.\d+|\d+)               # A number
    \s*                           # Possible spacing
    (?P<unit>([KMG]|Ki|Mi|Gi)?B)  # Unit - KB, MB, GB, KiB, MiB, GiB 
    """,
    re.VERBOSE | re.IGNORECASE,
)


def parse_memory_string(mem: str) -> float:
    match = MEM_RE.match(mem)
    if not match:
        raise ValueError(f"Invalid memory size string: {mem}")

    number = float(match.group("number"))
    unit = match.group("unit").lower()
    unit_size = {
        "b": 1,
        "kb": 1000**1,
        "mb": 1000**2,
        "gb": 1000**3,
        "kib": 1024**1,
        "mib": 1024**2,
        "gib": 1024**3,
    }[unit]

    return number * unit_size


def format_memory(mem: float) -> str:
    for unit in ["B", "KiB", "MiB"]:
        if abs(mem) > 1024:
            mem /= 1024
        else:
            return f"{mem:1f}{unit}"
    return f"{mem:1f}GiB"


@pytest.fixture
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
        "--memlog-all",
        dest="memlog-all",
        action="store_true",
        help="Run memlog for all tests.",
    )

    parser.addoption(
        "--memlog-only",
        dest="memlog-only",
        action="store_true",
        help="Run only memlog tests, and collect their data.",
    )

    parser.addoption(
        "--no-memlog",
        dest="memlog",
        action="store_false",
        help="Disable memlog.",
    )

    parser.addoption(
        "--memlog-path",
        dest="memlog-path",
        action="store",
        metavar="FILEPATH",
        help="Path to store the memlog JSON log.",
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


def pytest_configure(config):
    # register an additional marker
    config.addinivalue_line(
        "markers",
        "limit_memory(memory): mark the test to fail if exceeding the memory limit.",
    )

    config.addinivalue_line(
        "markers",
        "memlog: include the test in memlog runs, and log the test name in the logs.",
    )


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config: pytest.Config, items: List[pytest.Item]):
    """
    Check if any tests are marked to use the mock.
    """
    skip_not_memlog = pytest.mark.skip(
        reason="Need memlog marker to run with --memlog-only option."
    )
    for item in items:
        if config.getoption("memlog-all") or item.get_closest_marker("memlog"):
            item.fixturenames.append("memlog_me")  # type: ignore[attr-defined]

        elif config.getoption("memlog-only") and not item.get_closest_marker("memlog"):
            item.add_marker(skip_not_memlog)


def main():
    with Memlog() as ml:
        ml.begin_test("Hello, World!")
        time.sleep(2)
        print(ml.end_test())


if __name__ == "__main__":
    main()
