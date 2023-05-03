# pytest-memlog

Continuously logs the memory usage of your test session.

![Memlog graph of the example tests](https://github.com/tmr232/pytest-memlog/raw/main/example.png)

## Installation

```bash
pip install pytest-memlog
```

## Usage

Use `--memlog` to enable the plugin.

By default, memory usage of a test run will be logged to `memlog.json`.

### Options

- `--memlog-path`: The path to save the log to, defaults to `memlog.json`.
- `--memlog-interval`: Measurement interval, defaults to 0.1 seconds.
- `--memlog-warmup`: Memlog will capture memory usage for this many seconds _before_ starting your tests. Defaults to 0.

### Markers

- `limit_memory(memory)`: Will mark a test as failed if the program memory exceeds this number during a test run.
    Note that due to garbage collection, this does not necessarily reflect memory usage in a specific test.

## Implementation

pytest-memlog uses a separate process to track the memory of the test process.
This allows for a very low overhead, as the only data passed between the processes
are test names & the maximum memory usage during a test.

The memory logging is done at fixed intervals (given by `--memlog-interval`)
and saved to a JSON log.
Each log entry is of the following form:

```json
    {
        "rss": 40939520,
        "time": 1814626.921,
        "name": "tests/test_basic.py::test_0"
    }
```

- `rss` is the used memory, in bytes.
- `time` is the value from `time.monotonic()`.
    You'll probably want to normalize this when analyzing.
- `name` is the name of the current running test, or an empty string between tests.

## Analysis

The visualization at the top was generated using the data from our examples.

You can see how in the [sample notebook](https://github.com/tmr232/pytest-memlog/blob/main/Example.ipynb) or [view it live](https://nbviewer.org/github/tmr232/pytest-memlog/blob/main/Example.ipynb).

To generate the log for the examples run:

```shell
pytest --memlog ./examples/
```

Or use it on your own tests!
