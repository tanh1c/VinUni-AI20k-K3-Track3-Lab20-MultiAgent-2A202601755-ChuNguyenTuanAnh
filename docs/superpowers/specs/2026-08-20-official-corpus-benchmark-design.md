# Official Offline Corpus Benchmark Design

## Goal

Extend Lab 20 with the school's 30-topic offline research corpus so single-agent and multi-agent architectures can be compared against the same fixed evidence, while preserving the existing Tavily/OpenAI live mode and the bonus CriticAgent.

## Constraints

- Keep the production graph: `Supervisor -> Researcher -> Analyst -> Writer -> Critic -> Done`.
- Do not add automatic `push` or `pull_request` GitHub Actions triggers.
- Corpus benchmark must not invoke Tavily or any browser/web-search tool.
- Both baseline and multi-agent runs receive the same topic, source budget, model, and corpus evidence policy.
- Preserve canonical corpus citation IDs such as `[autogen]`, `[A01]`, and `[T01-SYN-A]` rather than remapping them to `[S#]`.
- Evidence with `is_synthetic=true` must remain explicitly identifiable as synthetic benchmark material.
- Automated quality scoring must be labeled a transparent rubric-aligned proxy, never a teacher grade or ground truth.
- No fabricated benchmark measurements or LangSmith trace URLs.
- Keep all execution bounded: one Writer correction attempt, existing retry limits, `MAX_ITERATIONS`, and workflow timeout.

## Corpus integrity

The official input is `ai_agent_offline_research_corpus_30_topics_v2.zip` with SHA-256:

`276117a25e178937bfb20b08f944450f5278fd0490a9c5cdebed364fa24658bf`

The full course ZIP is kept as the authoritative local input but is not redistributed through the public repository. The repository commits deterministic gzip representations of the three benchmark topics used by CI (`AIAGENT-01`, `AIAGENT-12`, `AIAGENT-13`) plus their manifest/schema and `PROVENANCE.json`. Each gzip payload decompresses byte-for-byte to the official topic JSON. Provenance records the parent ZIP SHA-256, each committed payload SHA-256, and each decompressed topic SHA-256. Runtime verifies both layers before use; `CorpusSearchClient` also continues to accept the full verified ZIP for local runs.

## Architecture

`SearchProvider` becomes the interface consumed by Researcher and baseline code:

```text
Researcher / baseline
        |
        +-- SearchClient (Tavily, live)
        |
        +-- CorpusSearchClient (fixed topic, no network)
```

`CorpusSearchClient` loads one topic by `AIAGENT-NN`, selects embedded source documents deterministically, and returns `SourceDocument` objects while retaining canonical IDs and provenance metadata (`document_class`, `is_synthetic`, `year`, `recommended_weight`, topic ID).

For corpus benchmarks, source budget defaults to 8. Retrieval is deterministic and stratified so the evidence set retains strong public references plus synthetic benchmark evidence when available. The same `CorpusSearchClient` configuration is instantiated independently for both architectures.

## Citation validation

Citation parsing accepts canonical bracket IDs rather than only `S<number>`. The Writer requires:

1. at least one valid citation;
2. zero invented citation IDs; and
3. material-sentence citation coverage of at least 80%.

If the first draft fails, the Writer gets exactly one corrective call. If the corrected draft still fails, it raises `ValidationError`. The Critic remains an independent post-writer reviewer and does not rewrite the answer.

## Corpus evaluation

For each run, compute exact deterministic metrics:

- latency;
- estimated provider cost;
- failure rate;
- citation coverage;
- invalid citation count/rate;
- distinct cited source count;
- cited public-source count;
- cited synthetic-source count;
- synthetic-source disclosure;
- required-section coverage;
- minimum-source-target attainment;
- counterargument signal;
- gold-coverage-point lexical coverage;
- rubric-aligned proxy score (0-100).

The proxy is transparent and derived only from measurable report properties and corpus expectations. It is not presented as semantic ground truth. Reports also retain the existing live benchmark metrics so cost/latency trade-offs remain visible.

Representative corpus suite:

- `AIAGENT-01`: single-agent vs multi-agent architectures;
- `AIAGENT-12`: Critic/verifier agents;
- `AIAGENT-13`: cascading hallucinations.

These cover the core architecture choice, the bonus CriticAgent, and cross-agent failure propagation.

## CLI and reports

Add a `corpus-benchmark` command accepting one or more topic IDs, corpus path, source budget, Markdown output, and JSON-details output. It runs baseline and multi-agent against each selected topic and writes:

- `reports/corpus_benchmark_report.md`
- `reports/corpus_benchmark_details.json`

The Markdown report explains methodology, corpus integrity, metric definitions, per-topic results, aggregate trade-offs, and limitations.

## GitHub Actions

The existing manual workflow gains `corpus` mode in addition to `offline` and `live`.

- All modes run lint, format, mypy, and pytest.
- `live` keeps the existing Tavily/OpenAI benchmark.
- `corpus` validates `OPENAI_API_KEY` and `LANGSMITH_API_KEY`, verifies subset provenance and every committed payload checksum against the official parent package, runs the three-topic corpus benchmark, and uploads both corpus reports.
- No automatic trigger is added.

## Testing

TDD coverage includes:

- corpus checksum and topic lookup;
- canonical citation IDs and synthetic metadata;
- deterministic equal-budget retrieval;
- generalized citation parsing;
- Writer retry when coverage is below 80%;
- Writer failure after one inadequate correction;
- corpus metric calculations and transparent rubric proxy;
- Markdown/JSON report generation;
- CLI comparison wiring with injected fake LLMs where possible;
- CI policy remains manual-only.
