"""Provider-agnostic LLM client with retry, timeout, and usage accounting."""

from collections.abc import Callable
from dataclasses import dataclass
from time import sleep
from typing import Any

from multi_agent_research_lab.core.config import Settings, get_settings
from multi_agent_research_lab.core.errors import AgentExecutionError
from multi_agent_research_lab.observability.tracing import maybe_traceable

_MODEL_PRICING_PER_1M: dict[str, tuple[float, float]] = {
    "gpt-5.6-luna": (0.20, 1.20),
    "gpt-5.6-terra": (2.00, 12.00),
    "gpt-5.6-sol": (5.00, 30.00),
    "gpt-5.4-mini": (0.75, 4.50),
}


@dataclass(frozen=True)
class LLMResponse:
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


class LLMClient:
    """Thin OpenAI Responses API adapter used by all agents."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: Any | None = None,
        sleep_fn: Callable[[float], None] = sleep,
    ) -> None:
        self.settings = settings or get_settings()
        self._client = client
        self._sleep = sleep_fn

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self.settings.openai_api_key:
            raise AgentExecutionError("OPENAI_API_KEY is required for live LLM calls")
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - exercised in minimal installs
            raise AgentExecutionError("Install the 'llm' extra to use OpenAI") from exc
        self._client = OpenAI(
            api_key=self.settings.openai_api_key,
            timeout=float(self.settings.timeout_seconds),
            max_retries=0,
        )
        return self._client

    def _estimate_cost(self, input_tokens: int | None, output_tokens: int | None) -> float | None:
        if input_tokens is None and output_tokens is None:
            return None
        if (
            self.settings.openai_input_cost_per_1m is not None
            and self.settings.openai_output_cost_per_1m is not None
        ):
            input_price = self.settings.openai_input_cost_per_1m
            output_price = self.settings.openai_output_cost_per_1m
        else:
            pricing = _MODEL_PRICING_PER_1M.get(self.settings.openai_model)
            if pricing is None:
                return None
            input_price, output_price = pricing
        return ((input_tokens or 0) * input_price + (output_tokens or 0) * output_price) / 1_000_000

    @staticmethod
    def _retryable(exc: Exception) -> bool:
        status = getattr(exc, "status_code", None)
        return status not in {400, 401, 403, 404, 422}

    @maybe_traceable("llm.complete")
    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """Return an OpenAI completion after bounded retries."""

        client = self._get_client()
        last_error: Exception | None = None
        for attempt in range(self.settings.provider_max_retries):
            try:
                response = client.responses.create(
                    model=self.settings.openai_model,
                    instructions=system_prompt,
                    input=user_prompt,
                )
                usage = getattr(response, "usage", None)
                input_tokens = getattr(usage, "input_tokens", None)
                output_tokens = getattr(usage, "output_tokens", None)
                content = str(getattr(response, "output_text", "")).strip()
                if not content:
                    raise AgentExecutionError("OpenAI returned an empty response")
                return LLMResponse(
                    content=content,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_usd=self._estimate_cost(input_tokens, output_tokens),
                )
            except AgentExecutionError:
                raise
            except Exception as exc:
                last_error = exc
                if not self._retryable(exc) or attempt + 1 >= self.settings.provider_max_retries:
                    break
                self._sleep(min(2**attempt, 4))
        raise AgentExecutionError(f"LLM request failed after retries: {last_error}") from last_error
