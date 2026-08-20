import re
from pathlib import Path


def test_github_actions_are_manual_only() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert re.search(r"^\s+push:\s*$", workflow, flags=re.MULTILINE) is None
    assert re.search(r"^\s+pull_request:\s*$", workflow, flags=re.MULTILINE) is None
