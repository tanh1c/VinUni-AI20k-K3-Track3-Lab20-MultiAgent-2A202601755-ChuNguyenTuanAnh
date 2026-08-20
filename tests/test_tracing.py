from multi_agent_research_lab.observability.tracing import maybe_traceable, trace_span


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
