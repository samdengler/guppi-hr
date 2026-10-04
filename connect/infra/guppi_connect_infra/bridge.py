"""The AG-UI to Connect bridge as a chat.dengler.io agent project (docs/platform-plan.md).

An AgentCore Runtime running `agent/` behind the platform's edge gateway as the target
`hr`, so the page's `/api/hr/invocations` reaches it. The Runtime takes
the platform's own JWT authorizer and forwards Authorization; the bridge trades that Okta
token through AgentCore Identity (its credential provider and workload identity, from
guppi-gpt's /guppi/obo/*) for the two tokens the canvas carries to the HR gateways, an
agents token and a read-only tools token (guppi-hr D47). A DynamoDB table holds each
thread's chat contact between runs. Everything about the platform comes from its
`/guppi/platform/*` parameters at deploy time.

The kit's conversation log stays off: the platform's log bucket admits only the platform
runtime's role, so the bridge's run lines go to its CloudWatch log group instead.
"""

import json
from pathlib import Path

from aws_cdk import CfnOutput, RemovalPolicy, Stack
from aws_cdk import aws_bedrockagentcore as agentcore
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_ssm as ssm
from constructs import Construct

AGENT_DIR = Path(__file__).resolve().parents[2] / "agent"
# The canvas's domains (connect/acxd/hr.js checks it), which the warm start addresses.
DOMAINS_FILE = Path(__file__).resolve().parents[2] / "acxd" / "domains.json"
RUNTIME_NAME = "guppi_connect_bridge"
# The project is "hr" on the platform since 3 Oct 2026 (it was "hr-connect"; guppi-hr D37).
TARGET_NAME = "hr"
TRACE_HEADER = "traceparent"
SESSION_HEADER = "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id"
PLATFORM = "/guppi/platform"
OBO = "/guppi/obo"
CONNECT_INSTANCE_ID = "5665011a-f5fa-40e3-92d0-85ff625d10f6"


def platform_parameter(scope: Construct, name: str) -> str:
    return ssm.StringParameter.value_for_string_parameter(scope, f"{PLATFORM}/{name}")


