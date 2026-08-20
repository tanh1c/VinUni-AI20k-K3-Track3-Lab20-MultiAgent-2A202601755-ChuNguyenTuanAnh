# Lab 20: Multi-Agent Research System

## Student information

- **Student:** Chu Nguyễn Tuấn Anh
- **MSSV:** 2A202601755

Hoàn thiện bài lab **Multi-Agent Systems** với hệ thống research gồm **Supervisor + Researcher + Analyst + Writer + Critic**, LangGraph orchestration, Tavily retrieval, official offline research corpus, OpenAI Responses API, LangSmith tracing và benchmark single-agent vs multi-agent.

## Submission evidence

- Final verified GitHub Actions corpus run: `32363603155` / job `96408254950`
- Verified implementation commit: `3ba21d4b6d1407f1ab50dcf481c069d70f05135a`
- Final CI: Ruff lint pass, Ruff format pass, mypy pass, **54 tests passed**
- Public LangSmith trace: https://smith.langchain.com/public/c30ff728-4cc9-43fa-8a7e-f086c932fd8c/r/01a01ef0-dfb2-7ea3-8569-4cea7dfe2f55?start_time=2026-08-20T11%3A31%3A37.522091Z
- Required benchmark report: [`reports/benchmark_report.md`](reports/benchmark_report.md)
- Trace evidence summary: [`reports/trace_evidence.md`](reports/trace_evidence.md)
- Exit ticket: [`reports/exit_ticket.md`](reports/exit_ticket.md)

## Architecture

```text
User Query
   |
   v
Supervisor (deterministic router)
   |----> Researcher -> sources + research_notes
   |----> Analyst ----> analysis_notes
   |----> Writer -----> final_answer + citation guard
   |----> Critic -----> independent citation/fact-check review   [BONUS]
   |
   v
Done -> trace + token/cost accounting + benchmark reports
```

Mỗi agent có responsibility riêng và mọi handoff đều đi qua `ResearchState`, giúp trace/debug toàn bộ pipeline mà không phụ thuộc hidden memory giữa agent.

Researcher dùng cùng một `SearchProvider` interface cho hai evidence modes:

```text
Researcher / baseline
        |
        +-- SearchClient       -> Tavily live research
        |
        +-- CorpusSearchClient -> fixed official corpus, no web search
```

## Rubric coverage

| Tiêu chí | Evidence trong implementation |
|---|---|
| Role clarity | Supervisor, Researcher, Analyst, Writer, Critic tách nhiệm vụ rõ ràng |
| State design | Sources, research/analysis notes, final answer, critic review, usage, trace, errors |
| Failure guard | Max iterations, provider timeout, bounded retry, citation validation, safe-stop |
| Benchmark | Live + fixed-corpus comparisons với quality, latency, cost, citations, failure rate |
| Trace explanation | Local structured trace + public LangSmith trace evidence |
| Bonus | `CriticAgent` kiểm invalid citations, unsupported claims và hallucination risk |
| Reproducibility | Official-corpus subset được provenance-verified và dùng cùng evidence budget cho hai kiến trúc |

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev,llm]"
cp .env.example .env
```

Điền tối thiểu cho live research:

```bash
OPENAI_API_KEY=...
TAVILY_API_KEY=...
LANGSMITH_API_KEY=...
```

Corpus benchmark không gọi Tavily, nên chỉ cần OpenAI + LangSmith khi chạy qua GitHub Actions. Default model là `gpt-5.6-luna`; có thể đổi bằng `OPENAI_MODEL`.

## Run

### Single-agent baseline

```bash
python -m multi_agent_research_lab.cli baseline \
  --query "Research GraphRAG state-of-the-art and write a concise summary"
```

### Multi-agent workflow

```bash
python -m multi_agent_research_lab.cli multi-agent \
  --query "Research GraphRAG state-of-the-art and write a concise summary"
```

Expected route history:

```text
researcher -> analyst -> writer -> critic -> done
```

### Live benchmark

```bash
python -m multi_agent_research_lab.cli benchmark \
  --query "Compare single-agent and multi-agent research systems and explain when each is preferable" \
  --output reports/benchmark_report.md
```

### Official offline-corpus benchmark

School corpus v2 gồm 30 self-contained research topics. Repo public chỉ commit representation của ba topic benchmark đại diện (`AIAGENT-01`, `AIAGENT-12`, `AIAGENT-13`) cùng manifest/schema và provenance tại:

```text
data/offline_corpus_subset/
```

Để tránh binary corruption khi truyền qua GitHub connector, byte-exact topic JSON được đóng gói theo pipeline:

```text
official JSON -> deterministic gzip (mtime=0) -> base64 ASCII -> ordered text chunks
```

Loader nối các chunk, base64-decode, gzip-decompress và xác minh SHA-256 của decoded original JSON trước khi load.

Full course package không được redistribute trong repo. `PROVENANCE.json` khóa subset vào parent package bằng SHA-256:

```text
276117a25e178937bfb20b08f944450f5278fd0490a9c5cdebed364fa24658bf
```

Chạy representative suite:

```bash
python -m multi_agent_research_lab.cli corpus-benchmark \
  --topics "AIAGENT-01,AIAGENT-12,AIAGENT-13" \
  --source-budget 8 \
  --output reports/corpus_benchmark_report.md \
  --details reports/corpus_benchmark_details.json
