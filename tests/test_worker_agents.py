import pytest

from multi_agent_research_lab.agents.analyst import AnalystAgent
from multi_agent_research_lab.agents.critic import CriticAgent
from multi_agent_research_lab.agents.researcher import ResearcherAgent
from multi_agent_research_lab.agents.writer import WriterAgent
from multi_agent_research_lab.core.errors import ValidationError
from multi_agent_research_lab.core.schemas import ResearchQuery, SourceDocument
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMResponse


class FakeLLM:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        self.calls.append((system_prompt, user_prompt))
        return LLMResponse(
            content=self.responses.pop(0),
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.001,
        )


class FakeSearch:
    def search(self, query: str, max_results: int = 5) -> list[SourceDocument]:
        return [
            SourceDocument(
                title="Paper A",
                url="https://a.test",
                snippet="Evidence A",
                metadata={"source_id": "S1"},
            ),
            SourceDocument(
                title="Paper B",
                url="https://b.test",
                snippet="Evidence B",
                metadata={"source_id": "S2"},
            ),
        ][:max_results]


def make_state() -> ResearchState:
    return ResearchState(request=ResearchQuery(query="Compare multi-agent research systems"))


def test_researcher_populates_sources_notes_result_and_usage() -> None:
    state = make_state()
    agent = ResearcherAgent(llm=FakeLLM(["[S1] finding A\n[S2] finding B"]), search=FakeSearch())

    result = agent.run(state)

    assert [source.metadata["source_id"] for source in result.sources] == ["S1", "S2"]
    assert result.research_notes == "[S1] finding A\n[S2] finding B"
    assert result.agent_results[-1].agent == "researcher"
    assert result.input_tokens == 10
    assert result.output_tokens == 5


def test_analyst_requires_research_notes() -> None:
    with pytest.raises(ValidationError, match="research_notes"):
        AnalystAgent(llm=FakeLLM(["analysis"])).run(make_state())


def test_analyst_populates_analysis_notes() -> None:
    state = make_state()
    state.sources = FakeSearch().search(state.request.query)
    state.research_notes = "[S1] finding"

    AnalystAgent(llm=FakeLLM(["Strong evidence: [S1]"])).run(state)

    assert state.analysis_notes == "Strong evidence: [S1]"
    assert state.agent_results[-1].agent == "analyst"


def test_analyst_prompt_preserves_provider_canonical_source_ids() -> None:
    state = make_state()
    state.sources = [
        SourceDocument(title="AutoGen", snippet="Evidence", metadata={"source_id": "autogen"}),
        SourceDocument(
            title="Synthetic",
            snippet="Evidence",
            metadata={"source_id": "T01-SYN-A"},
        ),
    ]
    state.research_notes = "Finding [autogen]. Synthetic check [T01-SYN-A]."
    llm = FakeLLM(["Analysis [autogen] [T01-SYN-A]."])

    AnalystAgent(llm=llm).run(state)

    system_prompt = llm.calls[0][0]
    assert "[autogen]" in system_prompt
    assert "[T01-SYN-A]" in system_prompt
    assert "[S#]" not in system_prompt


def test_writer_accepts_only_existing_source_citations() -> None:
    state = make_state()
    state.sources = FakeSearch().search(state.request.query)
    state.research_notes = "notes"
    state.analysis_notes = "analysis"

    WriterAgent(llm=FakeLLM(["Conclusion grounded in evidence [S1]."])).run(state)

    assert state.final_answer == "Conclusion grounded in evidence [S1]."
    assert state.agent_results[-1].agent == "writer"


def test_writer_retries_once_when_citations_are_invalid() -> None:
    state = make_state()
    state.sources = FakeSearch().search(state.request.query)
    state.research_notes = "notes"
    state.analysis_notes = "analysis"
    llm = FakeLLM(["Bad answer [S99].", "Corrected answer [S1]."])

    WriterAgent(llm=llm).run(state)

    assert state.final_answer == "Corrected answer [S1]."
    assert len(llm.calls) == 2
    assert state.input_tokens == 20


