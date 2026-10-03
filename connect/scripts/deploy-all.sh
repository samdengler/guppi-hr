#!/usr/bin/env bash
# Deploy everything behind /p/hr/ in the order that works (critique finding 15):
#
#   1. HrSuperAgent (scripts/deploy.sh): the sub-agents, the tools server, both HR
#      gateways, and the SSM parameters the canvas and the bridge read
#      (/guppi-hr/agents-gateway-url, /guppi-hr/tools-gateway-url).
#   2. The canvas (connect/acxd/deploy.js), development then production.
#   3. The contact flow (connect/scripts/contact_flow.py --env production), which binds the
#      production canvas alias and publishes /guppi-hr/connect/contact-flow-id.
#   4. GuppiConnect (connect/scripts/deploy.sh): the bridge, its table, alarms and page.
#
# The GuppiGpt platform stack is deployed from guppi-gpt and must exist first; it
# publishes /guppi/platform/*. Each step stops the run if it fails.
#
#   connect/scripts/deploy-all.sh            # everything
#   connect/scripts/deploy-all.sh --from 3   # resume at a step
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FROM=1
if [[ "${1:-}" == "--from" ]]; then
  FROM="$2"
  shift 2
fi
export AWS_REGION="${AWS_REGION:-us-east-1}"

step() { echo; echo "== step $1: $2"; }

if (( FROM <= 1 )); then
  step 1 "HrSuperAgent"
  "$ROOT/scripts/deploy.sh" --reuse-parameters --require-approval never
fi
if (( FROM <= 2 )); then
  step 2 "canvas, development and production"
  (cd "$ROOT/connect/acxd" && node deploy.js && node deploy.js --env production)
fi
if (( FROM <= 3 )); then
  step 3 "contact flow"
  (cd "$ROOT/connect" && uv run scripts/contact_flow.py --env production)
fi
if (( FROM <= 4 )); then
  step 4 "GuppiConnect"
  "$ROOT/connect/scripts/deploy.sh" --require-approval never
fi
echo
echo "deploy-all done"
