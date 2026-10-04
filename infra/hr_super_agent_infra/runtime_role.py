"""The documented AgentCore Runtime execution role, shared by every runtime in the stack.

Each runtime gets its own role, scoped by its runtime name; callers add what only their
runtime needs (the orchestrator's model access, the tools server's tables).
"""

from __future__ import annotations

from aws_cdk import Stack
from aws_cdk import aws_bedrockagentcore as agentcore
from aws_cdk import aws_iam as iam
from constructs import Construct


def runtime_execution_role(
    scope: Construct, construct_id: str, runtime_name: str, description: str
) -> iam.Role:
    stack = Stack.of(scope)
    region, account = stack.region, stack.account
    role = iam.Role(
        scope,
        construct_id,
        assumed_by=iam.ServicePrincipal(
            "bedrock-agentcore.amazonaws.com",
            conditions={
                "StringEquals": {"aws:SourceAccount": account},
                "ArnLike": {"aws:SourceArn": f"arn:aws:bedrock-agentcore:{region}:{account}:*"},
            },
        ),
        description=description,
    )
    role.add_to_policy(iam.PolicyStatement(actions=["ecr:GetAuthorizationToken"], resources=["*"]))
    role.add_to_policy(
        iam.PolicyStatement(
            actions=["logs:DescribeLogGroups"],
            resources=[f"arn:aws:logs:{region}:{account}:log-group:*"],
        )
    )
    role.add_to_policy(
        iam.PolicyStatement(
            actions=[
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:DescribeLogStreams",
                "logs:PutLogEvents",
            ],
            resources=[
                f"arn:aws:logs:{region}:{account}:log-group:/aws/bedrock-agentcore/runtimes/*"
            ],
        )
    )
    # The documented execution role adds this so the runtime can let X-Ray deliver
    # spans into the agent's own log group (the unified span destination) instead of
    # the shared aws/spans group; scoped to this runtime's log groups as the docs show.
    role.add_to_policy(
        iam.PolicyStatement(
            actions=["logs:PutResourcePolicy"],
            resources=[
                f"arn:aws:logs:{region}:{account}:log-group:"
                f"/aws/bedrock-agentcore/runtimes/{runtime_name}-*"
            ],
        )
    )
    role.add_to_policy(
        iam.PolicyStatement(
            actions=[
                "xray:PutTraceSegments",
                "xray:PutTelemetryRecords",
                "xray:GetSamplingRules",
                "xray:GetSamplingTargets",
            ],
            resources=["*"],
        )
    )
    role.add_to_policy(
        iam.PolicyStatement(
            actions=["cloudwatch:PutMetricData"],
            resources=["*"],
            conditions={"StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"}},
        )
    )
    role.add_to_policy(
        iam.PolicyStatement(
            actions=[
                "bedrock-agentcore:GetWorkloadAccessToken",
                # For the on-behalf-of exchange (D47). Not ForUserId, which would mint a
                # workload token for any user id with no JWT at all.
                "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
            ],
            resources=[
                f"arn:aws:bedrock-agentcore:{region}:{account}:workload-identity-directory/default",
                f"arn:aws:bedrock-agentcore:{region}:{account}:workload-identity-directory/default/workload-identity/{runtime_name}-*",
            ],
        )
    )
    return role


# The platform version of the runtimes behind Connect, set explicitly because an update that
# omits it keeps the current one. V2 (the new AgentCore Runtime, September 2026) restores a
# fresh instance from a snapshot for every new session. With our short sessions and a new
# tools runtime session per tool call (A23), first answers were 2.7 to 4.8 s slower than on
# V1 (latency log L32, L33; aws-feedback A25). Sam keeps V2 while its cold start is studied
# (docs/handoff-runtime-v2.md). CloudFormation takes PlatformVersion and updates it in place;
# CDK 2.268's CfnRuntime has no property for it yet.
PLATFORM_VERSION = "V2"


def use_platform_version(runtime: agentcore.CfnRuntime) -> None:
    runtime.add_property_override("PlatformVersion", PLATFORM_VERSION)
