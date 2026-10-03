"""Throwaway prototype stack for D20: the token-exchange issuer (issuer/handler.py) on an
HTTP API and Lambda, with a KMS signing key, and a role a test gateway can use.

    cd prototypes/obo-issuer && ../../.venv/bin/python run.py   # deploys and tests
"""

import json

import aws_cdk as cdk
from aws_cdk import aws_apigatewayv2 as apigw
from aws_cdk import aws_apigatewayv2_integrations as integrations
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs

app = cdk.App()
stack = cdk.Stack(app, "GuppiOboPrototype", env=cdk.Environment(region="us-east-1"),
                  description="Throwaway: RFC 8693 token-exchange issuer prototype (guppi-hr D20)")
key = kms.Key(stack, "SigningKey", key_spec=kms.KeySpec.RSA_2048, key_usage=kms.KeyUsage.SIGN_VERIFY,
              removal_policy=cdk.RemovalPolicy.DESTROY, pending_window=cdk.Duration.days(7),
              description="Throwaway: signs prototype on-behalf-of tokens")
function = lambda_.Function(
    stack, "Issuer",
    runtime=lambda_.Runtime.PYTHON_3_12, architecture=lambda_.Architecture.ARM_64,
    handler="handler.handler", code=lambda_.Code.from_asset("issuer"),
    timeout=cdk.Duration.seconds(10), memory_size=256,
    log_retention=logs.RetentionDays.ONE_WEEK,
    environment={
        "KEY_ID": key.key_id,
        "UPSTREAM_ISSUER": app.node.try_get_context("upstream_issuer"),
        "UPSTREAM_AUDIENCE": "api://guppi",
        "ALLOW_SHAPE": "1",
        # SHA-256 of each client's secret, never the secret (run.py generates them).
        "CLIENTS": app.node.try_get_context("clients"),
        "SCOPE_AUDIENCE": json.dumps({
            "hr.agents": "api://hr-agents", "hr.agents.other": "api://hr-agents",
            "hr.tools.profile.read": "api://hr-tools", "hr.tools.profile.write": "api://hr-tools",
            "hr.tools.pay.read": "api://hr-tools", "hr.tools.pay.write": "api://hr-tools",
            "hr.tools.policy": "api://hr-tools", "hr.tools.profile": "api://hr-tools", "hr.tools.pay": "api://hr-tools",
        }),
    },
)
key.grant(function, "kms:Sign", "kms:GetPublicKey")
api = apigw.HttpApi(stack, "Api", api_name="guppi-obo-prototype",
                    default_integration=integrations.HttpLambdaIntegration("Issuer", function))
gateway_role = iam.Role(stack, "GatewayRole", assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
                        description="Throwaway: role for the prototype's test gateway")
# Spike: a throwaway runtime whose authorizer trusts this issuer, from an existing HR image.
runtime_role = iam.Role(stack, "RuntimeRole", assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
                        description="Throwaway: role for the spike's test runtime")
runtime_role.add_to_policy(iam.PolicyStatement(actions=["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"],
                                               resources=[f"arn:aws:ecr:us-east-1:{stack.account}:repository/cdk-*"]))
runtime_role.add_to_policy(iam.PolicyStatement(actions=["ecr:GetAuthorizationToken", "logs:CreateLogGroup", "logs:CreateLogStream",
                                                        "logs:PutLogEvents", "logs:DescribeLogStreams", "logs:DescribeLogGroups"],
                                               resources=["*"]))
cdk.CfnOutput(stack, "RuntimeRoleArn", value=runtime_role.role_arn)
cdk.CfnOutput(stack, "IssuerUrl", value=api.api_endpoint)
# Spike: the gateway exchanges tokens itself (an OAuth target with TOKEN_EXCHANGE) and
# invokes the spike runtime.
gateway_role.add_to_policy(iam.PolicyStatement(
    actions=["bedrock-agentcore:GetWorkloadAccessToken", "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
             "bedrock-agentcore:GetResourceOauth2Token", "bedrock-agentcore:InvokeAgentRuntime"],
    resources=["*"]))
gateway_role.add_to_policy(iam.PolicyStatement(
    actions=["secretsmanager:GetSecretValue"],
    resources=[f"arn:aws:secretsmanager:us-east-1:{stack.account}:secret:bedrock-agentcore-identity!*"]))
# Spike: Policy in AgentCore on the test tools gateway.
gateway_role.add_to_policy(iam.PolicyStatement(
    actions=["bedrock-agentcore:GetPolicyEngine", "bedrock-agentcore:AuthorizeAction",
             "bedrock-agentcore:PartiallyAuthorizeActions"],
    resources=[f"arn:aws:bedrock-agentcore:us-east-1:{stack.account}:policy-engine/*",
               f"arn:aws:bedrock-agentcore:us-east-1:{stack.account}:gateway/*"]))
cdk.CfnOutput(stack, "GatewayRoleArn", value=gateway_role.role_arn)
app.synth()
