"""The chat start for /p/hr/ (guppi-hr D55; docs/proposals/connect-chatjs.md).

`hr-chat-start` is a Rust function on `provided.al2023`, arm64, built by cargo-lambda when
the stack is synthesized, as guppi-gpt builds its token issuer (`ChatStartBuild`; D51);
test synths skip the build. The page reaches it at https://chat.dengler.io/api/hr/chat/*
through a CloudFront behavior in guppi-gpt's stack, whose origin is this stack's regional
REST API, stage `prod` (D57): the shape of AWS's StartChatContact sample, a `POST` method
on each route with a standard (buffered) Lambda proxy integration. guppi-gpt reads the
API's host from /guppi/hr/chat-start-host and the stage path from /guppi/hr/chat-start-path.

The methods have no authorizer: the function verifies the Okta token itself (a REST API
has no JWT authorizer, and a Lambda authorizer would be a second function). Per-method
throttles on the stage and the function's reserved concurrency cap it. No web ACL: Sam
accepted the risk for the POC (D57), as for the token issuer (D48).

The function is the on-behalf-of client hr-bridge through a workload identity of its own,
like the bridge (bridge.py): the same credential provider from /guppi/obo/hr-bridge/*, the
client secret read as its own role (aws-feedback A16), and Connect calls on the bridge's
contact flow and the instance's contacts only. Sam approved it as a Lambda function in the
request path (D55).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import aws_cdk as cdk
import jsii
from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_bedrockagentcore as agentcore
from aws_cdk import aws_cloudwatch as cw
from aws_cdk import aws_cloudwatch_actions as cw_actions
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_sns as sns
from aws_cdk import aws_ssm as ssm
from constructs import Construct

from guppi_connect_infra.bridge import CONNECT_INSTANCE_ID

CHAT_START_DIR = Path(__file__).resolve().parents[2] / "chat_start"
FUNCTION_NAME = "hr-chat-start"
BINARY = "hr-chat-start"
WORKLOAD_NAME = "hr-chat-start"
HOST_PARAMETER = "/guppi/hr/chat-start-host"
PATH_PARAMETER = "/guppi/hr/chat-start-path"
API_NAME = "hr-chat-start"
STAGE = "prod"
# The routes CloudFront forwards with the path unchanged, under the stage's origin path.
ROUTES = ("/api/hr/chat/start", "/api/hr/chat/report")
# Requests a second and burst, per method on the stage (Sam, 4 Oct 2026; D57). A start
# holds the function for its greeting wait, so its limit sits well under the reserved
# concurrency and StartChatContact's 5 a second; a report is short.
THROTTLES = {"/api/hr/chat/start": (2, 5), "/api/hr/chat/report": (10, 20)}
# guppi-gpt publishes the on-behalf-of providers here (bridge.py reads the same).
OBO = "/guppi/obo"
OKTA = "/guppi/okta"
RESERVED_CONCURRENCY = 10
NAMESPACE = "GuppiConnect/ChatStart"
# The function's chat_problem lines (connect/chat_start/src/lib.rs, `problem`).
PROBLEM_PATTERN = '{ $.event = "chat_problem" }'
# cargo-lambda from PyPI, with the Zig linker it cross-compiles with; no install needed.
CARGO_LAMBDA = [
    "uvx",
    "--from",
    "cargo-lambda",
    "cargo-lambda",
    "lambda",
    "build",
    "--release",
    "--arm64",
]
CARGO_LAMBDA_IMAGE = "ghcr.io/cargo-lambda/cargo-lambda:latest"


@jsii.implements(cdk.ILocalBundling)
class ChatStartBuild:
    """Builds the function on this machine with cargo-lambda; CDK falls back to
    cargo-lambda's image in Docker when this returns False (no uv, no cargo)."""

    def try_bundle(self, output_dir: str, *, image=None, **_options) -> bool:
        if not (shutil.which("uvx") and shutil.which("cargo")):
            return False
        subprocess.run(CARGO_LAMBDA, cwd=CHAT_START_DIR, check=True)
        shutil.copy2(
            CHAT_START_DIR / "target" / "lambda" / BINARY / "bootstrap",
            Path(output_dir) / "bootstrap",
        )
        return True


