"""Alarms for the bridge (critique finding 14), on one SNS topic.

- Connect's concurrent chats at 60 percent of the instance's 500-chat quota.
- Any `bridge_problem` line in the bridge's log: a turn with no reply, a contact that never
  greeted, a token the bridge could not clear, a WebSocket that failed mid-turn
  (connect_bridge.turn.problem).
- Any run the platform kit logged as failed ("run failed").

The topic takes an email subscription when the deploy passes AlarmEmail (connect/scripts/
deploy.sh reads GUPPI_ALARM_EMAIL); the address is never in the repository.
"""

from aws_cdk import CfnCondition, CfnParameter, Duration, Fn
from aws_cdk import aws_bedrockagentcore as agentcore
from aws_cdk import aws_cloudwatch as cw
from aws_cdk import aws_cloudwatch_actions as cw_actions
from aws_cdk import aws_logs as logs
from aws_cdk import aws_sns as sns
from constructs import Construct

from guppi_connect_infra.bridge import CONNECT_INSTANCE_ID

CHAT_QUOTA = 500
NAMESPACE = "GuppiConnect/Bridge"


class BridgeAlarms(Construct):
    def __init__(self, scope: Construct, construct_id: str, *, runtime: agentcore.CfnRuntime) -> None:
        super().__init__(scope, construct_id)
        self.topic = sns.Topic(self, "Topic", topic_name="guppi-connect-alarms")
        email = CfnParameter(
            scope,
            "AlarmEmail",
            type="String",
            default="",
            description="Address for the bridge's alarm email; empty for none",
        )
        has_email = CfnCondition(self, "HasAlarmEmail", expression=Fn.condition_not(Fn.condition_equals(email.value_as_string, "")))
        subscription = sns.CfnSubscription(
            self,
            "Email",
            topic_arn=self.topic.topic_arn,
            protocol="email",
            endpoint=email.value_as_string,
        )
        subscription.cfn_options.condition = has_email
        action = cw_actions.SnsAction(self.topic)

        chats = cw.Metric(
            namespace="AWS/Connect",
            metric_name="ConcurrentActiveChats",
            dimensions_map={"InstanceId": CONNECT_INSTANCE_ID, "MetricGroup": "Chats"},
            statistic="Maximum",
            period=Duration.minutes(5),
        )
        cw.Alarm(
            self,
            "ConcurrentChats",
            alarm_name="guppi-connect-concurrent-chats",
            alarm_description=f"Connect chats at 60 percent of the instance's {CHAT_QUOTA}-chat quota",
            metric=chats,
            threshold=CHAT_QUOTA * 0.6,
            evaluation_periods=1,
            comparison_operator=cw.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
        ).add_alarm_action(action)

        log_group = logs.LogGroup.from_log_group_name(
            self, "RuntimeLogs", f"/aws/bedrock-agentcore/runtimes/{runtime.attr_agent_runtime_id}-DEFAULT"
        )
        for name, pattern, description in (
            ("Problems", "bridge_problem", "A bridge turn went wrong: no reply, no greeting, token not cleared or socket failure"),
            ("RunFailures", '"run failed"', "The platform kit logged a failed bridge run"),
        ):
            metric = logs.MetricFilter(
                self,
                f"{name}Filter",
                log_group=log_group,
                filter_pattern=logs.FilterPattern.literal(pattern),
                metric_namespace=NAMESPACE,
                metric_name=name,
                metric_value="1",
            ).metric(statistic="Sum", period=Duration.minutes(5))
            cw.Alarm(
                self,
                name,
                alarm_name=f"guppi-connect-bridge-{name.lower()}",
                alarm_description=description,
                metric=metric,
                threshold=1,
                evaluation_periods=1,
                comparison_operator=cw.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
                treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
            ).add_alarm_action(action)
