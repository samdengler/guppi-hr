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
