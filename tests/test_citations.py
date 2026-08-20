import pytest

from multi_agent_research_lab.core.schemas import SourceDocument
from multi_agent_research_lab.utils.citations import (
    citation_coverage,
    citation_ids,
    invalid_citation_ids,
)


def _sources() -> list[SourceDocument]:
    return [
        SourceDocument(
            title="AutoGen",
            snippet="Evidence",
            metadata={"source_id": "autogen"},
        ),
        SourceDocument(
            title="Synthetic study",
            snippet="Benchmark evidence",
            metadata={"source_id": "T01-SYN-A"},
        ),
        SourceDocument(
            title="Article",
            snippet="Knowledge article",
            metadata={"source_id": "A01"},
        ),
    ]


def test_citation_parser_accepts_canonical_corpus_ids() -> None:
    text = "Architecture evidence [autogen]. Synthetic result [T01-SYN-A]. Overview [A01]."

    assert citation_ids(text) == ["autogen", "T01-SYN-A", "A01"]
    assert invalid_citation_ids(text, _sources()) == []


def test_citation_parser_still_accepts_s_number_ids() -> None:
    text = "Supported claim [S1]."
    sources = [SourceDocument(title="S", snippet="E", metadata={"source_id": "S1"})]

    assert citation_ids(text) == ["S1"]
    assert invalid_citation_ids(text, sources) == []


def test_citation_coverage_counts_canonical_ids() -> None:
    text = (
        "The first material factual claim is supported by evidence [autogen]. "
        "The second material factual claim is not cited anywhere."
    )

    coverage, unsupported = citation_coverage(text)

    assert coverage == pytest.approx(0.5)
    assert len(unsupported) == 1
