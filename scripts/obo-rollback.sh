#!/usr/bin/env bash
# Rolls the HR hops back from on-behalf-of tokens (D47) to the employee's Okta token
# everywhere. In a temporary worktree it reverts every commit since BEFORE on top of HEAD
# (so later unrelated work is kept unless it sits in that range), then deploys the result:
# the HR stack, the Connect bridge, the canvas and its contact flow. The issuer in
# guppi-gpt's platform stack stays; nothing calls it after a rollback.
#
#   scripts/obo-rollback.sh --diff     # show the CloudFormation changes, deploy nothing
#   scripts/obo-rollback.sh            # deploy the rollback (asks first)
#
# Known risks, from the critique of the build (finding 6):
# - between the HR stack's deploy and the bridge's, /p/hr/ fails: the gateways want the
#   Okta token while the bridge still sends hop tokens; contacts started before the
#   rollback keep hop tokens until they end (an hour at most);
# - the HR update detaches the tools gateway's policy engine and drops the role's
#   GetPolicyEngine grant together; if CloudFormation removes the grant first the gateway
#   update fails (the mirror of aws-feedback A16), so a second run may be needed;
# - the tools runtime moves from its JWT authorizer back to IAM in place, which is untested.
# After a rollback, run the harness (connect/scripts/latency_bench.py --rounds 2).
set -euo pipefail

BEFORE="73c346b" # D47 decisions recorded; the last commit before the code switched
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)/guppi-hr-rollback"
MODE="${1:-deploy}"

git -C "$ROOT" worktree add --detach "$WORK" HEAD >/dev/null
trap 'git -C "$ROOT" worktree remove --force "$WORK" || true' EXIT

echo "reverting, newest first:"
git -C "$WORK" log --oneline "$BEFORE..HEAD"
git -C "$WORK" -c user.name=rollback -c user.email=rollback@localhost revert --no-edit "$BEFORE..HEAD" >/dev/null

if [[ "$MODE" == "--diff" ]]; then
  (cd "$WORK" && uv sync --all-packages --dev -q &&
    cd infra && uv run -- cdk diff HrSuperAgent -c image_uri=unused.dkr.ecr.us-east-1.amazonaws.com/x:y) || true
  (cd "$WORK/connect/infra" && uv run -- cdk diff GuppiConnect) || true
  exit 0
fi

read -r -p "Deploy the rollback to HrSuperAgent, GuppiConnect, the canvas and the contact flow? [y/N] " answer
[[ "$answer" == "y" ]] || exit 1

echo "== HR stack"
(cd "$WORK" && uv sync --all-packages --dev -q && scripts/deploy.sh --reuse-parameters --require-approval never)
echo "== Connect bridge"
(cd "$WORK/connect" && scripts/deploy.sh --require-approval never)
echo "== canvas and contact flow"
(cd "$WORK/connect/acxd" && npm ci --silent && node deploy.js --env production)
(cd "$WORK/connect" && uv run scripts/contact_flow.py --env production)
echo "rolled back; now run the harness"
