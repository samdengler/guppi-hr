# /// script
# requires-python = ">=3.12"
# dependencies = ["boto3"]
# ///
"""Create or update the Connect contact flow that hands a chat to the ACXD application.

The flow sets the contact language, then runs the Agentic CX block with the deployed
application's alias (from .deploy/acxd.json, written by acxd/deploy.js). The block maps
the contact attributes `hrToken` and `employeeId` to ACXD context variables. The
canvas's EscalationFlow opens a ticket and ends the conversation, so the Escalation branch
to the instance's BasicQueue is no longer taken; an error says so in the chat and
disconnects. A production run publishes the flow id and the canvas alias to SSM for the
bridge stack.

    uv run scripts/contact_flow.py                    # development deployment (mock sub-agents)
    uv run scripts/contact_flow.py --env production   # production deployment (real gateways)
"""

from __future__ import annotations

import json
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]
INSTANCE_ID = "5665011a-f5fa-40e3-92d0-85ff625d10f6"
WORKSPACE_ID = "f77cf767-cecf-407a-9671-02b07d536b0f"
FLOW_NAME = "guppi-connect-hr-assistant"
CONTACT_FLOW_PARAMETER = "/guppi-hr/connect/contact-flow-id"
ALIAS_PARAMETER = "/guppi-hr/connect/canvas-alias"
REGION = "us-east-1"


def flow_content(application_id: str, alias: str, queue_arn: str) -> dict:
    return {
        "Version": "2019-10-30",
        "StartAction": "SetLanguage",
        "Metadata": {},
        "Actions": [
            {
                "Identifier": "SetLanguage",
                "Type": "UpdateContactData",
                "Parameters": {"LanguageCode": "en-US"},
                "Transitions": {
                    "NextAction": "AgenticCX",
                    "Errors": [{"ErrorType": "NoMatchingError", "NextAction": "AgenticCX"}],
                },
            },
            {
                "Identifier": "AgenticCX",
                "Type": "ConnectParticipantWithAgenticCX",
                "Parameters": {
                    "AgentConfiguration": {
                        "WorkspaceId": WORKSPACE_ID,
                        "ApplicationId": application_id,
                        "Alias": alias,
                        "ContextVariables": {
                            "hrToken": "$.Attributes.hrToken",
                            "employeeId": "$.Attributes.employeeId",
                        },
                    },
                    # Both blocks below appear in the console export; without them the
                    # import fails with "Invalid Action property value".
                    "SpeechRecognitionConfiguration": {"SpeechRecognitionEngine": "AMAZON_AGENTIC_VOICE"},
                    "AudioFillerConfiguration": {
                        "Enabled": True,
                        "AudioType": "MELODY_CHIPPER_CHIME",
                        "StartDelayInMilliseconds": 2500,
                        "MinimumPlayDurationInMilliseconds": 3000,
                        "ResponseDeliveryDelayInMilliseconds": 500,
                    },
                },
                "Transitions": {
                    "NextAction": "Goodbye",
                    "Conditions": [
                        {
                            "NextAction": "EscalationMessage",
                            "Condition": {"Operator": "Equals", "Operands": ["Escalation"]},
                        }
                    ],
                    "Errors": [
                        {"ErrorType": "NoMatchingError", "NextAction": "ErrorMessage"},
                        {"ErrorType": "NoMatchingCondition", "NextAction": "Goodbye"},
                        {"ErrorType": "InputTimeLimitExceeded", "NextAction": "Disconnect"},
                    ],
                },
            },
            {
                "Identifier": "EscalationMessage",
                "Type": "MessageParticipant",
                "Parameters": {"Text": "[flow] Escalation: transferring you to the HR service desk queue."},
                "Transitions": {
                    "NextAction": "SetQueue",
                    "Errors": [{"ErrorType": "NoMatchingError", "NextAction": "SetQueue"}],
                },
            },
            {
                "Identifier": "SetQueue",
                "Type": "UpdateContactTargetQueue",
                "Parameters": {"QueueId": queue_arn},
                "Transitions": {
                    "NextAction": "Transfer",
                    "Errors": [{"ErrorType": "NoMatchingError", "NextAction": "Disconnect"}],
                },
            },
            {
                "Identifier": "Transfer",
                "Type": "TransferContactToQueue",
                "Parameters": {},
                "Transitions": {
                    "NextAction": "Disconnect",
                    "Errors": [
                        {"ErrorType": "QueueAtCapacity", "NextAction": "Disconnect"},
                        {"ErrorType": "NoMatchingError", "NextAction": "Disconnect"},
                    ],
                },
            },
            {
                "Identifier": "ErrorMessage",
                "Type": "MessageParticipant",
                "Parameters": {"Text": "[flow] The Agentic CX block returned an error."},
                "Transitions": {
                    "NextAction": "Disconnect",
                    "Errors": [{"ErrorType": "NoMatchingError", "NextAction": "Disconnect"}],
                },
            },
            {
                "Identifier": "Goodbye",
                "Type": "MessageParticipant",
                "Parameters": {"Text": "[flow] The conversation ended."},
                "Transitions": {
                    "NextAction": "Disconnect",
                    "Errors": [{"ErrorType": "NoMatchingError", "NextAction": "Disconnect"}],
                },
            },
            {"Identifier": "Disconnect", "Type": "DisconnectParticipant", "Parameters": {}, "Transitions": {}},
        ],
    }


def state_file(env: str) -> Path:
    return ROOT / ".deploy" / ("acxd.json" if env == "development" else f"acxd-{env}.json")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default="development")
    env = parser.parse_args().env
    path = state_file(env)
    state = json.loads(path.read_text())
    flow_name = FLOW_NAME if env == "development" else f"{FLOW_NAME}-{env}"
    connect = boto3.client("connect", region_name=REGION)
    queues = connect.list_queues(InstanceId=INSTANCE_ID, QueueTypes=["STANDARD"])["QueueSummaryList"]
    queue_arn = next(q["Arn"] for q in queues if q["Name"] == "BasicQueue")
    content = json.dumps(flow_content(state["applicationId"], state["deploymentAlias"], queue_arn))

    existing = [
        f for f in connect.list_contact_flows(InstanceId=INSTANCE_ID, ContactFlowTypes=["CONTACT_FLOW"])[
            "ContactFlowSummaryList"
        ]
        if f["Name"] == flow_name
    ]
    if existing:
        flow_id = existing[0]["Id"]
        connect.update_contact_flow_content(InstanceId=INSTANCE_ID, ContactFlowId=flow_id, Content=content)
        print(f"updated contact flow {flow_id}")
    else:
        flow_id = connect.create_contact_flow(
            InstanceId=INSTANCE_ID,
            Name=flow_name,
            Type="CONTACT_FLOW",
            Description="guppi-connect spike: hands a chat to the hr-assistant ACXD application",
            Content=content,
            Status="PUBLISHED",
            Tags={"project": "guppi-connect"},
        )["ContactFlowId"]
        print(f"created contact flow {flow_id}")
    state["contactFlowId"] = flow_id
    state["alias_bound"] = state["deploymentAlias"]
    path.write_text(json.dumps(state, indent=2))
    if env == "production":
        # The bridge stack reads these at deploy time, so it needs no local state
        # (critique finding 15).
        ssm = boto3.client("ssm", region_name=REGION)
        for name, value in ((CONTACT_FLOW_PARAMETER, flow_id), (ALIAS_PARAMETER, state["deploymentAlias"])):
            ssm.put_parameter(Name=name, Value=value, Type="String", Overwrite=True)
            print(f"published {name}")


if __name__ == "__main__":
    main()
