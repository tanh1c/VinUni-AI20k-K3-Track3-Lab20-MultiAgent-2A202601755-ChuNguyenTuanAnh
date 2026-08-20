# Lab 20 Full-Score Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the Lab 20 multi-agent research starter for full rubric coverage plus the CriticAgent bonus, with deterministic offline tests and manual-only GitHub Actions.

**Architecture:** Keep orchestration deterministic: Supervisor routes by missing state fields; worker agents use injected LLM/search clients; Critic validates the final answer; shared state records trace/usage/errors. Use LangGraph when the optional `llm` dependencies are installed, with no network calls in default tests.

**Tech Stack:** Python 3.11+, Pydantic v2, OpenAI Python SDK Responses API, Tavily Search API, LangGraph, LangSmith, Typer, pytest, Ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-08-20-lab20-full-score-design.md`

## Global Constraints

- Do not commit secrets.
- Default tests must not call OpenAI, Tavily, or LangSmith.
- GitHub Actions must use `workflow_dispatch` only; no `push` or `pull_request` trigger.
- `MAX_ITERATIONS` defaults to 6 and `TIMEOUT_SECONDS` defaults to 60.
- Preserve the starter package/module structure.
- Use `[S1]`, `[S2]`, ... as canonical source identifiers.
- `ResearchState` is the only cross-agent state container.
- Critic runs after Writer and does not silently rewrite the Writer output.

---

### Task 1: Shared state, schemas, and deterministic Supervisor

**Files:**
- Modify: `src/multi_agent_research_lab/core/schemas.py`
- Modify: `src/multi_agent_research_lab/core/state.py`
- Modify: `src/multi_agent_research_lab/agents/supervisor.py`
- Replace: `tests/test_agents_todo.py`
- Test: `tests/test_supervisor.py`

**Interfaces:**
- Produces `CriticReview` schema with `citation_coverage`, `invalid_citations`, `unsupported_claims`, `verdict`.
- Produces state usage fields `input_tokens`, `output_tokens`, `estimated_cost_usd`, `critic_review`.
- `SupervisorAgent(settings: Settings | None = None).run(state) -> ResearchState` records exactly one next route.

- [ ] **Step 1: Write failing Supervisor/state tests**

Tests assert routing sequence from empty state (`researcher`) through populated stages (`analyst`, `writer`, `critic`, `done`), plus max-iteration stop and usage accumulation.

- [ ] **Step 2: Run the targeted tests and confirm RED**

Run: `pytest tests/test_supervisor.py tests/test_state.py -q`
Expected: failures because `CriticReview`, usage fields, and Supervisor implementation do not exist.

- [ ] **Step 3: Implement minimal schemas/state/Supervisor**

Routing policy:

```python
if state.iteration >= settings.max_iterations:
    route = "done"
elif not state.sources or not state.research_notes:
    route = "researcher"
elif not state.analysis_notes:
    route = "analyst"
elif not state.final_answer:
    route = "writer"
elif state.critic_review is None:
    route = "critic"
else:
    route = "done"
state.record_route(route)
```

- [ ] **Step 4: Run targeted tests and existing tests**

Run: `pytest tests/test_supervisor.py tests/test_state.py tests/test_config.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `feat: add shared execution state and supervisor routing`

### Task 2: Provider clients with retry, timeout, and usage accounting

**Files:**
- Modify: `src/multi_agent_research_lab/core/config.py`
- Modify: `src/multi_agent_research_lab/services/llm_client.py`
- Modify: `src/multi_agent_research_lab/services/search_client.py`
- Test: `tests/test_llm_client.py`
- Test: `tests/test_search_client.py`

**Interfaces:**
- `LLMClient(settings: Settings | None = None).complete(system_prompt, user_prompt) -> LLMResponse`.
- `SearchClient(settings: Settings | None = None).search(query, max_results=5) -> list[SourceDocument]`.
- Provider objects accept injectable transport/client factories in tests.

- [ ] **Step 1: Write failing provider tests**

