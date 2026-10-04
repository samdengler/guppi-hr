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


def test_every_code_commit_since_d47_is_in_the_rollback_list():
    """A code commit missing from OBO_COMMITS would quietly survive a rollback (round 4)."""
    import re

    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    listed = set(re.search(r"^OBO_COMMITS=\(([^)]*)\)", (ROOT / "scripts" / "obo-rollback.sh").read_text(),
                           re.MULTILINE).group(1).split())
    since = subprocess.run(["git", "log", "--format=%h", "--abbrev=7", "c6d96e0^..HEAD", "--",
                            "agent", "connect", "infra", "scripts", ":(exclude)scripts/obo-rollback.sh",
                            ":(exclude)infra/tests/test_rollback.py"],
                           cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    assert set(since) - listed == set(), "add these to OBO_COMMITS in scripts/obo-rollback.sh"
