"""guppi-connect's AWS resources outside Connect: the spike's mock Lambda, the bridge and the
chat start.

The function answers two kinds of request from Agentic CX designer data requests:
`/echo` reports which headers arrived (token values shortened to a preview), and
`/a2a/<domain>/invocations` imitates an hr-super-agent sub-agent's A2A `message/send`
reply, so the canvas can be built and tested before a real employee token is available.
The URL has no auth because a data request cannot sign; it never returns a full token.

The bridge (bridge.py) is the chat.dengler.io agent project `hr` (until 3 Oct 2026
`hr-connect`). It needs the
production contact flow id, which scripts/contact_flow.py publishes at
/guppi-hr/connect/contact-flow-id; the context value `contact_flow_id` overrides it.

The chat start (chat_start.py, guppi-hr D55) starts /p/hr/ chats for a page that talks to
Connect itself; it uses the same contact flow and alarm topic. The bridge stays deployed as
the fallback behind the page's flag.
"""

from pathlib import Path

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack, Tags
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_ssm as ssm
from constructs import Construct

from guppi_connect_infra.alarms import BridgeAlarms
from guppi_connect_infra.bridge import ConnectBridge
from guppi_connect_infra.chat_start import ChatStart
from guppi_connect_infra.dashboard import BridgeDashboard

ROOT = Path(__file__).resolve().parents[2]
MOCK_DIR = ROOT / "mock"
# Written by scripts/contact_flow.py --env production.
CONTACT_FLOW_PARAMETER = "/guppi-hr/connect/contact-flow-id"


def production_contact_flow_id(scope: Construct) -> str:
    """The production contact flow id that scripts/contact_flow.py publishes to SSM, read at
    deploy time, so a fresh clone deploys without local state (critique finding 15)."""
    return ssm.StringParameter.value_for_string_parameter(scope, CONTACT_FLOW_PARAMETER)


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
        # The canvas's development environment reads it here (connect/acxd/lib/common.js).
        ssm.StringParameter(
            self,
            "MockUrlParameter",
            parameter_name="/guppi-hr/connect/mock-url",
            string_value=url.url,
            description="The spike's mock sub-agents, for the canvas's development environment",
        )

        contact_flow_id = self.node.try_get_context("contact_flow_id") or production_contact_flow_id(self)
        bridge = ConnectBridge(self, "Bridge", contact_flow_id=contact_flow_id)
        dashboard = BridgeDashboard(self, "BridgeDashboard", runtime=bridge.runtime, table=bridge.table)
        CfnOutput(self, "BridgeDashboardUrl", value=dashboard.url)
        alarms = BridgeAlarms(self, "BridgeAlarms", runtime=bridge.runtime)
        CfnOutput(self, "AlarmTopicArn", value=alarms.topic.topic_arn)
        ChatStart(self, "ChatStart", contact_flow_id=contact_flow_id, alarm_topic=alarms.topic)
        # scripts/deploy.sh sets this log group's retention; AgentCore creates it.
        CfnOutput(
            self,
            "RuntimeLogGroup",
            value=f"/aws/bedrock-agentcore/runtimes/{bridge.runtime.attr_agent_runtime_id}-DEFAULT",
        )
