"""Public schemas exchanged between CLI, agents, and evaluators."""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentName(StrEnum):
    SUPERVISOR = "supervisor"
    RESEARCHER = "researcher"
    ANALYST = "analyst"
    WRITER = "writer"
    CRITIC = "critic"


class ResearchQuery(BaseModel):
    query: str = Field(..., min_length=5)
    max_sources: int = Field(default=5, ge=1, le=20)
    audience: str = "technical learners"


class AgentResult(BaseModel):
    agent: AgentName
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceDocument(BaseModel):
    title: str
    url: str | None = None
    snippet: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class CriticReview(BaseModel):
    """Structured verification result produced by the bonus critic agent."""

    citation_coverage: float = Field(ge=0, le=1)
    invalid_citations: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    verdict: Literal["pass", "warn", "fail"]
    notes: str = ""


class BenchmarkMetrics(BaseModel):
    run_name: str
    latency_seconds: float
    estimated_cost_usd: float | None = None
    quality_score: float | None = Field(default=None, ge=0, le=10)
    citation_coverage: float | None = Field(default=None, ge=0, le=1)
    failure_rate: float | None = Field(default=None, ge=0, le=1)
    notes: str = ""


class CorpusBenchmarkMetrics(BaseModel):
    """Transparent rubric-aligned measurements for one official-corpus run."""

    topic_id: str
    run_name: str
    latency_seconds: float
    estimated_cost_usd: float | None = None
    failure_rate: float = Field(ge=0, le=1)
    citation_coverage: float = Field(ge=0, le=1)
    invalid_citation_count: int = Field(ge=0)
    invalid_citation_rate: float = Field(ge=0, le=1)
    distinct_source_count: int = Field(ge=0)
    public_source_count: int = Field(ge=0)
    synthetic_source_count: int = Field(ge=0)
    synthetic_disclosure: bool
    required_section_coverage: float = Field(ge=0, le=1)
    meets_source_targets: bool
    counterargument_present: bool
    gold_coverage: float = Field(ge=0, le=1)
    rubric_proxy_score: float = Field(ge=0, le=100)
    notes: str = "rubric-aligned deterministic proxy; not a teacher grade or semantic ground truth"
