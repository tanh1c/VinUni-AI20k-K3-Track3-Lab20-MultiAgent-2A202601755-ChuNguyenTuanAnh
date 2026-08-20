"""Writer agent: synthesis with validated source citations."""

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.errors import ValidationError
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient, LLMResponse
from multi_agent_research_lab.utils.citations import citation_ids, invalid_citation_ids, source_ids


class WriterAgent(BaseAgent):
    name = "writer"

    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient()

    @staticmethod
    def _is_valid(response: LLMResponse, state: ResearchState) -> bool:
        return bool(citation_ids(response.content)) and not invalid_citation_ids(
            response.content,
            state.sources,
        )

    @staticmethod
    def _record_usage(state: ResearchState, response: LLMResponse) -> None:
        state.add_usage(
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_usd=response.cost_usd,
        )

    def run(self, state: ResearchState) -> ResearchState:
        if not state.analysis_notes or not state.sources:
            raise ValidationError("Writer requires analysis_notes and sources")
        valid_ids = ", ".join(sorted(source_ids(state.sources)))
        system = (
            "You are the Writer. Produce a clear, balanced answer for the requested audience using "
            "only the supplied research and analysis. Cite material factual claims inline using the "
            f"allowed source identifiers only: {valid_ids}."
        )
        user = (
            f"Query: {state.request.query}\nAudience: {state.request.audience}\n\n"
            f"Research notes:\n{state.research_notes}\n\nAnalysis:\n{state.analysis_notes}"
        )
        response = self.llm.complete(system, user)
        self._record_usage(state, response)
        if not self._is_valid(response, state):
            correction = self.llm.complete(
                system,
                (
                    "Rewrite this draft so every material factual claim uses only valid citations "
                    f"({valid_ids}) and no invented citation IDs appear.\n\nDraft:\n{response.content}"
                ),
            )
            self._record_usage(state, correction)
            response = correction
        if not self._is_valid(response, state):
            raise ValidationError("Writer output failed citation validation after one correction")

        state.final_answer = response.content
        state.agent_results.append(AgentResult(agent=AgentName.WRITER, content=response.content))
        state.add_trace_event("agent.writer", {"citation_ids": citation_ids(response.content)})
        return state
