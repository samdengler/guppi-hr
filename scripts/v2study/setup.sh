#!/usr/bin/env bash
# Shared fixtures for the Runtime V2 cold start study (docs/runtime-v2-experiments.md):
# one ECR repository, one execution role, one vended log group and delivery destination.
# Idempotent. `setup.sh teardown` removes them (runtimes first: see create.py delete).
set -euo pipefail
REGION=${AWS_REGION:-us-east-1}
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REPO=hr-v2-study
ROLE=hr-v2-study-runtime
LOG_GROUP=/aws/vendedlogs/bedrock-agentcore/hr-v2-study
DEST=hr-v2-study-logs
TAGS="Key=hr-v2-study,Value=2026-10-04"

if [ "${1:-}" = "teardown" ]; then
  for src in $(aws logs describe-delivery-sources --query "deliverySources[?starts_with(name, 'hr-v2-study-')].name" --output text); do
    for d in $(aws logs describe-deliveries --query "deliveries[?deliverySourceName=='$src'].id" --output text); do aws logs delete-delivery --id "$d"; done
    aws logs delete-delivery-source --name "$src"
  done
  aws logs delete-delivery-destination --name "$DEST" 2>/dev/null || true
  aws iam delete-role-policy --role-name "$ROLE" --policy-name runtime 2>/dev/null || true
  aws iam delete-role --role-name "$ROLE" 2>/dev/null || true
  aws ecr delete-repository --repository-name "$REPO" --force >/dev/null 2>&1 || true
  echo "kept log group $LOG_GROUP (evidence); delete by hand when the records are no longer needed"
  exit 0
fi

aws ecr describe-repositories --repository-names "$REPO" >/dev/null 2>&1 \
  || aws ecr create-repository --repository-name "$REPO" --tags "$TAGS" >/dev/null
echo "repo: $ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO"

TRUST=$(cat <<JSON
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"bedrock-agentcore.amazonaws.com"},
 "Action":"sts:AssumeRole","Condition":{"StringEquals":{"aws:SourceAccount":"$ACCOUNT"},
 "ArnLike":{"aws:SourceArn":"arn:aws:bedrock-agentcore:$REGION:$ACCOUNT:*"}}}]}
JSON
)
POLICY=$(cat <<JSON
{"Version":"2012-10-17","Statement":[
 {"Effect":"Allow","Action":["ecr:GetAuthorizationToken","xray:PutTraceSegments","xray:PutTelemetryRecords","xray:GetSamplingRules","xray:GetSamplingTargets","cloudwatch:PutMetricData"],"Resource":"*"},
 {"Effect":"Allow","Action":["ecr:BatchGetImage","ecr:GetDownloadUrlForLayer","ecr:BatchCheckLayerAvailability"],"Resource":"arn:aws:ecr:$REGION:$ACCOUNT:repository/$REPO"},
 {"Effect":"Allow","Action":["logs:DescribeLogGroups"],"Resource":"arn:aws:logs:$REGION:$ACCOUNT:log-group:*"},
 {"Effect":"Allow","Action":["logs:CreateLogGroup","logs:CreateLogStream","logs:DescribeLogStreams","logs:PutLogEvents"],"Resource":"arn:aws:logs:$REGION:$ACCOUNT:log-group:/aws/bedrock-agentcore/runtimes/*"},
 {"Effect":"Allow","Action":["bedrock-agentcore:GetWorkloadAccessToken","bedrock-agentcore:GetWorkloadAccessTokenForJWT"],"Resource":["arn:aws:bedrock-agentcore:$REGION:$ACCOUNT:workload-identity-directory/default","arn:aws:bedrock-agentcore:$REGION:$ACCOUNT:workload-identity-directory/default/workload-identity/hr_v2_*"]}
]}
JSON
)
aws iam get-role --role-name "$ROLE" >/dev/null 2>&1 \
  || aws iam create-role --role-name "$ROLE" --assume-role-policy-document "$TRUST" --tags "$TAGS" >/dev/null
aws iam put-role-policy --role-name "$ROLE" --policy-name runtime --policy-document "$POLICY"
echo "role: arn:aws:iam::$ACCOUNT:role/$ROLE"

aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP" --query "logGroups[?logGroupName=='$LOG_GROUP']" --output text | grep -q . \
  || { aws logs create-log-group --log-group-name "$LOG_GROUP" --tags hr-v2-study=2026-10-04; aws logs put-retention-policy --log-group-name "$LOG_GROUP" --retention-in-days 30; }
aws logs get-delivery-destination --name "$DEST" >/dev/null 2>&1 \
  || aws logs put-delivery-destination --name "$DEST" --delivery-destination-type CWL \
       --delivery-destination-configuration "destinationResourceArn=arn:aws:logs:$REGION:$ACCOUNT:log-group:$LOG_GROUP" --tags hr-v2-study=2026-10-04 >/dev/null
echo "logs: $LOG_GROUP via destination $DEST"
