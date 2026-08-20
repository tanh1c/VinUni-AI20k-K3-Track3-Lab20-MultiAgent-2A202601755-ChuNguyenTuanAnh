"""Prompt-safe rendering helpers for retrieved evidence."""

from multi_agent_research_lab.core.schemas import SourceDocument


def source_prompt_block(source: SourceDocument) -> str:
    """Render one source with canonical ID and relevant provenance metadata."""

    provenance: list[str] = []
    if "is_synthetic" in source.metadata:
        value = str(bool(source.metadata["is_synthetic"])).lower()
        provenance.append(f"is_synthetic={value}")
    if "document_class" in source.metadata:
        provenance.append(f"document_class={source.metadata['document_class']}")
    provenance_line = f"\nProvenance: {'; '.join(provenance)}" if provenance else ""
    return (
        f"[{source.metadata['source_id']}] {source.title}\n"
        f"URL: {source.url or 'n/a'}{provenance_line}\n{source.snippet}"
    )
