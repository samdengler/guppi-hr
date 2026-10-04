"""GuppiConnect's template: the bridge's permissions, encryption, environment and alarms
(critique findings 2, 10, 13, 14, 15)."""

from __future__ import annotations

import json

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template

from guppi_connect_infra.stack import GuppiConnectStack


@pytest.fixture(scope="module")
def template() -> Template:
    app = cdk.App(context={"contact_flow_id": "flow-123", "aws:cdk:bundling-stacks": []})
    stack = GuppiConnectStack(app, "GuppiConnect", env=cdk.Environment(account="111111111111", region="us-east-1"))
    return Template.from_stack(without_chat_start(stack))


def without_chat_start(stack: GuppiConnectStack) -> GuppiConnectStack:
    """The bridge's resources alone: the chat start (D55) has its own role, workload identity
    and alarms, which tests/test_chat_start.py checks. Its Rust build is skipped above, as
    guppi-gpt's issuer tests skip theirs."""
    assert stack.node.try_remove_child("ChatStart")
    return stack


def statements(template: Template) -> list[dict]:
    found = []
    for policy in template.find_resources("AWS::IAM::Policy").values():
        found.extend(policy["Properties"]["PolicyDocument"]["Statement"])
    return found


def actions(statement: dict) -> list[str]:
    value = statement["Action"]
    return value if isinstance(value, list) else [value]


def test_the_bridge_can_end_contacts_but_only_contacts(template):
    stop = [s for s in statements(template) if "connect:StopContact" in actions(s)]
    assert len(stop) == 1
    assert "/contact/*" in json.dumps(stop[0]["Resource"])


def test_the_bridge_starts_contacts_only_on_its_contact_flow(template):
    start = [s for s in statements(template) if "connect:StartChatContact" in actions(s)]
    assert "contact-flow/flow-123" in json.dumps(start[0]["Resource"])


def test_the_session_table_uses_the_stacks_own_key(template):
    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {"SSESpecification": {"SSEEnabled": True, "SSEType": "KMS", "KMSMasterKeyId": Match.any_value()}},
    )
    template.has_resource_properties("AWS::KMS::Key", {"EnableKeyRotation": True})


def test_the_runtime_takes_the_platform_jwt_and_forwards_only_two_headers(template):
    runtime = next(iter(template.find_resources("AWS::BedrockAgentCore::Runtime").values()))["Properties"]
    assert runtime["RequestHeaderConfiguration"]["RequestHeaderAllowlist"] == ["Authorization", "traceparent"]
    assert "CustomJWTAuthorizer" in runtime["AuthorizerConfiguration"]
    env = runtime["EnvironmentVariables"]
    assert env["CONTACT_FLOW_ID"] == "flow-123"
    assert env["CONVERSATION_LOG_ENABLED"] == "false"
    assert "AGENTS_GATEWAY_URL" in env


def test_the_contact_flow_id_comes_from_ssm_without_context():
    app = cdk.App(context={"aws:cdk:bundling-stacks": []})
    stack = without_chat_start(GuppiConnectStack(app, "Fresh", env=cdk.Environment(account="111111111111", region="us-east-1")))
    params = Template.from_stack(stack).to_json()["Parameters"]
    assert any(p.get("Default") == "/guppi-hr/connect/contact-flow-id" for p in params.values())


def test_alarms_cover_chats_problems_and_failed_runs(template):
    names = {a["Properties"]["AlarmName"] for a in template.find_resources("AWS::CloudWatch::Alarm").values()}
    assert names == {
        "guppi-connect-concurrent-chats",
        "guppi-connect-bridge-problems",
        "guppi-connect-bridge-runfailures",
    }
    template.has_resource_properties(
        "AWS::CloudWatch::Alarm", {"AlarmName": "guppi-connect-concurrent-chats", "Threshold": 300}
    )
    patterns = {f["Properties"]["FilterPattern"] for f in template.find_resources("AWS::Logs::MetricFilter").values()}
    assert patterns == {"bridge_problem", '"run failed"'}


def test_the_alarm_email_is_a_parameter_and_never_in_the_template(template):
    sub = next(iter(template.find_resources("AWS::SNS::Subscription").values()))
    assert sub["Condition"]
    assert sub["Properties"]["Endpoint"] == {"Ref": "AlarmEmail"}


def test_the_warm_start_domains_come_from_the_canvas_list(template):
    from pathlib import Path

    names = json.loads((Path(__file__).resolve().parents[2] / "acxd" / "domains.json").read_text())
    runtime = next(iter(template.find_resources("AWS::BedrockAgentCore::Runtime").values()))["Properties"]
    assert runtime["EnvironmentVariables"]["WARM_DOMAINS"] == ",".join(names)


def test_the_bridge_accepts_the_platform_audience(template):
    runtime = next(iter(template.find_resources("AWS::BedrockAgentCore::Runtime").values()))["Properties"]
    authorizer = runtime["AuthorizerConfiguration"]["CustomJWTAuthorizer"]
    assert "AllowedAudience" in authorizer and "AllowedClients" not in authorizer


def test_the_bridge_exchanges_only_through_its_own_provider_and_workload(template):
    # guppi-hr D47: the bridge trades the Okta token for the canvas's hop tokens.
    runtime = next(iter(template.find_resources("AWS::BedrockAgentCore::Runtime").values()))["Properties"]
    env = runtime["EnvironmentVariables"]
    assert env["OBO_WORKLOAD"] == "guppi_connect_bridge-obo"
    assert "/guppi/obo/hr-bridge/provider-name" in json.dumps(template.to_json()["Parameters"])
    (grant,) = [s for s in statements(template) if "bedrock-agentcore:GetResourceOauth2Token" in actions(s)]
    assert "/guppi/obo/hr-bridge/provider-arn" in json.dumps(template.to_json()["Parameters"])
    assert len(grant["Resource"]) == 4  # the provider, the vault, the directory, the workload
    names = {w["Properties"]["Name"] for w in template.find_resources("AWS::BedrockAgentCore::WorkloadIdentity").values()}
    assert names == {"guppi_connect_bridge-obo"}


def test_the_bridge_never_switches_the_exchange_off(template):
    # OBO=off passes the Okta token through; for local runs and tests only (guppi-hr D48).
    runtime = next(iter(template.find_resources("AWS::BedrockAgentCore::Runtime").values()))["Properties"]
    assert "OBO" not in runtime["EnvironmentVariables"]
