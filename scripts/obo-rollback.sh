#!/usr/bin/env bash
# Rolls the HR hops back from on-behalf-of tokens (D47) to the employee's Okta token
# everywhere. In a temporary worktree it reverts the on-behalf-of commits on top of HEAD,
# then deploys the result:
# the HR stack, the Connect bridge, the canvas and its contact flow. The issuer in
# guppi-gpt's platform stack stays; nothing calls it after a rollback.
#
# Only the commits in OBO_COMMITS are reverted, newest first; add each later on-behalf-of
# commit to the list in the same commit. Everything else at HEAD is kept.
#
#   scripts/obo-rollback.sh --check    # the revert step only (infra/tests runs this)
#   scripts/obo-rollback.sh --diff     # show the CloudFormation changes, deploy nothing
#   scripts/obo-rollback.sh            # deploy the rollback (asks first)
#
# Each listed commit is reverse-applied with this script itself left out, so a commit that
# adds itself to the list cannot make the revert conflict (critique round 3, finding 1).
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

# The on-behalf-of commits, newest first (D47, D48 and their follow-ups).
OBO_COMMITS=(8040b10 9a18c00 454f90d 91f9580 c6d96e0)
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)/guppi-hr-rollback"
MODE="${1:-deploy}"

git -C "$ROOT" worktree add --detach "$WORK" HEAD >/dev/null
trap 'git -C "$ROOT" worktree remove --force "$WORK" || true' EXIT

echo "reverting, newest first:"
for commit in "${OBO_COMMITS[@]}"; do
  git -C "$WORK" log --oneline -1 "$commit"
  patch="$(git -C "$WORK" show --binary --format= "$commit" -- . ':(exclude)scripts/obo-rollback.sh')"
  if [[ -n "$patch" ]]; then
    printf '%s\n' "$patch" | git -C "$WORK" apply -R --3way --index
  fi
done
git -C "$WORK" -c user.name=rollback -c user.email=rollback@localhost commit -q -m "Roll back on-behalf-of tokens"
echo "paths the rollback changes:"
git -C "$WORK" diff --stat HEAD~1 HEAD

if [[ "$MODE" == "--check" ]]; then
  exit 0
fi

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
