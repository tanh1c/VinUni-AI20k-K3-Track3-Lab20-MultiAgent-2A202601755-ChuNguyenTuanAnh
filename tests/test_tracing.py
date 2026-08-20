from multi_agent_research_lab.observability.tracing import (
    _sanitize_trace_inputs,
    maybe_traceable,
    trace_span,
)


def test_local_trace_span_records_duration() -> None:
    with trace_span("unit", {"role": "test"}) as span:
        assert span["name"] == "unit"
    assert span["duration_seconds"] is not None
    assert span["duration_seconds"] >= 0


def test_maybe_traceable_is_safe_without_langsmith(monkeypatch) -> None:
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)

    @maybe_traceable("example")
    def add_one(value: int) -> int:
        return value + 1

    assert add_one(2) == 3


def test_trace_input_sanitizer_drops_credential_bearing_arguments() -> None:
    marker = object()
    sanitized = _sanitize_trace_inputs(
        {
            "self": marker,
            "settings": marker,
            "client": marker,
            "openai_api_key": "secret-value",
            "service_secret": "secret-value",
            "query": "safe query",
        }
    )

    assert sanitized == {"query": "safe query"}
