#!/usr/bin/env bash
# D60 rollout, one commit at a time: d60.sh A, then d60.sh B after A's checks pass.
# The sub-agents exchange their agents token on the workload token AgentCore Runtime already
# fetched for the request (doc "Sub-agent token exchange on the Runtime workload token").
#
# Runs the tests and synth, deploys the HR stack, runs the live checks, then reads the three
# sub-agents' exchange log lines and, after 10 minutes, CloudTrail's
# GetWorkloadAccessTokenForJWT callers. Needs AWS credentials and the Okta test session
# (~/.config/guppi/test-session.json, from guppi-gpt scripts/test-token.sh) for the checks.
#
# Expected after A: every exchange line names the Runtime workload token, and CloudTrail
# shows AWSServiceRoleForBedrockAgentCoreRuntimeIdentity and no sub-agent role (the chat
# start and orchestrator roles may appear). Undo A: git revert <hash> && scripts/deploy.sh.
set -euo pipefail
STEP="${1:?usage: d60.sh A|B}"
REGION=us-east-1
cd "$(dirname "$0")/.."
aws sts get-caller-identity >/dev/null 2>&1 || aws sso login
[[ -s "$HOME/.config/guppi/test-session.json" ]] || {
  echo "no Okta test session at ~/.config/guppi/test-session.json: the live checks cannot run here" >&2
  exit 1
}

uv run -- pytest
(cd infra && uv run -- cdk synth -q -c image_uri=000000000000.dkr.ecr.us-east-1.amazonaws.com/synth:check >/dev/null)
scripts/deploy.sh --reuse-parameters --require-approval never
START_EPOCH=$(date +%s)
START=$(date -u -r "$START_EPOCH" +%Y-%m-%dT%H:%M:%SZ)

uv run scripts/obo-checks.py
uv run connect/scripts/latency_bench.py --rounds 2 --label "d60-$STEP"

for name in profile pay travel; do
  id=$(aws bedrock-agentcore-control list-agent-runtimes --region "$REGION" \
    --query "agentRuntimes[?agentRuntimeName=='hr_super_agent_$name'].agentRuntimeId | [0]" --output text)
  qid=$(aws logs start-query --region "$REGION" \
    --log-group-name "/aws/bedrock-agentcore/runtimes/$id-DEFAULT" \
    --start-time "$START_EPOCH" --end-time "$(date +%s)" \
    --query-string 'filter @message like /workload token/ | stats count() by @message' \
    --query queryId --output text)
  sleep 15
  echo "== $name"
  aws logs get-query-results --region "$REGION" --query-id "$qid" --output json \
    | jq -r '.results[] | map(.value) | join("  ")'
done

echo "waiting 10 minutes for CloudTrail"
sleep 600
echo "== GetWorkloadAccessTokenForJWT callers since $START"
aws cloudtrail lookup-events --region "$REGION" --start-time "$START" \
  --lookup-attributes AttributeKey=EventName,AttributeValue=GetWorkloadAccessTokenForJWT \
  --query 'Events[].CloudTrailEvent' --output json \
  | jq -r '.[] | fromjson | .userIdentity.sessionContext.sessionIssuer.userName // .userIdentity.arn' \
  | sort | uniq -c
