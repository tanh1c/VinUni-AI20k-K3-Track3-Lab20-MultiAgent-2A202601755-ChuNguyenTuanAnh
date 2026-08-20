"""Markdown rendering for official-corpus benchmark results."""

from collections import defaultdict

from multi_agent_research_lab.core.schemas import CorpusBenchmarkMetrics


def _fmt_cost(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def render_corpus_markdown(metrics: list[CorpusBenchmarkMetrics], corpus_sha256: str) -> str:
    """Render per-topic and aggregate corpus benchmark evidence."""

    lines = [
        "# Official Offline Corpus Benchmark",
        "",
        f"Corpus SHA-256: `{corpus_sha256}`",
        "",
        (
            "All quality values below are a transparent rubric-aligned proxy, not a teacher grade "
            "or semantic ground truth. Both architectures receive the same fixed corpus topic and "
            "source budget; no Tavily/browser search is used in this benchmark."
        ),
        "",
        "## Per-topic results",
        "",
        (
            "| Topic | Run | Latency (s) | Cost (USD) | Proxy /100 | Citation | Invalid | "
            "Sources | Public | Synthetic | Sections | Targets | Failure |"
        ),
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|",
    ]
    for item in metrics:
        lines.append(
            f"| {item.topic_id} | {item.run_name} | {item.latency_seconds:.2f} | "
            f"{_fmt_cost(item.estimated_cost_usd)} | {item.rubric_proxy_score:.1f} | "
            f"{item.citation_coverage:.0%} | {item.invalid_citation_count} | "
            f"{item.distinct_source_count} | {item.public_source_count} | "
            f"{item.synthetic_source_count} | {item.required_section_coverage:.0%} | "
            f"{'yes' if item.meets_source_targets else 'no'} | {item.failure_rate:.0%} |"
        )

    groups: dict[str, list[CorpusBenchmarkMetrics]] = defaultdict(list)
    for item in metrics:
        groups[item.run_name].append(item)

    lines.extend(
        [
            "",
            "## Aggregate trade-off",
            "",
            "| Run | Avg proxy /100 | Avg citation | Avg latency (s) | Avg cost (USD) |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for run_name, items in groups.items():
        avg_proxy = sum(item.rubric_proxy_score for item in items) / len(items)
        avg_citation = sum(item.citation_coverage for item in items) / len(items)
        avg_latency = sum(item.latency_seconds for item in items) / len(items)
        costs = [item.estimated_cost_usd for item in items if item.estimated_cost_usd is not None]
        avg_cost = sum(costs) / len(costs) if costs else None
        lines.append(
            f"| {run_name} | {avg_proxy:.1f} | {avg_citation:.0%} | "
            f"{avg_latency:.2f} | {_fmt_cost(avg_cost)} |"
        )

    lines.extend(
        [
            "",
            "## Metric interpretation",
            "",
            (
                "The proxy combines corpus rubric weights with deterministic signals for report "
                "structure, source quality, citation validity/coverage, conflict/counterargument "
                "handling, technical coverage, evaluation design, governance, coordination "
                "evidence, and uncertainty language. It intentionally does not claim semantic "
                "entailment."
            ),
            "",
            (
                "Multi-agent execution is justified only when improvements in evidence handling, "
                "verification, or rubric alignment outweigh added latency and token cost. A strong "
                "single-agent baseline can remain preferable for narrow tasks."
            ),
            "",
        ]
    )
    return "\n".join(lines)
