import pytest

from multi_agent_research_lab.agents.analyst import AnalystAgent
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
    agent = ResearcherAgent(
        llm=FakeLLM(["[S1] finding A\n[S2] finding B"]),
        search=FakeSearch(),
    )

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
