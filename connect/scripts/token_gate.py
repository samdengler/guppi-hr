# /// script
# requires-python = ">=3.12"
# dependencies = ["boto3", "websocket-client"]
# ///
"""Phase 0 of docs/platform-plan.md: can the token leave the contact record, and can a
bridge drive the canvas without a WebSocket?

Runs against the development application (mock sub-agents) with dummy tokens whose 20th
character marks them (the mock logs a 20-character preview of the Authorization header):

  clear    token A on the contact; after the first reply, hrToken is blanked with
           UpdateContactAttributes; does the second turn still carry A?
  refresh  token A on the contact; after the first reply, hrToken becomes token B; does the
           second turn carry A or B?

Each case is one chat driven through the participant API: the customer's WebSocket is
opened once to start the flow and closed, then SendMessage and GetTranscript polling. The mock's
CloudWatch log for the contact says which token each sub-agent call carried, and
GetContactAttributes says what the contact record kept (attribute names and a marker only).

Predates guppi-hr D47: the production canvas now reads one agents token per sub-agent
(`hrProfileToken`, `hrPayToken`, `hrTravelToken`) and `hrToolsToken`, which only the bridge
can mint; this script's `hrToken` reaches only the spike's development application.

    uv run scripts/token_gate.py
"""

from __future__ import annotations

import json
import secrets
import time
from pathlib import Path

import boto3
import websocket

ROOT = Path(__file__).resolve().parents[1]
INSTANCE_ID = "5665011a-f5fa-40e3-92d0-85ff625d10f6"
REGION = "us-east-1"
MOCK_LOG_GROUP = "/guppi-connect/mock"


def dummy(marker: str) -> str:
    # "Bearer guppi-dummy-" is 19 characters, so the preview's 20th character is the marker.
    return f"guppi-dummy-{marker}{secrets.token_hex(8)}"


class PolledChat:
    """A Connect chat driven without a WebSocket: send, then poll the transcript."""

    def __init__(self, flow_id: str, token: str) -> None:
        self.connect = boto3.client("connect", region_name=REGION)
        self.participant = boto3.client("connectparticipant", region_name=REGION)
        started = self.connect.start_chat_contact(
            InstanceId=INSTANCE_ID,
            ContactFlowId=flow_id,
            ParticipantDetails={"DisplayName": "token-gate"},
            Attributes={"hrToken": token, "employeeId": "spike-employee-1"},
            SupportedMessagingContentTypes=["text/plain"],
        )
        self.contact_id = started["ContactId"]
        conn = self.participant.create_participant_connection(
            Type=["WEBSOCKET", "CONNECTION_CREDENTIALS"],
            ParticipantToken=started["ParticipantToken"],
        )
        self.connection = conn["ConnectionCredentials"]["ConnectionToken"]
        # The flow runs only once the customer's WebSocket connects (AICC sample notes;
        # confirmed here: with credentials alone the transcript stayed empty). Connect,
        # subscribe, then close: everything after this uses the API alone.
        ws = websocket.create_connection(conn["Websocket"]["Url"], timeout=30)
        ws.send(json.dumps({"topic": "aws/subscribe", "content": {"topics": ["aws/chat"]}}))
        time.sleep(2)
        ws.close()
        self.seen: set[str] = set()

    def new_replies(self) -> list[str]:
        items = self.participant.get_transcript(
            ConnectionToken=self.connection, SortOrder="ASCENDING", MaxResults=100
        )["Transcript"]
        out = []
        for item in items:
            if item["Id"] in self.seen:
                continue
            self.seen.add(item["Id"])
            if item.get("Type") == "MESSAGE" and item.get("ParticipantRole") != "CUSTOMER":
                out.append(item.get("Content", ""))
        return out

    def wait(self, quiet: float = 3.0, limit: float = 45.0) -> list[str]:
        """Replies until the canvas has said something and then been quiet for `quiet` s."""
        got: list[str] = []
        start = last = time.monotonic()
        while time.monotonic() - start < limit:
            time.sleep(0.7)
            new = self.new_replies()
            if new:
                got.extend(new)
                last = time.monotonic()
            elif got and time.monotonic() - last > quiet:
                break
        return got

    def say(self, text: str) -> list[str]:
        self.participant.send_message(ContentType="text/plain", Content=text, ConnectionToken=self.connection)
        return self.wait()

    def set_token(self, value: str) -> None:
        self.connect.update_contact_attributes(
            InitialContactId=self.contact_id, InstanceId=INSTANCE_ID, Attributes={"hrToken": value}
        )

    def stored_token_marker(self) -> str:
        value = self.connect.get_contact_attributes(InstanceId=INSTANCE_ID, InitialContactId=self.contact_id)[
            "Attributes"
        ].get("hrToken")
        if value is None:
            return "absent"
        if value.startswith("guppi-dummy-"):
            return f"dummy {value[12]}"
        return f"other ({len(value)} chars)"

    def close(self) -> None:
        try:
            self.participant.disconnect_participant(ConnectionToken=self.connection)
        except Exception:
            pass


