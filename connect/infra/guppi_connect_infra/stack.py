"""guppi-connect's AWS resources outside Connect: the spike's mock Lambda and the bridge.

The function answers two kinds of request from Agentic CX designer data requests:
`/echo` reports which headers arrived (token values shortened to a preview), and
`/a2a/<domain>/invocations` imitates an hr-super-agent sub-agent's A2A `message/send`
reply, so the canvas can be built and tested before a real employee token is available.
The URL has no auth because a data request cannot sign; it never returns a full token.

The bridge (bridge.py) is the chat.dengler.io agent project `hr-connect`. It needs the
production contact flow id, which scripts/contact_flow.py records in
.deploy/acxd-production.json; the context value `contact_flow_id` overrides it.
"""

import json

from pathlib import Path

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack, Tags
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from constructs import Construct

from guppi_connect_infra.bridge import ConnectBridge
from guppi_connect_infra.dashboard import BridgeDashboard

ROOT = Path(__file__).resolve().parents[2]
MOCK_DIR = ROOT / "mock"
PRODUCTION_STATE = ROOT / ".deploy" / "acxd-production.json"


def production_contact_flow_id() -> str:
    try:
        return json.loads(PRODUCTION_STATE.read_text())["contactFlowId"]
    except (OSError, KeyError, ValueError) as exc:
        raise SystemExit(
            f"no contact flow id: run scripts/contact_flow.py --env production first ({exc})"
        ) from exc


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

        contact_flow_id = self.node.try_get_context("contact_flow_id") or production_contact_flow_id()
        bridge = ConnectBridge(self, "Bridge", contact_flow_id=contact_flow_id)
        dashboard = BridgeDashboard(self, "BridgeDashboard", runtime=bridge.runtime, table=bridge.table)
        CfnOutput(self, "BridgeDashboardUrl", value=dashboard.url)
