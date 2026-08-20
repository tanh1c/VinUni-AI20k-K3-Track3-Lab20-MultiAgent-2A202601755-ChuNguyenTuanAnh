"""Benchmark single-agent vs multi-agent with concrete rubric metrics."""

from collections.abc import Callable
from time import perf_counter

from multi_agent_research_lab.core.schemas import BenchmarkMetrics, ResearchQuery
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.utils.citations import citation_coverage

Runner = Callable[[str], ResearchState]


def _quality_score(state: ResearchState, coverage: float) -> float:
    if not state.final_answer or state.errors:
        return 0.0
    score = 4.0
    score += 3.0 * coverage
    score += 1.0 if state.sources else 0.0
    score += 2.0
    return min(10.0, round(score, 2))


def run_benchmark(
    run_name: str,
    query: str,
    runner: Runner,
) -> tuple[ResearchState, BenchmarkMetrics]:
    """Execute one runner and compute latency, cost, quality proxy, citations, and failure rate."""

    started = perf_counter()
    try:
        state = runner(query)
    except Exception as exc:
        state = ResearchState(request=ResearchQuery(query=query))
        state.errors.append(f"benchmark runner failed: {exc}")
    latency = perf_counter() - started
    coverage = citation_coverage(state.final_answer or "")[0] if state.final_answer else 0.0
    failed = bool(state.errors or not state.final_answer)
    metrics = BenchmarkMetrics(
        run_name=run_name,
        latency_seconds=latency,
        estimated_cost_usd=state.estimated_cost_usd,
        quality_score=_quality_score(state, coverage),
        citation_coverage=coverage,
        failure_rate=1.0 if failed else 0.0,
        notes="deterministic quality proxy; semantic quality should also be peer-reviewed",
    )
    return state, metrics