def mock_calls(contact_id: str) -> list[dict]:
    """The mock sub-agent calls for this contact, in order, with the auth preview."""
    logs = boto3.client("logs", region_name=REGION)
    found: list[dict] = []
    for _ in range(12):
        events = logs.filter_log_events(
            logGroupName=MOCK_LOG_GROUP,
            startTime=int((time.time() - 900) * 1000),
            filterPattern=f'"{contact_id}"',
        )["events"]
        found = []
        for e in events:
            try:
                record = json.loads(e["message"])
            except (json.JSONDecodeError, TypeError):
                continue
            if record.get("contextId") == contact_id and "domain" in record:
                found.append({"text": record.get("text"), "auth": record.get("auth", {}).get("preview", "")})
        if len(found) >= 2:
            break
        time.sleep(5)
    return found


def run_case(name: str, flow_id: str) -> dict:
    token_a = dummy("A")
    chat = PolledChat(flow_id, token_a)
    result: dict = {"case": name, "contactId": chat.contact_id}
    try:
        result["greeting"] = chat.wait(quiet=2.0, limit=30.0)
        result["turn1"] = chat.say("Change my home address to 1 Alpha St, Atlanta GA")
        result["afterTurn1Stored"] = chat.stored_token_marker()
        chat.set_token("cleared" if name == "clear" else dummy("B"))
        result["afterUpdateStored"] = chat.stored_token_marker()
        result["turn2"] = chat.say("what about my emergency contact?")
    finally:
        chat.close()
    result["afterCloseStored"] = chat.stored_token_marker()
    calls = mock_calls(chat.contact_id)
    result["subAgentCalls"] = [{"text": c["text"], "tokenMarker": c["auth"][19:20] if len(c["auth"]) >= 20 else c["auth"]} for c in calls]
    return result


def main() -> None:
    state = json.loads((ROOT / ".deploy" / "acxd.json").read_text())
    results = [run_case("clear", state["contactFlowId"]), run_case("refresh", state["contactFlowId"])]
    out = ROOT / ".deploy" / "token-gate.json"
    out.write_text(json.dumps(results, indent=2))
    for r in results:
        print(f"== {r['case']} ({r['contactId']})")
        print(f"   greeting: {r['greeting'][:1]}")
        print(f"   turn 1:   {r['turn1'][:1]}")
        print(f"   stored after turn 1: {r['afterTurn1Stored']}; after update: {r['afterUpdateStored']}; after close: {r['afterCloseStored']}")
        print(f"   turn 2:   {r['turn2'][:1]}")
        print(f"   sub-agent calls (token marker): {[(c['text'][:30], c['tokenMarker']) for c in r['subAgentCalls']]}")
    print(f"details in {out}")


if __name__ == "__main__":
    main()
