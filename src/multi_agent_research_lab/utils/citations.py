"""Citation parsing helpers shared by Writer and Critic."""

import re

from multi_agent_research_lab.core.schemas import SourceDocument

_CITATION_RE = re.compile(r"\[S(\d+)\]")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def source_ids(sources: list[SourceDocument]) -> set[str]:
    ids: set[str] = set()
    for index, source in enumerate(sources, start=1):
        raw = source.metadata.get("source_id")
        ids.add(str(raw or f"S{index}"))
    return ids


def citation_ids(text: str) -> list[str]:
    return [f"S{match}" for match in _CITATION_RE.findall(text)]


def invalid_citation_ids(text: str, sources: list[SourceDocument]) -> list[str]:
    valid = source_ids(sources)
    return sorted({citation for citation in citation_ids(text) if citation not in valid})


def material_sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_RE.split(text) if len(part.strip()) >= 20]


def citation_coverage(text: str) -> tuple[float, list[str]]:
    claims = material_sentences(text)
    if not claims:
        return 1.0, []
    unsupported = [claim for claim in claims if not citation_ids(claim)]
    return (len(claims) - len(unsupported)) / len(claims), unsupported
