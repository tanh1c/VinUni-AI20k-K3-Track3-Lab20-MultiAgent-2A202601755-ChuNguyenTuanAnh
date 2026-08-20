"""Deterministic retrieval over the school's official offline research corpus."""

import base64
import binascii
import csv
import gzip
import hashlib
import io
import json
import re
import zlib
from pathlib import Path
from typing import Any, cast
from zipfile import ZipFile

from multi_agent_research_lab.core.errors import ValidationError
from multi_agent_research_lab.core.schemas import SourceDocument

OFFICIAL_CORPUS_SHA256 = "276117a25e178937bfb20b08f944450f5278fd0490a9c5cdebed364fa24658bf"
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.casefold()))


class CorpusSearchClient:
    """Load one fixed corpus topic and retrieve embedded evidence without network access."""

    def __init__(
        self,
        corpus_path: Path,
        *,
        topic_id: str,
        expected_sha256: str = OFFICIAL_CORPUS_SHA256,
    ) -> None:
        self.corpus_path = Path(corpus_path)
        self.topic_id = topic_id
        if self.corpus_path.is_dir():
            self.corpus_sha256 = self._verify_subset(expected_sha256)
        else:
            self.corpus_sha256 = hashlib.sha256(self.corpus_path.read_bytes()).hexdigest()
            if self.corpus_sha256 != expected_sha256:
                raise ValidationError(
                    "Offline corpus checksum mismatch: "
                    f"expected {expected_sha256}, got {self.corpus_sha256}"
                )
        self.topic = self._load_topic(topic_id)

    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _verify_subset(self, expected_sha256: str) -> str:
        provenance_path = self.corpus_path / "PROVENANCE.json"
        try:
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValidationError(f"Invalid corpus subset provenance: {exc}") from exc

        source_sha = str(provenance.get("source_zip_sha256") or "")
        if source_sha != expected_sha256:
            raise ValidationError(
                "Offline corpus checksum mismatch: "
                f"expected {expected_sha256}, got {source_sha or 'missing'}"
            )

        file_hashes = provenance.get("file_sha256")
        if not isinstance(file_hashes, dict):
            raise ValidationError("Invalid corpus subset provenance: file_sha256 is missing")
        for relative_path, expected in file_hashes.items():
            path = self.corpus_path / str(relative_path)
            actual = self._sha256(path) if path.is_file() else "missing"
            if actual != str(expected):
                raise ValidationError(
                    "Corpus subset checksum mismatch: "
                    f"{relative_path} expected {expected}, got {actual}"
                )

        decoded_hashes = provenance.get("decoded_topic_sha256", {})
        if not isinstance(decoded_hashes, dict):
            raise ValidationError(
                "Invalid corpus subset provenance: decoded_topic_sha256 must be an object"
            )
        for relative_path, expected in decoded_hashes.items():
            raw = self._read_subset_topic_bytes(str(relative_path))
            actual = hashlib.sha256(raw).hexdigest()
            if actual != str(expected):
                raise ValidationError(
                    "Corpus decoded topic checksum mismatch: "
                    f"{relative_path} expected {expected}, got {actual}"
                )
        return source_sha

    def _read_subset_topic_bytes(self, relative_path: str) -> bytes:
        path = self.corpus_path / relative_path
        if path.is_file():
            return path.read_bytes()

        gzip_path = Path(f"{path}.gz")
        try:
            if gzip_path.is_file():
                return gzip.decompress(gzip_path.read_bytes())

            chunk_paths = sorted(path.parent.glob(f"{path.name}.gz.b64.part*"))
            if not chunk_paths:
                raise ValidationError(f"Missing corpus subset topic payload: {relative_path}")
            encoded = "".join(chunk.read_text(encoding="ascii").strip() for chunk in chunk_paths)
            compressed = base64.b64decode(encoded, validate=True)
            return gzip.decompress(compressed)
        except (OSError, EOFError, UnicodeError, binascii.Error, zlib.error) as exc:
            raise ValidationError(
                f"Corpus subset checksum mismatch: invalid topic payload {relative_path}"
            ) from exc

    @staticmethod
    def _manifest_filename(manifest: str, topic_id: str) -> str:
        rows = csv.DictReader(io.StringIO(manifest))
        filename = next(
            (row["filename"] for row in rows if row.get("topic_id") == topic_id),
            None,
        )
        if filename is None:
            raise ValidationError(f"Unknown corpus topic_id: {topic_id}")
        return filename

    def _load_topic(self, topic_id: str) -> dict[str, Any]:
        if self.corpus_path.is_dir():
            manifest = (self.corpus_path / "manifest.csv").read_text(encoding="utf-8")
            filename = self._manifest_filename(manifest, topic_id)
            raw = self._read_subset_topic_bytes(f"topics/{filename}")
            payload = json.loads(raw.decode("utf-8"))
        else:
            with ZipFile(self.corpus_path) as archive:
                manifest_name = next(
                    name for name in archive.namelist() if name.endswith("/manifest.csv")
                )
                manifest = archive.read(manifest_name).decode("utf-8")
                filename = self._manifest_filename(manifest, topic_id)
                root = manifest_name.rsplit("/", 1)[0]
                payload = json.loads(archive.read(f"{root}/topics/{filename}"))
        if not isinstance(payload, dict):
            raise ValidationError(f"Corpus topic {topic_id} is not a JSON object")
        return cast(dict[str, Any], payload)

    @staticmethod
    def _rank(query: str, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        query_tokens = _tokens(query)

        def score(document: dict[str, Any]) -> tuple[int, str]:
            haystack = " ".join(
                str(document.get(field) or "") for field in ("title", "full_text", "authors_or_org")
            )
            overlap = len(query_tokens & _tokens(haystack))
            return (-overlap, str(document.get("document_id") or ""))

        return sorted(documents, key=score)

    def search(self, query: str, max_results: int = 5) -> list[SourceDocument]:
        limit = max(1, min(max_results, 20))
        raw_documents = self.topic["knowledge_base"]["source_documents"]
        public = self._rank(query, [item for item in raw_documents if not item["is_synthetic"]])
        synthetic = self._rank(query, [item for item in raw_documents if item["is_synthetic"]])

        synthetic_budget = max(1, limit // 4) if synthetic and limit > 1 else 0
        public_budget = min(len(public), limit - synthetic_budget)
        synthetic_budget = min(len(synthetic), limit - public_budget)
        selected = public[:public_budget] + synthetic[:synthetic_budget]
        if len(selected) < limit:
            selected_ids = {item["document_id"] for item in selected}
            remainder = [
                item
                for item in self._rank(query, list(raw_documents))
                if item["document_id"] not in selected_ids
            ]
            selected.extend(remainder[: limit - len(selected)])

        return [
            SourceDocument(
                title=str(item["title"]),
                url=str(item.get("provenance_url") or "") or None,
                snippet=str(item["full_text"]),
                metadata={
                    "source_id": str(item["document_id"]),
                    "provider": "official_offline_corpus",
                    "topic_id": self.topic_id,
                    "document_class": item["document_class"],
                    "is_synthetic": bool(item["is_synthetic"]),
                    "year": item.get("year"),
                    "recommended_weight": item.get("recommended_weight"),
                },
            )
            for item in selected[:limit]
        ]
