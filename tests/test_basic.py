import json
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class LogEntry:
    rss: int
    time: float
    name: str


def load_memlog(logpath: Path) -> List[LogEntry]:
    with logpath.open() as f:
        log_json = json.load(f)

    log = [LogEntry(**entry) for entry in log_json]

    return log


def test_log(pytester, tmp_path):
    """Ensure we only log marked tests."""
    example_file = pytester.copy_example("examples/test_example.py")
    pytester.makepyfile(__init__="")

    items = pytester.getitems(example_file)

    logpath = tmp_path / "memlog.json"

    result = pytester.runpytest("-s", "--memlog", "--memlog-path", logpath)
    result.assert_outcomes(passed=2)

    log = load_memlog(logpath)

    # Make sure we ignore the non-test samples
    test_names = {entry.name for entry in log} - {""}

    assert {item.nodeid for item in items} == test_names
