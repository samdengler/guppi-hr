#!/usr/bin/env bash
# Deploy the GuppiConnect stack (the mock Lambda and the bridge: its Runtime, session table
# and the hr target on the platform's edge gateway), then publish web/ to the
# platform's site bucket under projects/hr/ and invalidate that prefix. The bridge
# needs the production contact flow id from .deploy/acxd-production.json, which
# scripts/contact_flow.py --env production writes. Extra arguments go to `cdk deploy`.
# `--site-only` skips cdk deploy and only publishes web/.
set -euo pipefail

SITE_ONLY=0
if [[ "${1:-}" == "--site-only" ]]; then
  SITE_ONLY=1
  shift
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT="hr"
OUTPUTS="$ROOT/cdk-outputs.json"

# The run is also written to .deploy/deploy-<timestamp>.log, with .deploy/latest.log
# pointing at the newest; the last line is always "deploy exit=<code>".
LOG_DIR="$ROOT/.deploy"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/deploy-$(date +%Y%m%d-%H%M%S).log"
ln -sfn "$(basename "$LOG")" "$LOG_DIR/latest.log"
exec > >(tee -a "$LOG") 2>&1
trap 'code=$?; echo "deploy exit=$code"; exit $code' EXIT
echo "deploy log: $LOG"

tools=(aws)
[[ "$SITE_ONLY" == 0 ]] && tools+=(uv docker)
for tool in "${tools[@]}"; do
  command -v "$tool" >/dev/null || { echo "missing: $tool" >&2; exit 1; }
done

export AWS_REGION="${AWS_REGION:-us-east-1}"

if [[ "$SITE_ONLY" == 1 ]]; then
  echo "site only: skipping cdk deploy"
else
  # The bridge image installs the platform kit from the private guppi-gpt repository; the
  # build reads this token as a BuildKit secret (agent/Dockerfile). It stays in this
  # process's environment and is never printed.
  if [[ -z "${HR_GITHUB_TOKEN:-}" ]]; then
    command -v gh >/dev/null || { echo "missing: gh (or set HR_GITHUB_TOKEN)" >&2; exit 1; }
    HR_GITHUB_TOKEN="$(gh auth token)"
  fi
  export HR_GITHUB_TOKEN
  cd "$ROOT/infra"
  uv run cdk deploy GuppiConnect --outputs-file "$OUTPUTS" "$@"
fi

cd "$ROOT"
platform_parameter() {
  aws ssm get-parameter --name "/guppi/platform/$1" --query Parameter.Value --output text
}
bucket="$(platform_parameter site-bucket-name)"
distribution="$(platform_parameter distribution-id)"

# Only this project's prefix is written, and --delete never reaches outside it.
aws s3 sync web "s3://$bucket/projects/$PROJECT/" --delete --exclude '.*' \
  --cache-control no-store
aws cloudfront create-invalidation --distribution-id "$distribution" \
  --paths "/projects/$PROJECT/*" >/dev/null
echo "published $(platform_parameter site-url)p/$PROJECT/"
