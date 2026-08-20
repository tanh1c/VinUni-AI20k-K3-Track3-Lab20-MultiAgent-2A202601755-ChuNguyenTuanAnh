import json
from pathlib import Path

from multi_agent_research_lab.cli import run_corpus_comparison
from multi_agent_research_lab.core.schemas import ResearchQuery
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.search_client import SearchProvider

CORPUS = Path("data/offline_corpus_subset")


def test_corpus_comparison_uses_equal_budget_and_writes_reports(tmp_path) -> None:
    budgets: list[int] = []

    def runner(query: str, source_budget: int, search: SearchProvider) -> ResearchState:
        budgets.append(source_budget)
        state = ResearchState(request=ResearchQuery(query=query, max_sources=source_budget))
        state.sources = search.search(query, max_results=source_budget)
        cited = [str(source.metadata["source_id"]) for source in state.sources]
        public = next(
            source_id
            for source_id, source in zip(cited, state.sources, strict=True)
            if not source.metadata["is_synthetic"]
        )
        synthetic = next(
            source_id
            for source_id, source in zip(cited, state.sources, strict=True)
            if source.metadata["is_synthetic"]
        )
        state.final_answer = (
            "# Executive Summary\n"
            f"Evidence supports a conditional architecture choice [{public}].\n\n"
            "# Problem Definition and Scope\n"
            f"The task compares agent architectures [{public}].\n\n"
            "# Architecture / Mechanism Analysis\n"
            f"Coordination changes verification and integration cost [{public}].\n\n"
            "# Evidence Review\n"
            f"The corpus includes explicitly synthetic benchmark evidence [{synthetic}].\n\n"
            "# Trade-offs and Failure Modes\n"
            f"However, simpler systems can be preferable when overhead dominates [{public}].\n\n"
            "# Evaluation Framework\n"
            "Compare quality, latency, cost, citations, failures, baselines, and "
            f"ablations [{public}].\n\n"
            "# Security / Governance Considerations\n"
            f"Security, governance, permission boundaries, and oversight matter [{public}].\n\n"
            "# Recommendations\n"
            f"Use multi-agent designs when independent verification adds value [{public}].\n\n"
            "# Limitations and Open Questions\n"
            f"Results depend on task structure and may not generalize [{public}].\n\n"
            "# References\n" + " ".join(f"[{source_id}]" for source_id in cited)
        )
        state.route_history = ["researcher", "analyst", "writer", "critic", "done"]
        return state

    markdown = tmp_path / "corpus.md"
    details = tmp_path / "corpus.json"
    metrics = run_corpus_comparison(
        "AIAGENT-01",
        corpus_path=CORPUS,
        source_budget=8,
        baseline_runner=runner,
        multi_runner=runner,
        markdown_path=markdown,
        details_path=details,
    )

    assert budgets == [8, 8]
    assert [item.run_name for item in metrics] == ["baseline", "multi-agent"]
    assert markdown.exists()
    assert "rubric-aligned proxy" in markdown.read_text().casefold()
    payload = json.loads(details.read_text())
    assert len(payload["runs"]) == 2
    assert payload["topic_id"] == "AIAGENT-01"


def test_corpus_suite_aggregates_multiple_topics(tmp_path) -> None:
    from multi_agent_research_lab.cli import run_corpus_suite

    def runner(query: str, source_budget: int, search: SearchProvider) -> ResearchState:
        state = ResearchState(request=ResearchQuery(query=query, max_sources=source_budget))
        state.sources = search.search(query, max_results=source_budget)
        public = next(
            str(source.metadata["source_id"])
            for source in state.sources
            if not source.metadata["is_synthetic"]
        )
        synthetic = next(
            str(source.metadata["source_id"])
            for source in state.sources
            if source.metadata["is_synthetic"]
        )
        state.final_answer = (
            "# Executive Summary\n"
            f"Conditional evidence supports the analysis [{public}].\n\n"
            "# Evidence Review\n"
            f"Synthetic benchmark evidence is labeled synthetic [{synthetic}].\n\n"
            "# Evaluation Framework\n"
            "Quality, latency, cost, citation, failure, baseline, and ablation metrics "
            f"apply [{public}].\n\n"
            "# Security / Governance Considerations\n"
            "Security, governance, permissions, oversight, and risk controls matter "
            f"[{public}].\n\n"
            "# Limitations and Open Questions\n"
            f"However, simpler designs may be preferable depending on task structure [{public}].\n"
        )
        state.route_history = ["researcher", "analyst", "writer", "critic", "done"]
        return state

    markdown = tmp_path / "suite.md"
    details = tmp_path / "suite.json"
    metrics = run_corpus_suite(
        ["AIAGENT-01", "AIAGENT-12", "AIAGENT-13"],
        corpus_path=CORPUS,
        source_budget=8,
        baseline_runner=runner,
        multi_runner=runner,
        markdown_path=markdown,
        details_path=details,
    )

    assert len(metrics) == 6
    assert {item.topic_id for item in metrics} == {"AIAGENT-01", "AIAGENT-12", "AIAGENT-13"}
    payload = json.loads(details.read_text())
    assert len(payload["runs"]) == 6
    assert payload["topic_ids"] == ["AIAGENT-01", "AIAGENT-12", "AIAGENT-13"]
