"""
New design is needed!

As a session fixture, we should have a process that constantly logs the memory of the test process.

As each test starts or stops, the process gets notified, so it can log accordingly.

Marks with arguments can be used to trigger test-failure on extreme memory usage.

Pytest flags & config can be used to:
    1. Set measurement interval
    2. Log measurements to file
"""
import json
import multiprocessing
import multiprocessing.connection
import os
import time
from pathlib import Path
from typing import Optional

import attrs
import psutil

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


def memlog(
    pid: int,
    conn: multiprocessing.connection.Connection,
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
    conn: multiprocessing.connection.Connection
    memlog_process: multiprocessing.Process

    def __init__(self, interval: float = 0.1, logpath: Optional[Path] = None):
        self.conn, child_conn = multiprocessing.Pipe(True)
        self.memlog_process = multiprocessing.Process(
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
        self.memlog_process.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # We use a Close command instead of closing the pipe because closing the pipe
        # causes a BrokenPipeError, and handling a Close command is cleaner.
        self.conn.send(Close())
        self.memlog_process.join()
        return False


def main():
    with Memlog() as ml:
        ml.begin_test("Hello, World!")
        time.sleep(2)
        print(ml.end_test())


if __name__ == "__main__":
    main()
