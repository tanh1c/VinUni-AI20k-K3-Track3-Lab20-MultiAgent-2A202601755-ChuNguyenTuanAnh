from multi_agent_research_lab.cli import run_baseline, run_comparison
from multi_agent_research_lab.core.schemas import ResearchQuery, SourceDocument
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMResponse


class FakeLLM:
    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        return LLMResponse(
            content="Baseline answer [S1]",
            input_tokens=12,
            output_tokens=6,
            cost_usd=0.002,
        )


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


def test_baseline_helper_returns_real_state_and_usage() -> None:
    state = run_baseline(
        "Explain multi-agent research systems",
        llm=FakeLLM(),
        search=FakeSearch(),
    )

    assert state.final_answer == "Baseline answer [S1]"
    assert len(state.sources) == 1
    assert state.input_tokens == 12
    assert state.output_tokens == 6
    assert state.estimated_cost_usd == 0.002


def test_comparison_helper_writes_benchmark_report(tmp_path) -> None:
    def runner(query: str) -> ResearchState:
        state = ResearchState(request=ResearchQuery(query=query))
        state.sources = FakeSearch().search(query)
        state.final_answer = "Measured answer [S1]."
        return state

    output = tmp_path / "benchmark.md"
    metrics = run_comparison(
        "Explain multi-agent research systems",
        baseline_runner=runner,
        multi_runner=runner,
        output_path=output,
    )

    assert [item.run_name for item in metrics] == ["baseline", "multi-agent"]
    assert output.exists()
    assert "## Interpretation" in output.read_text()