def test_researcher_preserves_provider_canonical_source_ids() -> None:
    class CanonicalSearch:
        def search(self, query: str, max_results: int = 5) -> list[SourceDocument]:
            return [
                SourceDocument(
                    title="AutoGen",
                    snippet="Embedded evidence",
                    metadata={
                        "source_id": "autogen",
                        "provider": "official_offline_corpus",
                    },
                )
            ]

    state = make_state()
    agent = ResearcherAgent(llm=FakeLLM(["Finding [autogen]."]), search=CanonicalSearch())

    agent.run(state)

    assert state.sources[0].metadata["source_id"] == "autogen"


def test_writer_retries_when_citation_coverage_is_below_threshold() -> None:
    state = make_state()
    state.sources = FakeSearch().search(state.request.query)
    state.research_notes = "notes"
    state.analysis_notes = "analysis"
    low_coverage = (
        "The first material factual claim is supported [S1]. "
        "The second material factual claim has no citation."
    )
    corrected = (
        "The first material factual claim is supported [S1]. "
        "The second material factual claim is supported too [S2]."
    )
    llm = FakeLLM([low_coverage, corrected])

    WriterAgent(llm=llm).run(state)

    assert state.final_answer == corrected
    assert len(llm.calls) == 2
    assert "Research notes:\nnotes" in llm.calls[1][1]
    assert "Analysis:\nanalysis" in llm.calls[1][1]


def test_writer_keeps_valid_draft_when_coverage_stays_low_after_correction() -> None:
    state = make_state()
    state.sources = FakeSearch().search(state.request.query)
    state.research_notes = "notes"
    state.analysis_notes = "analysis"
    low_coverage = (
        "The first material factual claim is supported [S1]. "
        "The second material factual claim has no citation."
    )
    llm = FakeLLM([low_coverage, low_coverage])

    WriterAgent(llm=llm).run(state)

    assert state.final_answer == low_coverage
    assert len(llm.calls) == 2
    assert state.trace[-1]["payload"]["citation_coverage"] == 0.5
    assert state.trace[-1]["payload"]["coverage_target_met"] is False


def test_writer_fails_after_one_correction_when_invalid_citations_remain() -> None:
    state = make_state()
    state.sources = FakeSearch().search(state.request.query)
    state.research_notes = "notes"
    state.analysis_notes = "analysis"
    llm = FakeLLM(["Bad answer [S99].", "Still bad [S99]."])

    with pytest.raises(ValidationError, match="invalid citation IDs"):
        WriterAgent(llm=llm).run(state)

    assert len(llm.calls) == 2


def test_low_coverage_writer_output_reaches_critic_as_warning() -> None:
    state = make_state()
    state.sources = FakeSearch().search(state.request.query)
    state.research_notes = "notes"
    state.analysis_notes = "analysis"
    low_coverage = (
        "The first material factual claim is supported [S1]. "
        "The second material factual claim has no citation."
    )

    WriterAgent(llm=FakeLLM([low_coverage, low_coverage])).run(state)
    CriticAgent(llm=FakeLLM(["One material claim remains uncited."])).run(state)

    assert state.critic_review is not None
    assert state.critic_review.verdict == "warn"
    assert state.critic_review.citation_coverage == 0.5


def test_researcher_exposes_synthetic_provenance_to_llm() -> None:
    class SyntheticSearch:
        def search(self, query: str, max_results: int = 5) -> list[SourceDocument]:
            return [
                SourceDocument(
                    title="Synthetic study",
                    snippet="Benchmark-only evidence",
                    metadata={
                        "source_id": "T01-SYN-A",
                        "provider": "official_offline_corpus",
                        "is_synthetic": True,
                        "document_class": "synthetic_benchmark",
                    },
                )
            ]

    llm = FakeLLM(["Synthetic finding [T01-SYN-A]."])
    ResearcherAgent(llm=llm, search=SyntheticSearch()).run(make_state())

    assert "is_synthetic=true" in llm.calls[0][1]
    assert "document_class=synthetic_benchmark" in llm.calls[0][1]