Cover missing-key error, OpenAI response token extraction, retry of a transient exception, Tavily payload bounds, result normalization, and deduplication.

- [ ] **Step 2: Run provider tests and confirm RED**

Run: `pytest tests/test_llm_client.py tests/test_search_client.py -q`
Expected: failures from starter `StudentTodoError`.

- [ ] **Step 3: Implement provider clients**

OpenAI call uses `client.responses.create(model=settings.openai_model, instructions=system_prompt, input=user_prompt)` and reads `response.output_text` plus `response.usage.input_tokens`/`output_tokens` when available. Tavily uses `POST https://api.tavily.com/search` with `query`, `search_depth="basic"`, `max_results`, and bounded timeout.

- [ ] **Step 4: Run provider tests**

Run: `pytest tests/test_llm_client.py tests/test_search_client.py -q`
Expected: PASS without network access.

- [ ] **Step 5: Commit**

Commit message: `feat: implement resilient llm and search clients`

### Task 3: Researcher, Analyst, Writer, and bonus Critic

**Files:**
- Modify: `src/multi_agent_research_lab/agents/researcher.py`
- Modify: `src/multi_agent_research_lab/agents/analyst.py`
- Modify: `src/multi_agent_research_lab/agents/writer.py`
- Modify: `src/multi_agent_research_lab/agents/critic.py`
- Test: `tests/test_worker_agents.py`
- Test: `tests/test_critic.py`

**Interfaces:**
- Each worker accepts injected `LLMClient`; Researcher also accepts injected `SearchClient`.
- Each worker appends one `AgentResult`, trace metadata, and usage accounting.
- Critic returns structured `CriticReview` parsed from deterministic citation checks plus optional LLM review text.

- [ ] **Step 1: Write failing worker tests with fake clients**

Researcher must produce deduplicated sources and source-indexed notes. Analyst must refuse missing research input. Writer must preserve valid `[S#]` citations. Critic must detect `[S99]` as invalid and compute citation coverage in `[0,1]`.

- [ ] **Step 2: Run worker tests and confirm RED**

Run: `pytest tests/test_worker_agents.py tests/test_critic.py -q`
Expected: starter TODO failures.

- [ ] **Step 3: Implement minimal worker behavior**

Use explicit role prompts, validate preconditions, record `AgentResult`, accumulate usage, and add local trace events.

- [ ] **Step 4: Run worker tests**

Run: `pytest tests/test_worker_agents.py tests/test_critic.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `feat: implement research analyst writer and critic agents`

### Task 4: LangGraph workflow and single-agent baseline

**Files:**
- Modify: `src/multi_agent_research_lab/graph/workflow.py`
- Modify: `src/multi_agent_research_lab/cli.py`
- Test: `tests/test_workflow.py`
- Test: `tests/test_cli_helpers.py`

**Interfaces:**
- `MultiAgentWorkflow(...dependencies...).build() -> object` returns a compiled-capable LangGraph state graph when LangGraph is installed.
- `MultiAgentWorkflow.run(state) -> ResearchState` returns completed state.
- Baseline helper returns a `ResearchState` with answer and usage rather than printing a placeholder.

- [ ] **Step 1: Write failing end-to-end workflow tests**

With fake LLM/search dependencies, assert route history is `researcher -> analyst -> writer -> critic -> done`, answer is non-empty, critic review exists, and no `StudentTodoError` is raised.

- [ ] **Step 2: Run workflow tests and confirm RED**

Run: `pytest tests/test_workflow.py tests/test_cli_helpers.py -q`
Expected: starter TODO/placeholder failures.

- [ ] **Step 3: Implement LangGraph orchestration and baseline helper**

Graph nodes map to agents, worker nodes return to Supervisor, and Supervisor conditional edge selects the latest recorded route. Provide a deterministic fallback executor only when LangGraph is not installed so minimal/offline environments remain testable; live installation must use LangGraph.

- [ ] **Step 4: Run workflow tests**

Run: `pytest tests/test_workflow.py tests/test_cli_helpers.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `feat: build multi-agent workflow and real baseline`

