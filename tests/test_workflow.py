from multi_agent_research_lab.core.config import Settings
from multi_agent_research_lab.core.schemas import ResearchQuery, SourceDocument
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.graph.workflow import MultiAgentWorkflow
from multi_agent_research_lab.services.llm_client import LLMResponse


class FakeLLM:
    def __init__(self) -> None:
        self.responses = [
            "Research finding [S1].",
            "Analysis supports the finding [S1].",
            "Final answer is supported by evidence [S1].",
            "Critic found no material issue.",
        ]

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        return LLMResponse(content=self.responses.pop(0), input_tokens=10, output_tokens=5)


class FakeSearch:
    def search(self, query: str, max_results: int = 5) -> list[SourceDocument]:
        return [
            SourceDocument(
                title="Source",
                url="https://example.test",
                snippet="Evidence",
                metadata={"source_id": "S1"},
            )
        ]


def test_workflow_runs_all_roles_in_order() -> None:
    state = ResearchState(request=ResearchQuery(query="Explain multi-agent research systems"))
    workflow = MultiAgentWorkflow(
        settings=Settings(MAX_ITERATIONS=10),
        llm=FakeLLM(),
        search=FakeSearch(),
    )

    result = workflow.run(state)

    assert result.route_history == ["researcher", "analyst", "writer", "critic", "done"]
    assert result.final_answer == "Final answer is supported by evidence [S1]."
    assert result.critic_review is not None
    assert result.critic_review.verdict == "pass"
    assert result.errors == []


class FailingSearch:
    def search(self, query: str, max_results: int = 5) -> list[SourceDocument]:
        raise RuntimeError("search unavailable")


def test_workflow_records_agent_failure_and_stops() -> None:
    state = ResearchState(request=ResearchQuery(query="Explain multi-agent research systems"))
    workflow = MultiAgentWorkflow(
        settings=Settings(MAX_ITERATIONS=10),
        llm=FakeLLM(),
        search=FailingSearch(),
    )

    result = workflow.run(state)

    assert result.route_history == ["researcher", "done"]
    assert "search unavailable" in result.errors[-1]
