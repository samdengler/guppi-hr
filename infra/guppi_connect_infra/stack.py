"""The spike's only AWS resources outside Connect: one Lambda behind a function URL.

The function answers two kinds of request from Agentic CX designer data requests:
`/echo` reports which headers arrived (token values shortened to a preview), and
`/a2a/<domain>/invocations` imitates an hr-super-agent sub-agent's A2A `message/send`
reply, so the canvas can be built and tested before a real employee token is available.
The URL has no auth because a data request cannot sign; it never returns a full token.
"""

from pathlib import Path

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack, Tags
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from constructs import Construct

MOCK_DIR = Path(__file__).resolve().parents[2] / "mock"


class GuppiConnectStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        Tags.of(self).add("project", "guppi-connect")

        log_group = logs.LogGroup(
            self,
            "MockLogs",
            log_group_name="/guppi-connect/mock",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )
        mock = lambda_.Function(
            self,
            "Mock",
            function_name="guppi-connect-mock",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            handler="handler.handler",
            code=lambda_.Code.from_asset(str(MOCK_DIR)),
            timeout=Duration.seconds(10),
            memory_size=256,
            log_group=log_group,
        )
        url = mock.add_function_url(auth_type=lambda_.FunctionUrlAuthType.NONE)
        CfnOutput(self, "MockUrl", value=url.url)
