# Lab 20 Exit Ticket

**Student:** Chu Nguyễn Tuấn Anh  
**MSSV:** 2A202601755

## 1. Khi nào nên dùng multi-agent? Vì sao?

Nên dùng multi-agent khi bài toán có nhiều giai đoạn khác nhau về trách nhiệm và tiêu chí kiểm chứng, ví dụ nghiên cứu cần tìm nguồn, phân tích bằng chứng, tổng hợp câu trả lời và fact-check độc lập. Việc tách Researcher, Analyst, Writer và Critic giúp mỗi bước có input/output rõ ràng, dễ trace, dễ đánh giá failure mode và cho phép thêm guardrail riêng. Lợi ích này đáng với chi phí/latency tăng thêm khi chất lượng bằng chứng và khả năng kiểm chứng quan trọng.

## 2. Khi nào không nên dùng multi-agent? Vì sao?

Không nên dùng multi-agent cho câu hỏi đơn giản, tác vụ latency-sensitive hoặc trường hợp một prompt + một tool call đã đủ. Khi đó orchestration, nhiều lượt LLM và handoff chỉ tăng token cost, latency và số điểm có thể lỗi mà không tạo thêm chất lượng tương xứng. Single-agent là lựa chọn tốt hơn nếu decomposition không tạo ra trách nhiệm độc lập hoặc không có intermediate artifact cần kiểm tra.
