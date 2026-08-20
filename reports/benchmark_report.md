# Benchmark Report

**Student:** Chu Nguyễn Tuấn Anh  
**MSSV:** 2A202601755

## 1. Live single-agent vs multi-agent benchmark

**Measured evidence:** GitHub Actions run `32335002667`, job `96322741178`, commit `eda395e2e3373f5617e3d4968981bdd939787d51` (2026-08-20).

| Run | Latency (s) | Cost (USD) | Quality /10 | Citation coverage | Failure rate | Notes |
|---|---:|---:|---:|---:|---:|---|
| baseline | 18.53 | 0.0019 | 7.3 | 10% | 0% | deterministic quality proxy; semantic quality should also be peer-reviewed |
| multi-agent | 52.40 | 0.0082 | 7.2 | 6% | 0% | deterministic quality proxy; semantic quality should also be peer-reviewed |

Both approaches receive the same query and retrieval budget. Latency is wall-clock time; cost is derived from provider token usage. The automated quality score is a transparent 0-10 proxy based on successful completion, source use, citation coverage, and absence of execution errors; it is not a teacher grade.

The live multi-agent run added `+33.87s` relative to the baseline. This illustrates the core trade-off: decomposition and verification add orchestration/token overhead, so multi-agent is justified only when the extra evidence handling or review quality is worth that cost.

## 2. Final official-corpus benchmark

**Measured evidence:** GitHub Actions run `32363603155`, job `96408254950`, commit `3ba21d4b6d1407f1ab50dcf481c069d70f05135a` (2026-08-20), artifact `lab20-official-corpus-benchmark` ID `9404722554`.

| Run | Avg latency (s) | Avg cost (USD) | Avg quality proxy /100 | Avg citation | Failure rate |
|---|---:|---:|---:|---:|---:|
| baseline | 46.21 | 0.0065 | 79.0 | 37% | 0% |
| multi-agent | 143.03 | 0.0328 | 85.2 | 33% | 0% |

Across all three representative corpus topics, the multi-agent pipeline improved the deterministic rubric-aligned quality proxy (`79.0 -> 85.2`) while remaining substantially slower and more expensive. Citation coverage was mixed rather than universally better, so the result does not claim that multi-agent is always superior.

## 3. Failure mode actually encountered and how it was fixed

During an earlier corpus run (`32359559858`), CI itself was green, but all three multi-agent benchmark cases ended with `failure_rate=100%`. The route stopped at Writer with the error:

`Writer output failed citation validation after one correction`

Root cause analysis found two coupled issues:

1. The Analyst prompt said `Preserve [S#] citations`, but the official corpus uses canonical IDs such as `[autogen]`, `[gaia]`, and `[T01-SYN-A]`.
2. Writer treated residual citation coverage below 80% as a hard execution failure after one correction attempt. That prevented a valid-but-imperfect draft from reaching the independent Critic stage.

The fix was deliberately bounded rather than weakening citation validity:

- Analyst now receives and preserves the exact canonical source IDs from retrieved evidence.
- Writer still performs at most one correction attempt.
- The correction prompt now includes the research notes and analysis again so the model has evidence context while repairing citations.
- Invented/invalid citation IDs remain a hard failure.
- If citation IDs are valid but coverage is still below the 80% target, Writer records the coverage and passes the draft to Critic, which independently returns `pass`, `warn`, or `fail`.

The final corpus run (`32363603155`) verified the fix: all three multi-agent cases completed `researcher -> analyst -> writer -> critic -> done`, with `errors=[]`, `0%` execution failure rate, and zero invalid citations across all six baseline/multi-agent runs.

## 4. Trace evidence

Public LangSmith trace:

https://smith.langchain.com/public/c30ff728-4cc9-43fa-8a7e-f086c932fd8c/r/01a01ef0-dfb2-7ea3-8569-4cea7dfe2f55?start_time=2026-08-20T11%3A31%3A37.522091Z

Machine-readable route evidence for the same final corpus suite is preserved in `reports/corpus_benchmark_details.json` and records the multi-agent route as `researcher -> analyst -> writer -> critic -> done` with no workflow errors.
