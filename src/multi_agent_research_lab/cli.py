"""Command-line entrypoint for the completed multi-agent research lab."""

from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError as PydanticValidationError
from rich.console import Console
from rich.panel import Panel

from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.errors import LabError
from multi_agent_research_lab.core.schemas import BenchmarkMetrics, ResearchQuery
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.evaluation.benchmark import run_benchmark
from multi_agent_research_lab.evaluation.report import render_markdown_report
from multi_agent_research_lab.graph.workflow import MultiAgentWorkflow
from multi_agent_research_lab.observability.logging import configure_logging
from multi_agent_research_lab.observability.tracing import maybe_traceable
from multi_agent_research_lab.services.llm_client import LLMClient
from multi_agent_research_lab.services.search_client import SearchClient

app = typer.Typer(help="Multi-Agent Research Lab")
console = Console()


def _init() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)


def _parse_query(query: str) -> ResearchQuery:
    try:
        return ResearchQuery(query=query)
    except PydanticValidationError as exc:
        console.print(Panel.fit(str(exc), title="Input Error", style="red"))
        raise typer.Exit(code=1) from exc


@maybe_traceable("workflow.baseline")
def run_baseline(
    query: str,
    *,
    llm: LLMClient | None = None,
    search: SearchClient | None = None,
) -> ResearchState:
    """Run one research agent with the same retrieval source used by multi-agent mode."""

    request = ResearchQuery(query=query)
    state = ResearchState(request=request)
    llm_client = llm or LLMClient()
    search_client = search or SearchClient()
    sources = search_client.search(request.query, max_results=request.max_sources)
    normalized = []
    for index, source in enumerate(sources, start=1):
        item = source.model_copy(deep=True)
        item.metadata["source_id"] = f"S{index}"
        normalized.append(item)
    state.sources = normalized
    context = "\n\n".join(
        f"[S{i}] {source.title}\nURL: {source.url or 'n/a'}\n{source.snippet}"
        for i, source in enumerate(normalized, start=1)
    )
    response = llm_client.complete(
        (
            "You are a single-agent research assistant. Research, analyze, and write the final answer "
            "in one pass from the supplied sources. Cite factual claims with [S#]."
        ),
        f"Query: {request.query}\n\nSources:\n{context}",
    )
    state.final_answer = response.content
    state.add_usage(
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cost_usd=response.cost_usd,
    )
    state.add_trace_event("baseline.complete", {"source_count": len(normalized)})
    return state


def run_comparison(
    query: str,
    *,
    baseline_runner: Callable[[str], ResearchState] | None = None,
    multi_runner: Callable[[str], ResearchState] | None = None,
    output_path: Path = Path("reports/benchmark_report.md"),
) -> list[BenchmarkMetrics]:
    """Run both architectures once and persist a measured Markdown report."""

    baseline_fn = baseline_runner or (lambda value: run_baseline(value))
    multi_fn = multi_runner or (
        lambda value: MultiAgentWorkflow().run(ResearchState(request=ResearchQuery(query=value)))
    )
    _, baseline_metrics = run_benchmark("baseline", query, baseline_fn)
    _, multi_metrics = run_benchmark("multi-agent", query, multi_fn)
    metrics = [baseline_metrics, multi_metrics]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_report(metrics), encoding="utf-8")
    return metrics


@app.command()
def baseline(
    query: Annotated[str, typer.Option("--query", "-q", help="Research query")],
) -> None:
    """Run the real single-agent baseline."""

    _init()
    try:
        state = run_baseline(_parse_query(query).query)
    except LabError as exc:
        console.print(Panel.fit(str(exc), title="Baseline Error", style="red"))
        raise typer.Exit(code=2) from exc
    console.print(Panel.fit(state.final_answer or "", title="Single-Agent Baseline"))


@app.command("multi-agent")
def multi_agent(
    query: Annotated[str, typer.Option("--query", "-q", help="Research query")],
) -> None:
    """Run Supervisor -> Researcher -> Analyst -> Writer -> Critic."""

    _init()
    state = ResearchState(request=_parse_query(query))
    result = MultiAgentWorkflow().run(state)
    console.print(result.model_dump_json(indent=2))


@app.command("benchmark")
def benchmark_command(
    query: Annotated[str, typer.Option("--query", "-q", help="Benchmark query")],
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Markdown report path"),
    ] = Path("reports/benchmark_report.md"),
) -> None:
    """Run one bounded baseline-vs-multi comparison and write the report."""

    _init()
    metrics = run_comparison(_parse_query(query).query, output_path=output)
    console.print(render_markdown_report(metrics))


if __name__ == "__main__":
    app()
