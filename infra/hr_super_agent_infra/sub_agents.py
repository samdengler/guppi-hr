"""The Profile, Pay, and Travel sub-agents (phase 3, D2): one A2A runtime each behind an
agents gateway with runtime targets and JWT passthrough.

The gateway has no protocol type, like the edge gateway, because runtime targets cannot
join an MCP gateway. The gateway and each runtime accept only an agents token the bridge's
client gets from the on-behalf-of issuer (D47: client `hr-bridge`, one audience and scope
per sub-agent, `api://hr-agents/<name>` and `hr.agents.<name>`, so a token for one sub-agent
cannot drive another); the gateway passes it through, since runtime targets cannot
exchange (aws-feedback A13). Each runtime lets Authorization through to the container,
which trades it through AgentCore Identity for its own domain's tools token. Each
runtime's agent card advertises its gateway path (AGENTCORE_RUNTIME_URL), so an A2A client
that follows the card stays on the gateway.
"""

from __future__ import annotations

from collections.abc import Callable

import aws_cdk as cdk
from aws_cdk import aws_bedrockagentcore as agentcore
from aws_cdk import aws_iam as iam
from constructs import Construct

from hr_super_agent_infra.obo import (
    BRIDGE_CLIENT,
    DOMAIN_SCOPES,
    agents_audience,
    agents_scope,
    grant_exchange,
    workload_identity,
)
from hr_super_agent_infra.runtime_role import runtime_execution_role

SUB_AGENT_NAMES = ("profile", "pay", "travel")  # AGENT_ROLE values and target names (D4)
AGENTS_GATEWAY_NAME = "hr-super-agent-agents"


def sub_agent_runtime_name(name: str) -> str:
    return f"hr_super_agent_{name}"


