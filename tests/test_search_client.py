import json

import pytest

from multi_agent_research_lab.core.config import Settings
from multi_agent_research_lab.core.errors import AgentExecutionError
from multi_agent_research_lab.services.search_client import SearchClient


def test_search_requires_tavily_key() -> None:
    client = SearchClient(settings=Settings(TAVILY_API_KEY=None))
    with pytest.raises(AgentExecutionError, match="TAVILY_API_KEY"):
        client.search("multi agent research")


def test_search_sends_bounded_payload_and_deduplicates() -> None:
    captured: dict[str, object] = {}

    def transport(
        url: str,
        body: bytes,
        headers: dict[str, str],
        timeout: float,
    ) -> dict[str, object]:
        captured.update(url=url, body=body, headers=headers, timeout=timeout)
        return {
            "results": [
                {"title": "A", "url": "https://a.test", "content": "alpha", "score": 0.9},
                {
                    "title": "A duplicate",
                    "url": "https://a.test",
                    "content": "dup",
                    "score": 0.8,
                },
                {"title": "B", "url": "https://b.test", "content": "beta", "score": 0.7},
            ]
        }

    client = SearchClient(
        settings=Settings(TAVILY_API_KEY="tvly-test", TIMEOUT_SECONDS=15),
        transport=transport,
    )

    results = client.search("multi agent research", max_results=2)

    body = captured["body"]
    headers = captured["headers"]
    assert isinstance(body, bytes)
    assert isinstance(headers, dict)
    payload = json.loads(body)
    assert captured["url"] == "https://api.tavily.com/search"
    assert headers["Authorization"] == "Bearer tvly-test"
    assert payload["search_depth"] == "basic"
    assert payload["max_results"] == 2
    assert len(results) == 2
    assert results[0].metadata["source_id"] == "S1"
    assert results[1].metadata["source_id"] == "S2"