### Task 5: Tracing and benchmark/reporting

**Files:**
- Modify: `src/multi_agent_research_lab/observability/tracing.py`
- Modify: `src/multi_agent_research_lab/evaluation/benchmark.py`
- Modify: `src/multi_agent_research_lab/evaluation/report.py`
- Modify: `src/multi_agent_research_lab/cli.py`
- Create: `reports/benchmark_report.md`
- Test: `tests/test_tracing.py`
- Test: `tests/test_benchmark.py`
- Modify: `tests/test_report.py`

**Interfaces:**
- Local `trace_span()` remains usable without LangSmith.
- Benchmark computes latency, cost, citation coverage, failure rate, and a documented deterministic quality heuristic.
- CLI exposes a bounded benchmark command that writes `reports/benchmark_report.md`.

- [ ] **Step 1: Write failing benchmark/tracing tests**

Assert citation coverage, cost propagation, failure-rate behavior, Markdown analysis sections, and no-op tracing without external SDK.

- [ ] **Step 2: Run tests and confirm RED**

Run: `pytest tests/test_tracing.py tests/test_benchmark.py tests/test_report.py -q`
Expected: missing metrics/analysis failures.

- [ ] **Step 3: Implement tracing and benchmark/report logic**

Use local trace events always; when LangSmith is available/configured, wrap provider/workflow functions with traceable instrumentation. Report includes measured table, trade-off interpretation, failure mode, and submission-evidence placeholders that are explicitly marked as requiring a live run rather than fabricated evidence.

- [ ] **Step 4: Run benchmark/tracing tests**

Run: `pytest tests/test_tracing.py tests/test_benchmark.py tests/test_report.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `feat: add traceable benchmark and report generation`

### Task 6: Manual-only GitHub Actions and documentation

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `docs/lab_guide.md`

**Interfaces:**
- Workflow has only `workflow_dispatch` trigger with `mode: offline|live` input.
- Offline job runs lint/format/mypy/pytest without provider calls.
- Live steps only run when `mode == 'live'`, after offline checks, with repository secrets.

- [ ] **Step 1: Add a static workflow-policy test**

Create `tests/test_ci_policy.py` that parses `.github/workflows/ci.yml` as text/YAML and asserts it contains `workflow_dispatch` but no `pull_request` or `push` trigger.

- [ ] **Step 2: Run policy test and confirm RED**

Run: `pytest tests/test_ci_policy.py -q`
Expected: FAIL because current CI still auto-runs.

- [ ] **Step 3: Replace CI trigger and document live setup**

Install `.[dev,llm]`; offline runs Ruff check, Ruff format check, mypy, pytest. Live mode runs one bounded smoke query and one bounded benchmark after secrets are available.

- [ ] **Step 4: Run policy test and full pytest**

Run: `pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `ci: make lab validation manual only`

### Task 7: Final verification and PR

**Files:**
- Review all changed files.

**Interfaces:**
- No new interface; this is the release gate.

- [ ] **Step 1: Verify no core TODO path remains**

Run: `grep -R "TODO(student)" -n src || true`
Expected: no core TODO markers in executable source.

- [ ] **Step 2: Run offline quality gate**

Run: `pytest -q`, `ruff check src tests`, `ruff format --check src tests`, `mypy src` in an environment with dev dependencies.
Expected: all pass.

- [ ] **Step 3: Review diff against rubric/spec**

Confirm explicit evidence for all five rubric rows plus Critic bonus and no secret values in the diff.

- [ ] **Step 4: Create PR only after manual-only workflow is present**

PR title: `feat: complete Lab 20 multi-agent research system`

- [ ] **Step 5: Trigger one manual live validation**

Use `mode=live` once. Do not rerun repeatedly. Capture resulting benchmark artifact/trace evidence or report the exact live blocker without fabricating success.