class SubAgents(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        image_uri: str,
        grant_image: Callable[[iam.Role], None],
        obo_discovery_url: str,
        provider_names: dict[str, str],
        provider_arns: dict[str, str],
        secret_arns: dict[str, str],
        tools_gateway_url: str,
        model_id: str,
        hr_tool_prefix: str,
        base_environment: dict[str, str],
        session_header: str,
        trace_header: str,
    ) -> None:
        super().__init__(scope, construct_id)
        stack = cdk.Stack.of(self)
        region, account = stack.region, stack.account

        self.gateway_role = iam.Role(
            self,
            "GatewayRole",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            description="Lets the agents gateway invoke the HR sub-agent runtimes",
        )
        self.gateway = agentcore.CfnGateway(
            self,
            "Gateway",
            name=AGENTS_GATEWAY_NAME,
            description="HR Super Agent sub-agents: JWT check, runtime targets, token passthrough",
            role_arn=self.gateway_role.role_arn,
            authorizer_type="CUSTOM_JWT",
            authorizer_configuration=agentcore.CfnGateway.AuthorizerConfigurationProperty(
                custom_jwt_authorizer=agentcore.CfnGateway.CustomJWTAuthorizerConfigurationProperty(
                    discovery_url=obo_discovery_url,
                    # One agents audience per sub-agent; the gateway takes any of the three,
                    # each runtime only its own (critique of the build, finding 3).
                    allowed_audience=[agents_audience(d) for d in SUB_AGENT_NAMES],
                    allowed_clients=[BRIDGE_CLIENT],
                    allowed_scopes=[agents_scope(d) for d in SUB_AGENT_NAMES],
                )
            ),
            # protocol_type is left unset: runtime targets cannot join MCP gateways.
        )

        self.runtimes: dict[str, agentcore.CfnRuntime] = {}
        self.roles: dict[str, iam.Role] = {}
        for name in SUB_AGENT_NAMES:
            title = name.capitalize()
            runtime_name = sub_agent_runtime_name(name)
            role = runtime_execution_role(
                self, f"{title}Role", runtime_name, f"Execution role for the HR {name} sub-agent"
            )
            role.add_to_policy(
                iam.PolicyStatement(
                    actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                    resources=[
                        "arn:aws:bedrock:*::foundation-model/*",
                        f"arn:aws:bedrock:{region}:{account}:inference-profile/{model_id}",
                    ],
                )
            )
            grant_image(role)
            workload = workload_identity(self, f"{title}Workload", runtime_name)
            grant_exchange(role, provider_arns[name], secret_arns[name], workload)

            runtime = agentcore.CfnRuntime(
                self,
                f"{title}Runtime",
                agent_runtime_name=runtime_name,
                description=f"HR {name} sub-agent (A2A)",
                role_arn=role.role_arn,
                agent_runtime_artifact=agentcore.CfnRuntime.AgentRuntimeArtifactProperty(
                    container_configuration=agentcore.CfnRuntime.ContainerConfigurationProperty(
                        container_uri=image_uri
                    )
                ),
                network_configuration=agentcore.CfnRuntime.NetworkConfigurationProperty(
                    network_mode="PUBLIC"
                ),
                protocol_configuration="A2A",
                # Without Authorization on the allowlist the runtime validates the token and
                # drops it, and the sub-agent has nothing to present to the tools gateway.
                request_header_configuration=agentcore.CfnRuntime.RequestHeaderConfigurationProperty(
                    request_header_allowlist=["Authorization", trace_header]
                ),
                authorizer_configuration=agentcore.CfnRuntime.AuthorizerConfigurationProperty(
                    custom_jwt_authorizer=agentcore.CfnRuntime.CustomJWTAuthorizerConfigurationProperty(
                        discovery_url=obo_discovery_url,
                        allowed_audience=[agents_audience(name)],
                        allowed_clients=[BRIDGE_CLIENT],
                        allowed_scopes=[agents_scope(name)],
                    )
                ),
                environment_variables={
                    **base_environment,
                    "AGENT_ROLE": name,
                    "TOOLS_GATEWAY_URL": tools_gateway_url,
                    "MODEL_ID": model_id,
                    "HR_TOOL_PREFIX": hr_tool_prefix,
                    "OBO_PROVIDER": provider_names[name],
                    "OBO_WORKLOAD": workload.name,
                    "OBO_SCOPES": " ".join(DOMAIN_SCOPES[name]),
                    "AGENTCORE_RUNTIME_URL": cdk.Fn.join(
                        "", [self.gateway.attr_gateway_url, f"/{name}/invocations/"]
                    ),
                },
            )
            runtime.node.add_dependency(role)
            self.runtimes[name] = runtime
            self.roles[name] = role

            runtime_arn = runtime.attr_agent_runtime_arn
            self.gateway_role.add_to_policy(
                iam.PolicyStatement(
                    actions=["bedrock-agentcore:InvokeAgentRuntime"],
                    resources=[runtime_arn, f"{runtime_arn}/runtime-endpoint/*"],
                )
            )
            target = agentcore.CfnGatewayTarget(
                self,
                f"{title}Target",
                gateway_identifier=self.gateway.attr_gateway_identifier,
                name=name,
                description=f"HR {name} sub-agent, token passthrough",
                target_configuration=agentcore.CfnGatewayTarget.TargetConfigurationProperty(
                    http=agentcore.CfnGatewayTarget.HttpTargetConfigurationProperty(
                        agentcore_runtime=agentcore.CfnGatewayTarget.RuntimeTargetConfigurationProperty(
                            arn=runtime_arn, qualifier="DEFAULT"
                        )
                    )
                ),
                credential_provider_configurations=[
                    agentcore.CfnGatewayTarget.CredentialProviderConfigurationProperty(
                        credential_provider_type="JWT_PASSTHROUGH"
                    )
                ],
                metadata_configuration=agentcore.CfnGatewayTarget.MetadataConfigurationProperty(
                    allowed_request_headers=[session_header, trace_header]
                ),
            )
            target.node.add_dependency(self.gateway_role)
