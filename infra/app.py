"""CDK app entry. One stack, one region."""

import os

import aws_cdk as cdk
from hr_super_agent_infra.stack import HrSuperAgentStack

REGION = "us-east-1"

app = cdk.App()
HrSuperAgentStack(
    app,
    "HrSuperAgent",
    env=cdk.Environment(account=os.environ.get("CDK_DEFAULT_ACCOUNT"), region=REGION),
    description="HR Super Agent: stateless chat page on AgentCore (spike stage)",
)
app.synth()
