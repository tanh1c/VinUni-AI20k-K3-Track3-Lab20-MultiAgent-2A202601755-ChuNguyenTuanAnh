# Official Offline Corpus Benchmark

Corpus SHA-256: `276117a25e178937bfb20b08f944450f5278fd0490a9c5cdebed364fa24658bf`

All quality values below are a transparent rubric-aligned proxy, not a teacher grade or semantic ground truth. Both architectures receive the same fixed corpus topic and source budget; no Tavily/browser search is used in this benchmark.

## Per-topic results

| Topic | Run | Latency (s) | Cost (USD) | Proxy /100 | Citation | Invalid | Sources | Public | Synthetic | Sections | Targets | Failure |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| AIAGENT-01 | baseline | 48.68 | 0.0067 | 80.2 | 46% | 0 | 8 | 6 | 2 | 100% | yes | 0% |
| AIAGENT-01 | multi-agent | 144.40 | 0.0338 | 85.9 | 36% | 0 | 8 | 6 | 2 | 80% | yes | 0% |
| AIAGENT-12 | baseline | 52.18 | 0.0068 | 78.3 | 24% | 0 | 8 | 6 | 2 | 100% | yes | 0% |
| AIAGENT-12 | multi-agent | 140.02 | 0.0314 | 83.6 | 21% | 0 | 8 | 6 | 2 | 80% | yes | 0% |
| AIAGENT-13 | baseline | 37.78 | 0.0060 | 78.4 | 41% | 0 | 8 | 6 | 2 | 100% | yes | 0% |
| AIAGENT-13 | multi-agent | 144.67 | 0.0331 | 86.1 | 44% | 0 | 8 | 6 | 2 | 80% | yes | 0% |

## Aggregate trade-off

| Run | Avg proxy /100 | Avg citation | Avg latency (s) | Avg cost (USD) |
|---|---:|---:|---:|---:|
| baseline | 79.0 | 37% | 46.21 | 0.0065 |
| multi-agent | 85.2 | 33% | 143.03 | 0.0328 |

## Metric interpretation

The proxy combines corpus rubric weights with deterministic signals for report structure, source quality, citation validity/coverage, conflict/counterargument handling, technical coverage, evaluation design, governance, coordination evidence, and uncertainty language. It intentionally does not claim semantic entailment.

Multi-agent execution is justified only when improvements in evidence handling, verification, or rubric alignment outweigh added latency and token cost. A strong single-agent baseline can remain preferable for narrow tasks.
