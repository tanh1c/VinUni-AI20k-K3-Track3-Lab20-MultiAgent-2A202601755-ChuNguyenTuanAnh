from pathlib import Path

import pytest

from multi_agent_research_lab.core.errors import ValidationError
from multi_agent_research_lab.services.corpus_client import CorpusSearchClient

CORPUS = Path("data/offline_corpus_subset")


def test_corpus_client_verifies_official_checksum_and_loads_topic() -> None:
    client = CorpusSearchClient(CORPUS, topic_id="AIAGENT-01")
    assert client.topic_id == "AIAGENT-01"
    assert client.topic["benchmark_metadata"]["topic_id"] == "AIAGENT-01"
    assert client.corpus_sha256 == (
        "276117a25e178937bfb20b08f944450f5278fd0490a9c5cdebed364fa24658bf"
    )


def test_corpus_client_preserves_canonical_ids_and_synthetic_metadata() -> None:
    client = CorpusSearchClient(CORPUS, topic_id="AIAGENT-01")
    documents = client.search("multi-agent verification trade-offs", max_results=8)
    ids = [str(item.metadata["source_id"]) for item in documents]
    assert len(documents) == 8
    assert len(set(ids)) == 8
    assert "autogen" in ids
    assert any(bool(item.metadata["is_synthetic"]) for item in documents)
    synthetic = next(item for item in documents if item.metadata["is_synthetic"])
    assert str(synthetic.metadata["source_id"]).startswith("T01-SYN-")
    assert synthetic.metadata["provider"] == "official_offline_corpus"


def test_corpus_client_is_deterministic_and_bounded() -> None:
    client = CorpusSearchClient(CORPUS, topic_id="AIAGENT-12")
    first = client.search("critic verifier factual quality", max_results=5)
    second = client.search("critic verifier factual quality", max_results=5)
    assert [item.metadata["source_id"] for item in first] == [
        item.metadata["source_id"] for item in second
    ]
    assert len(first) == 5


def test_corpus_client_rejects_unknown_topic() -> None:
    with pytest.raises(ValidationError, match="Unknown corpus topic_id"):
        CorpusSearchClient(CORPUS, topic_id="AIAGENT-99")


def test_corpus_client_rejects_tampered_subset_chunk(tmp_path) -> None:
    import shutil

    copied = tmp_path / "corpus"
    shutil.copytree(CORPUS, copied)
    chunk = (
        copied
        / "topics"
        / (
            "01_single_agent_vs_multi_agent_architectures_for_complex_"
            "research_tasks.json.gz.b64.part01"
        )
    )
    text = chunk.read_text(encoding="ascii")
    chunk.write_text(("A" if text[0] != "A" else "B") + text[1:], encoding="ascii")

    with pytest.raises(ValidationError, match="subset checksum mismatch"):
        CorpusSearchClient(copied, topic_id="AIAGENT-01")


@pytest.mark.parametrize("topic_id", ["AIAGENT-01", "AIAGENT-12", "AIAGENT-13"])
def test_chunked_topic_decodes_and_hashes(topic_id: str) -> None:
    client = CorpusSearchClient(CORPUS, topic_id=topic_id)
    assert client.topic["benchmark_metadata"]["topic_id"] == topic_id
