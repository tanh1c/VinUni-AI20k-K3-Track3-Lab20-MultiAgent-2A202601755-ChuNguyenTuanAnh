"""Analyst agent: compare evidence and identify weak support."""

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.errors import ValidationError
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient
from multi_agent_research_lab.utils.citations import source_ids


class AnalystAgent(BaseAgent):
    name = "analyst"

    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient()

    def run(self, state: ResearchState) -> ResearchState:
        if not state.research_notes or not state.sources:
            raise ValidationError("Analyst requires sources and research_notes")
        valid_ids = ", ".join(f"[{source_id}]" for source_id in sorted(source_ids(state.sources)))
        response = self.llm.complete(
            (
                "You are the Analyst. Compare the evidence, identify major claims "
                "and disagreements, rate evidence strength, and explicitly flag weak support. "
                f"Preserve the exact canonical bracketed source IDs: {valid_ids}."
            ),
            f"Query: {state.request.query}\n\nResearch notes:\n{state.research_notes}",
        )
        state.analysis_notes = response.content
        state.add_usage(
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_usd=response.cost_usd,
        )
        state.agent_results.append(AgentResult(agent=AgentName.ANALYST, content=response.content))
        state.add_trace_event("agent.analyst", {"status": "completed"})
        return state
