"""LangGraph orchestration for the research workflow."""

from collections.abc import Callable
from typing import Any, Protocol, cast

from multi_agent_research_lab.agents.analyst import AnalystAgent
from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.agents.critic import CriticAgent
from multi_agent_research_lab.agents.researcher import ResearcherAgent
from multi_agent_research_lab.agents.supervisor import SupervisorAgent
from multi_agent_research_lab.agents.writer import WriterAgent
from multi_agent_research_lab.core.config import Settings, get_settings
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.observability.tracing import maybe_traceable
from multi_agent_research_lab.services.llm_client import LLMClient
from multi_agent_research_lab.services.search_client import SearchClient


class GraphRunner(Protocol):
    def invoke(
        self,
        state: Any,
        config: dict[str, Any] | None = None,
    ) -> Any: ...


class _FallbackGraph:
    """Offline executor used only when the optional LangGraph dependency is absent."""

    def __init__(self, workflow: "MultiAgentWorkflow") -> None:
        self.workflow = workflow

    def invoke(
        self,
        state: ResearchState | dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> ResearchState:
        del config
        model = state if isinstance(state, ResearchState) else ResearchState.model_validate(state)
        return self.workflow._run_fallback(model)


class MultiAgentWorkflow:
    """Build and execute Supervisor -> workers -> Critic with bounded routing."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        llm: LLMClient | None = None,
        search: SearchClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        shared_llm = llm or LLMClient(self.settings)
        shared_search = search or SearchClient(self.settings)
        self.supervisor = SupervisorAgent(self.settings)
        self.researcher = ResearcherAgent(shared_llm, shared_search)
        self.analyst = AnalystAgent(shared_llm)
        self.writer = WriterAgent(shared_llm)
        self.critic = CriticAgent(shared_llm)
        self.workers: dict[str, BaseAgent] = {
            "researcher": self.researcher,
            "analyst": self.analyst,
            "writer": self.writer,
            "critic": self.critic,
        }

    @staticmethod
    def _coerce_state(state: ResearchState | dict[str, Any]) -> ResearchState:
        return state if isinstance(state, ResearchState) else ResearchState.model_validate(state)

    def _run_agent(self, name: str, state: ResearchState) -> ResearchState:
        try:
            return self.workers[name].run(state)
        except Exception as exc:
            state.errors.append(f"{name} failed: {exc}")
            state.add_trace_event("workflow.error", {"agent": name, "error": str(exc)})
            return state

    def _supervisor_node(self, raw_state: ResearchState | dict[str, Any]) -> dict[str, Any]:
        state = self._coerce_state(raw_state)
        return self.supervisor.run(state).model_dump()

    def _worker_node(
        self,
        name: str,
    ) -> Callable[[ResearchState | dict[str, Any]], dict[str, Any]]:
        def node(raw_state: ResearchState | dict[str, Any]) -> dict[str, Any]:
            state = self._coerce_state(raw_state)
            return self._run_agent(name, state).model_dump()

        return node

    @staticmethod
    def _next_route(raw_state: ResearchState | dict[str, Any]) -> str:
        state = MultiAgentWorkflow._coerce_state(raw_state)
        return state.route_history[-1] if state.route_history else "done"

    def build(self) -> GraphRunner:
        """Build a real LangGraph when installed, otherwise an offline fallback executor."""

        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError:
            return cast(GraphRunner, _FallbackGraph(self))

        builder = StateGraph(ResearchState)
        builder.add_node("supervisor", self._supervisor_node)
        for name in self.workers:
            builder.add_node(name, self._worker_node(name))
        builder.add_edge(START, "supervisor")
        builder.add_conditional_edges(
            "supervisor",
            self._next_route,
            {
                "researcher": "researcher",
                "analyst": "analyst",
                "writer": "writer",
                "critic": "critic",
                "done": END,
            },
        )
        for name in self.workers:
            builder.add_edge(name, "supervisor")
        return cast(GraphRunner, builder.compile())

    def _run_fallback(self, state: ResearchState) -> ResearchState:
        while True:
            self.supervisor.run(state)
            route = state.route_history[-1]
            if route == "done":
                return state
            self._run_agent(route, state)

    @maybe_traceable("workflow.multi_agent")
    def run(self, state: ResearchState) -> ResearchState:
        graph = self.build()
        if isinstance(graph, _FallbackGraph):
            return graph.invoke(state)
        result = graph.invoke(
            state.model_dump(),
            config={"recursion_limit": max(25, self.settings.max_iterations * 3)},
        )
        return ResearchState.model_validate(result)
