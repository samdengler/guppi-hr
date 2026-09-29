#!/usr/bin/env bash
# Refresh the knowledge base corpus: the synthetic HR policy documents in content/hr/
# (decision D5), synced to docs/hr/ in the content bucket. --delete also removes any
# earlier corpus under docs/, such as the guppi-gpt documentation sources. Run
# scripts/ingest.sh afterwards.
# Usage: scripts/seed-content.sh [bucket]   (default: ContentBucketName from cdk-outputs.json)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
bucket="${1:-$(jq -r '.HrSuperAgent.ContentBucketName' "$ROOT/cdk-outputs.json")}"

for tool in aws jq; do
  command -v "$tool" >/dev/null || { echo "missing: $tool" >&2; exit 1; }
done

stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
mkdir -p "$stage/docs/hr"
cp "$ROOT"/content/hr/*.md "$stage/docs/hr/"
echo "hr: $(find "$stage/docs/hr" -type f | wc -l | tr -d ' ') files" >&2

aws s3 sync "$stage/docs" "s3://$bucket/docs" --delete --only-show-errors
echo "synced to s3://$bucket/docs; run scripts/ingest.sh to index the changes"
