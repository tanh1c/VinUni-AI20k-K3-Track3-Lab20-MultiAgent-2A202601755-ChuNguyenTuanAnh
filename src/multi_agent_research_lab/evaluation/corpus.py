"""Deterministic evaluation for the school's official offline corpus."""

import re
from typing import Any

from multi_agent_research_lab.core.schemas import CorpusBenchmarkMetrics
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.utils.citations import citation_coverage, citation_ids, source_ids

_WORD_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "can",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "when",
    "with",
}


def _tokens(text: str) -> set[str]:
    return {token for token in _WORD_RE.findall(text.casefold()) if token not in _STOPWORDS}


def _ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 1.0
    return min(1.0, max(0.0, numerator / denominator))


def _gold_coverage(answer: str, points: list[str]) -> float:
    if not points:
        return 1.0
    answer_tokens = _tokens(answer)
    scores: list[float] = []
    for point in points:
        point_tokens = _tokens(point)
        scores.append(_ratio(len(answer_tokens & point_tokens), len(point_tokens)))
    return sum(scores) / len(scores)


def _contains_markers(answer: str, markers: set[str], minimum: int = 1) -> bool:
    lowered = answer.casefold()
    return sum(marker in lowered for marker in markers) >= minimum


def _coordination_alignment(state: ResearchState, run_name: str) -> float:
    if "multi" not in run_name.casefold():
        return 0.0
    required = {"researcher", "analyst", "writer", "critic", "done"}
    return 1.0 if required.issubset(set(state.route_history)) and not state.errors else 0.0


def evaluate_corpus_run(
    state: ResearchState,
    topic: dict[str, Any],
    run_name: str,
    latency_seconds: float,
) -> CorpusBenchmarkMetrics:
    """Evaluate one report using exact corpus metadata plus transparent proxy signals."""

    answer = state.final_answer or ""
    expected = topic["research_task"]["expected_report"]
    topic_id = str(topic["benchmark_metadata"]["topic_id"])
    coverage, _ = citation_coverage(answer) if answer else (0.0, [])

    all_citations = citation_ids(answer)
    unique_citations = set(all_citations)
    valid_ids = source_ids(state.sources)
    invalid = unique_citations - valid_ids
    valid_citations = unique_citations & valid_ids
    invalid_rate = _ratio(len(invalid), len(unique_citations)) if unique_citations else 0.0

    source_by_id = {str(source.metadata.get("source_id")): source for source in state.sources}
    public_ids = {
        source_id
        for source_id in valid_citations
        if not bool(source_by_id[source_id].metadata.get("is_synthetic", False))
    }
    synthetic_ids = {
        source_id
        for source_id in valid_citations
        if bool(source_by_id[source_id].metadata.get("is_synthetic", False))
    }

    required_sections = [str(item) for item in expected.get("required_sections", [])]
    lowered = answer.casefold()
    section_hits = sum(section.casefold() in lowered for section in required_sections)
    section_coverage = _ratio(section_hits, len(required_sections))

    min_public = int(expected.get("minimum_distinct_public_sources", 0))
    min_total = int(expected.get("minimum_total_source_ids_used", 0))
    meets_targets = len(public_ids) >= min_public and len(valid_citations) >= min_total

    must_distinguish = bool(expected.get("must_distinguish_synthetic_sources", False))
    synthetic_disclosure = not must_distinguish or (bool(synthetic_ids) and "synthetic" in lowered)

    must_counter = bool(expected.get("must_include_counterargument", False))
    counter_markers = {
        "however",
        "counterargument",
        "simpler",
        "single-agent",
        "single agent",
        "limitation",
        "not always",
        "preferable",
    }
    counterargument = not must_counter or _contains_markers(answer, counter_markers)

    gold_points = [str(item) for item in expected.get("gold_coverage_points", [])]
    gold = _gold_coverage(answer, gold_points)

    public_target = _ratio(len(public_ids), min_public)
    citation_validity = 1.0 - invalid_rate if unique_citations else 0.0
    evaluation_signal = _ratio(
        sum(
            marker in lowered
            for marker in {
                "quality",
                "latency",
                "cost",
                "citation",
                "failure",
                "baseline",
                "ablation",
            }
        ),
        5,
    )
    safety_signal = (
        1.0
        if _contains_markers(
            answer,
            {"security", "governance", "permission", "privacy", "oversight", "risk"},
            minimum=2,
        )
        else 0.0
    )
    uncertainty_signal = _ratio(
        sum(
            marker in lowered
            for marker in {
                "depends",
                "may",
                "however",
                "limitation",
                "uncertain",
                "conditional",
                "not always",
            }
        ),
        2,
    )

    dimension_scores = {
        "question_decomposition": section_coverage,
        "source_quality_reasoning": 0.6 * public_target + 0.4 * float(synthetic_disclosure),
        "claim_citation_alignment": 0.67 * coverage + 0.33 * citation_validity,
        "conflict_resolution": 0.5 * float(counterargument) + 0.5 * gold,
        "multi_agent_coordination": _coordination_alignment(state, run_name),
        "technical_depth": gold,
        "evaluation_design": evaluation_signal,
        "safety_governance": safety_signal,
        "report_structure_and_clarity": section_coverage,
        "uncertainty_calibration": uncertainty_signal,
    }
    proxy = 0.0
    for row in topic["research_task"].get("evaluation_rubric", []):
        dimension = str(row.get("dimension") or "")
        weight = float(row.get("weight") or 0)
        proxy += weight * dimension_scores.get(dimension, 0.0)

    failed = bool(state.errors or not answer)
    return CorpusBenchmarkMetrics(
        topic_id=topic_id,
        run_name=run_name,
        latency_seconds=latency_seconds,
        estimated_cost_usd=state.estimated_cost_usd,
        failure_rate=1.0 if failed else 0.0,
        citation_coverage=coverage,
        invalid_citation_count=len(invalid),
        invalid_citation_rate=invalid_rate,
        distinct_source_count=len(valid_citations),
        public_source_count=len(public_ids),
        synthetic_source_count=len(synthetic_ids),
        synthetic_disclosure=synthetic_disclosure,
        required_section_coverage=section_coverage,
        meets_source_targets=meets_targets,
        counterargument_present=counterargument,
        gold_coverage=gold,
        rubric_proxy_score=round(min(100.0, proxy), 2),
    )
