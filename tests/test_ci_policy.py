import re
from pathlib import Path


def test_github_actions_are_manual_only() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert re.search(r"^\s+push:\s*$", workflow, flags=re.MULTILINE) is None
    assert re.search(r"^\s+pull_request:\s*$", workflow, flags=re.MULTILINE) is None


def test_github_actions_expose_manual_corpus_benchmark_mode() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "- corpus" in workflow
    assert "inputs.mode == 'corpus'" in workflow
    assert "corpus-benchmark" in workflow
    assert "AIAGENT-01,AIAGENT-12,AIAGENT-13" in workflow
    assert "corpus_benchmark_report.md" in workflow
    assert "corpus_benchmark_details.json" in workflow
