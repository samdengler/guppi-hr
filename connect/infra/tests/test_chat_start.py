"""The chat start's template (guppi-hr D55): a Rust function behind a streaming function URL
with reserved concurrency, the bridge's on-behalf-of grants through a workload identity of
its own, Connect calls on the contact flow and contacts only, the host parameter guppi-gpt's
CloudFront reads, and alarms on its chat_problem lines. Its Rust tests run here through
cargo, as guppi-gpt runs the token issuer's."""

from __future__ import annotations

import json
import shutil
import subprocess

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template
from guppi_connect_infra.chat_start import CHAT_START_DIR, HOST_PARAMETER, PROBLEM_PATTERN
from guppi_connect_infra.stack import GuppiConnectStack


@pytest.fixture(scope="module")
def template() -> Template:
    app = cdk.App(context={"contact_flow_id": "flow-123", "aws:cdk:bundling-stacks": []})
    stack = GuppiConnectStack(
        app, "GuppiConnect", env=cdk.Environment(account="111111111111", region="us-east-1")
    )
    return Template.from_stack(stack)


def function(template: Template) -> dict:
    (found,) = [
        f["Properties"]
        for f in template.find_resources("AWS::Lambda::Function").values()
        if f["Properties"].get("FunctionName") == "hr-chat-start"
    ]
    return found


def role_statements(template: Template) -> list[dict]:
    role = function(template)["Role"]["Fn::GetAtt"][0]
    found = []
    for policy in template.find_resources("AWS::IAM::Policy").values():
        if {"Ref": role} in policy["Properties"].get("Roles", []):
            found.extend(policy["Properties"]["PolicyDocument"]["Statement"])
    return found


def actions(statement: dict) -> list[str]:
    value = statement["Action"]
    return value if isinstance(value, list) else [value]


def granted(template: Template, action: str) -> list[dict]:
    return [s for s in role_statements(template) if action in actions(s)]


def parameters(template: Template) -> str:
    return json.dumps(template.to_json()["Parameters"])


def test_the_function_is_rust_on_arm64_with_reserved_concurrency(template):
    props = function(template)
    assert props["Runtime"] == "provided.al2023"
    assert props["Architectures"] == ["arm64"]
    assert props["Handler"] == "bootstrap"
    assert props["ReservedConcurrentExecutions"] == 10
    assert props["Timeout"] == 60


def test_the_url_streams_and_leaves_the_token_check_to_the_function(template):
    template.has_resource_properties(
        "AWS::Lambda::Url",
        {
            "AuthType": "NONE",
            "InvokeMode": "RESPONSE_STREAM",
            "TargetFunctionArn": Match.any_value(),
        },
    )


def test_the_environment_names_okta_connect_the_gateway_and_the_provider(template):
    env = function(template)["Environment"]["Variables"]
    assert env["CONTACT_FLOW_ID"] == "flow-123"
    assert env["OBO_WORKLOAD"] == "hr-chat-start"
    assert env["WARM_DOMAINS"] == "profile,pay,travel"
    assert "OBO" not in env, "OBO=off would pass the Okta token through (guppi-hr D48)"
    for name in (
        "OKTA_ISSUER",
        "OKTA_AUDIENCE",
        "OKTA_CLIENTS",
        "AGENTS_GATEWAY_URL",
        "OBO_PROVIDER",
        "CONNECT_INSTANCE_ID",
    ):
        assert env[name], name
    for name in (
        "/guppi/okta/issuer",
        "/guppi/okta/audience",
        "/guppi/okta/client-id",
        "/guppi/okta/harness-client-id",
        "/guppi/obo/hr-bridge/provider-name",
        "/guppi/obo/hr-bridge/provider-arn",
        "/guppi-hr/agents-gateway-url",
    ):
        assert name in parameters(template), name
    assert "secret" not in json.dumps(env).lower()


def test_connect_calls_are_on_the_contact_flow_and_contacts_only(template):
    (start,) = granted(template, "connect:StartChatContact")
    assert "contact-flow/flow-123" in json.dumps(start["Resource"])
    (contacts,) = granted(template, "connect:StopContact")
    assert set(actions(contacts)) == {
        "connect:UpdateContactAttributes",
        "connect:StopContact",
        "connect:GetContactAttributes",
    }
    assert json.dumps(contacts["Resource"]).endswith('/contact/*"')


def test_the_exchange_goes_through_the_hr_bridge_provider_as_its_own_workload(template):
    names = {
        w["Properties"]["Name"]
        for w in template.find_resources("AWS::BedrockAgentCore::WorkloadIdentity").values()
    }
    assert "hr-chat-start" in names
    (oauth,) = granted(template, "bedrock-agentcore:GetResourceOauth2Token")
    assert len(oauth["Resource"]) == 4  # the provider, the vault, the directory, the workload
    (jwt,) = granted(template, "bedrock-agentcore:GetWorkloadAccessTokenForJWT")
    assert len(jwt["Resource"]) == 2
    (secret,) = granted(template, "secretsmanager:GetSecretValue")
    assert json.dumps(secret["Resource"]).endswith('secret:guppi/obo/hr-bridge-??????"')
    assert not granted(template, "bedrock-agentcore:GetWorkloadAccessTokenForUserId")


def test_the_host_parameter_is_the_url_host_for_cloudfront(template):
    (found,) = [
        p["Properties"]
        for p in template.find_resources("AWS::SSM::Parameter").values()
        if p["Properties"]["Name"] == HOST_PARAMETER
    ]
    select = found["Value"]["Fn::Select"]
    assert select[0] == 2
    assert select[1]["Fn::Split"][0] == "/"


def test_chat_problems_raise_an_alarm(template):
    filters = [f["Properties"] for f in template.find_resources("AWS::Logs::MetricFilter").values()]
    (problems,) = [f for f in filters if f["FilterPattern"] == PROBLEM_PATTERN]
    assert problems["MetricTransformations"][0]["MetricNamespace"] == "GuppiConnect/ChatStart"
    template.has_resource_properties(
        "AWS::CloudWatch::Alarm",
        {
            "AlarmName": "guppi-connect-chat-start-problems",
            "Threshold": 1,
            "AlarmActions": Match.any_value(),
        },
    )
    template.has_resource_properties(
        "AWS::Logs::LogGroup", {"LogGroupName": "/aws/lambda/hr-chat-start", "RetentionInDays": 30}
    )


def test_the_built_in_okta_keys_are_public_rsa_keys():
    keys = json.loads((CHAT_START_DIR / "okta-keys.json").read_text())["keys"]
    assert keys and all(set(k) == {"kid", "kty", "n", "e"} and k["kty"] == "RSA" for k in keys)


@pytest.mark.skipif(shutil.which("cargo") is None, reason="no Rust toolchain")
def test_the_functions_rust_tests_pass():
    result = subprocess.run(
        ["cargo", "test", "--lib", "--quiet"], cwd=CHAT_START_DIR, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
