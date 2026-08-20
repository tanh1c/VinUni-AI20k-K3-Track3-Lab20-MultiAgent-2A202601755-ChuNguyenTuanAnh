"""Researcher agent: retrieval plus source-grounded notes."""

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.errors import AgentExecutionError
from multi_agent_research_lab.core.schemas import AgentName, AgentResult, SourceDocument
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient
from multi_agent_research_lab.services.search_client import SearchClient, SearchProvider
from multi_agent_research_lab.utils.evidence import source_prompt_block


class ResearcherAgent(BaseAgent):
    name = "researcher"

    def __init__(self, llm: LLMClient | None = None, search: SearchProvider | None = None) -> None:
        self.llm = llm or LLMClient()
        self.search = search or SearchClient()

    @staticmethod
    def _normalize_sources(sources: list[SourceDocument]) -> list[SourceDocument]:
        normalized: list[SourceDocument] = []
        seen: set[str] = set()
        for source in sources:
            key = (source.url or source.title).casefold()
            if key in seen:
                continue
            seen.add(key)
            copy = source.model_copy(deep=True)
            copy.metadata.setdefault("source_id", f"S{len(normalized) + 1}")
            normalized.append(copy)
        return normalized

    def run(self, state: ResearchState) -> ResearchState:
        sources = self._normalize_sources(
            self.search.search(state.request.query, max_results=state.request.max_sources)
        )
        if not sources:
            raise AgentExecutionError("Researcher found no usable sources")

        source_context = "\n\n".join(source_prompt_block(source) for source in sources)
        response = self.llm.complete(
            (
                "You are the Researcher. Extract concise factual research notes only from the "
                "supplied sources. Cite every factual bullet with its exact bracketed "
                "source identifier. "
                "Do not invent facts."
            ),
            f"Query: {state.request.query}\n\nSources:\n{source_context}",
        )
        state.sources = sources
        state.research_notes = response.content
        state.add_usage(
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_usd=response.cost_usd,
        )
        state.agent_results.append(
            AgentResult(
                agent=AgentName.RESEARCHER,
                content=response.content,
                metadata={"source_count": len(sources)},
            )
        )
        state.add_trace_event("agent.researcher", {"source_count": len(sources)})
        return state
