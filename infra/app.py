"""CDK app entry. One stack, one region."""

import os

import aws_cdk as cdk
from guppi_connect_infra.stack import GuppiConnectStack

REGION = "us-east-1"

app = cdk.App()
GuppiConnectStack(
    app,
    "GuppiConnect",
    env=cdk.Environment(account=os.environ.get("CDK_DEFAULT_ACCOUNT"), region=REGION),
    description="guppi-connect: mock A2A endpoints and the AG-UI to Connect bridge",
)
app.synth()
