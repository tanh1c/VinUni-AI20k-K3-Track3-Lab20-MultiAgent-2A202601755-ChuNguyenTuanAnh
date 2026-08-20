# Official Offline Corpus Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reproducible school-corpus benchmark with canonical citations, stronger Writer validation, rubric-aligned evaluation, and manual-only CI support.

**Architecture:** Introduce a `SearchProvider` protocol with Tavily and fixed-topic corpus implementations. Keep the existing graph unchanged, strengthen Writer citation coverage to 80%, and add a corpus evaluator/report pipeline that compares baseline and multi-agent on identical evidence.

**Tech Stack:** Python 3.11, Pydantic, LangGraph, OpenAI Responses API, pytest, Ruff, mypy, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-20-official-corpus-benchmark-design.md`

## Global Constraints

- Keep `Supervisor -> Researcher -> Analyst -> Writer -> Critic -> Done`.
- Corpus mode performs no Tavily/browser search.
- Preserve canonical corpus citation IDs and `is_synthetic` metadata.
- Writer coverage threshold is 0.80 with one correction attempt maximum.
- CI remains `workflow_dispatch` only.
- Automated rubric score is explicitly a proxy, never a teacher grade.
- Official corpus SHA-256 is `276117a25e178937bfb20b08f944450f5278fd0490a9c5cdebed364fa24658bf`.

---

### Task 1: Corpus loader and provider interface

**Files:**
- Create: `src/multi_agent_research_lab/services/corpus_client.py`
- Modify: `src/multi_agent_research_lab/services/search_client.py`
- Modify: `src/multi_agent_research_lab/agents/researcher.py`
- Modify: `src/multi_agent_research_lab/graph/workflow.py`
- Test: `tests/test_corpus_client.py`

**Interfaces:**
- Produces: `SearchProvider.search(query: str, max_results: int = 5) -> list[SourceDocument]`
- Produces: `CorpusSearchClient(corpus_path: Path, topic_id: str)`
- Produces: `CorpusSearchClient.topic` metadata used by evaluation.

- [ ] Write tests proving checksum validation, topic lookup, canonical source IDs, synthetic metadata, and deterministic max-result bounds.
- [ ] Run the new tests and confirm they fail because corpus support is missing.
- [ ] Implement `SearchProvider` and `CorpusSearchClient` minimally.
- [ ] Update Researcher/Workflow type annotations to consume `SearchProvider` without changing runtime graph behavior.
- [ ] Run corpus/search/workflow tests to green.

### Task 2: Generic citations and Writer coverage guard

**Files:**
- Modify: `src/multi_agent_research_lab/utils/citations.py`
- Modify: `src/multi_agent_research_lab/agents/writer.py`
- Test: `tests/test_citations.py`
- Modify: `tests/test_worker_agents.py`

**Interfaces:**
- `citation_ids(text: str) -> list[str]` accepts `[S1]`, `[autogen]`, `[A01]`, `[T01-SYN-A]`.
- Writer validity requires citation coverage `>= 0.80` and no invalid IDs.

- [ ] Write failing tests for canonical IDs and low-coverage Writer retry/failure behavior.
- [ ] Run focused tests and verify expected failures.
- [ ] Generalize citation parsing and update Writer prompt/validation.
- [ ] Run focused tests to green and then existing Critic tests.

### Task 3: Rubric-aligned corpus evaluator

**Files:**
- Modify: `src/multi_agent_research_lab/core/schemas.py`
- Create: `src/multi_agent_research_lab/evaluation/corpus.py`
- Test: `tests/test_corpus_evaluation.py`

**Interfaces:**
- Produces `CorpusBenchmarkMetrics` with exact citation/source/section/gold-point metrics and `rubric_proxy_score` 0..100.
- Produces `evaluate_corpus_run(state, topic, run_name, latency_seconds)`.

- [ ] Write failing metric tests using a compact synthetic topic fixture.
- [ ] Verify red state.
- [ ] Implement deterministic metric extraction and transparent weighted proxy.
- [ ] Verify focused tests and schema validation.

### Task 4: Corpus comparison and reports

**Files:**
- Create: `src/multi_agent_research_lab/evaluation/corpus_report.py`
- Modify: `src/multi_agent_research_lab/cli.py`
- Test: `tests/test_corpus_report.py`
- Modify: `tests/test_cli_helpers.py`

**Interfaces:**
- Produces `run_corpus_comparison(topic_id, corpus_path, source_budget=8, ...)`.
- Produces Markdown and JSON details for baseline + multi-agent.
- Adds CLI `corpus-benchmark`.

- [ ] Write failing tests for equal source budgets, output files, and report labels.
- [ ] Verify red state.
- [ ] Implement comparison runner and renderers.
- [ ] Verify focused tests to green.

### Task 5: Official corpus data, CI, and documentation

**Files:**
- Create: `data/offline_corpus_subset/PROVENANCE.json`
- Create: `data/offline_corpus_subset/manifest.csv`
- Create: `data/offline_corpus_subset/SCHEMA.json`
- Create: `data/offline_corpus_subset/topics/01_single_agent_vs_multi_agent_architectures_for_complex_research_tasks.json.gz`
- Create: `data/offline_corpus_subset/topics/12_critic_and_verifier_agents_for_research_report_quality.json.gz`
- Create: `data/offline_corpus_subset/topics/13_cascading_hallucinations_in_multi_agent_pipelines.json.gz`
- Modify: `.github/workflows/ci.yml`
- Modify: `README.md`
- Modify: `Makefile`
- Modify: `reports/benchmark_report.md` only if documenting the already measured live run without fabricating new values.
- Test: `tests/test_ci_policy.py`

- [ ] Add tests asserting workflow remains manual-only and exposes `offline|live|corpus` modes.
- [ ] Verify CI-policy test fails before config change.
- [ ] Add corpus mode, subset provenance/checksum verification, three-topic command, and artifact upload.
- [ ] Document corpus provenance, benchmark methodology, Critic bonus, and exact commands.
- [ ] Run all tests.

### Task 6: Full verification and PR update

**Files:** all changed files.

- [ ] Run `python -m compileall -q src tests`.
- [ ] Run `pytest -q`.
- [ ] Run local line-length and corpus checksum checks; use Ruff/mypy locally if available.
- [ ] Review diff for secrets, fabricated results, accidental automatic CI triggers, and corpus integrity.
- [ ] Update `feat/lab20-full-score`, squash to one implementation commit on top of `main`, and verify PR #2 remains open/mergeable.
- [ ] Ask for exactly one final manual `corpus` workflow run only after all static/unit verification is clean.
