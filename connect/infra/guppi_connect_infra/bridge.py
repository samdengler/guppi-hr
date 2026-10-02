"""The AG-UI to Connect bridge as a chat.dengler.io agent project (docs/platform-plan.md).

An AgentCore Runtime running `agent/` behind the platform's edge gateway as the target
`hr-connect`, so the page's `/api/hr-connect/invocations` reaches it. The Runtime takes
the platform's own JWT authorizer and forwards Authorization, the bearer becoming the
contact attribute the canvas sends on to the HR gateways. A DynamoDB table holds each
thread's chat contact between runs. Everything about the platform comes from its
`/guppi/platform/*` parameters at deploy time.

The kit's conversation log stays off: the platform's log bucket admits only the platform
runtime's role, so the bridge's run lines go to its CloudWatch log group instead.
"""

from pathlib import Path

from aws_cdk import CfnOutput, RemovalPolicy, Stack
from aws_cdk import aws_bedrockagentcore as agentcore
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_ssm as ssm
from constructs import Construct

AGENT_DIR = Path(__file__).resolve().parents[2] / "agent"
RUNTIME_NAME = "guppi_connect_bridge"
TARGET_NAME = "hr-connect"
TRACE_HEADER = "traceparent"
SESSION_HEADER = "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id"
PLATFORM = "/guppi/platform"
CONNECT_INSTANCE_ID = "5665011a-f5fa-40e3-92d0-85ff625d10f6"


def platform_parameter(scope: Construct, name: str) -> str:
    return ssm.StringParameter.value_for_string_parameter(scope, f"{PLATFORM}/{name}")


class ConnectBridge(Construct):
    def __init__(self, scope: Construct, construct_id: str, *, contact_flow_id: str) -> None:
        super().__init__(scope, construct_id)
        stack = Stack.of(self)
        region, account = stack.region, stack.account

        table = dynamodb.Table(
            self,
            "Sessions",
            table_name="guppi-connect-bridge-sessions",
            partition_key=dynamodb.Attribute(name="pk", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="ttl",
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
                actions=["connect:UpdateContactAttributes"],
                resources=[f"{instance_arn}/contact/*"],
            )
        )
        table.grant_read_write_data(role)

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
                    allowed_clients=[platform_parameter(self, "user-pool-client-id")],
                )
            ),
            environment_variables={
                "CONNECT_INSTANCE_ID": CONNECT_INSTANCE_ID,
                "CONTACT_FLOW_ID": contact_flow_id,
                "SESSION_TABLE": table.table_name,
                "CONVERSATION_LOG_ENABLED": "false",
            },
        )
        runtime.node.add_dependency(role)

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

        CfnOutput(stack, "BridgeRuntimeArn", value=runtime.attr_agent_runtime_arn)
        CfnOutput(stack, "BridgeSessionTable", value=table.table_name)
        CfnOutput(stack, "BridgeTargetName", value=TARGET_NAME)
