"""Module for tiered debugging with a global TieredDebug instance.

Provides a global `TieredDebug` instance and a `begin_end` decorator to log function
entry and exit at specified debug levels. Designed for use in projects like ES Tools
to trace function execution with configurable stack levels.

Examples:
    >>> from tiered_debug.debug import debug, begin_end
    >>> debug.level = 3
    >>> import logging
    >>> debug.add_handler(logging.StreamHandler())
    >>> @begin_end(debug, begin=2, end=3, stacklevel=2, extra={"func": "test"})
    ... def example():
    ...     return "Test"
    >>> example()
    'Test'
"""

from collections.abc import Callable
from functools import wraps
from typing import Any, Literal, ParamSpec, TypeVar

from tiered_debug import TieredDebug

P = ParamSpec("P")
R = TypeVar("R")

DEFAULT_BEGIN = 2
"""Default debug level for BEGIN messages."""

DEFAULT_END = 3
"""Default debug level for END messages."""

debug = TieredDebug(level=1, stacklevel=3)
"""Global TieredDebug instance with default level 1 and stacklevel 3."""


def begin_end(
    debug_obj: TieredDebug | None = None,
    begin: Literal[1, 2, 3, 4, 5] = DEFAULT_BEGIN,
    end: Literal[1, 2, 3, 4, 5] = DEFAULT_END,
    stacklevel: int = 2,
    extra: dict[str, Any] | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to log function entry and exit at specified debug levels.

    Logs "BEGIN CALL" at the `begin` level and "END CALL" at the `end`
    level using the provided or global debug instance. Adjusts the
    stacklevel by 1 to report the correct caller.

    Args:
        debug_obj: TieredDebug instance to use (default: global debug).
        begin: Debug level for BEGIN message (1-5, default 2). (int)
        end: Debug level for END message (1-5, default 3). (int)
        stacklevel: Stack level for reporting (1-9, default 2). (int)
        extra: Extra metadata dictionary (default None). (dict[str, Any])

    Returns:
        Callable: Decorated function with logging.

    Examples:
        >>> debug.level = 3
        >>> import logging
        >>> debug.add_handler(logging.StreamHandler())
        >>> @begin_end(debug, begin=2, end=3)
        ... def test_func():
        ...     return "Result"
        >>> test_func()
        'Result'
    """
    debug_instance = debug_obj if debug_obj is not None else debug

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            effective_stacklevel = stacklevel + 1
            debug_instance.log(
                begin,
                f"BEGIN CALL: {func.__name__}()",
                exc_info=None,
                stack_info=None,
                stacklevel=effective_stacklevel,
                extra=extra,
            )
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                debug_instance.log(
                    end,
                    f"END CALL: {func.__name__}()",
                    exc_info=None,
                    stack_info=None,
                    stacklevel=effective_stacklevel,
                    extra=extra,
                )

        return wrapper

    return decorator
