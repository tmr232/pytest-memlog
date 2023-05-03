import re

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
