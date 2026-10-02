#!/usr/bin/env bash
# Deploy the HrSuperAgent stack, then publish the HR project's manifest and extension to
# the chat.dengler.io platform (the GuppiGpt stack in guppi-gpt owns the page itself).
# Extra arguments are passed to `cdk deploy` (for example --hotswap or --require-approval never).
# `--site-only` skips cdk deploy (and the image build and push) and only publishes
# web/manifest.json and the built web/dist/ext.js.
# `--reuse-parameters` skips 1Password entirely and lets CloudFormation reuse the stack's
# existing Dynatrace values, so an unattended deploy never waits on a locked vault; it
# needs an earlier deploy that supplied them.
set -euo pipefail

SITE_ONLY=0
REUSE_PARAMETERS=0
while [[ "${1:-}" == "--site-only" || "${1:-}" == "--reuse-parameters" ]]; do
  if [[ "$1" == "--site-only" ]]; then SITE_ONLY=1; else REUSE_PARAMETERS=1; fi
  shift
done

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DT_ITEM_TITLE="GuppiGPT Dynatrace"
OUTPUTS="$ROOT/cdk-outputs.json"
PROJECT="hr"
# The platform's identifiers (guppi-gpt's docs/proposals/platform.md, "Platform contract").
PARAM_SITE_BUCKET="/guppi/platform/site-bucket-name"
PARAM_DISTRIBUTION="/guppi/platform/distribution-id"
PARAM_SITE_URL="/guppi/platform/site-url"

# Everything below is also written to .deploy/deploy-<timestamp>.log (gitignored), with
# .deploy/latest.log pointing at the newest run, so another session can follow a deploy
# started from any terminal. The last line of a run is always "deploy exit=<code>".
LOG_DIR="$ROOT/.deploy"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/deploy-$(date +%Y%m%d-%H%M%S).log"
ln -sfn "$(basename "$LOG")" "$LOG_DIR/latest.log"
exec > >(tee -a "$LOG") 2>&1
trap 'code=$?; echo "deploy exit=$code"; exit $code' EXIT
echo "deploy log: $LOG"

tools=(npx npm aws jq)
[[ "$SITE_ONLY" == 1 ]] || tools+=(uv docker)
for tool in "${tools[@]}"; do
  command -v "$tool" >/dev/null || { echo "missing: $tool" >&2; exit 1; }
done

export AWS_REGION="${AWS_REGION:-us-east-1}"

param_args=()
if [[ "$SITE_ONLY" == 1 ]]; then
  echo "site only: skipping cdk deploy"
elif [[ "$REUSE_PARAMETERS" == 1 ]]; then
  echo "reusing the stack's existing Dynatrace parameters; 1Password not read"
# `op whoami` can report "not signed in" while reads succeed through the desktop app
# integration, so the gate is a read of the item itself. When it fails (no op, a locked
# vault, no item) CloudFormation keeps the values the stack already has.
elif command -v op >/dev/null && op item get "$DT_ITEM_TITLE" --vault Personal >/dev/null 2>&1; then
  dt_endpoint="$(op read "op://Personal/$DT_ITEM_TITLE/hostname" 2>/dev/null || true)"
  dt_token="$(op read "op://Personal/$DT_ITEM_TITLE/credential" 2>/dev/null || true)"
  if [[ -n "$dt_endpoint" && -n "$dt_token" ]]; then
    param_args+=(--parameters "DynatraceOtlpEndpoint=$dt_endpoint" --parameters "DynatraceApiToken=$dt_token")
  else
    echo "found the '$DT_ITEM_TITLE' item but hostname or credential was empty; reusing the stack's Dynatrace parameters" >&2
  fi
else
  echo "1Password is not readable; reusing the stack's existing Dynatrace parameters" >&2
fi
if [[ -n "${HR_ALARM_EMAIL:-}" ]]; then
  param_args+=(--parameters "AlarmEmail=$HR_ALARM_EMAIL")
fi
if [[ -n "${HR_INVESTIGATOR_ARN:-}" ]]; then
  param_args+=(--parameters "InvestigatorPrincipalArn=$HR_INVESTIGATOR_ARN")
fi
if [[ "$SITE_ONLY" == 0 ]]; then
  # The agent image installs the platform kit from the private guppi-gpt repository; the
  # build reads this token as a BuildKit secret (agent/Dockerfile, D29). It stays in this
  # process's environment and is never printed.
  if [[ -z "${HR_GITHUB_TOKEN:-}" ]]; then
    command -v gh >/dev/null || { echo "missing: gh (or set HR_GITHUB_TOKEN)" >&2; exit 1; }
    HR_GITHUB_TOKEN="$(gh auth token)"
  fi
  export HR_GITHUB_TOKEN
  cd "$ROOT/infra"
  npx --yes aws-cdk@2 deploy HrSuperAgent \
    "${param_args[@]+"${param_args[@]}"}" \
    --outputs-file "$OUTPUTS" \
    "$@"
fi

cd "$ROOT/web"
npm ci --silent --no-audit --no-fund
npm run build --silent

cd "$ROOT"
ssm() { aws ssm get-parameter --name "$1" --query Parameter.Value --output text; }
bucket="$(ssm "$PARAM_SITE_BUCKET")"
distribution="$(ssm "$PARAM_DISTRIBUTION")"
site_url="$(ssm "$PARAM_SITE_URL")"

# no-cache, like the platform's config.json: the page fetches the manifest with
# cache: "no-store" and a new extension must reach the next page load.
aws s3 cp web/manifest.json "s3://$bucket/projects/$PROJECT/manifest.json" \
  --cache-control no-cache --content-type application/json
aws s3 cp web/dist/ext.js "s3://$bucket/projects/$PROJECT/ext.js" \
  --cache-control no-cache --content-type text/javascript
aws cloudfront create-invalidation --distribution-id "$distribution" \
  --paths "/projects/$PROJECT/*" >/dev/null
echo "published ${site_url}p/$PROJECT/"
