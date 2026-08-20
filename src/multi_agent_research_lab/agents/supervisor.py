"""Deterministic supervisor/router."""

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.config import Settings, get_settings
from multi_agent_research_lab.core.state import ResearchState


class SupervisorAgent(BaseAgent):
    """Route according to which required shared-state artifact is still missing."""

    name = "supervisor"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def run(self, state: ResearchState) -> ResearchState:
        if state.iteration >= self.settings.max_iterations:
            route = "done"
            state.errors.append(
                f"max_iterations reached ({self.settings.max_iterations}); workflow stopped safely"
            )
        elif state.errors:
            route = "done"
        elif not state.sources or not state.research_notes:
            route = "researcher"
        elif not state.analysis_notes:
            route = "analyst"
        elif not state.final_answer:
            route = "writer"
        elif state.critic_review is None:
            route = "critic"
        else:
            route = "done"

        state.record_route(route)
        state.add_trace_event(
            "supervisor.route",
            {"next": route, "iteration": state.iteration},
        )
        return state