class ConnectBridge(Construct):
    def __init__(self, scope: Construct, construct_id: str, *, contact_flow_id: str) -> None:
        super().__init__(scope, construct_id)
        stack = Stack.of(self)
        region, account = stack.region, stack.account

        # The table holds participant and connection tokens, which can join an employee's
        # chat while it lasts, so its key is the stack's own: reading an item needs
        # kms:Decrypt on it, which a read-only policy does not grant (critique finding 10).
        key = kms.Key(
            self,
            "SessionsKey",
            alias="alias/guppi-connect-bridge-sessions",
            description="Encrypts the Connect bridge's session table",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.DESTROY,
        )
        table = dynamodb.Table(
            self,
            "Sessions",
            table_name="guppi-connect-bridge-sessions",
            partition_key=dynamodb.Attribute(name="pk", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="ttl",
            encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED,
            encryption_key=key,
            removal_policy=RemovalPolicy.DESTROY,
        )

        role = iam.Role(
            self,
            "RuntimeRole",
            assumed_by=iam.ServicePrincipal(
                "bedrock-agentcore.amazonaws.com",
                conditions={
                    "StringEquals": {"aws:SourceAccount": account},
                    "ArnLike": {"aws:SourceArn": f"arn:aws:bedrock-agentcore:{region}:{account}:*"},
                },
            ),
            description="Execution role for the guppi-connect bridge runtime",
        )
        image = ecr_assets.DockerImageAsset(
            self,
            "Image",
            directory=str(AGENT_DIR),
            platform=ecr_assets.Platform.LINUX_ARM64,
            # The kit comes from the private guppi-gpt repository; the build reads a GitHub
            # token from this variable as a BuildKit secret (guppi-hr D29).
            build_secrets={"github_token": "env=HR_GITHUB_TOKEN"},
        )
        image.repository.grant_pull(role)
        role.add_to_policy(iam.PolicyStatement(actions=["ecr:GetAuthorizationToken"], resources=["*"]))
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:DescribeLogGroups"],
                resources=[f"arn:aws:logs:{region}:{account}:log-group:*"],
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:DescribeLogStreams",
                    "logs:PutLogEvents",
                ],
                resources=[f"arn:aws:logs:{region}:{account}:log-group:/aws/bedrock-agentcore/runtimes/*"],
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                    "xray:GetSamplingRules",
                    "xray:GetSamplingTargets",
                ],
                resources=["*"],
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],
                conditions={"StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"}},
            )
        )
        instance_arn = f"arn:aws:connect:{region}:{account}:instance/{CONNECT_INSTANCE_ID}"
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["connect:StartChatContact"],
                resources=[
                    f"{instance_arn}/contact-flow/{contact_flow_id}",
                    f"{instance_arn}/contact/*",
                ],
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                # StopContact ends the contacts the bridge leaves behind (critique finding 2).
                actions=["connect:UpdateContactAttributes", "connect:StopContact"],
                resources=[f"{instance_arn}/contact/*"],
            )
        )
        table.grant_read_write_data(role)

        # On-behalf-of exchange (guppi-hr D47): this workload identity and the bridge's
        # credential provider only. The name falls under the documented runtime role pattern.
        workload = agentcore.CfnWorkloadIdentity(self, "Workload", name=f"{RUNTIME_NAME}-obo")
        provider_arn = ssm.StringParameter.value_for_string_parameter(self, f"{OBO}/hr-bridge/provider-arn")
        # Identity reads the bridge client's secret as this role (guppi-hr aws-feedback A16).
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                resources=[ssm.StringParameter.value_for_string_parameter(self, f"{OBO}/hr-bridge/secret-arn")],
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock-agentcore:GetWorkloadAccessTokenForJWT"],
                resources=[
                    f"arn:aws:bedrock-agentcore:{region}:{account}:workload-identity-directory/default",
                    workload.attr_workload_identity_arn,
                ],
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock-agentcore:GetResourceOauth2Token"],
                resources=[
                    provider_arn,
                    f"arn:aws:bedrock-agentcore:{region}:{account}:token-vault/default",
                    f"arn:aws:bedrock-agentcore:{region}:{account}:workload-identity-directory/default",
                    workload.attr_workload_identity_arn,
                ],
            )
        )

        runtime = agentcore.CfnRuntime(
            self,
            "Runtime",
            agent_runtime_name=RUNTIME_NAME,
            description="guppi-connect bridge: AG-UI runs as Amazon Connect chat turns",
            role_arn=role.role_arn,
            agent_runtime_artifact=agentcore.CfnRuntime.AgentRuntimeArtifactProperty(
                container_configuration=agentcore.CfnRuntime.ContainerConfigurationProperty(
                    container_uri=image.image_uri
                )
            ),
            network_configuration=agentcore.CfnRuntime.NetworkConfigurationProperty(network_mode="PUBLIC"),
            protocol_configuration="AGUI",
            # The bearer becomes the contact attribute, so the runtime must keep it.
            request_header_configuration=agentcore.CfnRuntime.RequestHeaderConfigurationProperty(
                request_header_allowlist=["Authorization", TRACE_HEADER]
            ),
            authorizer_configuration=agentcore.CfnRuntime.AuthorizerConfigurationProperty(
                custom_jwt_authorizer=agentcore.CfnRuntime.CustomJWTAuthorizerConfigurationProperty(
                    discovery_url=platform_parameter(self, "jwt-discovery-url"),
                    # Okta's access tokens name the client in cid, so the audience (D46).
                    allowed_audience=[platform_parameter(self, "jwt-audience")],
                )
            ),
            environment_variables={
                "CONNECT_INSTANCE_ID": CONNECT_INSTANCE_ID,
                "CONTACT_FLOW_ID": contact_flow_id,
                "SESSION_TABLE": table.table_name,
                "CONVERSATION_LOG_ENABLED": "false",
                # A warm start also warms each sub-agent through the HR agents gateway,
                # with the agents token (D41, D47); the HR stack publishes the URL.
                "AGENTS_GATEWAY_URL": ssm.StringParameter.value_for_string_parameter(
                    self, "/guppi-hr/agents-gateway-url"
                ),
                "WARM_DOMAINS": ",".join(json.loads(DOMAINS_FILE.read_text())),
                "OBO_PROVIDER": ssm.StringParameter.value_for_string_parameter(self, f"{OBO}/hr-bridge/provider-name"),
                "OBO_WORKLOAD": workload.name,
                # Traces go to the platform's Dynatrace tenant, beside the HR runtimes the
                # canvas calls, with the platform's token read from its secret at start
                # (connect_bridge.otel_headers; guppi-hr D36).
                "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": platform_parameter(self, "dynatrace-traces-endpoint"),
                "DYNATRACE_TOKEN_SECRET_ARN": platform_parameter(self, "dynatrace-token-secret-arn"),
            },
        )
        runtime.node.add_dependency(role)
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                resources=[platform_parameter(self, "dynatrace-token-secret-arn")],
            )
        )

        gateway_role = iam.Role.from_role_arn(
            self,
            "EdgeGatewayRole",
            platform_parameter(self, "edge-gateway-role-arn"),
            mutable=True,
        )
        invoke_policy = iam.Policy(
            self,
            "EdgeGatewayInvokePolicy",
            roles=[gateway_role],
            statements=[
                iam.PolicyStatement(
                    actions=["bedrock-agentcore:InvokeAgentRuntime"],
                    resources=[
                        runtime.attr_agent_runtime_arn,
                        f"{runtime.attr_agent_runtime_arn}/runtime-endpoint/*",
                    ],
                )
            ],
        )
        target = agentcore.CfnGatewayTarget(
            self,
            "EdgeTarget",
            gateway_identifier=platform_parameter(self, "edge-gateway-id"),
            name=TARGET_NAME,
            description="guppi-connect bridge runtime, token passthrough",
            target_configuration=agentcore.CfnGatewayTarget.TargetConfigurationProperty(
                http=agentcore.CfnGatewayTarget.HttpTargetConfigurationProperty(
                    agentcore_runtime=agentcore.CfnGatewayTarget.RuntimeTargetConfigurationProperty(
                        arn=runtime.attr_agent_runtime_arn,
                        qualifier="DEFAULT",
                    )
                )
            ),
            credential_provider_configurations=[
                agentcore.CfnGatewayTarget.CredentialProviderConfigurationProperty(
                    credential_provider_type="JWT_PASSTHROUGH"
                )
            ],
            metadata_configuration=agentcore.CfnGatewayTarget.MetadataConfigurationProperty(
                allowed_request_headers=[SESSION_HEADER, TRACE_HEADER]
            ),
        )
        target.node.add_dependency(invoke_policy)

        self.runtime = runtime
        self.table = table

        CfnOutput(stack, "BridgeRuntimeArn", value=runtime.attr_agent_runtime_arn)
        CfnOutput(stack, "BridgeSessionTable", value=table.table_name)
        CfnOutput(stack, "BridgeTargetName", value=TARGET_NAME)
