import pytest

from multi_agent_research_lab.agents.critic import CriticAgent
from multi_agent_research_lab.core.schemas import ResearchQuery, SourceDocument
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMResponse


class FakeLLM:
    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        return LLMResponse(content="Fact-check review completed.", input_tokens=8, output_tokens=4)


def state_with_answer(answer: str) -> ResearchState:
    state = ResearchState(request=ResearchQuery(query="Explain multi-agent systems"))
    state.sources = [
        SourceDocument(
            title="Source",
            url="https://source.test",
            snippet="Evidence",
            metadata={"source_id": "S1"},
        )
    ]
    state.research_notes = "notes"
    state.analysis_notes = "analysis"
    state.final_answer = answer
    return state


def test_critic_flags_invalid_citations() -> None:
    state = state_with_answer("Supported claim [S1]. Invalid claim [S99].")

    CriticAgent(llm=FakeLLM()).run(state)

    assert state.critic_review is not None
    assert state.critic_review.invalid_citations == ["S99"]
    assert state.critic_review.verdict == "fail"


def test_critic_computes_citation_coverage_and_unsupported_claims() -> None:
    state = state_with_answer(
        "The first material claim is supported [S1]. The second material claim has no source."
    )

    CriticAgent(llm=FakeLLM()).run(state)

    assert state.critic_review is not None
    assert state.critic_review.citation_coverage == pytest.approx(0.5)
    assert len(state.critic_review.unsupported_claims) == 1
    assert state.critic_review.verdict == "warn"