```

Corpus mode **không dùng Tavily/browser search**. Baseline và multi-agent nhận cùng topic, cùng source budget và cùng deterministic retrieval policy. Canonical citations như `[autogen]`, `[A01]`, `[T01-SYN-A]` được giữ nguyên; evidence có `is_synthetic=true` phải được trình bày là synthetic benchmark evidence.

Final measured aggregate:

| Run | Avg proxy /100 | Avg citation | Avg latency (s) | Avg cost (USD) | Failure |
|---|---:|---:|---:|---:|---:|
| baseline | 79.0 | 37% | 46.21 | 0.0065 | 0% |
| multi-agent | 85.2 | 33% | 143.03 | 0.0328 | 0% |

Chi tiết đầy đủ nằm trong [`reports/corpus_benchmark_report.md`](reports/corpus_benchmark_report.md) và [`reports/corpus_benchmark_details.json`](reports/corpus_benchmark_details.json). Proxy là metric deterministic rubric-aligned, **không phải điểm giảng viên hoặc semantic ground truth**.

## Citation and evidence guardrails

- `MAX_ITERATIONS` chặn workflow lặp vô hạn.
- `TIMEOUT_SECONDS` giới hạn OpenAI/Tavily calls.
- `PROVIDER_MAX_RETRIES` retry có giới hạn cho lỗi transient.
- Provider/search failure được ghi vào `ResearchState.errors`, sau đó Supervisor safe-stop.
- Analyst giữ nguyên exact canonical source IDs từ retrieved evidence.
- Writer chỉ cho phép citation IDs có trong retrieved sources.
- Writer **target >=80% material-sentence citation coverage** và có tối đa một correction attempt.
- Invalid/invented citation IDs sau correction vẫn hard-fail.
- Nếu IDs hợp lệ nhưng coverage còn dưới target, Writer ghi quality signal và chuyển draft sang Critic thay vì giết graph.
- Critic kiểm citation coverage, invalid citations và unsupported claims độc lập với Writer.
- Corpus loader xác minh parent-package SHA-256 và từng committed payload hash trước khi benchmark.

## Tests

Default tests hoàn toàn offline: không gọi OpenAI, Tavily hoặc LangSmith.

```bash
make lint
make test
make typecheck
```

Final verified Actions run trên implementation commit cho kết quả:

```text
ruff check src tests              PASS
ruff format --check src tests     PASS (50 files already formatted)
mypy src                          PASS (33 source files)
pytest                            PASS (54 passed)
```

Bộ test bao phủ routing, state/usage accounting, provider adapters, retries, Tavily retrieval, corpus integrity/retrieval, canonical citations, Writer correction/validation, Critic bonus, workflow end-to-end, benchmark/report, corpus evaluator/report và manual-only CI policy.

## Tracing

Local structured trace luôn được lưu trong `ResearchState.trace`. Khi có `LANGSMITH_API_KEY`, workflow/provider entry points được instrument bằng LangSmith.

- Live project: `multi-agent-research-lab`
- Corpus project: `multi-agent-research-lab-corpus`
- Public submission trace: https://smith.langchain.com/public/c30ff728-4cc9-43fa-8a7e-f086c932fd8c/r/01a01ef0-dfb2-7ea3-8569-4cea7dfe2f55?start_time=2026-08-20T11%3A31%3A37.522091Z

Machine-readable final corpus evidence records all three multi-agent routes as:

```text
researcher -> analyst -> writer -> critic -> done
```

with `errors=[]`, zero invalid citations, and `failure_rate=0%`.

## GitHub Actions — manual only

Workflow `.github/workflows/ci.yml` chỉ dùng:

```yaml
on:
  workflow_dispatch:
```

Không có trigger `push` hoặc `pull_request`.

Manual modes:

- `offline`: install + Ruff lint/format + mypy + pytest.
- `live`: offline gate, then Tavily/OpenAI benchmark + LangSmith tracing.
- `corpus`: offline gate, verify corpus provenance, run AIAGENT-01/12/13 with fixed corpus + OpenAI + LangSmith, upload Markdown + JSON evidence.

## Submission artefacts

1. **GitHub repo** — completed implementation; `make lint` + `make test` equivalent gates pass; `StudentTodoError` is not used by the main execution path.
2. **Trace evidence** — public LangSmith trace above and [`reports/trace_evidence.md`](reports/trace_evidence.md).
3. **`reports/benchmark_report.md`** — live and official-corpus single vs multi-agent metrics plus the actual failure mode and implemented fix.
4. **Exit ticket** — answered in [`reports/exit_ticket.md`](reports/exit_ticket.md) and mirrored in `docs/lab_guide.md`.

## Project structure

```text
src/multi_agent_research_lab/
├── agents/
│   ├── supervisor.py
│   ├── researcher.py
│   ├── analyst.py
│   ├── writer.py
│   └── critic.py
├── core/
├── graph/
├── services/
│   ├── search_client.py
│   └── corpus_client.py
├── evaluation/
│   ├── benchmark.py
│   ├── corpus.py
│   └── corpus_report.py
├── observability/
└── cli.py

data/
└── offline_corpus_subset/
    ├── PROVENANCE.json
    ├── README.md
    ├── SCHEMA.json
    ├── manifest.csv
    └── topics/
        ├── 01_...json.gz.b64.part01
        ├── 01_...json.gz.b64.part02
        ├── 12_...json.gz.b64.part01
        ├── 12_...json.gz.b64.part02
        ├── 13_...json.gz.b64.part01
        └── 13_...json.gz.b64.part02
```

## References

- Anthropic: Building effective agents
- OpenAI API model/orchestration documentation
- LangGraph documentation
- LangSmith tracing documentation
- Tavily Search API documentation
- VinUniversity AI Agent Offline Research Corpus Benchmark v2 (provided course asset)
