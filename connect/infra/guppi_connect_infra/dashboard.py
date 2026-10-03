"""A CloudWatch dashboard for the bridge, in place of the platform's conversation log.

The bridge's run lines stay in its Runtime log group (bridge.py), one per AG-UI run. The
kit writes each as a JSON string in the OpenTelemetry record's `body`, so the queries
below parse the fields they need out of `body`: `total_ms`, `outcome`, and the bridge's
own `connect_contact`, `connect_replied` and `connect_closed` (ConnectTurn.usage). Beside
them sit the Runtime's AgentCore metrics and the Connect instance's chat and queue
metrics; an escalated chat waits in BasicQueue.
"""

from aws_cdk import Duration, Stack
from aws_cdk import aws_bedrockagentcore as agentcore
from aws_cdk import aws_cloudwatch as cw
from aws_cdk import aws_dynamodb as dynamodb
from constructs import Construct

from guppi_connect_infra.bridge import CONNECT_INSTANCE_ID, RUNTIME_NAME

DASHBOARD_NAME = "guppi-connect-bridge"
RUN_LINE = 'filter body like /"connect_contact"/'
PARSE_RUN = "\n".join(
    [
        RUN_LINE,
        '| parse body /"total_ms": (?<total_ms>\\d+)/',
        '| parse body /"outcome": "(?<outcome>[^"]+)"/',
        '| parse body /"connect_replied": (?<replied>true|false)/',
        '| parse body /"connect_closed": (?<closed>true|false)/',
        '| parse body /"connect_contact": "(?<contact>[^"]+)"/',
    ]
)


def run_queries() -> dict[str, str]:
    """The Logs Insights queries over the run lines, by widget title."""
    return {
        "Turns and time per turn": PARSE_RUN
        + "\n| stats count(*) as turns, avg(total_ms) as avg_ms, pct(total_ms, 95) as p95_ms by bin(1h)",
        "How turns ended": PARSE_RUN
        + "\n| stats count(*) as turns, avg(total_ms) as avg_ms by outcome, replied, closed",
        "Recent turns": PARSE_RUN
        + "\n| display @timestamp, outcome, total_ms, replied, closed, contact"
        + "\n| sort @timestamp desc\n| limit 50",
        "Errors in the bridge": "filter severityText = 'ERROR' or body like /Traceback/"
        + "\n| fields @timestamp, body\n| sort @timestamp desc\n| limit 20",
    }


class BridgeDashboard(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        runtime: agentcore.CfnRuntime,
        table: dynamodb.Table,
    ) -> None:
        super().__init__(scope, construct_id)
        log_group = f"/aws/bedrock-agentcore/runtimes/{runtime.attr_agent_runtime_id}-DEFAULT"
        period = Duration.minutes(5)

        def runtime_metric(name: str, statistic: str) -> cw.Metric:
            return cw.Metric(
                namespace="AWS/Bedrock-AgentCore",
                metric_name=name,
                dimensions_map={
                    "Resource": runtime.attr_agent_runtime_arn,
                    "Operation": "InvokeAgentRuntime",
                    "Name": f"{RUNTIME_NAME}::DEFAULT",
                },
                statistic=statistic,
                period=period,
            )

        def connect_metric(name: str, statistic: str, **dimensions: str) -> cw.Metric:
            return cw.Metric(
                namespace="AWS/Connect",
                metric_name=name,
                dimensions_map={"InstanceId": CONNECT_INSTANCE_ID, **dimensions},
                statistic=statistic,
                period=period,
            )

        queries = run_queries()

        def log_widget(title: str, width: int, view: cw.LogQueryVisualizationType) -> cw.LogQueryWidget:
            return cw.LogQueryWidget(
                title=title,
                log_group_names=[log_group],
                query_lines=queries[title].split("\n"),
                view=view,
                width=width,
                height=6,
            )

        dashboard = cw.Dashboard(
            self,
            "Dashboard",
            dashboard_name=DASHBOARD_NAME,
            default_interval=Duration.days(7),
        )
        dashboard.add_widgets(
            cw.TextWidget(
                markdown=(
                    "## hr-connect bridge\n"
                    "AG-UI runs from `https://chat.dengler.io/p/hr-connect/` as Amazon Connect "
                    "chat turns. One run line per turn in the Runtime log group; `closed` means "
                    "the contact flow escalated or the chat ended, and the next message starts a "
                    "new contact."
                ),
                width=24,
                height=2,
            )
        )
        dashboard.add_widgets(
            log_widget("Turns and time per turn", 12, cw.LogQueryVisualizationType.LINE),
            log_widget("How turns ended", 12, cw.LogQueryVisualizationType.TABLE),
        )
        dashboard.add_widgets(
            cw.GraphWidget(
                title="Runtime invocations and errors",
                left=[
                    runtime_metric("Invocations", "Sum"),
                    runtime_metric("SystemErrors", "Sum"),
                    runtime_metric("UserErrors", "Sum"),
                    runtime_metric("Throttles", "Sum"),
                ],
                width=8,
                height=6,
            ),
            cw.GraphWidget(
                title="Runtime latency (ms)",
                left=[runtime_metric("Latency", "p50"), runtime_metric("Latency", "p95")],
                width=8,
                height=6,
            ),
            cw.GraphWidget(
                title="Connect chats and the escalation queue",
                left=[
                    connect_metric("ConcurrentActiveChats", "Maximum", MetricGroup="Chats"),
                    connect_metric("SuccessfulChatsPerInterval", "Sum", MetricGroup="Chats"),
                ],
                right=[
                    connect_metric("QueueSize", "Maximum", MetricGroup="Queue", QueueName="BasicQueue"),
                ],
                width=8,
                height=6,
            ),
        )
        dashboard.add_widgets(
            log_widget("Recent turns", 16, cw.LogQueryVisualizationType.TABLE),
            cw.GraphWidget(
                title="Session table",
                left=[
                    table.metric_consumed_read_capacity_units(period=period),
                    table.metric_consumed_write_capacity_units(period=period),
                ],
                width=8,
                height=6,
            ),
        )
        dashboard.add_widgets(log_widget("Errors in the bridge", 24, cw.LogQueryVisualizationType.TABLE))

        region = Stack.of(self).region
        self.url = (
            f"https://{region}.console.aws.amazon.com/cloudwatch/home"
            f"?region={region}#dashboards/dashboard/{DASHBOARD_NAME}"
        )
