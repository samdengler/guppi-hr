"""The chat start for /p/hr/ (guppi-hr D55; docs/proposals/connect-chatjs.md).

`hr-chat-start` is a Rust function on `provided.al2023`, arm64, built by cargo-lambda when
the stack is synthesized, as guppi-gpt builds its token issuer (`ChatStartBuild`; D51);
test synths skip the build. The page reaches it at https://chat.dengler.io/api/hr/chat/*
through a CloudFront behavior in guppi-gpt's stack, whose origin is this function's URL.
guppi-gpt reads the URL's host from /guppi/hr/chat-start-host.

The URL streams (RESPONSE_STREAM), so the credentials go out at the greeting while the
sub-agent warm-ups finish in the same invocation, and has no IAM auth: the function verifies
the Okta token itself (a function URL has no JWT authorizer). Reserved concurrency caps it.

The function is the on-behalf-of client hr-bridge through a workload identity of its own,
like the bridge (bridge.py): the same credential provider from /guppi/obo/hr-bridge/*, the
client secret read as its own role (aws-feedback A16), and Connect calls on the bridge's
contact flow and the instance's contacts only. Sam approved it as a Lambda function in the
request path (D55).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import aws_cdk as cdk
import jsii
from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_bedrockagentcore as agentcore
from aws_cdk import aws_cloudwatch as cw
from aws_cdk import aws_cloudwatch_actions as cw_actions
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_sns as sns
from aws_cdk import aws_ssm as ssm
from constructs import Construct

from guppi_connect_infra.bridge import CONNECT_INSTANCE_ID, DOMAINS_FILE, OBO

CHAT_START_DIR = Path(__file__).resolve().parents[2] / "chat_start"
FUNCTION_NAME = "hr-chat-start"
BINARY = "hr-chat-start"
WORKLOAD_NAME = "hr-chat-start"
HOST_PARAMETER = "/guppi/hr/chat-start-host"
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
            # Exchanges, the start, a 12 s greeting limit and 15 s warm-ups, with room.
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
                "AGENTS_GATEWAY_URL": parameter(self, "/guppi-hr/agents-gateway-url"),
                "WARM_DOMAINS": ",".join(json.loads(DOMAINS_FILE.read_text())),
                "OBO_PROVIDER": parameter(self, f"{OBO}/hr-bridge/provider-name"),
                "OBO_WORKLOAD": workload.name,
            },
        )
        self.function.node.add_dependency(workload)
        self.url = self.function.add_function_url(
            auth_type=lambda_.FunctionUrlAuthType.NONE,
            invoke_mode=lambda_.InvokeMode.RESPONSE_STREAM,
        )
        # https://<host>/ to <host>: CloudFront's origin takes a domain name.
        self.host = cdk.Fn.select(2, cdk.Fn.split("/", self.url.url))
        ssm.StringParameter(
            self,
            "HostParameter",
            parameter_name=HOST_PARAMETER,
            string_value=self.host,
            description="The /p/hr/ chat start's function URL host, for guppi-gpt's CloudFront (guppi-hr D55)",
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

        cdk.CfnOutput(stack, "ChatStartUrl", value=self.url.url)
        cdk.CfnOutput(stack, "ChatStartHost", value=self.host)
        cdk.CfnOutput(stack, "ChatStartLogGroup", value=self.log_group.log_group_name)
