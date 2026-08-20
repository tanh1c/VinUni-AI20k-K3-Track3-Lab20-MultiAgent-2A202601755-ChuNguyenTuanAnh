from multi_agent_research_lab.agents.supervisor import SupervisorAgent
from multi_agent_research_lab.core.config import Settings
from multi_agent_research_lab.core.schemas import CriticReview, ResearchQuery, SourceDocument
from multi_agent_research_lab.core.state import ResearchState


def _state() -> ResearchState:
    return ResearchState(request=ResearchQuery(query="Explain multi-agent systems"))


def test_supervisor_routes_through_missing_stages() -> None:
    supervisor = SupervisorAgent(settings=Settings(MAX_ITERATIONS=10))
    state = _state()

    supervisor.run(state)
    assert state.route_history[-1] == "researcher"

    state.sources = [
        SourceDocument(title="Source", url="https://example.com", snippet="Evidence")
    ]
    state.research_notes = "[S1] Evidence"
    supervisor.run(state)
    assert state.route_history[-1] == "analyst"

    state.analysis_notes = "Analysis"
    supervisor.run(state)
    assert state.route_history[-1] == "writer"

    state.final_answer = "Answer [S1]"
    supervisor.run(state)
    assert state.route_history[-1] == "critic"

    state.critic_review = CriticReview(citation_coverage=1.0, verdict="pass")
    supervisor.run(state)
    assert state.route_history[-1] == "done"


def test_supervisor_stops_at_iteration_limit() -> None:
    state = _state()
    state.iteration = 2
    supervisor = SupervisorAgent(settings=Settings(MAX_ITERATIONS=2))

    supervisor.run(state)

    assert state.route_history[-1] == "done"
    assert "max_iterations" in state.errors[-1]


def test_state_accumulates_usage() -> None:
    state = _state()
    state.add_usage(input_tokens=100, output_tokens=50, cost_usd=0.012)
    state.add_usage(input_tokens=20, output_tokens=5, cost_usd=None)

    assert state.input_tokens == 120
    assert state.output_tokens == 55
    assert state.estimated_cost_usd == 0.012
