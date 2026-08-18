"""Default configuration values for es_tools.wait."""

from typing import TypedDict


class WaitParams(TypedDict):
    pause: float
    timeout: float
    max_exceptions: int


BASE: WaitParams = {
    "pause": 9.0,
    "timeout": 15.0,
    "max_exceptions": 10,
}

EXISTS: WaitParams = {
    "pause": 0.5,
    "timeout": 30.0,
    "max_exceptions": 10,
}

HEALTH: WaitParams = {
    "pause": 1.0,
    "timeout": 30.0,
    "max_exceptions": 10,
}

ILM: WaitParams = {
    "pause": 2.0,
    "timeout": 60.0,
    "max_exceptions": 10,
}

RELOCATE: WaitParams = {
    "pause": 3.0,
    "timeout": 120.0,
    "max_exceptions": 10,
}

RESTORE: WaitParams = {
    "pause": 5.0,
    "timeout": 7200.0,
    "max_exceptions": 10,
}

SNAPSHOT: WaitParams = {
    "pause": 5.0,
    "timeout": 600.0,
    "max_exceptions": 10,
}

TASK: WaitParams = {
    "pause": 9.0,
    "timeout": 7200.0,
    "max_exceptions": 10,
}
