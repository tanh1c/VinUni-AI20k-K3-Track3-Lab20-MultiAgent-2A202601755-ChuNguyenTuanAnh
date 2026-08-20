# Lab 20 Full-Score Multi-Agent Design

## Goal

Complete the Lab 20 starter into a production-style multi-agent research system that satisfies all five peer-review rubric categories at the 2/2 level and implements the optional CriticAgent bonus, while keeping GitHub Actions manual-only to avoid automatic CI runs on pushes or pull requests.

## Architecture

The workflow is deterministic at the orchestration layer and LLM-driven at the worker layer:

```text
User Query
   |
   v
Supervisor
   |
   +--> Researcher --> sources + research_notes
   |
   +--> Analyst -----> analysis_notes
   |
   +--> Writer ------> final_answer with [S#] citations
   |
   +--> Critic ------> critic_review + citation/hallucination checks
   |
   v
Done + trace + benchmark metrics
```

The Supervisor does not spend an LLM call on routing. It inspects shared state and selects the next missing stage. This makes routing deterministic, cheap, testable, and easy to explain in the rubric review.

## Responsibilities

### Supervisor

- Inspect shared state.
- Route to `researcher`, `analyst`, `writer`, `critic`, or `done`.
- Enforce `MAX_ITERATIONS`.
- Stop safely when fatal errors or iteration limits make further progress unsafe.

### Researcher

- Call `SearchClient` with the user query and `max_sources`.
- Normalize, deduplicate, and label sources as `[S1]`, `[S2]`, ... in deterministic order.
- Produce concise research notes grounded only in retrieved sources.
- Preserve source title, URL, snippet, and provider metadata in shared state.

### Analyst

- Consume source-backed research notes.
- Extract major claims, compare viewpoints, identify evidence strength, and flag unsupported or weakly supported points.
- Produce analysis notes used by the Writer.

### Writer

- Produce the final response for the requested audience.
- Cite factual claims with source identifiers such as `[S1]`.
- Never invent citation identifiers that do not exist in state.

### Critic (bonus)

- Run after Writer.
- Evaluate citation coverage, invalid citation identifiers, unsupported-claim risk, and hallucination/factual-risk signals.
- Store a structured critic review in shared state.
- The Critic is a reviewer, not a second Writer; it does not silently rewrite the answer.

## Shared State

`ResearchState` remains the single source of truth and is extended with explicit execution/evaluation fields:

- `sources`
- `research_notes`
- `analysis_notes`
- `final_answer`
- `critic_review`
- `route_history`
- `agent_results`
- `trace`
- `errors`
- cumulative token usage and estimated cost

Every handoff must be inspectable without reading hidden agent memory.

## LLM Client

`LLMClient` is the only production component that imports and calls the OpenAI SDK. Agents depend on this abstraction.

Requirements:

- Load model/key/timeout from `Settings`.
- Retry transient provider failures with a bounded retry policy.
- Return `LLMResponse(content, input_tokens, output_tokens, cost_usd)`.
- Raise clear configuration/provider errors rather than returning fake successful data.
- Unit tests use a fake LLM implementation and never call OpenAI.

## Search Client

`SearchClient` uses Tavily when `TAVILY_API_KEY` is configured.

Requirements:

- HTTPS request with bounded timeout.
- Map Tavily results to `SourceDocument`.
- Deduplicate repeated URLs/titles.
- Provide an injectable deterministic in-memory/fake implementation for tests.
- Unit tests and offline CI never call Tavily.

## Guardrails

The implementation must demonstrate all four rubric guard categories:

1. **Max iterations:** Supervisor refuses to continue past `MAX_ITERATIONS`.
2. **Timeout:** LLM and search calls use `TIMEOUT_SECONDS` or a smaller bounded timeout.
3. **Retry/fallback:** transient provider failures retry; workflow records failure and stops/falls back safely instead of looping forever.
4. **Validation:** Pydantic schemas validate input/state; Writer/Critic validate citation identifiers against retrieved sources.

## Tracing

Tracing has two layers:

1. Local structured trace events are always recorded in `ResearchState.trace` so offline tests and debugging work without external services.
2. LangSmith tracing is enabled when `LANGSMITH_API_KEY` is present. Trace input processing removes object/config/credential-bearing arguments before serialization.

A final live run will provide trace evidence for submission.

## Benchmark

The same query set is run through:

- single-agent baseline
- multi-agent workflow

Metrics:

- wall-clock latency
- estimated token cost
- quality score (deterministic heuristic plus documented human/LLM-review slot)
- citation coverage
- failure rate

The report generator writes `reports/benchmark_report.md` with a comparison table, interpretation, trade-offs, and a documented failure mode/fix.

## Baseline

The baseline is a real single OpenAI call that performs research-style synthesis from the user query without the multi-agent decomposition. It records tokens/cost so the comparison is meaningful.

## Testing Strategy

All core behavior is validated offline with injected fakes:

- Supervisor routing and max-iteration behavior.
- Researcher source normalization/deduplication.
- Analyst handoff behavior.
- Writer citation behavior.
- Critic invalid-citation/coverage checks.
- Workflow end-to-end route history.
- Provider retry/configuration behavior without network calls.
- Benchmark metric computation and Markdown report rendering.
- LangSmith input sanitization for credentials/config objects.

No default pytest test may call OpenAI, Tavily, or LangSmith.

## GitHub Actions

`.github/workflows/ci.yml` is `workflow_dispatch` only.

Manual input selects:

- `offline`: install dependencies, Ruff lint/format check, mypy, pytest.
- `live`: run offline checks first, then one bounded real-provider benchmark using repository secrets.

There are no `push` or `pull_request` triggers in the final workflow.

## Environment

Required for live execution:

- `OPENAI_API_KEY`
- `TAVILY_API_KEY`
- `LANGSMITH_API_KEY`

Non-secret configuration has safe defaults and may be overridden:

- `OPENAI_MODEL`
- `LANGSMITH_PROJECT`
- `MAX_ITERATIONS`
- `TIMEOUT_SECONDS`
- `LOG_LEVEL`

No secret is committed to the repository.

## Rubric Mapping

| Rubric | Evidence |
|---|---|
| Role clarity | Explicit, non-overlapping Supervisor/Researcher/Analyst/Writer/Critic responsibilities |
| State design | Inspectable shared state with source-backed intermediate artifacts, trace, errors, and usage |
| Failure guard | Max iterations, timeout, retry/fallback, and validation |
| Benchmark | Baseline vs multi-agent with latency, cost, quality, citation coverage, failure rate |
| Trace explanation | Local event trace plus LangSmith live trace |
| Bonus | Critic fact-check/citation/hallucination review |

## Acceptance Criteria

- `make lint` passes.
- `make test` passes.
- `python -m multi_agent_research_lab.cli baseline --query "..."` returns a real answer when live secrets are configured.
- `python -m multi_agent_research_lab.cli multi-agent --query "..."` completes through Critic and returns final answer, route history, and critic review.
- No core `TODO(student)` or `StudentTodoError` remains in the main execution path.
- `reports/benchmark_report.md` contains measured comparison data after live benchmark.
- At least one LangSmith trace can be used as submission evidence.
- GitHub Actions does not auto-run on push or pull request.
