"""The HR tools MCP server (phase 2): its tables, its runtime, and its target on the tools
gateway (D3, D21, D47).

The tools gateway's target exchanges each caller's tools token through AgentCore Identity
(OAuth `TOKEN_EXCHANGE`, the client `hr-tools-gateway`) for a token only this runtime
accepts, audience `api://hr-tools-runtime`, still naming the employee and carrying the
caller's scopes. The runtime's JWT authorizer checks it and passes `Authorization` to the
server, which verifies it again. This replaced the gateway's SigV4 call and the second copy
of the user's token in X-Hr-User-Token (D19). The target carries its tool list inline, so
the gateway never lists tools with a token that names no employee (aws-feedback A14).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import aws_cdk as cdk
from aws_cdk import RemovalPolicy
from aws_cdk import aws_bedrockagentcore as agentcore
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from constructs import Construct

from hr_super_agent_infra.obo import (
    grant_secret,
    POLICY_SCOPE,
    TOOLS_GATEWAY_CLIENT,
    TOOLS_RUNTIME_AUDIENCE,
)

TOOLS_RUNTIME_NAME = "hr_super_agent_tools"
HR_TARGET_NAME = "hr"  # tools reach the model as hr___get_profile and so on
HR_TOOL_PREFIX = f"{HR_TARGET_NAME}___"
# Must match hr_agent.tools.identity.FORWARDED_HEADERS (a test holds them together).
FORWARDED_HEADERS = ["X-Hr-Thread-Id", "traceparent"]
TOOLS_SCHEMA = Path(__file__).resolve().parent / "hr_tools_schema.json"  # scripts/tools-schema.py
TOOLS_SOURCE = Path(__file__).resolve().parents[2] / "agent" / "src" / "hr_agent" / "tools"


def tools_source_digest() -> str:
    """A short hash of the tools server's source. It sits in the target description, so a
    change to any tool updates the target, and the update makes the gateway list the
    server's tools again (implicit synchronization)."""
    digest = hashlib.sha256()
    for path in sorted(TOOLS_SOURCE.glob("*.py")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


class HrTools(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        image_uri: str,
        role: iam.Role,
        gateway: agentcore.CfnGateway,
        gateway_role: iam.Role,
        gateway_name: str,
        obo_discovery_url: str,
        obo_issuer: str,
        tools_gateway_provider_arn: str,
        tools_gateway_secret_arn: str,
        base_environment: dict[str, str],
    ) -> None:
        super().__init__(scope, construct_id)
        stack = cdk.Stack.of(self)
        region, account = stack.region, stack.account

        # Synthetic data only, so the tables go with the stack; names are generated so a
        # second stack in the account never collides (D18, D21).
        def table(
            table_id: str, partition: str, sort: str | None = None, ttl: str | None = None
        ) -> dynamodb.Table:
            return dynamodb.Table(
                self,
                table_id,
                partition_key=dynamodb.Attribute(
                    name=partition, type=dynamodb.AttributeType.STRING
                ),
                sort_key=(
                    dynamodb.Attribute(name=sort, type=dynamodb.AttributeType.STRING)
                    if sort
                    else None
                ),
                billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
                time_to_live_attribute=ttl,
                removal_policy=RemovalPolicy.DESTROY,
            )

        self.employees = table("Employees", "sub")
        self.proposals = table("Proposals", "proposal_id", ttl="expires_at")
        self.tickets = table("Tickets", "ticket_id")
        self.audit = table("Audit", "sub", sort="audit_id")
        self.employees.grant_read_write_data(role)
        self.proposals.grant_read_write_data(role)
        self.tickets.grant_write_data(role)
        self.audit.grant_write_data(role)

        self.runtime = agentcore.CfnRuntime(
            self,
            "Runtime",
            agent_runtime_name=TOOLS_RUNTIME_NAME,
            description="HR tools MCP server (profile, pay, tickets), exchanged tokens from the tools gateway",
            role_arn=role.role_arn,
            agent_runtime_artifact=agentcore.CfnRuntime.AgentRuntimeArtifactProperty(
                container_configuration=agentcore.CfnRuntime.ContainerConfigurationProperty(
                    container_uri=image_uri
                )
            ),
            network_configuration=agentcore.CfnRuntime.NetworkConfigurationProperty(
                network_mode="PUBLIC"
            ),
            protocol_configuration="MCP",
            request_header_configuration=agentcore.CfnRuntime.RequestHeaderConfigurationProperty(
                request_header_allowlist=["Authorization", *FORWARDED_HEADERS]
            ),
            # Only the tools gateway's exchanged token gets in: this issuer, this audience,
            # the gateway's client. A caller's own tools token cannot skip Policy (D47).
            authorizer_configuration=agentcore.CfnRuntime.AuthorizerConfigurationProperty(
                custom_jwt_authorizer=agentcore.CfnRuntime.CustomJWTAuthorizerConfigurationProperty(
                    discovery_url=obo_discovery_url,
                    allowed_audience=[TOOLS_RUNTIME_AUDIENCE],
                    allowed_clients=[TOOLS_GATEWAY_CLIENT],
                )
            ),
            environment_variables={
                **base_environment,
                "AGENT_ROLE": "tools",
                "EMPLOYEES_TABLE": self.employees.table_name,
                "PROPOSALS_TABLE": self.proposals.table_name,
                "TICKETS_TABLE": self.tickets.table_name,
                "AUDIT_TABLE": self.audit.table_name,
                # The server verifies the runtime token again: the on-behalf-of issuer, its
                # keys, the runtime's audience and the gateway's client; no token_use claim.
                "TOKEN_ISSUER": obo_issuer,
                "TOKEN_JWKS_URL": cdk.Fn.join("", [obo_issuer, "/jwks.json"]),
                "TOKEN_AUDIENCE": TOOLS_RUNTIME_AUDIENCE,
                "TOKEN_ALLOWED_CLIENTS": TOOLS_GATEWAY_CLIENT,
                "TOKEN_USE": "",
            },
        )
        # AgentCore checks the image pull grants when it creates the runtime, so the
        # runtime waits for the whole role, DefaultPolicy included.
        self.runtime.node.add_dependency(role)

        # The gateway asks Identity for the runtime token under its own workload identity,
        # through the tools gateway's credential provider only, and Identity reads that
        # client's secret as the gateway's role (aws-feedback A16).
        grant_secret(gateway_role, tools_gateway_secret_arn)
        gateway_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock-agentcore:GetWorkloadAccessToken",
                    "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                ],
                resources=[
                    f"arn:aws:bedrock-agentcore:{region}:{account}:workload-identity-directory/default",
                    f"arn:aws:bedrock-agentcore:{region}:{account}:workload-identity-directory/default/workload-identity/{gateway_name}-*",
                ],
            )
        )
        gateway_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock-agentcore:GetResourceOauth2Token"],
                resources=[
                    tools_gateway_provider_arn,
                    f"arn:aws:bedrock-agentcore:{region}:{account}:token-vault/default",
                    f"arn:aws:bedrock-agentcore:{region}:{account}:workload-identity-directory/default",
                    f"arn:aws:bedrock-agentcore:{region}:{account}:workload-identity-directory/default/workload-identity/{gateway_name}-*",
                ],
            )
        )

        # The runtime's invocation URL with the ARN percent-encoded, as the MCP target
        # requires; built from the runtime id because CloudFormation cannot encode a string.
        endpoint = cdk.Fn.join(
            "",
            [
                f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/"
                f"arn%3Aaws%3Abedrock-agentcore%3A{region}%3A{account}%3Aruntime%2F",
                self.runtime.attr_agent_runtime_id,
                "/invocations?qualifier=DEFAULT",
            ],
        )
        self.target = agentcore.CfnGatewayTarget(
            self,
            "Target",
            gateway_identifier=gateway.attr_gateway_identifier,
            name=HR_TARGET_NAME,
            description=f"HR self-service tools, source {tools_source_digest()}",
            target_configuration=agentcore.CfnGatewayTarget.TargetConfigurationProperty(
                mcp=agentcore.CfnGatewayTarget.McpTargetConfigurationProperty(
                    mcp_server=agentcore.CfnGatewayTarget.McpServerTargetConfigurationProperty(
                        endpoint=endpoint,
                        mcp_tool_schema=agentcore.CfnGatewayTarget.McpToolSchemaConfigurationProperty(
                            inline_payload=json.dumps(json.loads(TOOLS_SCHEMA.read_text()), separators=(",", ":"))
                        ),
                    )
                )
            ),
            credential_provider_configurations=[
                agentcore.CfnGatewayTarget.CredentialProviderConfigurationProperty(
                    credential_provider_type="OAUTH",
                    credential_provider=agentcore.CfnGatewayTarget.CredentialProviderProperty(
                        oauth_credential_provider=agentcore.CfnGatewayTarget.OAuthCredentialProviderProperty(
                            provider_arn=tools_gateway_provider_arn,
                            # The issuer ignores this and carries the caller's own scopes.
                            scopes=[POLICY_SCOPE],
                            grant_type="TOKEN_EXCHANGE",
                            custom_parameters={
                                "subject_token_type": "urn:ietf:params:oauth:token-type:access_token"
                            },
                        )
                    ),
                )
            ],
            metadata_configuration=agentcore.CfnGatewayTarget.MetadataConfigurationProperty(
                allowed_request_headers=FORWARDED_HEADERS
            ),
        )
        # The tool list is inline, but the runtime and the role's grants come first anyway.
        self.target.node.add_dependency(self.runtime)
        self.target.node.add_dependency(gateway_role)
