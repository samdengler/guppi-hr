"""The HR tools MCP server (phase 2): its tables, its runtime, and its target on the tools
gateway (D3, D19, D21).

The tools gateway reaches the runtime as an MCP server target signed with the gateway's
role (SigV4), since an MCP gateway cannot pass the user's bearer token to a target. The
runtime has no JWT authorizer; the user's token arrives in X-Hr-User-Token, which the
target forwards and the server verifies against the user pool's keys.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import aws_cdk as cdk
from aws_cdk import RemovalPolicy
from aws_cdk import aws_bedrockagentcore as agentcore
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from constructs import Construct

TOOLS_RUNTIME_NAME = "hr_super_agent_tools"
HR_TARGET_NAME = "hr"  # tools reach the model as hr___get_profile and so on
HR_TOOL_PREFIX = f"{HR_TARGET_NAME}___"
# Must match hr_agent.tools.identity.FORWARDED_HEADERS (a test holds them together).
FORWARDED_HEADERS = ["X-Hr-User-Token", "X-Hr-Thread-Id", "traceparent"]
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
        token_issuer: str,
        allowed_clients: list[str],
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
            description="HR tools MCP server (profile, pay, tickets), SigV4 from the tools gateway",
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
                request_header_allowlist=FORWARDED_HEADERS
            ),
            environment_variables={
                **base_environment,
                "AGENT_ROLE": "tools",
                "EMPLOYEES_TABLE": self.employees.table_name,
                "PROPOSALS_TABLE": self.proposals.table_name,
                "TICKETS_TABLE": self.tickets.table_name,
                "AUDIT_TABLE": self.audit.table_name,
                "TOKEN_ISSUER": token_issuer,
                "TOKEN_ALLOWED_CLIENTS": cdk.Fn.join(",", allowed_clients),
            },
        )
        # AgentCore checks the image pull grants when it creates the runtime, so the
        # runtime waits for the whole role, DefaultPolicy included.
        self.runtime.node.add_dependency(role)

        runtime_arn = self.runtime.attr_agent_runtime_arn
        gateway_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock-agentcore:InvokeAgentRuntime"],
                resources=[runtime_arn, f"{runtime_arn}/runtime-endpoint/*"],
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
                        endpoint=endpoint
                    )
                )
            ),
            credential_provider_configurations=[
                agentcore.CfnGatewayTarget.CredentialProviderConfigurationProperty(
                    credential_provider_type="GATEWAY_IAM_ROLE",
                    credential_provider=agentcore.CfnGatewayTarget.CredentialProviderProperty(
                        iam_credential_provider=agentcore.CfnGatewayTarget.IamCredentialProviderProperty(
                            service="bedrock-agentcore", region=region
                        )
                    ),
                )
            ],
            metadata_configuration=agentcore.CfnGatewayTarget.MetadataConfigurationProperty(
                allowed_request_headers=FORWARDED_HEADERS
            ),
        )
        # Creating the target lists the server's tools, so the runtime must be up and the
        # gateway role allowed to invoke it first.
        self.target.node.add_dependency(self.runtime)
        self.target.node.add_dependency(gateway_role)
