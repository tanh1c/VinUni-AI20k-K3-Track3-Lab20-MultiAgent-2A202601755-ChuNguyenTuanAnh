"""Benchmark report rendering."""

from multi_agent_research_lab.core.schemas import BenchmarkMetrics


def _fmt_optional(value: float | None, digits: int = 4) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def render_markdown_report(metrics: list[BenchmarkMetrics]) -> str:
    """Render measured metrics plus methodology, interpretation, and failure-mode analysis."""

    lines = [
        "# Benchmark Report",
        "",
        "## Results",
        "",
        (
            "| Run | Latency (s) | Cost (USD) | Quality /10 | Citation coverage | "
            "Failure rate | Notes |"
        ),
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for item in metrics:
        citation = "n/a" if item.citation_coverage is None else f"{item.citation_coverage:.0%}"
        failure = "n/a" if item.failure_rate is None else f"{item.failure_rate:.0%}"
        quality = _fmt_optional(item.quality_score, 1)
        lines.append(
            f"| {item.run_name} | {item.latency_seconds:.2f} | "
            f"{_fmt_optional(item.estimated_cost_usd)} | {quality} | {citation} | "
            f"{failure} | {item.notes} |"
        )

    lines.extend(
        [
            "",
            "## Methodology",
            "",
            (
                "Both approaches receive the same query and retrieval budget. "
                "Latency is wall-clock time; cost is derived from provider token usage; "
                "citation coverage is the fraction of material sentences containing "
                "a [S#] source reference. The automated quality score is a transparent "
                "0-10 proxy based on successful completion, source use, citation coverage, "
                "and absence of execution errors; it should be paired with the lab "
                "peer-review rubric for semantic quality."
            ),
            "",
            "## Interpretation",
            "",
        ]
    )
    if len(metrics) >= 2:
        baseline, multi = metrics[0], metrics[1]
        latency_delta = multi.latency_seconds - baseline.latency_seconds
        lines.append(
            f"The multi-agent run changed latency by {latency_delta:+.2f}s "
            "relative to the baseline. Its extra calls are justified only when "
            "the decomposition improves evidence handling, citation coverage, or "
            "review quality enough to offset the added latency and token cost."
        )
    else:
        lines.append(
            "Add both baseline and multi-agent measurements for a direct trade-off comparison."
        )

    lines.extend(
        [
            "",
            "## Failure mode",
            "",
            (
                "A common failure is an LLM producing an invented or missing citation. "
                "The Writer performs one bounded correction attempt using the known "
                "source IDs; the Critic then independently checks invalid citations "
                "and unsupported material claims. Provider/search failures are recorded "
                "in shared state and route to a safe stop instead of creating an infinite loop."
            ),
            "",
            "## Trace evidence",
            "",
            (
                "Live runs are instrumented for LangSmith when `LANGSMITH_API_KEY` "
                "is configured. Use the corresponding LangSmith project trace as "
                "submission evidence; this report does not fabricate a trace URL "
                "when no live trace has been captured."
            ),
            "",
        ]
    )
    return "\n".join(lines)
