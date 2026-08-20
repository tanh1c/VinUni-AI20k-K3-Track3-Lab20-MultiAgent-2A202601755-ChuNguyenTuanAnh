# Lab Guide: Multi-Agent Research System

## Scenario

Bạn cần xây dựng một research assistant có thể nhận câu hỏi dài, tìm thông tin, phân tích và viết câu trả lời cuối cùng. Lab yêu cầu so sánh hai cách làm:

1. **Single-agent baseline**: một agent làm toàn bộ.
2. **Multi-agent workflow**: Supervisor điều phối Researcher, Analyst, Writer.

## Quy tắc quan trọng

- Không thêm agent nếu không có lý do rõ ràng.
- Mỗi agent phải có responsibility riêng.
- Shared state phải đủ rõ để debug.
- Phải có trace hoặc log cho từng bước.
- Phải benchmark, không chỉ nhìn output bằng cảm tính.

## Milestone 1: Baseline

File gợi ý:

- `src/multi_agent_research_lab/cli.py`
- `src/multi_agent_research_lab/services/llm_client.py`

TODO(student): thay baseline placeholder bằng một call LLM thật.

## Milestone 2: Supervisor

File gợi ý:

- `src/multi_agent_research_lab/agents/supervisor.py`
- `src/multi_agent_research_lab/graph/workflow.py`

TODO(student): implement routing policy.

Gợi ý câu hỏi thiết kế:

- Khi nào gọi Researcher?
- Khi nào gọi Analyst?
- Khi nào gọi Writer?
- Khi nào stop?
- Nếu agent fail thì retry hay fallback?

## Milestone 3: Worker agents

File gợi ý:

- `src/multi_agent_research_lab/agents/researcher.py`
- `src/multi_agent_research_lab/agents/analyst.py`
- `src/multi_agent_research_lab/agents/writer.py`

TODO(student): implement từng worker.

## Milestone 4: Trace và benchmark

File gợi ý:

- `src/multi_agent_research_lab/observability/tracing.py`
- `src/multi_agent_research_lab/evaluation/benchmark.py`
- `src/multi_agent_research_lab/evaluation/report.py`

Benchmark tối thiểu:

| Metric | Cách đo gợi ý |
|---|---|
| Latency | wall-clock time |
| Cost | token usage hoặc provider usage |
| Quality | rubric 0-10 do peer review |
| Citation coverage | số claims có source / tổng claims chính |
| Failure rate | số query fail / tổng query |

## Troubleshooting

### macOS: lỗi SSL certificate khi gọi API qua HTTPS (Tavily, OpenAI, ...)

Triệu chứng: khi implement `SearchClient` (hoặc bất kỳ HTTPS call nào) trên macOS, bạn có thể gặp lỗi kiểu:

```text
ssl.SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed:
unable to get local issuer certificate
```

Nguyên nhân: Python cài từ python.org trên macOS **không dùng** certificate store của hệ điều hành, nên không tìm thấy CA bundle hợp lệ. Đây là lỗi môi trường, **không phải** do API key sai.

Cách khắc phục (chọn 1 trong 3):

1. Chạy script cài certificate đi kèm Python:

   ```bash
   /Applications/Python\ 3.12/Install\ Certificates.command
   ```

2. Dùng `certifi` trong code.

3. Set biến môi trường trỏ tới CA bundle của certifi:

   ```bash
   export SSL_CERT_FILE=$(python -m certifi)
   ```

## Exit ticket

Mỗi nhóm trả lời 2 câu:

1. Case nào nên dùng multi-agent? Vì sao?
2. Case nào không nên dùng multi-agent? Vì sao?

### Submitted answers — Chu Nguyễn Tuấn Anh (2A202601755)

**1. Khi nào nên dùng multi-agent? Vì sao?**

Nên dùng multi-agent khi bài toán có nhiều giai đoạn khác nhau về trách nhiệm và tiêu chí kiểm chứng, ví dụ nghiên cứu cần tìm nguồn, phân tích bằng chứng, tổng hợp câu trả lời và fact-check độc lập. Việc tách Researcher, Analyst, Writer và Critic giúp mỗi bước có input/output rõ ràng, dễ trace, dễ đánh giá failure mode và cho phép thêm guardrail riêng. Lợi ích này đáng với chi phí/latency tăng thêm khi chất lượng bằng chứng và khả năng kiểm chứng quan trọng.

**2. Khi nào không nên dùng multi-agent? Vì sao?**

Không nên dùng multi-agent cho câu hỏi đơn giản, tác vụ latency-sensitive hoặc trường hợp một prompt + một tool call đã đủ. Khi đó orchestration, nhiều lượt LLM và handoff chỉ tăng token cost, latency và số điểm có thể lỗi mà không tạo thêm chất lượng tương xứng. Single-agent là lựa chọn tốt hơn nếu decomposition không tạo ra trách nhiệm độc lập hoặc không có intermediate artifact cần kiểm tra.

Bản riêng để grader dễ mở: [`../reports/exit_ticket.md`](../reports/exit_ticket.md).
