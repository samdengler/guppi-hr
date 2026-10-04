"""The HrSuperAgent stack, an agent project on the chat.dengler.io platform.

The platform stack in guppi-gpt (GuppiGpt) owns the page, sign-in, CloudFront, WAF, the edge
gateway and its per-user limits, and publishes their identifiers as /guppi/platform/* SSM
parameters (docs/proposals/platform.md there). This stack reads those parameters and holds
what is HR's own: the orchestrator runtime and its target named "hr-diy" on the platform's edge
gateway, the three sub-agent runtimes and their agents gateway, the HR tools server and its
tables, the tools gateway in front of the knowledge base and the HR tools, nightly
ingestion, the conversation log, alarms, vended log delivery, and the Dynatrace export.
Every JWT authorizer accepts the platform user pool's token, so the token the page holds
on chat.dengler.io is the one checked on every hop.

Resource ordering that matters:
  runtime -> platform gateway role policy -> "hr-diy" target on the platform edge gateway
  tools gateway -> runtime environment variables (the runtime needs the tools gateway url)
"""

from __future__ import annotations

import json
from pathlib import Path

import aws_cdk as cdk
from aws_cdk import (
    Duration,
    RemovalPolicy,
    SecretValue,
    Size,
)
from aws_cdk import (
    aws_bedrock as bedrock,
)
from aws_cdk import (
    aws_bedrockagentcore as agentcore,
)
from aws_cdk import (
    aws_cloudwatch as cloudwatch,
)
from aws_cdk import (
    aws_cloudwatch_actions as cloudwatch_actions,
)
from aws_cdk import (
    aws_ecr_assets as ecr_assets,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_kinesisfirehose as firehose,
)
from aws_cdk import (
    aws_kms as kms,
)
from aws_cdk import (
    aws_logs as logs,
)
from aws_cdk import (
    aws_logs_destinations as logs_destinations,
)
from aws_cdk import (
    aws_s3 as s3,
)
from aws_cdk import (
    aws_scheduler as scheduler,
)
from aws_cdk import (
    aws_scheduler_targets as scheduler_targets,
)
from aws_cdk import (
    aws_secretsmanager as secretsmanager,
)
from aws_cdk import (
    aws_sns as sns,
)
from aws_cdk import (
    aws_ssm as ssm,
)
from aws_cdk import (
    aws_xray as xray,
)
from constructs import Construct

from hr_super_agent_infra.hr_tools import HR_TOOL_PREFIX, TOOLS_RUNTIME_NAME, HrTools
from hr_super_agent_infra.obo import (
    AGENT_CLIENTS,
    BRIDGE_CLIENT,
    DOMAIN_SCOPES,
    POLICY_SCOPE,
    TOOLS_AUDIENCE,
    TOOLS_GATEWAY_CLIENT,
    Obo,
    agent_client,
    grant_exchange,
    policy_statements,
    workload_identity,
)
from hr_super_agent_infra.runtime_role import runtime_execution_role
from hr_super_agent_infra.sub_agents import AGENTS_GATEWAY_NAME, SubAgents, sub_agent_runtime_name

# ---- Platform contract ---------------------------------------------------------------
# The identifiers the GuppiGpt platform stack publishes for its projects, read at deploy
# time with ssm.StringParameter.value_for_string_parameter (guppi-gpt's
# docs/proposals/platform.md, "Platform contract").
PLATFORM_PARAMETER_PREFIX = "/guppi/platform"
PARAM_SITE_URL = f"{PLATFORM_PARAMETER_PREFIX}/site-url"
PARAM_EDGE_GATEWAY_ID = f"{PLATFORM_PARAMETER_PREFIX}/edge-gateway-id"
PARAM_EDGE_GATEWAY_ARN = f"{PLATFORM_PARAMETER_PREFIX}/edge-gateway-arn"
PARAM_EDGE_GATEWAY_ROLE_ARN = f"{PLATFORM_PARAMETER_PREFIX}/edge-gateway-role-arn"
PARAM_USER_POOL_CLIENT_ID = f"{PLATFORM_PARAMETER_PREFIX}/user-pool-client-id"
PARAM_JWT_DISCOVERY_URL = f"{PLATFORM_PARAMETER_PREFIX}/jwt-discovery-url"
PARAM_JWT_AUDIENCE = f"{PLATFORM_PARAMETER_PREFIX}/jwt-audience"
# What this stack publishes for the Connect bridge (connect/), which deploys after it.
AGENTS_GATEWAY_URL_PARAMETER = "/guppi-hr/agents-gateway-url"
TOOLS_GATEWAY_URL_PARAMETER = "/guppi-hr/tools-gateway-url"
# The project's name on the platform: the page is /p/hr-diy/, the manifest and extension
# are under /projects/hr-diy/, and the edge gateway target of the same name makes the
# orchestrator answer at /api/hr-diy/invocations (the platform's CloudFront function
# rewrites that to /hr-diy/invocations on the gateway). It was "hr" until 3 Oct 2026, when
# the Connect version took that name (D37).
PROJECT_NAME = "hr-diy"
TARGET_NAME = PROJECT_NAME
OIDC_DISCOVERY_SUFFIX = "/.well-known/openid-configuration"

# Transaction Search exists once per account. The GuppiGpt stack in the same account
# already owns it, so this stack creates it only with -c own_account_singletons=true, for
# an account without it (D16).
OWN_ACCOUNT_SINGLETONS_CONTEXT = "own_account_singletons"

RUNTIME_NAME = "hr_super_agent"
SESSION_HEADER = "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id"
# W3C trace context minted by the page per run (docs/proposals/traceability.md). Both the
# edge gateway target and the runtime drop request headers they were not told to keep,
# so the header is named in both allowlists. The X-Ray form (X-Amzn-Trace-Id) cannot be
# used here: the runtime allowlist refuses every x-amzn- header except its own custom
# prefix ("Pass custom headers to Amazon Bedrock AgentCore Runtime", devguide).
TRACE_HEADER = "traceparent"
TOOLS_GATEWAY_NAME = "hr-super-agent-tools"
KB_TARGET_NAME = "docs"  # tools are named docs___Retrieve and docs___AgenticRetrieveStream
KB_NAME = "hr-super-agent-docs"
CONTENT_PREFIX = "docs/"  # scripts/seed-content.sh writes docs/<source>/... to the content bucket
RETRIEVE_TOOL = f"{KB_TARGET_NAME}___Retrieve"

# The orchestrator routes and answers general questions on Sonnet; the sub-agents run on
# Haiku (D8). MODEL_ID is the sub-agents' model.
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
ORCHESTRATOR_MODEL_ID = "us.anthropic.claude-sonnet-4-6"

# Environment the runtime hands the container before the tools gateway exists. The
# container starts under opentelemetry-instrument (agent/Dockerfile); the runtime itself
# supplies the ADOT exporter settings (AGENT_OBSERVABILITY_ENABLED and the OTEL_* values,
# devguide "Add observability to your Amazon Bedrock AgentCore resources"), so only the
# app's own knobs live here. The health check is kept out of the trace stream: the
# runtime pings /ping often and a span per ping would only add log volume.
RUNTIME_BASE_ENVIRONMENT = {
    "LOG_LEVEL": "INFO",
    "OTEL_PYTHON_EXCLUDED_URLS": "/ping$",
    # Strands puts prompts, model replies, tool arguments and tool results into spans
    # unless this token is set; an empty list redacts all of them, so account numbers and
    # addresses never reach the trace backend (critique finding 5). Token counts stay.
    "OTEL_SEMCONV_STABILITY_OPT_IN": "gen_ai_unredacted_attributes=",
    # The AWS distro's own MCP instrumentation puts every tool call's arguments and result
    # (a profile, an account number) on its span, with no switch to leave them out
    # (aws-feedback A9); Strands' own execute_tool spans keep the timing, redacted.
    "OTEL_PYTHON_DISABLED_INSTRUMENTATIONS": "aws_mcp",
    # Under AgentCore the AWS distro turns this on by default, and the Bedrock
    # instrumentation then writes every prompt and reply as an OpenTelemetry log record
    # (the runtime log group's otel-rt-logs stream, aws-feedback A10).
    "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "false",
}

