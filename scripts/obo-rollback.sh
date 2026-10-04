#!/usr/bin/env bash
# Rolls the HR hops back from on-behalf-of tokens (D47) to the employee's Okta token
# everywhere, by deploying the commit before the switch: the HR stack (gateways, runtimes,
# tools target), the Connect bridge, the canvas and its contact flow. The issuer in
# guppi-gpt's platform stack stays; nothing calls it after a rollback.
#
#   scripts/obo-rollback.sh            # the commit before the switch (BEFORE below)
#   scripts/obo-rollback.sh <commit>   # any other commit
#
# It deploys from a temporary git worktree, so the working copy is untouched, and runs
# unattended (no approval prompt). The page's refresh before a warm start is harmless
# either way and stays.
set -euo pipefail

BEFORE="73c346b" # D47 decisions recorded; the last commit before the code switched
COMMIT="${1:-$BEFORE}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)/guppi-hr-rollback"

git -C "$ROOT" worktree add --detach "$WORK" "$COMMIT"
trap 'git -C "$ROOT" worktree remove --force "$WORK" || true' EXIT

echo "== HR stack at $COMMIT"
(cd "$WORK" && uv sync --all-packages --dev -q && scripts/deploy.sh --reuse-parameters --require-approval never)

echo "== Connect bridge at $COMMIT"
(cd "$WORK/connect" && scripts/deploy.sh --require-approval never)

echo "== canvas and contact flow at $COMMIT"
(cd "$WORK/connect/acxd" && npm ci --silent && node deploy.js --env production)
(cd "$WORK/connect" && uv run scripts/contact_flow.py --env production)

echo "rolled back to $COMMIT"
