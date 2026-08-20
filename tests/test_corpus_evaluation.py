import pytest

from multi_agent_research_lab.core.schemas import ResearchQuery, SourceDocument
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.evaluation.corpus import evaluate_corpus_run


def _topic() -> dict[str, object]:
    return {
        "benchmark_metadata": {"topic_id": "AIAGENT-TEST"},
        "research_task": {
            "expected_report": {
                "required_sections": [
                    "Executive Summary",
                    "Evidence Review",
                    "Evaluation Framework",
                    "Security / Governance Considerations",
                    "Limitations and Open Questions",
                ],
                "gold_coverage_points": [
                    "Multi-agent verification can improve evidence checking but adds "
                    "coordination cost.",
                    "A simpler single-agent baseline can be preferable for narrow tasks.",
                ],
                "minimum_distinct_public_sources": 2,
                "minimum_total_source_ids_used": 3,
                "must_include_counterargument": True,
                "must_distinguish_synthetic_sources": True,
            },
            "evaluation_rubric": [
                {"dimension": "question_decomposition", "weight": 10},
                {"dimension": "source_quality_reasoning", "weight": 15},
                {"dimension": "claim_citation_alignment", "weight": 15},
                {"dimension": "conflict_resolution", "weight": 10},
                {"dimension": "multi_agent_coordination", "weight": 10},
                {"dimension": "technical_depth", "weight": 15},
                {"dimension": "evaluation_design", "weight": 10},
                {"dimension": "safety_governance", "weight": 5},
                {"dimension": "report_structure_and_clarity", "weight": 5},
                {"dimension": "uncertainty_calibration", "weight": 5},
            ],
        },
    }


def _state(answer: str) -> ResearchState:
    state = ResearchState(request=ResearchQuery(query="Compare research architectures"))
    state.sources = [
        SourceDocument(
            title="Public one",
            snippet="Evidence",
            metadata={"source_id": "pub1", "is_synthetic": False},
        ),
        SourceDocument(
            title="Public two",
            snippet="Evidence",
            metadata={"source_id": "pub2", "is_synthetic": False},
        ),
        SourceDocument(
            title="Synthetic experiment",
            snippet="Evidence",
            metadata={"source_id": "T00-SYN-A", "is_synthetic": True},
        ),
    ]
    state.final_answer = answer
    state.route_history = ["researcher", "analyst", "writer", "critic", "done"]
    return state


def test_corpus_evaluator_computes_exact_source_and_structure_metrics() -> None:
    answer = """# Executive Summary
Multi-agent verification can improve evidence checking but adds coordination cost [pub1].

# Evidence Review
A second public source supports the architecture comparison [pub2].
The synthetic benchmark study is explicitly synthetic evidence [T00-SYN-A].

# Evaluation Framework
Compare quality, latency, cost, citation coverage, failure rate, and a single-agent baseline [pub1].

# Security / Governance Considerations
Permission boundaries and human oversight may reduce deployment risk [pub2].

# Limitations and Open Questions
However, a simpler single-agent baseline can be preferable for narrow tasks [pub1].
Results depend on task structure [pub2].
"""

    metrics = evaluate_corpus_run(_state(answer), _topic(), "multi-agent", 12.5)

    assert metrics.topic_id == "AIAGENT-TEST"
    assert metrics.citation_coverage == pytest.approx(1.0)
    assert metrics.invalid_citation_count == 0
    assert metrics.distinct_source_count == 3
    assert metrics.public_source_count == 2
    assert metrics.synthetic_source_count == 1
    assert metrics.synthetic_disclosure is True
    assert metrics.required_section_coverage == pytest.approx(1.0)
    assert metrics.meets_source_targets is True
    assert metrics.counterargument_present is True
    assert metrics.rubric_proxy_score >= 80
    assert metrics.failure_rate == 0.0


def test_corpus_evaluator_penalizes_invalid_and_unsupported_report() -> None:
    answer = (
        "This unsupported material claim has no citation and overstates the evidence. "
        "Another material claim uses an invented source [fake-source]."
    )

    metrics = evaluate_corpus_run(_state(answer), _topic(), "multi-agent", 1.0)

    assert metrics.citation_coverage == pytest.approx(0.5)
    assert metrics.invalid_citation_count == 1
    assert metrics.invalid_citation_rate == pytest.approx(1.0)
    assert metrics.required_section_coverage == 0.0
    assert metrics.meets_source_targets is False
    assert metrics.rubric_proxy_score < 50
