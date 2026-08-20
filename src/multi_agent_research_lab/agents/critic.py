"""Bonus critic agent for fact-checking and citation review."""

from typing import Literal

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.errors import ValidationError
from multi_agent_research_lab.core.schemas import AgentName, AgentResult, CriticReview
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient
from multi_agent_research_lab.utils.citations import citation_coverage, invalid_citation_ids
from multi_agent_research_lab.utils.evidence import source_prompt_block


class CriticAgent(BaseAgent):
    name = "critic"

    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient()

    def run(self, state: ResearchState) -> ResearchState:
        if not state.final_answer or not state.sources:
            raise ValidationError("Critic requires final_answer and sources")

        coverage, unsupported = citation_coverage(state.final_answer)
        invalid = invalid_citation_ids(state.final_answer, state.sources)
        source_context = "\n\n".join(source_prompt_block(source) for source in state.sources)
        response = self.llm.complete(
            (
                "You are the Critic. Fact-check the draft against the supplied evidence. Focus on "
                "unsupported claims, citation misuse, overclaiming, and hallucination risk. "
                "Do not rewrite it."
            ),
            (
                f"Draft:\n{state.final_answer}\n\nSources:\n{source_context}\n\n"
                f"Research notes:\n{state.research_notes}\n\nAnalysis:\n{state.analysis_notes}"
            ),
        )
        state.add_usage(
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_usd=response.cost_usd,
        )
        verdict: Literal["pass", "warn", "fail"]
        if invalid:
            verdict = "fail"
        elif coverage < 0.8 or unsupported:
            verdict = "warn"
        else:
            verdict = "pass"
        state.critic_review = CriticReview(
            citation_coverage=coverage,
            invalid_citations=invalid,
            unsupported_claims=unsupported,
            verdict=verdict,
            notes=response.content,
        )
        state.agent_results.append(
            AgentResult(
                agent=AgentName.CRITIC,
                content=response.content,
                metadata={"verdict": verdict, "citation_coverage": coverage},
            )
        )
        state.add_trace_event(
            "agent.critic",
            {
                "verdict": verdict,
                "citation_coverage": coverage,
                "invalid_citations": invalid,
            },
        )
        return state
