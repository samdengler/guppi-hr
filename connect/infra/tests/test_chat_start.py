"""The chat start's template (guppi-hr D55, D57): a Rust function behind a regional REST API
with per-method throttles and reserved concurrency, the bridge's on-behalf-of grants
through a workload identity of its own, Connect calls on the contact flow and contacts
only, the host and path parameters guppi-gpt's CloudFront reads, and alarms on its
chat_problem lines. Its Rust tests run here through cargo, as guppi-gpt runs the token
issuer's."""

from __future__ import annotations

import json
import shutil
import subprocess

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template
from guppi_connect_infra.chat_start import (
    CHAT_START_DIR,
    HOST_PARAMETER,
    PATH_PARAMETER,
    PROBLEM_PATTERN,
)
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


def test_the_front_door_is_a_regional_rest_api_with_a_proxy_post_on_each_route(template):
    template.has_resource_properties(
        "AWS::ApiGateway::RestApi",
        {"Name": "hr-chat-start", "EndpointConfiguration": {"Types": ["REGIONAL"]}},
    )
    resources = template.find_resources("AWS::ApiGateway::Resource")
    parts = {logical: r["Properties"]["PathPart"] for logical, r in resources.items()}
    methods = list(template.find_resources("AWS::ApiGateway::Method").values())
    routes = sorted(parts[m["Properties"]["ResourceId"]["Ref"]] for m in methods)
    assert routes == ["report", "start"]
    for method in methods:
        props = method["Properties"]
        assert props["HttpMethod"] == "POST"
        # The function verifies the Okta token itself (D57): no authorizer.
        assert props["AuthorizationType"] == "NONE"
        assert props["Integration"]["Type"] == "AWS_PROXY"
        assert props["Integration"]["IntegrationHttpMethod"] == "POST"
        # A standard integration: buffered, one JSON body (no response streaming).
        assert props["Integration"].get("ResponseTransferMode", "BUFFERED") == "BUFFERED"
        assert "invocations" in json.dumps(props["Integration"]["Uri"])
        assert "response-streaming" not in json.dumps(props["Integration"]["Uri"])


def test_the_stage_throttles_each_method_and_logs_no_headers_or_bodies(template):
    (stage,) = template.find_resources("AWS::ApiGateway::Stage").values()
    props = stage["Properties"]
    assert props["StageName"] == "prod"
    limits = {
        s["ResourcePath"]: (s["HttpMethod"], s["ThrottlingRateLimit"], s["ThrottlingBurstLimit"])
        for s in props["MethodSettings"]
    }
    assert limits == {
        "/~1api~1hr~1chat~1start": ("POST", 2, 5),
        "/~1api~1hr~1chat~1report": ("POST", 10, 20),
    }
    log_format = props["AccessLogSetting"]["Format"]
    for field in ("$context.requestId", "$context.status", "$context.resourcePath"):
        assert field in log_format
    for hidden in ("header", "body", "$input", "authorizer", "identity.user"):
        assert hidden not in log_format.lower(), hidden
    template.has_resource_properties(
        "AWS::Logs::LogGroup",
        {"LogGroupName": "/aws/apigateway/hr-chat-start", "RetentionInDays": 30},
    )


def test_no_web_acl_is_attached(template):
    # Accepted for the POC (D57), as for the token issuer (D48).
    assert not template.find_resources("AWS::WAFv2::WebACLAssociation")
    assert not template.find_resources("AWS::WAFv2::WebACL")


def test_the_environment_names_okta_connect_and_the_provider(template):
    env = function(template)["Environment"]["Variables"]
    assert env["CONTACT_FLOW_ID"] == "flow-123"
    assert env["OBO_WORKLOAD"] == "hr-chat-start"
    assert "OBO" not in env, "OBO=off would pass the Okta token through (guppi-hr D48)"
    # The chat start warms no sub-agent (D57), so it needs no agents gateway.
    assert "AGENTS_GATEWAY_URL" not in env and "WARM_DOMAINS" not in env
    for name in (
        "OKTA_ISSUER",
        "OKTA_AUDIENCE",
        "OKTA_CLIENTS",
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


def ssm_value(template: Template, name: str):
    (found,) = [
        p["Properties"]["Value"]
        for p in template.find_resources("AWS::SSM::Parameter").values()
        if p["Properties"]["Name"] == name
    ]
    return found


def test_the_host_and_path_parameters_name_the_api_and_its_stage_for_cloudfront(template):
    host = json.dumps(ssm_value(template, HOST_PARAMETER))
    assert ".execute-api.us-east-1.amazonaws.com" in host
    (api,) = template.find_resources("AWS::ApiGateway::RestApi")
    assert f'"Ref": "{api}"' in host
    assert ssm_value(template, PATH_PARAMETER) == "/prod"


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
