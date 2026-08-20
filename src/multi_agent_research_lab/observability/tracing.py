"""Local tracing plus optional LangSmith instrumentation."""

import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import wraps
from time import perf_counter
from typing import Any, TypeVar, cast

F = TypeVar("F", bound=Callable[..., Any])


def _sanitize_trace_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """Drop object/config arguments so credentials are never serialized into traces."""

    sanitized: dict[str, Any] = {}
    for key, value in inputs.items():
        lowered = key.casefold()
        if key in {"self", "settings", "client"} or "api_key" in lowered or "secret" in lowered:
            continue
        sanitized[key] = value
    return sanitized


def maybe_traceable(name: str) -> Callable[[F], F]:
    """Use LangSmith tracing only when configured, with sanitized function inputs."""

    def decorator(func: F) -> F:
        if not os.getenv("LANGSMITH_API_KEY"):
            return func
        try:
            from langsmith import traceable
        except ImportError:
            return func
        traced = traceable(name=name, process_inputs=_sanitize_trace_inputs)(func)

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
