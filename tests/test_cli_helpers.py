from multi_agent_research_lab.cli import run_baseline
from multi_agent_research_lab.core.schemas import SourceDocument
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
    state = run_baseline("Explain multi-agent research systems", llm=FakeLLM(), search=FakeSearch())

    assert state.final_answer == "Baseline answer [S1]"
    assert len(state.sources) == 1
    assert state.input_tokens == 12
    assert state.output_tokens == 6
    assert state.estimated_cost_usd == 0.002


def test_comparison_helper_writes_benchmark_report(tmp_path) -> None:
    from multi_agent_research_lab.cli import run_comparison
    from multi_agent_research_lab.core.schemas import ResearchQuery
    from multi_agent_research_lab.core.state import ResearchState

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


def test_baseline_preserves_canonical_source_ids_and_budget() -> None:
    class CanonicalLLM:
        def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
            assert "[autogen]" in user_prompt
            return LLMResponse(content="Canonical answer [autogen].")

    class CanonicalSearch:
        def search(self, query: str, max_results: int = 5) -> list[SourceDocument]:
            assert max_results == 1
            return [
                SourceDocument(
                    title="AutoGen",
                    snippet="Evidence",
                    metadata={"source_id": "autogen"},
                )
            ]

    state = run_baseline(
        "Explain multi-agent research systems",
        llm=CanonicalLLM(),
        search=CanonicalSearch(),
        max_sources=1,
    )

    assert state.sources[0].metadata["source_id"] == "autogen"
    assert state.final_answer == "Canonical answer [autogen]."


def test_baseline_exposes_synthetic_provenance_to_llm() -> None:
    class CapturingLLM:
        def __init__(self) -> None:
            self.user_prompt = ""

        def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
            self.user_prompt = user_prompt
            return LLMResponse(content="Synthetic evidence [T01-SYN-A].")

    class SyntheticSearch:
        def search(self, query: str, max_results: int = 5) -> list[SourceDocument]:
            return [
                SourceDocument(
                    title="Synthetic study",
                    snippet="Benchmark-only evidence",
                    metadata={
                        "source_id": "T01-SYN-A",
                        "is_synthetic": True,
                        "document_class": "synthetic_benchmark",
                    },
                )
            ]

    llm = CapturingLLM()
    run_baseline(
        "Explain multi-agent research systems",
        llm=llm,
        search=SyntheticSearch(),
        max_sources=1,
    )

    assert "is_synthetic=true" in llm.user_prompt
    assert "document_class=synthetic_benchmark" in llm.user_prompt
