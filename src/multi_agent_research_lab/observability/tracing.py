"""Local tracing plus optional LangSmith instrumentation."""

import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import wraps
from time import perf_counter
from typing import Any, TypeVar, cast

F = TypeVar("F", bound=Callable[..., Any])


def maybe_traceable(name: str) -> Callable[[F], F]:
    """Use LangSmith's traceable decorator only when tracing is configured and installed."""

    def decorator(func: F) -> F:
        if not os.getenv("LANGSMITH_API_KEY"):
            return func
        try:
            from langsmith import traceable
        except ImportError:
            return func
        traced = traceable(name=name)(func)

        @wraps(func)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            return traced(*args, **kwargs)

        return cast(F, wrapped)

    return decorator


@contextmanager
def trace_span(name: str, attributes: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
    """Always-available local span used for tests and in-state observability."""

    started = perf_counter()
    span: dict[str, Any] = {
        "name": name,
        "attributes": attributes or {},
        "duration_seconds": None,
    }
    try:
        yield span
    finally:
        span["duration_seconds"] = perf_counter() - started