# The JWT claim per-user gateway limits are keyed on (as in guppi-gpt's edge gateway).
JWT_SUB_CLAIM_DIMENSION = "$.context.jwt.sub"


def per_user_rate_limit(
    scope: Construct, construct_id: str, gateway: agentcore.CfnGateway, *, per_minute: int, connections: int
) -> agentcore.CfnGatewayRateLimit:
    """Requests per minute and open connections per signed-in user on one gateway. One
    entry carries both: a gateway takes one rate limit per set of dimension keys (A2)."""
    return agentcore.CfnGatewayRateLimit(
        scope,
        construct_id,
        gateway_identifier=gateway.attr_gateway_identifier,
        description="Per-user request rate and concurrency, keyed on the JWT sub claim",
        dimension_keys=[JWT_SUB_CLAIM_DIMENSION],
        entries=[
            agentcore.CfnGatewayRateLimit.LimitEntryProperty(
                dimensions={JWT_SUB_CLAIM_DIMENSION: "*"},
                requests=[agentcore.CfnGatewayRateLimit.RateConfigProperty(rate=per_minute, period="minute")],
                connections=[agentcore.CfnGatewayRateLimit.RateConfigProperty(rate=connections, period="second")],
            )
        ],
    )


# Conversation logging (docs/proposals/conversation-logging.md). The bucket, the key, the
# HMAC secret, and the investigator role are always created; this switch decides whether the
# agent writes thread records, so turning logging on is this line plus a deploy. The page
# has its own switch in web/features.json and is flipped after this one.
CONVERSATION_LOG_ENABLED = True
CONVERSATION_RETENTION_DAYS = 30
THREADS_PREFIX = "threads/"

# Twice the expected monthly figure (design section 11).
BILLING_ALARM_USD = 50

# The platform's CloudFront behavior for /api/* gives the edge gateway origin sixty seconds
# before it gives up on a response. Half of that is the
# point past which a run is already close to being cut off by CloudFront, not merely slow.
RUNTIME_LATENCY_P90_THRESHOLD_MS = 30_000

# Vended log group naming and retention for the gateways and runtimes this stack owns
# (docs/proposals/operations.md).
VENDED_LOG_PREFIX = "/aws/vendedlogs/bedrock-agentcore"
VENDED_LOG_RETENTION = logs.RetentionDays.ONE_MONTH

# Dynatrace log ingest path for a Firehose "Dynatrace" destination, appended to the
# tenant's base URL (docs.dynatrace.com/docs/ingest-from/amazon-web-services/
# integrate-with-aws/aws-logs-ingest/lma-stream-logs-with-firehose): "use the full URL
# https://<environment_ID>.live.dynatrace.com/api/v2/logs/ingest/aws_firehose in the
# Firehose HTTP endpoint destination configuration."
DYNATRACE_LOGS_INGEST_PATH = "/api/v2/logs/ingest/aws_firehose"
# The fixed suffix of DynatraceOtlpEndpoint (docs/proposals/dynatrace.md: "no trailing
# slash, no /v1/traces suffix"), split off to recover the tenant's base URL.
DYNATRACE_OTLP_SUFFIX = "/api/v2/otlp"


def _apply_condition(construct: Construct, condition: cdk.CfnCondition) -> None:
    """Set condition on every CloudFormation resource nested under construct.

    An L2 construct can create more than one underlying resource (a role's default
    policy, a bucket's SSL-enforcement policy); node.default_child only reaches the
    first. Walking the whole subtree catches every one of them, so a conditional L2
    construct never leaves a resource behind that CloudFormation would try to create
    unconditionally.
    """
    for child in construct.node.find_all():
        if isinstance(child, cdk.CfnResource):
            child.cfn_options.condition = condition


class HrSuperAgentStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        alarm_email = cdk.CfnParameter(
            self,
            "AlarmEmail",
            type="String",
            default="",
            description="Address subscribed to the alarm topic; left blank to subscribe no one",
        )
        has_alarm_email = cdk.CfnCondition(
            self,
            "HasAlarmEmail",
            expression=cdk.Fn.condition_not(
                cdk.Fn.condition_equals(alarm_email.value_as_string, "")
            ),
        )
        investigator_principal_arn = cdk.CfnParameter(
            self,
            "InvestigatorPrincipalArn",
            type="String",
            default="",
            description=(
                "ARN allowed to assume the conversation investigator role; "
                "left blank the role trusts the account root"
            ),
        )
        has_investigator_principal = cdk.CfnCondition(
            self,
            "HasInvestigatorPrincipal",
            expression=cdk.Fn.condition_not(
                cdk.Fn.condition_equals(investigator_principal_arn.value_as_string, "")
            ),
        )

        # ---- Dynatrace ------------------------------------------------------------------
        # Both values default empty, and trace export and log forwarding stay dark while
        # either is (docs/proposals/dynatrace.md). scripts/deploy.sh supplies them from
        # 1Password.
        dynatrace_otlp_endpoint = cdk.CfnParameter(
            self,
            "DynatraceOtlpEndpoint",
            type="String",
            default="",
            description=(
                "Dynatrace OTLP base endpoint, for example "
                "https://<tenant>.live.dynatrace.com/api/v2/otlp (no trailing slash, no "
                "/v1/traces suffix); left blank to send no traces to Dynatrace"
            ),
        )
        dynatrace_api_token = cdk.CfnParameter(
            self,
            "DynatraceApiToken",
            type="String",
            no_echo=True,
            default="",
            description=(
                "Dynatrace API token with the openTelemetryTrace.ingest scope; supplied "
                "by scripts/deploy.sh from 1Password when both this and "
                "DynatraceOtlpEndpoint are set"
            ),
        )
        has_dynatrace_otlp = cdk.CfnCondition(
            self,
            "HasDynatraceOtlp",
            expression=cdk.Fn.condition_and(
                cdk.Fn.condition_not(
                    cdk.Fn.condition_equals(dynatrace_otlp_endpoint.value_as_string, "")
                ),
                cdk.Fn.condition_not(
                    cdk.Fn.condition_equals(dynatrace_api_token.value_as_string, "")
                ),
            ),
        )
        # Backend log forwarding shares the trace export parameters rather than asking for
        # the same tenant a third time: once Sam has set the OTLP endpoint and the API
        # token, both trace export and log forwarding turn on together.
        has_dynatrace_logs = cdk.CfnCondition(
            self,
            "HasDynatraceLogs",
            expression=cdk.Fn.condition_and(
                cdk.Fn.condition_not(
                    cdk.Fn.condition_equals(dynatrace_otlp_endpoint.value_as_string, "")
                ),
                cdk.Fn.condition_not(
                    cdk.Fn.condition_equals(dynatrace_api_token.value_as_string, "")
                ),
            ),
        )
        # The tenant's base URL, recovered by splitting the OTLP endpoint on its fixed
        # suffix rather than naming the same tenant in a second parameter. Log forwarding
        # appends its ingest path to it.
        dynatrace_base_url = cdk.Fn.select(
            0, cdk.Fn.split(DYNATRACE_OTLP_SUFFIX, dynatrace_otlp_endpoint.value_as_string)
        )

        # ---- Transaction Search ----------------------------------------------------------
        # Account-wide, so created only with own_account_singletons: the instrumented
        # container sends spans to CloudWatch's OTLP endpoint, which answers 400 until the
        # trace segment destination is CloudWatch Logs (observed 3 Sep 2026). The resource
        # policy is the one the AgentCore observability guide gives for X-Ray to write the
        # span log groups; the config resource flips the destination and indexes 1 percent.
        own_account_singletons = self.node.try_get_context(
            OWN_ACCOUNT_SINGLETONS_CONTEXT
        ) in (True, "true")
        if own_account_singletons:
            span_policy = logs.CfnResourcePolicy(
                self,
                "TransactionSearchLogsPolicy",
                policy_name="HrSuperAgentTransactionSearchXRayAccess",
                policy_document=json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Sid": "TransactionSearchXRayAccess",
                                "Effect": "Allow",
                                "Principal": {"Service": "xray.amazonaws.com"},
                                "Action": "logs:PutLogEvents",
                                "Resource": [
                                    f"arn:aws:logs:{self.region}:{self.account}:log-group:aws/spans:*",
                                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/application-signals/data:*",
                                ],
                                "Condition": {
                                    "ArnLike": {
                                        "aws:SourceArn": (
                                            f"arn:aws:xray:{self.region}:{self.account}:*"
                                        )
                                    },
                                    "StringEquals": {"aws:SourceAccount": self.account},
                                },
                            }
                        ],
                    }
                ),
            )
            transaction_search = xray.CfnTransactionSearchConfig(
                self, "TransactionSearch", indexing_percentage=1
            )
            transaction_search.node.add_dependency(span_policy)

        # ---- Alerting --------------------------------------------------------------------
        alarm_topic = sns.Topic(self, "AlarmTopic", display_name="HR Super Agent alarms")
        email_subscription = sns.CfnSubscription(
            self,
            "AlarmEmailSubscription",
            protocol="email",
            topic_arn=alarm_topic.topic_arn,
            endpoint=alarm_email.value_as_string,
        )
        email_subscription.cfn_options.condition = has_alarm_email

        # Billing metrics exist only in us-east-1, which is also where this stack deploys.
        billing_alarm = cloudwatch.Alarm(
            self,
            "BillingAlarm",
            alarm_description="Estimated month-to-date charges crossed the cost limit",
            metric=cloudwatch.Metric(
                namespace="AWS/Billing",
                metric_name="EstimatedCharges",
                dimensions_map={"Currency": "USD"},
                region="us-east-1",
                statistic="Maximum",
                period=Duration.hours(6),
            ),
            threshold=BILLING_ALARM_USD,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        billing_alarm.add_alarm_action(cloudwatch_actions.SnsAction(alarm_topic))

        # ---- Platform -------------------------------------------------------------------
        # The platform's issuer (Okta since D46): every authorizer below accepts the token
        # the page holds on chat.dengler.io by its audience, and the HR tools server verifies
        # the same token against the same issuer and audience (D19).
        discovery_url = ssm.StringParameter.value_for_string_parameter(
            self, PARAM_JWT_DISCOVERY_URL
        )
        jwt_audience = [ssm.StringParameter.value_for_string_parameter(self, PARAM_JWT_AUDIENCE)]
        token_issuer = cdk.Fn.select(0, cdk.Fn.split(OIDC_DISCOVERY_SUFFIX, discovery_url))
        platform_gateway_id = ssm.StringParameter.value_for_string_parameter(
            self, PARAM_EDGE_GATEWAY_ID
        )
        platform_gateway_role = iam.Role.from_role_arn(
            self,
            "PlatformGatewayRole",
            ssm.StringParameter.value_for_string_parameter(self, PARAM_EDGE_GATEWAY_ROLE_ARN),
        )
        site_url = ssm.StringParameter.value_for_string_parameter(self, PARAM_SITE_URL)
        # The on-behalf-of issuer and its credential providers (D47), from guppi-gpt.
        obo = Obo.read(self)

        # ---- Agent image ---------------------------------------------------------------
        image_uri = self.node.try_get_context("image_uri")
        runtime_role = self._runtime_role()
        tools_role = runtime_execution_role(
            self, "ToolsRuntimeRole", TOOLS_RUNTIME_NAME, "Execution role for the HR tools runtime"
        )
        if image_uri is None:
            # The context is the repository root so agent/Dockerfile can read uv.lock;
            # .dockerignore at the root keeps the context and the asset hash to the agent
            # files, the lockfile, and the workspace pyprojects.
            repo_root = Path(__file__).resolve().parents[2]
            asset = ecr_assets.DockerImageAsset(
                self,
                "AgentImage",
                directory=str(repo_root),
                file="agent/Dockerfile",
                ignore_mode=cdk.IgnoreMode.DOCKER,
                platform=ecr_assets.Platform.LINUX_ARM64,
                # The platform kit is a git dependency on the private guppi-gpt repository;
                # the build reads a GitHub token from this environment variable as a
                # BuildKit secret, never a build argument (D29). scripts/deploy.sh sets it.
                build_secrets={"github_token": "env=HR_GITHUB_TOKEN"},
            )
            image_uri = asset.image_uri

            def grant_image(role: iam.Role) -> None:
                asset.repository.grant_pull(role)
        else:

            def grant_image(role: iam.Role) -> None:
                role.add_to_policy(
                    iam.PolicyStatement(
                        actions=["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"],
                        resources=[f"arn:aws:ecr:{self.region}:{self.account}:repository/*"],
                    )
                )

        for role in (runtime_role, tools_role):
            grant_image(role)

        # ---- Runtime -------------------------------------------------------------------
        protocol = self.node.try_get_context("runtime_protocol") or "AGUI"
        runtime = agentcore.CfnRuntime(
            self,
            "Runtime",
            agent_runtime_name=RUNTIME_NAME,
            description="HR Super Agent agent (AG-UI over SSE)",
            role_arn=runtime_role.role_arn,
            agent_runtime_artifact=agentcore.CfnRuntime.AgentRuntimeArtifactProperty(
                container_configuration=agentcore.CfnRuntime.ContainerConfigurationProperty(
                    container_uri=image_uri
                )
            ),
            network_configuration=agentcore.CfnRuntime.NetworkConfigurationProperty(
                network_mode="PUBLIC"
            ),
            protocol_configuration=protocol,
            # Without this allowlist the runtime validates the bearer and drops it; the
            # container then has no token to present to the tools gateway (observed 3 Sep
            # 2026 as RUN_ERROR UNAUTHORIZED on the first run of the real agent).
            request_header_configuration=agentcore.CfnRuntime.RequestHeaderConfigurationProperty(
                request_header_allowlist=["Authorization", TRACE_HEADER]
            ),
            authorizer_configuration=agentcore.CfnRuntime.AuthorizerConfigurationProperty(
                custom_jwt_authorizer=agentcore.CfnRuntime.CustomJWTAuthorizerConfigurationProperty(
                    discovery_url=discovery_url,
                    allowed_audience=jwt_audience,
                    # Binding the runtime to the platform's gateway is off by default. With it
                    # on, the runtime demands a transaction token, and the gateway only supplies
                    # one when it signs the request itself (GATEWAY_IAM_ROLE), which a JWT
                    # runtime then rejects as an authorization method mismatch. Token
                    # passthrough forwards the user JWT with no transaction token, so the
                    # two settings cannot be combined today (observed 2 Sep 2026).
                    allowed_workload_configuration=(
                        agentcore.CfnRuntime.AllowedWorkloadConfigurationProperty(
                            hosting_environments=[
                                agentcore.CfnRuntime.HostingEnvironmentProperty(
                                    arn=ssm.StringParameter.value_for_string_parameter(
                                        self, PARAM_EDGE_GATEWAY_ARN
                                    )
                                )
                            ]
                        )
                        if self.node.try_get_context("bind_runtime_to_gateway")
                        else None
                    ),
                )
            ),
            # TOOLS_GATEWAY_URL, MODEL_ID, and RETRIEVE_TOOL are set below, once the tools
            # gateway exists; it is defined later in this file.
            environment_variables=dict(RUNTIME_BASE_ENVIRONMENT),
        )
        # role_arn alone orders the runtime after the role but not after its DefaultPolicy,
        # and AgentCore checks the ECR pull grants at create time; a fresh stack failed with
        # "Access denied while validating ECR URI" (observed 28 Sep 2026).
        runtime.node.add_dependency(runtime_role)

        # The platform's edge gateway invokes this runtime with the gateway's own role, so
        # the grant is attached to that role, imported by ARN; the policy is this stack's
        # and leaves with it.
        invoke_policy = iam.Policy(
            self,
            "PlatformGatewayInvokePolicy",
            roles=[platform_gateway_role],
            statements=[
                iam.PolicyStatement(
                    actions=["bedrock-agentcore:InvokeAgentRuntime"],
                    resources=[
                        runtime.attr_agent_runtime_arn,
                        f"{runtime.attr_agent_runtime_arn}/runtime-endpoint/*",
                    ],
                )
            ],
        )

        # Built as the platform builds its own "api" target: the runtime by ARN, the user's
        # JWT passed through, and the session and trace headers allowed.
        target = agentcore.CfnGatewayTarget(
            self,
            "PlatformTarget",
            gateway_identifier=platform_gateway_id,
            name=TARGET_NAME,
            description="HR Super Agent orchestrator, token passthrough",
            target_configuration=agentcore.CfnGatewayTarget.TargetConfigurationProperty(
                http=agentcore.CfnGatewayTarget.HttpTargetConfigurationProperty(
                    agentcore_runtime=agentcore.CfnGatewayTarget.RuntimeTargetConfigurationProperty(
                        arn=runtime.attr_agent_runtime_arn,
                        qualifier="DEFAULT",
                    )
                )
            ),
            credential_provider_configurations=[
                agentcore.CfnGatewayTarget.CredentialProviderConfigurationProperty(
                    credential_provider_type=(
                        self.node.try_get_context("target_credentials") or "JWT_PASSTHROUGH"
                    )
                )
            ],
            metadata_configuration=agentcore.CfnGatewayTarget.MetadataConfigurationProperty(
                allowed_request_headers=[SESSION_HEADER, TRACE_HEADER]
            ),
        )
        target.node.add_dependency(invoke_policy)

        # ---- Knowledge base ------------------------------------------------------------
        content_bucket = s3.Bucket(
            self,
            "ContentBucket",
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN,
        )
        kb_role = iam.Role(
            self,
            "KnowledgeBaseRole",
            assumed_by=iam.ServicePrincipal(
                "bedrock.amazonaws.com",
                conditions={
                    "StringEquals": {"aws:SourceAccount": self.account},
                    "ArnLike": {
                        "aws:SourceArn": (
                            f"arn:aws:bedrock:{self.region}:{self.account}:knowledge-base/*"
                        )
                    },
                },
            ),
            description="Lets the managed knowledge base list and read the content bucket",
        )
        content_bucket.grant_read(kb_role)
        knowledge_base = bedrock.CfnKnowledgeBase(
            self,
            "KnowledgeBase",
            name=KB_NAME,
            description="Synthetic HR policy documents (D5)",
            role_arn=kb_role.role_arn,
            knowledge_base_configuration=bedrock.CfnKnowledgeBase.KnowledgeBaseConfigurationProperty(
                type="MANAGED",
                managed_knowledge_base_configuration=(
                    bedrock.CfnKnowledgeBase.ManagedKnowledgeBaseConfigurationProperty(
                        embedding_model_type="MANAGED"
                    )
                ),
            ),
        )
        knowledge_base.node.add_dependency(kb_role)
        # Deletion protection is off so that a seed run that renames or removes many files
        # is mirrored by the next ingestion instead of being skipped past a threshold.
        data_source = bedrock.CfnDataSource(
            self,
            "ContentSource",
            name="content-bucket",
            description="Markdown synced by scripts/seed-content.sh",
            knowledge_base_id=knowledge_base.attr_knowledge_base_id,
            data_deletion_policy="DELETE",
            data_source_configuration=bedrock.CfnDataSource.DataSourceConfigurationProperty(
                type="MANAGED_KNOWLEDGE_BASE_CONNECTOR",
                managed_knowledge_base_connector_configuration=(
                    bedrock.CfnDataSource.ManagedKnowledgeBaseConnectorConfigurationProperty(
                        connector_parameters={
                            "type": "S3",
                            "version": "1",
                            "connectionConfiguration": {
                                "bucketName": content_bucket.bucket_name,
                                "bucketOwnerAccountId": self.account,
                            },
                            "filterConfiguration": {"inclusionPrefixes": [CONTENT_PREFIX]},
                        },
                        deletion_protection_configuration=(
                            bedrock.CfnDataSource.DeletionProtectionConfigurationProperty(
                                deletion_protection_status="DISABLED"
                            )
                        ),
                    )
                ),
            ),
        )

        # Nightly incremental ingestion as a scheduler universal target: the SDK call is
        # scheduler configuration, with no function between the schedule and the API.
        ingestion = scheduler.Schedule(
            self,
            "NightlyIngestion",
            description="Incremental ingestion of the content bucket into the knowledge base",
            schedule=scheduler.ScheduleExpression.cron(minute="0", hour="9"),
            target=scheduler_targets.Universal(
                service="bedrockagent",  # SDK client name: aws-sdk:bedrockagent:startIngestionJob
                action="startIngestionJob",
                input=scheduler.ScheduleTargetInput.from_object(
                    {
                        "KnowledgeBaseId": knowledge_base.attr_knowledge_base_id,
                        "DataSourceId": data_source.attr_data_source_id,
                    }
                ),
                policy_statements=[
                    iam.PolicyStatement(
                        actions=["bedrock:StartIngestionJob"],
                        resources=[knowledge_base.attr_knowledge_base_arn],
                    )
                ],
            ),
        )
        ingestion_alarm = cloudwatch.Alarm(
            self,
            "IngestionScheduleErrors",
            alarm_description="The nightly StartIngestionJob call failed",
            metric=scheduler.Schedule.metric_all_errors(period=Duration.days(1)),
            threshold=1,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        ingestion_alarm.add_alarm_action(cloudwatch_actions.SnsAction(alarm_topic))

        # ---- Conversation log ------------------------------------------------------------
        # One JSON object per thread under threads/, written by the runtime after a run's
        # stream ends. Encryption is SSE-KMS with a stack-created key rather than SSE-S3: the
        # key is a second gate, so a principal holding s3:GetObject but no kms:Decrypt on this
        # key reads nothing, and every decrypt is a CloudTrail event. The investigator path
        # costs one grant for that, which is cheaper than the gate is worth.
        conversation_key = kms.Key(
            self,
            "ConversationLogKey",
            description="Encrypts the HR Super Agent conversation log bucket",
            enable_key_rotation=True,
            alias="hr-super-agent-conversations",
            removal_policy=RemovalPolicy.RETAIN,
        )
        conversation_bucket = s3.Bucket(
            self,
            "ConversationLogBucket",
            versioned=True,  # one version per run, which is the turn-by-turn history
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.KMS,
            encryption_key=conversation_key,
            bucket_key_enabled=True,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="ExpireThreadRecords",
                    prefix=THREADS_PREFIX,
                    expiration=Duration.days(CONVERSATION_RETENTION_DAYS),
                    noncurrent_version_expiration=Duration.days(CONVERSATION_RETENTION_DAYS),
                    abort_incomplete_multipart_upload_after=Duration.days(1),
                )
            ],
        )
        # The secret value is the HMAC key itself, with no JSON template around it, so the
        # agent uses the bytes of the secret string as they come back.
        conversation_secret = secretsmanager.Secret(
            self,
            "ConversationLogKeySecret",
            description="HMAC key that turns a Cognito sub into the pseudonym in thread records",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                password_length=32, exclude_punctuation=True
            ),
        )

        # The investigator role is the only principal outside the runtime that can read a
        # thread record, and the only one that can read the key and list the user pool, which
        # is what re-identification takes. Trust is the account root by default, so any
        # principal in the account holding sts:AssumeRole can assume it; a non-blank
        # InvestigatorPrincipalArn narrows it to that one ARN.
        investigator_role = iam.Role(
            self,
            "ConversationInvestigatorRole",
            assumed_by=iam.AccountRootPrincipal(),
            max_session_duration=Duration.hours(1),
            description="Reads conversation records and resolves a subject to a Cognito user",
        )
        cfn_investigator_role = investigator_role.node.default_child
        assert isinstance(cfn_investigator_role, iam.CfnRole)
        cfn_investigator_role.add_property_override(
            "AssumeRolePolicyDocument.Statement.0.Principal.AWS",
            cdk.Fn.condition_if(
                has_investigator_principal.logical_id,
                investigator_principal_arn.value_as_string,
                f"arn:aws:iam::{self.account}:root",
            ),
        )
        thread_objects = conversation_bucket.arn_for_objects(f"{THREADS_PREFIX}*")
        investigator_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject", "s3:GetObjectVersion"], resources=[thread_objects]
            )
        )
        investigator_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:ListBucket", "s3:ListBucketVersions"],
                resources=[conversation_bucket.bucket_arn],
            )
        )
        conversation_key.grant(investigator_role, "kms:Decrypt")
        investigator_role.add_to_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                resources=[conversation_secret.secret_arn],
            )
        )
        # The subjects in thread records are Okta user ids since D46; resolving one means
        # Okta's users API with the admin token, not an AWS permission (D31 superseded).

        # The runtime reads and writes single objects by key, and no delete. ListBucket is
        # granted only under the threads/ prefix: without it S3 answers a GET on a missing
        # key with 403 instead of 404 (observed on the first run, 5 Sep 2026), so the
        # first write of every thread failed.
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject", "s3:PutObject"], resources=[thread_objects]
            )
        )
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:ListBucket"],
                resources=[conversation_bucket.bucket_arn],
                conditions={"StringLike": {"s3:prefix": [f"{THREADS_PREFIX}*"]}},
            )
        )
        conversation_key.grant(runtime_role, "kms:Decrypt", "kms:GenerateDataKey")
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                resources=[conversation_secret.secret_arn],
            )
        )

        conversation_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="RuntimeThreadRecords",
                principals=[iam.ArnPrincipal(runtime_role.role_arn)],
                actions=["s3:GetObject", "s3:PutObject"],
                resources=[thread_objects],
            )
        )
        conversation_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="RuntimeThreadListing",
                principals=[iam.ArnPrincipal(runtime_role.role_arn)],
                actions=["s3:ListBucket"],
                resources=[conversation_bucket.bucket_arn],
                conditions={"StringLike": {"s3:prefix": [f"{THREADS_PREFIX}*"]}},
            )
        )
        conversation_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="InvestigatorReads",
                principals=[iam.ArnPrincipal(investigator_role.role_arn)],
                actions=[
                    "s3:GetObject",
                    "s3:GetObjectVersion",
                    "s3:ListBucket",
                    "s3:ListBucketVersions",
                ],
                resources=[conversation_bucket.bucket_arn, thread_objects],
            )
        )
        # The deny covers reads only, so an administrator keeps the ability to repair the
        # policy and to delete objects for a data subject deletion.
        conversation_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="DenyOtherReaders",
                effect=iam.Effect.DENY,
                principals=[iam.AnyPrincipal()],
                actions=["s3:GetObject", "s3:GetObjectVersion"],
                resources=[thread_objects],
                conditions={
                    "StringNotEquals": {
                        "aws:PrincipalArn": [
                            runtime_role.role_arn,
                            investigator_role.role_arn,
                        ]
                    }
                },
            )
        )

        # ---- Tools gateway -------------------------------------------------------------
        tools_gateway_role = iam.Role(
            self,
            "ToolsGatewayRole",
            assumed_by=iam.ServicePrincipal(
                "bedrock-agentcore.amazonaws.com",
                conditions={
                    "StringEquals": {"aws:SourceAccount": self.account},
                    "ArnLike": {
                        "aws:SourceArn": (
                            f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:gateway/*"
                        )
                    },
                },
            ),
            description="Lets the tools gateway retrieve from the HR Super Agent knowledge base",
        )
        tools_gateway_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:GetKnowledgeBase", "bedrock:Retrieve"],
                resources=[knowledge_base.attr_knowledge_base_arn],
            )
        )
        # AgenticRetrieveStream is not resource-scoped; the gateway target validation asks for it.
        tools_gateway_role.add_to_policy(
            iam.PolicyStatement(actions=["bedrock:AgenticRetrieveStream"], resources=["*"])
        )
        # Gateway Policy on the tools gateway (D47, A15): Cedar rules on the caller token's
        # scopes; a tool no rule permits is refused, and tools/list shows a caller only its own.
        tools_policy_engine = agentcore.CfnPolicyEngine(
            self,
            "ToolsPolicyEngine",
            name="hr_super_agent_tools_policy",
            description="Which HR tools each hop token may call, by scope (D47)",
        )
        tools_gateway_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock-agentcore:GetPolicyEngine"],
                resources=[tools_policy_engine.attr_policy_engine_arn],
            )
        )
        tools_gateway_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock-agentcore:AuthorizeAction", "bedrock-agentcore:PartiallyAuthorizeActions"],
                resources=[
                    tools_policy_engine.attr_policy_engine_arn,
                    f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:gateway/{TOOLS_GATEWAY_NAME}-*",
                ],
            )
        )
        tools_gateway = agentcore.CfnGateway(
            self,
            "ToolsGateway",
            name=TOOLS_GATEWAY_NAME,
            description="HR Super Agent tools: knowledge base and HR tools, hop tokens inbound, Policy per tool",
            role_arn=tools_gateway_role.role_arn,
            protocol_type="MCP",
            authorizer_type="CUSTOM_JWT",
            # A caller's tools token only (D47): the canvas's from the bridge's client, or a
            # sub-agent's for its domain. Every one holds hr.tools.policy; Gateway Policy
            # decides each tool from the rest of its scopes.
            authorizer_configuration=agentcore.CfnGateway.AuthorizerConfigurationProperty(
                custom_jwt_authorizer=agentcore.CfnGateway.CustomJWTAuthorizerConfigurationProperty(
                    discovery_url=obo.discovery_url,
                    allowed_audience=[TOOLS_AUDIENCE],
                    allowed_clients=[BRIDGE_CLIENT, *AGENT_CLIENTS],
                    allowed_scopes=[POLICY_SCOPE],
                )
            ),
            policy_engine_configuration=agentcore.CfnGateway.GatewayPolicyEngineConfigurationProperty(
                arn=tools_policy_engine.attr_policy_engine_arn, mode="ENFORCE"
            ),
            exception_level="DEBUG",
        )
        # Attaching the policy engine checks the role's GetPolicyEngine grant, so the gateway
        # waits for the role's whole policy, not only the role (observed 3 Oct 2026).
        tools_gateway.node.add_dependency(tools_gateway_role)
        # Per-user limits on both HR gateways (critique finding 17): the edge gateway's
        # limits never reach a caller that calls these gateways straight with its token.
        # A sub-agent keeps an MCP session per conversation, and a warm start opens three
        # at once, so the tools gateway allows more connections than the agents gateway.
        per_user_rate_limit(self, "ToolsGatewayPerUserRateLimit", tools_gateway, per_minute=240, connections=20)
        kb_target = agentcore.CfnGatewayTarget(
            self,
            "KnowledgeBaseTarget",
            gateway_identifier=tools_gateway.attr_gateway_identifier,
            name=KB_TARGET_NAME,
            description="HR Super Agent HR policy knowledge base",
            target_configuration=agentcore.CfnGatewayTarget.TargetConfigurationProperty(
                mcp=agentcore.CfnGatewayTarget.McpTargetConfigurationProperty(
                    connector=agentcore.CfnGatewayTarget.ConnectorTargetConfigurationProperty(
                        source=agentcore.CfnGatewayTarget.ConnectorSourceProperty(
                            connector_id="bedrock-knowledge-bases"
                        ),
                        configurations=[
                            agentcore.CfnGatewayTarget.ConnectorConfigurationProperty(
                                name="Retrieve",
                                description=(
                                    "Search the HR policy documents (pass travel, pay, direct "
                                    "deposit, profile changes, time off, benefits, contacting HR) "
                                    "and return the most relevant passages."
                                ),
                                # No retrievalConfiguration default: CloudFormation stores the
                                # JSON numbers in ParameterValues as strings, and the knowledge
                                # base rejects a string numberOfResults. Service defaults apply.
                                parameter_values={
                                    "knowledgeBaseId": knowledge_base.attr_knowledge_base_id,
                                },
                            ),
                            agentcore.CfnGatewayTarget.ConnectorConfigurationProperty(
                                name="AgenticRetrieveStream",
                                parameter_values={
                                    "retrievers": [
                                        {
                                            "description": "HR policy documents",
                                            "configuration": {
                                                "knowledgeBase": {
                                                    "knowledgeBaseId": (
                                                        knowledge_base.attr_knowledge_base_id
                                                    )
                                                }
                                            },
                                        }
                                    ],
                                    "agenticRetrieveConfiguration": {
                                        "foundationModelType": "MANAGED",
                                        "rerankingModelType": "MANAGED",
                                    },
                                },
                            ),
                        ],
                    )
                )
            ),
            credential_provider_configurations=[
                agentcore.CfnGatewayTarget.CredentialProviderConfigurationProperty(
                    credential_provider_type="GATEWAY_IAM_ROLE"
                )
            ],
        )
        kb_target.node.add_dependency(tools_gateway_role)
        kb_target.node.add_dependency(data_source)

        # Dynatrace trace export, shipped dark. The runtime's own OTEL_EXPORTER_OTLP_*
        # values are injected by the AgentCore platform when AGENT_OBSERVABILITY_ENABLED
        # is set (see RUNTIME_BASE_ENVIRONMENT above); OTEL's env var scheme carries only
        # one endpoint per signal, so this does not add a second export destination
        # beside CloudWatch, it redirects trace export to Dynatrace once both parameters
        # are set (docs/proposals/dynatrace.md covers the tradeoff and what was not
        # possible to confirm without a real deploy). Fn::If's AWS::NoValue branch omits
        # the two keys entirely while DynatraceOtlpEndpoint or DynatraceApiToken is
        # blank, which is the default, so the environment the container sees today does
        # not change until Sam supplies both.
        dynatrace_traces_endpoint = cdk.Token.as_string(
            cdk.Fn.condition_if(
                has_dynatrace_otlp.logical_id,
                f"{dynatrace_otlp_endpoint.value_as_string}/v1/traces",
                cdk.Aws.NO_VALUE,
            )
        )
        # The API token reaches every HR runtime through Secrets Manager, never its
        # environment, where GetAgentRuntime would show it to anyone allowed to read the
        # runtime (D35); since D36 the tools server and the sub-agents export there too, so
        # one trace covers the orchestrator, the sub-agent it delegates to, and the tools. The secret always exists so the role's grant has something to
        # name; its value is the token once both parameters are set. The image's launcher
        # (hr_agent.otel_headers) reads it and sets OTEL_EXPORTER_OTLP_TRACES_HEADERS inside
        # the process before opentelemetry-instrument starts.
        dynatrace_token_secret = secretsmanager.Secret(
            self,
            "DynatraceTokenSecret",
            description="Dynatrace API token for the HR runtimes' trace export (D35, D36)",
            secret_string_value=SecretValue.unsafe_plain_text(
                cdk.Token.as_string(
                    cdk.Fn.condition_if(
                        has_dynatrace_otlp.logical_id,
                        dynatrace_api_token.value_as_string,
                        "unset",
                    )
                )
            ),
        )
        dynatrace_token_secret.grant_read(runtime_role)
        dynatrace_token_secret.grant_read(tools_role)
        dynatrace_token_secret_arn = cdk.Token.as_string(
            cdk.Fn.condition_if(
                has_dynatrace_otlp.logical_id,
                dynatrace_token_secret.secret_arn,
                cdk.Aws.NO_VALUE,
            )
        )

        trace_environment = {
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": dynatrace_traces_endpoint,
            "DYNATRACE_TOKEN_SECRET_ARN": dynatrace_token_secret_arn,
        }

        # ---- HR tools (phase 2) ----------------------------------------------------------
        hr_tools = HrTools(
            self,
            "HrTools",
            image_uri=image_uri,
            role=tools_role,
            gateway=tools_gateway,
            gateway_role=tools_gateway_role,
            gateway_name=TOOLS_GATEWAY_NAME,
            obo_discovery_url=obo.discovery_url,
            obo_issuer=obo.issuer,
            tools_gateway_provider_arn=obo.provider_arn(self, TOOLS_GATEWAY_CLIENT),
            tools_gateway_secret_arn=obo.secret_arn(self, TOOLS_GATEWAY_CLIENT),
            base_environment={**RUNTIME_BASE_ENVIRONMENT, **trace_environment},
        )
        for name, statement in policy_statements(tools_gateway.attr_gateway_arn).items():
            policy = agentcore.CfnPolicy(
                self,
                f"ToolsPolicy{''.join(part.capitalize() for part in name.split('_'))}",
                name=f"hr_{name}",
                policy_engine_id=tools_policy_engine.attr_policy_engine_id,
                definition=agentcore.CfnPolicy.PolicyDefinitionProperty(
                    cedar=agentcore.CfnPolicy.CedarPolicyProperty(statement=statement)
                ),
                validation_mode="FAIL_ON_ANY_FINDINGS",
            )
            # Validation checks the actions against the gateway's tools, so both targets first.
            policy.node.add_dependency(hr_tools.target, kb_target)

        # ---- Sub-agents (phase 3) --------------------------------------------------------
        sub_agents = SubAgents(
            self,
            "SubAgents",
            image_uri=image_uri,
            grant_image=grant_image,
            obo_discovery_url=obo.discovery_url,
            provider_names={d: obo.provider_name(self, agent_client(d)) for d in DOMAIN_SCOPES},
            provider_arns={d: obo.provider_arn(self, agent_client(d)) for d in DOMAIN_SCOPES},
            secret_arns={d: obo.secret_arn(self, agent_client(d)) for d in DOMAIN_SCOPES},
            tools_gateway_url=tools_gateway.attr_gateway_url,
            model_id=MODEL_ID,
            hr_tool_prefix=HR_TOOL_PREFIX,
            base_environment={**RUNTIME_BASE_ENVIRONMENT, **trace_environment},
            session_header=SESSION_HEADER,
            trace_header=TRACE_HEADER,
        )
        for sub_agent_role in sub_agents.roles.values():
            dynatrace_token_secret.grant_read(sub_agent_role)
        per_user_rate_limit(self, "AgentsGatewayPerUserRateLimit", sub_agents.gateway, per_minute=120, connections=10)
        cdk.CfnOutput(self, "AgentsGatewayUrl", value=sub_agents.gateway.attr_gateway_url)
        # The Connect bridge's warm start calls each sub-agent through this gateway (D41).
        ssm.StringParameter(
            self,
            "AgentsGatewayUrlParameter",
            parameter_name=AGENTS_GATEWAY_URL_PARAMETER,
            string_value=sub_agents.gateway.attr_gateway_url,
            description="The HR agents gateway URL, for the Connect bridge's warm start",
        )

        orchestrator_workload = workload_identity(self, "OrchestratorWorkload", RUNTIME_NAME)
        grant_exchange(
            runtime_role, obo.provider_arn(self, BRIDGE_CLIENT), obo.secret_arn(self, BRIDGE_CLIENT), orchestrator_workload
        )

        # The tools gateway now exists, so the runtime's environment can point at it.
        runtime.environment_variables = {
            **RUNTIME_BASE_ENVIRONMENT,
            "TOOLS_GATEWAY_URL": tools_gateway.attr_gateway_url,
            "MODEL_ID": ORCHESTRATOR_MODEL_ID,
            "ROUTER_MODEL_ID": ORCHESTRATOR_MODEL_ID,
            "RETRIEVE_TOOL": RETRIEVE_TOOL,
            "ORCHESTRATOR_EXTRA_TOOLS": f"{HR_TOOL_PREFIX}open_ticket",
            "AGENTS_GATEWAY_URL": sub_agents.gateway.attr_gateway_url,
            # The orchestrator trades the employee's Okta token for the agents token and a
            # policy-only tools token through the bridge's client (D47).
            "OBO_PROVIDER": obo.provider_name(self, BRIDGE_CLIENT),
            "OBO_WORKLOAD": orchestrator_workload.name,
            "CONVERSATION_LOG_ENABLED": "true" if CONVERSATION_LOG_ENABLED else "false",
            "CONVERSATION_LOG_BUCKET": conversation_bucket.bucket_name,
            "CONVERSATION_LOG_KEY_SECRET_ARN": conversation_secret.secret_arn,
            **trace_environment,
        }

        # ---- Operational alarms ----------------------------------------------------------
        # docs/proposals/operations.md records the thresholds and why. Every metric here is
        # in the AWS/Bedrock-AgentCore namespace with a "Resource" dimension carrying the
        # resource's own ARN; the gateway devguide page states that dimension for gateway
        # invocation metrics (observability-gateway-metrics.html), and the runtime page
        # (observability-runtime-metrics.html) lists the same metric names without a
        # dimensions table, so using "Resource" there too is an assumption, not something
        # the docs state outright (the same caveat the WafBlocks alarms above already carry
        # for GatewayId).
        def _resource_error_alarm(construct_id: str, description: str, resource_arn: str) -> None:
            alarm = cloudwatch.Alarm(
                self,
                construct_id,
                alarm_description=description,
                metric=cloudwatch.Metric(
                    namespace="AWS/Bedrock-AgentCore",
                    metric_name="SystemErrors",
                    dimensions_map={"Resource": resource_arn},
                    statistic="Sum",
                    period=Duration.minutes(5),
                ),
                threshold=1,
                evaluation_periods=1,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            )
            alarm.add_alarm_action(cloudwatch_actions.SnsAction(alarm_topic))

        _resource_error_alarm(
            "ToolsGateway5xxAlarm",
            "5xx (SystemErrors) on the HR Super Agent tools gateway crossed zero",
            tools_gateway.attr_gateway_arn,
        )
        _resource_error_alarm(
            "Runtime5xxAlarm",
            "5xx (SystemErrors) on the HR Super Agent runtime crossed zero",
            runtime.attr_agent_runtime_arn,
        )
        # The phase 2 and 3 resources get the same 5xx alarm (phase 6).
        _resource_error_alarm(
            "ToolsRuntime5xxAlarm",
            "5xx (SystemErrors) on the HR tools runtime crossed zero",
            hr_tools.runtime.attr_agent_runtime_arn,
        )
        _resource_error_alarm(
            "AgentsGateway5xxAlarm",
            "5xx (SystemErrors) on the HR Super Agent agents gateway crossed zero",
            sub_agents.gateway.attr_gateway_arn,
        )
        for name, sub_agent_runtime in sub_agents.runtimes.items():
            _resource_error_alarm(
                f"{name.capitalize()}Runtime5xxAlarm",
                f"5xx (SystemErrors) on the HR {name} sub-agent runtime crossed zero",
                sub_agent_runtime.attr_agent_runtime_arn,
            )


        # Runtime "Latency" is end-to-end (receipt to final token), the same quantity the
        # gateway table calls "Duration". Threshold: RUNTIME_LATENCY_P90_THRESHOLD_MS above.
        runtime_latency_p90_alarm = cloudwatch.Alarm(
            self,
            "RuntimeLatencyP90Alarm",
            alarm_description=(
                "HR Super Agent runtime invocation latency p90 crossed "
                f"{RUNTIME_LATENCY_P90_THRESHOLD_MS} ms"
            ),
            metric=cloudwatch.Metric(
                namespace="AWS/Bedrock-AgentCore",
                metric_name="Latency",
                dimensions_map={"Resource": runtime.attr_agent_runtime_arn},
                statistic="p90",
                period=Duration.minutes(5),
            ),
            threshold=RUNTIME_LATENCY_P90_THRESHOLD_MS,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        runtime_latency_p90_alarm.add_alarm_action(cloudwatch_actions.SnsAction(alarm_topic))

        # Bedrock throttling for the one inference profile the runtime calls.
        bedrock_throttling_alarm = cloudwatch.Alarm(
            self,
            "BedrockThrottlingAlarm",
            alarm_description=(
                "Bedrock InvocationThrottles for the HR Super Agent model crossed zero"
            ),
            metric=cloudwatch.Metric(
                namespace="AWS/Bedrock",
                metric_name="InvocationThrottles",
                dimensions_map={"ModelId": MODEL_ID},
                statistic="Sum",
                period=Duration.minutes(5),
            ),
            threshold=1,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        bedrock_throttling_alarm.add_alarm_action(cloudwatch_actions.SnsAction(alarm_topic))

        # ---- Vended log delivery ----------------------------------------------------------
        # AWS::Logs::DeliverySource, AWS::Logs::DeliveryDestination, and AWS::Logs::Delivery
        # (the CDK L1s below) wire each resource's APPLICATION_LOGS into a CloudWatch Logs
        # group under VENDED_LOG_PREFIX. The gateways' TRACES log type is not delivered here:
        # CloudFormation rejected a CloudWatch Logs destination for it on 4 Sep 2026 with
        # "Invalid destination type provided for this resource and log type", so gateway
        # traces would need an X-Ray destination, and the runtime's spans already reach
        # Transaction Search. The resource policy below
        # grants delivery.logs.amazonaws.com permission to write to the log groups; without
        # it, only a principal with logs:PutResourcePolicy on the log group gets one created
        # automatically the first time delivery starts (AWS-logs-infrastructure-V2-
        # CloudWatchLogs.html), which the deploying principal is not guaranteed to have.
        def _vended_log_delivery(
            resource_label: str,
            resource_name: str,
            resource_arn: str,
            log_types: list[str],
            delivery_name: str | None = None,
        ) -> logs.LogGroup:
            # Delivery sources and destinations are named per account with underscores
            # made hyphens, so a runtime and a gateway whose names differ only by that
            # (hr_super_agent_tools, hr-super-agent-tools) need delivery_name to differ.
            delivery_name = (delivery_name or resource_name).replace("_", "-")
            log_group = logs.LogGroup(
                self,
                f"{resource_label}LogGroup",
                log_group_name=f"{VENDED_LOG_PREFIX}/{resource_name}",
                retention=VENDED_LOG_RETENTION,
                removal_policy=RemovalPolicy.DESTROY,
            )
            destination = logs.CfnDeliveryDestination(
                self,
                f"{resource_label}LogDeliveryDestination",
                name=f"{delivery_name}-logs",
                delivery_destination_type="CWL",
                destination_resource_arn=log_group.log_group_arn,
            )
            for log_type in log_types:
                source = logs.CfnDeliverySource(
                    self,
                    f"{resource_label}{log_type.title().replace('_', '')}Source",
                    name=f"{delivery_name}-{log_type}".replace("_", "-").lower(),
                    log_type=log_type,
                    resource_arn=resource_arn,
                )
                delivery = logs.CfnDelivery(
                    self,
                    f"{resource_label}{log_type.title().replace('_', '')}Delivery",
                    delivery_source_name=source.name,
                    delivery_destination_arn=destination.attr_arn,
                )
                delivery.node.add_dependency(source)
                delivery.node.add_dependency(destination)

            return log_group

        vended_log_groups = {
            "ToolsGateway": _vended_log_delivery(
                "ToolsGateway",
                TOOLS_GATEWAY_NAME,
                tools_gateway.attr_gateway_arn,
                ["APPLICATION_LOGS"],
            ),
            "Runtime": _vended_log_delivery(
                "Runtime", RUNTIME_NAME, runtime.attr_agent_runtime_arn, ["APPLICATION_LOGS"]
            ),
            "ToolsRuntime": _vended_log_delivery(
                "ToolsRuntime",
                TOOLS_RUNTIME_NAME,
                hr_tools.runtime.attr_agent_runtime_arn,
                ["APPLICATION_LOGS"],
                delivery_name=f"{TOOLS_RUNTIME_NAME}-runtime",
            ),
            "AgentsGateway": _vended_log_delivery(
                "AgentsGateway",
                AGENTS_GATEWAY_NAME,
                sub_agents.gateway.attr_gateway_arn,
                ["APPLICATION_LOGS"],
            ),
            **{
                f"{name.capitalize()}Runtime": _vended_log_delivery(
                    f"{name.capitalize()}Runtime",
                    sub_agent_runtime_name(name),
                    sub_agent_runtime.attr_agent_runtime_arn,
                    ["APPLICATION_LOGS"],
                )
                for name, sub_agent_runtime in sub_agents.runtimes.items()
            },
        }

        # Recommended prefix policy (AWS-logs-infrastructure-V2-CloudWatchLogs.html) rather
        # than one statement per log group, so a fourth vended-log destination needs no
        # policy change.
        logs.CfnResourcePolicy(
            self,
            "VendedLogDeliveryPolicy",
            policy_name="HrSuperAgentVendedLogDelivery",
            policy_document=json.dumps(
                iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            sid="AWSLogDeliveryWrite20150319",
                            effect=iam.Effect.ALLOW,
                            principals=[iam.ServicePrincipal("delivery.logs.amazonaws.com")],
                            actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                            resources=[
                                f"arn:aws:logs:{self.region}:{self.account}:log-group:"
                                f"{VENDED_LOG_PREFIX}/*"
                            ],
                            conditions={
                                "StringEquals": {"aws:SourceAccount": self.account},
                                "ArnLike": {
                                    "aws:SourceArn": (
                                        f"arn:aws:logs:{self.region}:{self.account}:*"
                                    )
                                },
                            },
                        )
                    ]
                ).to_json()
            ),
        )

        # ---- Dynatrace AWS integration ----------------------------------------------------
        # The log forwarding stream is shipped dark: every parameter above defaults empty,
        # so the condition below renders to nothing until Sam has a Dynatrace tenant
        # (docs/proposals/dynatrace.md). Dynatrace's own push-based AWS activation stack,
        # deployed outside this repo on 7 Sep 2026, polls CloudWatch on its own; the
        # role-based monitoring role this stack once created for that purpose was removed
        # the same day.
        # Log forwarding: a Firehose delivery stream with the "Dynatrace" HTTP endpoint
        # destination (docs.dynatrace.com/docs/ingest-from/amazon-web-services/
        # integrate-with-aws/aws-logs-ingest/lma-stream-logs-with-firehose), subscribed to
        # the three vended log groups above. The runtime's own log group
        # (/aws/bedrock-agentcore/runtimes/hr_super_agent-*) is created lazily by the service,
        # not by this stack (only _runtime_role's policy names its pattern); a
        # CloudFormation subscription filter needs an exact, stack-owned log group, so that
        # group is a follow-up, not something this change subscribes.
        #
        # The log ingest URL is derived from DynatraceOtlpEndpoint (Fn::Split on its fixed
        # "/api/v2/otlp" suffix recovers the tenant's base URL, then Fn::Join appends the
        # logs ingest path) rather than a separate DynatraceLogsEndpoint parameter: the
        # OTLP endpoint already names the tenant, and asking Sam to enter the same tenant a
        # second time would be redundant and one more way for the two to drift apart.
        dynatrace_logs_endpoint = cdk.Fn.join("", [dynatrace_base_url, DYNATRACE_LOGS_INGEST_PATH])

        # Failed deliveries only, in a small bucket of its own: the site and content
        # buckets are not reused for this.
        dynatrace_log_backup_bucket = s3.Bucket(
            self,
            "DynatraceLogBackupBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
            lifecycle_rules=[
                s3.LifecycleRule(id="ExpireFailedDeliveries", expiration=Duration.days(7))
            ],
        )
        dynatrace_firehose_role = iam.Role(
            self,
            "DynatraceFirehoseRole",
            assumed_by=iam.ServicePrincipal("firehose.amazonaws.com"),
            description=(
                "Lets Firehose write failed Dynatrace log deliveries to the backup bucket"
            ),
            inline_policies={
                "BackupBucketWrite": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["s3:PutObject", "s3:GetBucketLocation", "s3:ListBucket"],
                            resources=[
                                dynatrace_log_backup_bucket.bucket_arn,
                                dynatrace_log_backup_bucket.arn_for_objects("*"),
                            ],
                        )
                    ]
                )
            },
        )

        # Buffer hints, content encoding, and the backup mode default (failed data only)
        # follow docs.dynatrace.com/docs/ingest-from/amazon-web-services/integrate-with-aws/
        # aws-logs-ingest/lma-stream-logs-with-firehose: 1 MiB or 60 seconds, GZIP, the
        # API token as the destination's access key.
        dynatrace_http_destination = firehose.HttpEndpoint(
            endpoint_config=firehose.HttpEndpointConfig(
                url=dynatrace_logs_endpoint,
                name="Dynatrace",
                access_key=SecretValue.cfn_parameter(dynatrace_api_token),
            ),
            buffering_hints=firehose.HttpBufferingHints(
                interval=Duration.seconds(60), size=Size.mebibytes(1)
            ),
            request_compression=firehose.HttpCompression.GZIP,
            # The default error log group has no expiry and this stack retains everything
            # else at 30 days (VENDED_LOG_RETENTION); disabled on both the HTTP endpoint
            # and its S3 backup rather than adding a fifth retention policy for a log
            # group failed deliveries already land in, in S3.
            s3_backup=firehose.DestinationS3BackupProps(
                bucket=dynatrace_log_backup_bucket, logging_config=firehose.DisableLogging()
            ),
            role=dynatrace_firehose_role,
            logging_config=firehose.DisableLogging(),
        )
        dynatrace_delivery_stream = firehose.DeliveryStream(
            self, "DynatraceLogDeliveryStream", destination=dynatrace_http_destination
        )

        dynatrace_logs_to_firehose_role = iam.Role(
            self,
            "DynatraceLogsToFirehoseRole",
            assumed_by=iam.ServicePrincipal("logs.amazonaws.com"),
            description=(
                "Lets CloudWatch Logs subscription filters write to the Dynatrace Firehose stream"
            ),
            inline_policies={
                "PutToFirehose": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["firehose:PutRecord", "firehose:PutRecordBatch"],
                            resources=[dynatrace_delivery_stream.delivery_stream_arn],
                        )
                    ]
                )
            },
        )
        dynatrace_firehose_destination = logs_destinations.FirehoseDestination(
            dynatrace_delivery_stream, role=dynatrace_logs_to_firehose_role
        )
        dynatrace_subscription_filters = [
            logs.SubscriptionFilter(
                self,
                f"Dynatrace{label}SubscriptionFilter",
                log_group=log_group,
                destination=dynatrace_firehose_destination,
                filter_pattern=logs.FilterPattern.all_events(),
            )
            for label, log_group in vended_log_groups.items()
        ]

        # Every resource above (the backup bucket, its own SSL-enforcement policy, both
        # roles and the default policies grant_write and the destination's internal grants
        # add to them, the delivery stream, and the three subscription filters) is
        # conditional on the same switch, applied last so every nested resource each L2
        # construct created along the way is caught.
        for construct in (
            dynatrace_log_backup_bucket,
            dynatrace_firehose_role,
            dynatrace_delivery_stream,
            dynatrace_logs_to_firehose_role,
            *dynatrace_subscription_filters,
        ):
            _apply_condition(construct, has_dynatrace_logs)

        # ---- Outputs -------------------------------------------------------------------
        cdk.CfnOutput(self, "SiteUrl", value=cdk.Fn.join("", [site_url, f"p/{PROJECT_NAME}/"]))
        cdk.CfnOutput(self, "AgentPath", value=f"/api/{PROJECT_NAME}/invocations")
        cdk.CfnOutput(self, "RuntimeArn", value=runtime.attr_agent_runtime_arn)
        cdk.CfnOutput(self, "RuntimeProtocol", value=protocol)
        cdk.CfnOutput(self, "ContentBucketName", value=content_bucket.bucket_name)
        cdk.CfnOutput(self, "KnowledgeBaseId", value=knowledge_base.attr_knowledge_base_id)
        cdk.CfnOutput(self, "DataSourceId", value=data_source.attr_data_source_id)
        cdk.CfnOutput(self, "ToolsGatewayUrl", value=tools_gateway.attr_gateway_url)
        # The canvas (connect/acxd/lib/common.js) reads it here instead of a local file.
        ssm.StringParameter(
            self,
            "ToolsGatewayUrlParameter",
            parameter_name=TOOLS_GATEWAY_URL_PARAMETER,
            string_value=tools_gateway.attr_gateway_url,
            description="The HR tools gateway URL, for the Connect canvas",
        )
        cdk.CfnOutput(self, "IngestionScheduleName", value=ingestion.schedule_name)
        cdk.CfnOutput(self, "AlarmTopicArn", value=alarm_topic.topic_arn)
        cdk.CfnOutput(self, "ConversationLogBucketName", value=conversation_bucket.bucket_name)
        cdk.CfnOutput(self, "ConversationLogKeySecretArn", value=conversation_secret.secret_arn)
        cdk.CfnOutput(self, "InvestigatorRoleArn", value=investigator_role.role_arn)

    def _runtime_role(self) -> iam.Role:
        """Execution role for the orchestrator runtime: the documented base policy plus
        the one model it calls."""
        role = runtime_execution_role(
            self, "RuntimeRole", RUNTIME_NAME, "Execution role for the HR Super Agent agent runtime"
        )
        region, account = self.region, self.account
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                resources=[
                    # A cross-region inference profile fans out to models in several
                    # regions, so the foundation-model wildcard stays broad; the profile
                    # itself is narrowed to the one model the orchestrator calls.
                    "arn:aws:bedrock:*::foundation-model/*",
                    f"arn:aws:bedrock:{region}:{account}:inference-profile/{ORCHESTRATOR_MODEL_ID}",
                ],
            )
        )
        return role
