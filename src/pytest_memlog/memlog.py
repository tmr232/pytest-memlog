import json
import multiprocessing
import multiprocessing.connection
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import psutil


# TODO: Consider switching to standard dataclasses to reduce library dependencies.
@dataclass
class BeginTest:
    name: str


@dataclass
class EndTest:
    pass


@dataclass
class MaxRss:
    max_rss: int


@dataclass
class Close:
    pass


@dataclass
class Ready:
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
    conn.send(Ready())

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
        message = self.conn.recv()
        if not isinstance(message, Ready):
            raise RuntimeError(f"Expected {Ready}, got {type(message)}.")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # We use a Close command instead of closing the pipe because closing the pipe
        # causes a BrokenPipeError, and handling a Close command is cleaner.
        self.conn.send(Close())
        self.process.join()
        return False
