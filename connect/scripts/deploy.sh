#!/usr/bin/env bash
# Deploy the GuppiConnect stack (the mock Lambda; the bridge: its Runtime, session table
# and the hr target on the platform's edge gateway; the chat start function hr-chat-start,
# whose Rust is built by cargo-lambda through uvx at synth, or in Docker without cargo, and
# whose REST API host and stage go to /guppi/hr/chat-start-host and /guppi/hr/chat-start-path
# for guppi-gpt's CloudFront, D57), then publish web/ to the
# platform's site bucket under projects/hr/ and invalidate that prefix. The bridge
# reads the production contact flow id from SSM (/guppi-hr/connect/contact-flow-id),
# which scripts/contact_flow.py --env production publishes. Then build the /p/hr-widget/
# extension (touchpoint/, D62) and publish it under projects/hr-widget/. Extra arguments go to
# `cdk deploy`; GUPPI_ALARM_EMAIL, when set, subscribes that address to the alarms.
# `--site-only` skips cdk deploy and only publishes web/ and the widget.
set -euo pipefail

SITE_ONLY=0
if [[ "${1:-}" == "--site-only" ]]; then
  SITE_ONLY=1
  shift
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT="hr"
WIDGET_PROJECT="hr-widget"
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

tools=(aws npm)
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
  # The alarm topic's email subscription, from the environment only; without it the
  # stack keeps the address it has (CDK reuses a parameter's previous value).
  params=()
  if [[ -n "${GUPPI_ALARM_EMAIL:-}" ]]; then
    params+=(--parameters "AlarmEmail=$GUPPI_ALARM_EMAIL")
  fi
  # ${params[@]+...}: macOS bash 3.2 treats an empty array as unbound under set -u.
  uv run cdk deploy GuppiConnect --outputs-file "$OUTPUTS" ${params[@]+"${params[@]}"} "$@"
  # AgentCore creates the runtime's log group without a retention; keep 30 days.
  log_group="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["GuppiConnect"]["RuntimeLogGroup"])' "$OUTPUTS")"
  aws logs put-retention-policy --log-group-name "$log_group" --retention-in-days 30
  echo "retention 30 days: $log_group"
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

# The widget's bundle is about 3 MB, so browsers revalidate it (no-cache) rather than
# fetching it again on every page view.
(cd "$ROOT/touchpoint" && npm ci --silent --no-audit --no-fund && npm test && npm run build)
aws s3 sync touchpoint/dist/widget "s3://$bucket/projects/$WIDGET_PROJECT/" --delete --exclude '.*' \
  --cache-control no-cache
aws cloudfront create-invalidation --distribution-id "$distribution" \
  --paths "/projects/$WIDGET_PROJECT/*" >/dev/null
echo "published $(platform_parameter site-url)p/$WIDGET_PROJECT/"
