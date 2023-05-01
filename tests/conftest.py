"""
New design is needed!

As a session fixture, we should have a process that constantly logs the memory of the test process.

As each test starts or stops, the process gets notified, so it can log accordingly.

Marks with arguments can be used to trigger test-failure on extreme memory usage.

Pytest flags & config can be used to:
    1. Set measurement interval
    2. Log measurements to file
"""
import contextlib
import multiprocessing
import multiprocessing.connection
import os
import threading
import time

import pandas as pd
import psutil


def memlog(pid: int, interval:float=0.1) -> None:
    process = psutil.Process(pid)

    log = []

    while True:
        log.append(
            {
                "rss": process.memory_info().rss,
                "time": time.monotonic(),
            }
        )
        time.sleep(interval)


def _measure_memory(
    conn: multiprocessing.connection.Connection,
    start: threading.Event,
    stop: threading.Event,
    pid: int,
) -> None:
    process = psutil.Process(pid)
    start_rss = process.memory_info().rss
    start.set()
    log = []
    start_time = time.monotonic()
    while not stop.is_set():
        log.append(
            [time.monotonic() - start_time, process.memory_info().rss - start_rss]
        )
        time.sleep(0.1)
    conn.po
    conn.send(log)
    conn.close()


@contextlib.contextmanager
def track_memory():
    parent_conn, child_conn = multiprocessing.Pipe(False)
    stop = multiprocessing.Event()
    start = multiprocessing.Event()

    process = multiprocessing.Process(
        target=_measure_memory, args=(child_conn, start, stop, os.getpid())
    )
    process.start()

    start.wait(10)

    df = None

    try:
        yield lambda: df
    finally:
        stop.set()
        process.join(timeout=5)
        log = parent_conn.recv()
        df = pd.DataFrame(log, columns=["timestamp", "rss"])
