"""The on-behalf-of rollback's revert step still applies on top of HEAD (D47, D48; critique
round 3, finding 1). It runs scripts/obo-rollback.sh --check: a temporary worktree, the
listed commits reverse-applied, nothing deployed."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_the_rollback_reverts_cleanly_on_head():
    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    result = subprocess.run(["bash", "scripts/obo-rollback.sh", "--check"], cwd=ROOT,
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-2000:]
    # The revert removes what D47 added: the HR side's token module and the checks.
    assert "infra/hr_super_agent_infra/obo.py" in result.stdout
    assert "scripts/obo-checks.py" in result.stdout


def test_every_code_commit_since_d47_is_listed_to_revert_or_to_keep():
    """A code commit in neither list would be reverted or kept by accident (rounds 4 and 5).
    The paths are the ones the script reverts: all but the documents and its own files."""
    import re

    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    script = (ROOT / "scripts" / "obo-rollback.sh").read_text()

    def listed(name: str) -> set[str]:
        return set(re.search(rf"^{name}=\(([^)]*)\)", script, re.MULTILINE).group(1).split())

    since = subprocess.run(["git", "log", "--format=%h", "--abbrev=7", "c6d96e0^..HEAD", "--", ".",
                            ":(exclude)docs", ":(exclude)*.md", ":(exclude)scripts/obo-rollback.sh",
                            ":(exclude)infra/tests/test_rollback.py"],
                           cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    missing = set(since) - listed("OBO_COMMITS") - listed("KEPT_COMMITS")
    assert not missing, f"add {sorted(missing)} to OBO_COMMITS (to revert) or KEPT_COMMITS (to keep)"
