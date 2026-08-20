from types import SimpleNamespace

import pytest

from multi_agent_research_lab.core.config import Settings
from multi_agent_research_lab.core.errors import AgentExecutionError
from multi_agent_research_lab.services.llm_client import LLMClient


class FakeResponses:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeOpenAI:
    def __init__(self, outcomes: list[object]) -> None:
        self.responses = FakeResponses(outcomes)


def response(text: str = "ok", input_tokens: int = 100, output_tokens: int = 20) -> object:
    return SimpleNamespace(
        output_text=text,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def test_llm_requires_api_key_without_injected_client() -> None:
    client = LLMClient(settings=Settings(OPENAI_API_KEY=None))
    with pytest.raises(AgentExecutionError, match="OPENAI_API_KEY"):
        client.complete("system", "user")


def test_llm_extracts_text_tokens_and_cost() -> None:
    fake = FakeOpenAI([response("answer", 200, 40)])
    settings = Settings(
        OPENAI_API_KEY="test-key",
        OPENAI_MODEL="gpt-5.6-luna",
        PROVIDER_MAX_RETRIES=3,
    )
    client = LLMClient(settings=settings, client=fake, sleep_fn=lambda _: None)

    result = client.complete("system prompt", "user prompt")

    assert result.content == "answer"
    assert result.input_tokens == 200
    assert result.output_tokens == 40
    assert result.cost_usd == pytest.approx((200 * 0.20 + 40 * 1.20) / 1_000_000)
    assert fake.responses.calls[0]["instructions"] == "system prompt"
    assert fake.responses.calls[0]["input"] == "user prompt"


def test_llm_retries_transient_failures() -> None:
    fake = FakeOpenAI([RuntimeError("temporary"), response()])
    client = LLMClient(
        settings=Settings(OPENAI_API_KEY="test-key", PROVIDER_MAX_RETRIES=2),
        client=fake,
        sleep_fn=lambda _: None,
    )

    result = client.complete("system", "user")

    assert result.content == "ok"
    assert len(fake.responses.calls) == 2
