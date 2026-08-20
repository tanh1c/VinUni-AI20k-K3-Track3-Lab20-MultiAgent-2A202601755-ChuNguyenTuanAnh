import pytest

from multi_agent_research_lab.core.schemas import CriticReview, ResearchQuery, SourceDocument
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.evaluation.benchmark import run_benchmark


def successful_runner(query: str) -> ResearchState:
    state = ResearchState(request=ResearchQuery(query=query))
    state.sources = [
        SourceDocument(
            title="Source",
            url="https://example.test",
            snippet="Evidence",
            metadata={"source_id": "S1"},
        )
    ]
    state.final_answer = "Supported material claim [S1]. Another material claim lacks a citation."
    state.estimated_cost_usd = 0.012
    state.critic_review = CriticReview(citation_coverage=0.5, verdict="warn")
    return state


def test_benchmark_computes_cost_quality_citation_and_failure_metrics() -> None:
    state, metrics = run_benchmark(
        "multi-agent",
        "Explain multi-agent systems",
        successful_runner,
    )

    assert state.final_answer
    assert metrics.estimated_cost_usd == 0.012
    assert metrics.citation_coverage == pytest.approx(0.5)
    assert metrics.failure_rate == 0.0
    assert metrics.quality_score is not None
    assert 0 <= metrics.quality_score <= 10


def test_benchmark_converts_runner_exception_to_failed_state() -> None:
    def broken(query: str) -> ResearchState:
        raise RuntimeError("boom")

    state, metrics = run_benchmark("broken", "Explain multi-agent systems", broken)

    assert "boom" in state.errors[-1]
    assert metrics.failure_rate == 1.0
    assert metrics.quality_score == 0.0
