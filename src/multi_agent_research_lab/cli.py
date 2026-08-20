"""Command-line entrypoint for the completed multi-agent research lab."""

import json
from collections.abc import Callable
from pathlib import Path
from time import perf_counter
from typing import Annotated

import typer
from pydantic import ValidationError as PydanticValidationError
from rich.console import Console
from rich.panel import Panel

from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.errors import LabError
from multi_agent_research_lab.core.schemas import (
    BenchmarkMetrics,
    CorpusBenchmarkMetrics,
    ResearchQuery,
    SourceDocument,
)
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.evaluation.benchmark import run_benchmark
from multi_agent_research_lab.evaluation.corpus import evaluate_corpus_run
from multi_agent_research_lab.evaluation.corpus_report import render_corpus_markdown
from multi_agent_research_lab.evaluation.report import render_markdown_report
from multi_agent_research_lab.graph.workflow import MultiAgentWorkflow
from multi_agent_research_lab.observability.logging import configure_logging
from multi_agent_research_lab.observability.tracing import maybe_traceable
from multi_agent_research_lab.services.corpus_client import CorpusSearchClient
from multi_agent_research_lab.services.llm_client import LLMClient
from multi_agent_research_lab.services.search_client import SearchClient, SearchProvider
from multi_agent_research_lab.utils.evidence import source_prompt_block

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
    search: SearchProvider | None = None,
    max_sources: int = 5,
) -> ResearchState:
    """Run one research agent with the same retrieval source used by multi-agent mode."""

    request = ResearchQuery(query=query, max_sources=max_sources)
    state = ResearchState(request=request)
    llm_client = llm or LLMClient()
    search_client = search or SearchClient()
    sources = search_client.search(request.query, max_results=request.max_sources)
    normalized: list[SourceDocument] = []
    for index, source in enumerate(sources, start=1):
        item = source.model_copy(deep=True)
        item.metadata.setdefault("source_id", f"S{index}")
        normalized.append(item)
    state.sources = normalized
    context = "\n\n".join(source_prompt_block(source) for source in normalized)
    response = llm_client.complete(
        (
            "You are a single-agent research assistant. Research, analyze, and write "
            "the final answer in one pass from the supplied sources. "
            "Cite factual claims with the exact bracketed source identifiers supplied."
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


CorpusRunner = Callable[[str, int, SearchProvider], ResearchState]
DEFAULT_CORPUS_PATH = Path("data/offline_corpus_subset")


def _corpus_query(topic: dict[str, object]) -> str:
    topic_info = topic["topic"]
    research_task = topic["research_task"]
    assert isinstance(topic_info, dict)
    assert isinstance(research_task, dict)
    expected = research_task["expected_report"]
    assert isinstance(expected, dict)
    required_sections = expected.get("required_sections", [])
    subquestions = research_task.get("subquestions", [])
    question = str(topic_info["research_question"])
    return (
        f"{question}\n\n"
        "Use only the supplied official offline-corpus evidence. Do not assume external URLs "
        "were opened. Preserve source IDs exactly. Clearly label synthetic benchmark evidence.\n\n"
        f"Subquestions: {json.dumps(subquestions, ensure_ascii=False)}\n"
        f"Required report sections: {json.dumps(required_sections, ensure_ascii=False)}\n"
        "Include a counterargument/limitation, measurable evaluation criteria, "
        "failure propagation, and explicit trade-offs. Cite every material factual sentence."
    )


def _default_corpus_baseline(
    query: str,
    source_budget: int,
    search: SearchProvider,
) -> ResearchState:
    return run_baseline(query, search=search, max_sources=source_budget)


def _default_corpus_multi(
    query: str,
    source_budget: int,
    search: SearchProvider,
) -> ResearchState:
    request = ResearchQuery(query=query, max_sources=source_budget)
    return MultiAgentWorkflow(search=search).run(ResearchState(request=request))


def _execute_corpus_runner(
    run_name: str,
    query: str,
    source_budget: int,
    search: CorpusSearchClient,
    runner: CorpusRunner,
) -> tuple[ResearchState, CorpusBenchmarkMetrics]:
    started = perf_counter()
    try:
        state = runner(query, source_budget, search)
    except Exception as exc:
        state = ResearchState(request=ResearchQuery(query=query, max_sources=source_budget))
        state.errors.append(f"corpus benchmark runner failed: {exc}")
    latency = perf_counter() - started
    metrics = evaluate_corpus_run(state, search.topic, run_name, latency)
    return state, metrics


def _run_corpus_topic(
    topic_id: str,
    *,
    corpus_path: Path,
    source_budget: int,
    baseline_runner: CorpusRunner | None,
    multi_runner: CorpusRunner | None,
) -> tuple[str, list[tuple[ResearchState, CorpusBenchmarkMetrics]]]:
    topic_client = CorpusSearchClient(corpus_path, topic_id=topic_id)
    query = _corpus_query(topic_client.topic)
    baseline_search = CorpusSearchClient(corpus_path, topic_id=topic_id)
    multi_search = CorpusSearchClient(corpus_path, topic_id=topic_id)
    baseline_result = _execute_corpus_runner(
        "baseline",
        query,
        source_budget,
        baseline_search,
        baseline_runner or _default_corpus_baseline,
    )
    multi_result = _execute_corpus_runner(
        "multi-agent",
        query,
        source_budget,
        multi_search,
        multi_runner or _default_corpus_multi,
    )
    return topic_client.corpus_sha256, [baseline_result, multi_result]


def _write_corpus_outputs(
    topic_ids: list[str],
    corpus_sha256: str,
    results: list[tuple[ResearchState, CorpusBenchmarkMetrics]],
    *,
    markdown_path: Path,
    details_path: Path,
) -> list[CorpusBenchmarkMetrics]:
    metrics = [item for _, item in results]
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(
        render_corpus_markdown(metrics, corpus_sha256),
        encoding="utf-8",
    )
    runs = [
        {
            "metrics": item.model_dump(),
            "source_ids": [str(source.metadata.get("source_id")) for source in state.sources],
            "route_history": state.route_history,
            "errors": state.errors,
        }
        for state, item in results
    ]
    payload: dict[str, object] = {
        "topic_ids": topic_ids,
        "corpus_sha256": corpus_sha256,
        "runs": runs,
    }
    if len(topic_ids) == 1:
        payload["topic_id"] = topic_ids[0]
    details_path.parent.mkdir(parents=True, exist_ok=True)
    details_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return metrics


def run_corpus_comparison(
    topic_id: str,
    *,
    corpus_path: Path = DEFAULT_CORPUS_PATH,
    source_budget: int = 8,
    baseline_runner: CorpusRunner | None = None,
    multi_runner: CorpusRunner | None = None,
    markdown_path: Path = Path("reports/corpus_benchmark_report.md"),
    details_path: Path = Path("reports/corpus_benchmark_details.json"),
) -> list[CorpusBenchmarkMetrics]:
    """Compare both architectures on one fixed official-corpus topic."""

    corpus_sha256, results = _run_corpus_topic(
        topic_id,
        corpus_path=corpus_path,
        source_budget=source_budget,
        baseline_runner=baseline_runner,
        multi_runner=multi_runner,
    )
    return _write_corpus_outputs(
        [topic_id],
        corpus_sha256,
        results,
        markdown_path=markdown_path,
        details_path=details_path,
    )


def run_corpus_suite(
    topic_ids: list[str],
    *,
    corpus_path: Path = DEFAULT_CORPUS_PATH,
    source_budget: int = 8,
    baseline_runner: CorpusRunner | None = None,
    multi_runner: CorpusRunner | None = None,
    markdown_path: Path = Path("reports/corpus_benchmark_report.md"),
    details_path: Path = Path("reports/corpus_benchmark_details.json"),
) -> list[CorpusBenchmarkMetrics]:
    """Compare both architectures across a deterministic suite of corpus topics."""

    if not topic_ids:
        raise ValueError("At least one corpus topic ID is required")
    all_results: list[tuple[ResearchState, CorpusBenchmarkMetrics]] = []
    corpus_sha256 = ""
    for topic_id in topic_ids:
        current_sha, results = _run_corpus_topic(
            topic_id,
            corpus_path=corpus_path,
            source_budget=source_budget,
            baseline_runner=baseline_runner,
            multi_runner=multi_runner,
        )
        if corpus_sha256 and current_sha != corpus_sha256:
            raise ValueError("Corpus checksum changed during suite execution")
        corpus_sha256 = current_sha
        all_results.extend(results)
    return _write_corpus_outputs(
        topic_ids,
        corpus_sha256,
        all_results,
        markdown_path=markdown_path,
        details_path=details_path,
    )


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


@app.command("corpus-benchmark")
def corpus_benchmark_command(
    topics: Annotated[
        str,
        typer.Option(
            "--topics",
            help="Comma-separated official corpus topic IDs",
        ),
    ] = "AIAGENT-01,AIAGENT-12,AIAGENT-13",
    corpus_path: Annotated[
        Path,
        typer.Option("--corpus", help="Path to official corpus ZIP or verified subset"),
    ] = DEFAULT_CORPUS_PATH,
    source_budget: Annotated[
        int,
        typer.Option("--source-budget", min=1, max=20),
    ] = 8,
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Corpus Markdown report path"),
    ] = Path("reports/corpus_benchmark_report.md"),
    details: Annotated[
        Path,
        typer.Option("--details", help="Corpus JSON details path"),
    ] = Path("reports/corpus_benchmark_details.json"),
) -> None:
    """Run a fixed official-corpus baseline-vs-multi benchmark suite."""

    _init()
    topic_ids = [item.strip() for item in topics.split(",") if item.strip()]
    metrics = run_corpus_suite(
        topic_ids,
        corpus_path=corpus_path,
        source_budget=source_budget,
        markdown_path=output,
        details_path=details,
    )
    corpus_sha256 = CorpusSearchClient(corpus_path, topic_id=topic_ids[0]).corpus_sha256
    console.print(render_corpus_markdown(metrics, corpus_sha256))


if __name__ == "__main__":
    app()
