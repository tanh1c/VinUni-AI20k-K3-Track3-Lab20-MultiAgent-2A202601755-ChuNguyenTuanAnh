"""Tavily search client abstraction for ResearcherAgent."""

import json
import ssl
from collections.abc import Callable
from typing import Any, cast
from urllib.request import Request, urlopen

from multi_agent_research_lab.core.config import Settings, get_settings
from multi_agent_research_lab.core.errors import AgentExecutionError
from multi_agent_research_lab.core.schemas import SourceDocument
from multi_agent_research_lab.observability.tracing import maybe_traceable

SearchTransport = Callable[[str, bytes, dict[str, str], float], dict[str, Any]]


def _default_transport(
    url: str,
    body: bytes,
    headers: dict[str, str],
    timeout: float,
) -> dict[str, Any]:
    request = Request(url, data=body, headers=headers, method="POST")
    context = ssl.create_default_context()
    with urlopen(request, timeout=timeout, context=context) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise AgentExecutionError("Tavily returned a non-object JSON response")
    return cast(dict[str, Any], payload)


class SearchClient:
    """Small Tavily REST adapter with deterministic normalization."""

    endpoint = "https://api.tavily.com/search"

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transport: SearchTransport = _default_transport,
    ) -> None:
        self.settings = settings or get_settings()
        self._transport = transport

    @maybe_traceable("search.tavily")
    def search(self, query: str, max_results: int = 5) -> list[SourceDocument]:
        if not self.settings.tavily_api_key:
            raise AgentExecutionError("TAVILY_API_KEY is required for live search")
        limit = max(1, min(max_results, 20))
        body = json.dumps(
            {
                "query": query,
                "search_depth": "basic",
                "max_results": limit,
                "include_answer": False,
                "include_raw_content": False,
            }
        ).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.settings.tavily_api_key}",
            "Content-Type": "application/json",
        }
        try:
            payload = self._transport(
                self.endpoint,
                body,
                headers,
                float(self.settings.timeout_seconds),
            )
        except Exception as exc:
            raise AgentExecutionError(f"Tavily search failed: {exc}") from exc

        documents: list[SourceDocument] = []
        seen: set[str] = set()
        for raw in payload.get("results", []):
            if not isinstance(raw, dict):
                continue
            title = str(raw.get("title") or "Untitled source").strip()
            url = str(raw.get("url") or "").strip() or None
            snippet = str(raw.get("content") or raw.get("snippet") or "").strip()
            dedupe_key = (url or title).casefold()
            if not dedupe_key or dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            source_id = f"S{len(documents) + 1}"
            documents.append(
                SourceDocument(
                    title=title,
                    url=url,
                    snippet=snippet,
                    metadata={
                        "source_id": source_id,
                        "provider": "tavily",
                        "score": raw.get("score"),
                    },
                )
            )
            if len(documents) >= limit:
                break
        return documents
