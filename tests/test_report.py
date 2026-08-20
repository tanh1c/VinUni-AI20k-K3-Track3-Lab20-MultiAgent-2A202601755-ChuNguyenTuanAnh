from multi_agent_research_lab.core.schemas import BenchmarkMetrics
from multi_agent_research_lab.evaluation.report import render_markdown_report


def test_report_renders_metrics_interpretation_and_failure_mode() -> None:
    report = render_markdown_report(
        [
            BenchmarkMetrics(
                run_name="baseline",
                latency_seconds=1.23,
                estimated_cost_usd=0.01,
                quality_score=7.0,
                citation_coverage=0.6,
                failure_rate=0.0,
            ),
            BenchmarkMetrics(
                run_name="multi-agent",
                latency_seconds=2.0,
                estimated_cost_usd=0.03,
                quality_score=9.0,
                citation_coverage=0.9,
                failure_rate=0.0,
            ),
        ]
    )

    assert "Benchmark Report" in report
    assert "baseline" in report
    assert "multi-agent" in report
    assert "## Interpretation" in report
    assert "## Failure mode" in report
    assert "citation" in report.lower()