def chat_start_code() -> lambda_.Code:
    """The function's binary. The hash is of the source, so a deploy without a change to the
    Rust leaves the function alone even though builds are not byte for byte the same."""
    return lambda_.Code.from_asset(
        str(CHAT_START_DIR),
        exclude=["target", "**/*.pyc"],
        asset_hash_type=cdk.AssetHashType.SOURCE,
        bundling=cdk.BundlingOptions(
            image=cdk.DockerImage.from_registry(CARGO_LAMBDA_IMAGE),
            command=[
                "bash",
                "-c",
                f"cargo lambda build --release --arm64 && cp target/lambda/{BINARY}/bootstrap /asset-output/",
            ],
            local=ChatStartBuild(),
        ),
    )


def parameter(scope: Construct, name: str) -> str:
    return ssm.StringParameter.value_for_string_parameter(scope, name)


class ChatStart(Construct):
    def __init__(
        self, scope: Construct, construct_id: str, *, contact_flow_id: str, alarm_topic: sns.ITopic
    ) -> None:
        super().__init__(scope, construct_id)
        stack = Stack.of(self)
        region, account = stack.region, stack.account

        role = iam.Role(
            self,
            "Role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="The /p/hr/ chat start (guppi-hr D55)",
        )
        role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaBasicExecutionRole"
            )
        )

        instance_arn = f"arn:aws:connect:{region}:{account}:instance/{CONNECT_INSTANCE_ID}"
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["connect:StartChatContact"],
                resources=[
                    f"{instance_arn}/contact-flow/{contact_flow_id}",
                    f"{instance_arn}/contact/*",
                ],
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                # Blanking the token attributes, ending contacts, and checking a contact's
                # employeeId before ending it or taking its report.
                actions=[
                    "connect:UpdateContactAttributes",
                    "connect:StopContact",
                    "connect:GetContactAttributes",
                ],
                resources=[f"{instance_arn}/contact/*"],
            )
        )

        # On-behalf-of exchange (guppi-hr D47) through the hr-bridge credential provider, as
        # this workload identity only.
        workload = agentcore.CfnWorkloadIdentity(self, "Workload", name=WORKLOAD_NAME)
        provider_arn = parameter(self, f"{OBO}/hr-bridge/provider-arn")
        # Identity reads the client's secret as the caller (guppi-hr aws-feedback A16), by its
        # stable name; six characters match the suffix Secrets Manager adds, and no more.
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                resources=[
                    f"arn:aws:secretsmanager:{region}:{account}:secret:guppi/obo/hr-bridge-??????"
                ],
            )
        )
        directory = (
            f"arn:aws:bedrock-agentcore:{region}:{account}:workload-identity-directory/default"
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock-agentcore:GetWorkloadAccessTokenForJWT"],
                resources=[directory, workload.attr_workload_identity_arn],
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock-agentcore:GetResourceOauth2Token"],
                resources=[
                    provider_arn,
                    f"arn:aws:bedrock-agentcore:{region}:{account}:token-vault/default",
                    directory,
                    workload.attr_workload_identity_arn,
                ],
            )
        )

        self.log_group = logs.LogGroup(
            self,
            "Logs",
            log_group_name=f"/aws/lambda/{FUNCTION_NAME}",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )
        self.function = lambda_.Function(
            self,
            "Function",
            function_name=FUNCTION_NAME,
            runtime=lambda_.Runtime.PROVIDED_AL2023,
            architecture=lambda_.Architecture.ARM_64,
            handler="bootstrap",
            code=chat_start_code(),
            role=role,
            memory_size=1024,
            # Exchanges, the start, a 20 s socket limit and a 12 s greeting limit, with room.
            # API Gateway answers 504 after its 29 s integration timeout and the page stops
            # waiting at 25 s; past either the function still blanks and ends a failed start.
            timeout=Duration.seconds(60),
            reserved_concurrent_executions=RESERVED_CONCURRENCY,
            # X-Ray splits a cold start into Init and Invocation; the function's own steps
            # are in its cold_start and chat_start log lines.
            tracing=lambda_.Tracing.ACTIVE,
            log_group=self.log_group,
            description="Starts /p/hr/ chats on Amazon Connect (guppi-hr D55)",
            environment={
                "OKTA_ISSUER": parameter(self, f"{OKTA}/issuer"),
                "OKTA_AUDIENCE": parameter(self, f"{OKTA}/audience"),
                # The chat page's client and the harness's, as the issuer accepts them.
                "OKTA_CLIENTS": cdk.Fn.join(
                    ",",
                    [
                        parameter(self, f"{OKTA}/client-id"),
                        parameter(self, f"{OKTA}/harness-client-id"),
                    ],
                ),
                "CONNECT_INSTANCE_ID": CONNECT_INSTANCE_ID,
                "CONTACT_FLOW_ID": contact_flow_id,
                "OBO_PROVIDER": parameter(self, f"{OBO}/hr-bridge/provider-name"),
                "OBO_WORKLOAD": workload.name,
            },
        )
        self.function.node.add_dependency(workload)

        # The front door (D57): a regional REST API, stage prod, POST on each route with a
        # standard Lambda proxy integration. The access log has no headers and no bodies, so
        # no bearer or participant token reaches it.
        access_logs = logs.LogGroup(
            self,
            "ApiAccessLogs",
            log_group_name=f"/aws/apigateway/{API_NAME}",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )
        self.api = apigateway.RestApi(
            self,
            "Api",
            rest_api_name=API_NAME,
            description="The /p/hr/ chat start (guppi-hr D57)",
            endpoint_types=[apigateway.EndpointType.REGIONAL],
            deploy_options=apigateway.StageOptions(
                stage_name=STAGE,
                method_options={
                    f"{route}/POST": apigateway.MethodDeploymentOptions(
                        throttling_rate_limit=rate, throttling_burst_limit=burst
                    )
                    for route, (rate, burst) in THROTTLES.items()
                },
                access_log_destination=apigateway.LogGroupLogDestination(access_logs),
                access_log_format=apigateway.AccessLogFormat.json_with_standard_fields(
                    caller=False,
                    http_method=True,
                    ip=True,
                    protocol=False,
                    request_time=True,
                    resource_path=True,
                    response_length=True,
                    status=True,
                    user=False,
                ),
            ),
            # The account's API Gateway CloudWatch role is not this stack's; execution logging
            # stays off, as on guppi-gpt's APIs.
            cloud_watch_role=False,
        )
        integration = apigateway.LambdaIntegration(self.function)
        for route in ROUTES:
            self.api.root.resource_for_path(route).add_method(
                "POST", integration, authorization_type=apigateway.AuthorizationType.NONE
            )
        self.host = f"{self.api.rest_api_id}.execute-api.{region}.amazonaws.com"
        ssm.StringParameter(
            self,
            "HostParameter",
            parameter_name=HOST_PARAMETER,
            string_value=self.host,
            description=(
                "The /p/hr/ chat start's REST API host, for guppi-gpt's CloudFront (guppi-hr D57)"
            ),
        )
        ssm.StringParameter(
            self,
            "PathParameter",
            parameter_name=PATH_PARAMETER,
            string_value=f"/{STAGE}",
            description=(
                "The /p/hr/ chat start's stage, the origin path of guppi-gpt's CloudFront "
                "origin (guppi-hr D57)"
            ),
        )

        action = cw_actions.SnsAction(alarm_topic)
        problems = logs.MetricFilter(
            self,
            "ProblemsFilter",
            log_group=self.log_group,
            filter_pattern=logs.FilterPattern.literal(PROBLEM_PATTERN),
            metric_namespace=NAMESPACE,
            metric_name="Problems",
            metric_value="1",
        ).metric(statistic="Sum", period=Duration.minutes(5))
        for name, metric, description in (
            (
                "problems",
                problems,
                "A chat start or a reported turn went wrong: no greeting, token not cleared, exchange failed, contact not ended, no reply, designer error or socket failure",
            ),
            (
                "errors",
                self.function.metric_errors(period=Duration.minutes(5)),
                "The chat start function failed",
            ),
            (
                "throttles",
                self.function.metric_throttles(period=Duration.minutes(5)),
                "The chat start function hit its reserved concurrency",
            ),
        ):
            cw.Alarm(
                self,
                f"{name.capitalize()}Alarm",
                alarm_name=f"guppi-connect-chat-start-{name}",
                alarm_description=description,
                metric=metric,
                threshold=1,
                evaluation_periods=1,
                comparison_operator=cw.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
                treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
            ).add_alarm_action(action)

        # Outputs inside the construct, named as stack outputs, so the bridge's tests can
        # leave the whole chat start out.
        for name, value in (
            ("ChatStartApiUrl", self.api.url),
            ("ChatStartHost", self.host),
            ("ChatStartLogGroup", self.log_group.log_group_name),
        ):
            cdk.CfnOutput(self, name, value=value).override_logical_id(name)
