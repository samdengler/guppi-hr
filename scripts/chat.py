# /// script
# requires-python = ">=3.12"
# dependencies = ["boto3", "websocket-client"]
# ///
"""Drive the hr-assistant over Amazon Connect chat and print the transcript.

Starts a chat contact on the spike's contact flow with the contact attributes `hrToken`
and `employeeId`, connects the customer participant's WebSocket (the flow does not run
until it does), then sends each message once the application has gone quiet.

    uv run scripts/chat.py "run the header probe"
    uv run scripts/chat.py --token-file ~/.config/guppi-connect/hr_access_token "..." "yes"

Without --token-file the token is a dummy, `guppi-dummy-<random>`, which is enough to see
whether the value reaches a data request header. Tokens are never printed.
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
import threading
import time
from pathlib import Path

import boto3
import websocket

ROOT = Path(__file__).resolve().parents[1]
INSTANCE_ID = "5665011a-f5fa-40e3-92d0-85ff625d10f6"
REGION = "us-east-1"


class Chat:
    def __init__(self, flow_id: str, token: str, employee_id: str) -> None:
        self.connect = boto3.client("connect", region_name=REGION)
        self.participant = boto3.client("connectparticipant", region_name=REGION)
        started = self.connect.start_chat_contact(
            InstanceId=INSTANCE_ID,
            ContactFlowId=flow_id,
            ParticipantDetails={"DisplayName": "spike-tester"},
            Attributes={"hrToken": token, "employeeId": employee_id},
            SupportedMessagingContentTypes=["text/plain"],
        )
        self.contact_id = started["ContactId"]
        conn = self.participant.create_participant_connection(
            Type=["WEBSOCKET", "CONNECTION_CREDENTIALS"],
            ParticipantToken=started["ParticipantToken"],
        )
        self.connection_token = conn["ConnectionCredentials"]["ConnectionToken"]
        self.events: list[dict] = []
        self.last_event = time.monotonic()
        self.ended = False
        self.ws = websocket.create_connection(conn["Websocket"]["Url"], timeout=60)
        self.ws.send(json.dumps({"topic": "aws/subscribe", "content": {"topics": ["aws/chat"]}}))
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        while not self.ended:
            try:
                raw = self.ws.recv()
            except Exception:
                return
            if not raw:
                continue
            frame = json.loads(raw)
            if frame.get("topic") != "aws/chat":
                continue
            content = json.loads(frame.get("content") or "{}")
            kind = content.get("Type")
            role = content.get("ParticipantRole", "")
            if kind == "MESSAGE" and role != "CUSTOMER":
                self.events.append({"role": role, "text": content.get("Content", "")})
                print(f"  << [{role}] {content.get('Content', '')}", flush=True)
            elif kind == "EVENT" and content.get("ContentType", "").endswith("chat.ended"):
                self.ended = True
                print("  -- chat ended", flush=True)
            self.last_event = time.monotonic()

    def wait_quiet(self, quiet: float, limit: float) -> None:
        start = time.monotonic()
        seen = len(self.events)
        while time.monotonic() - start < limit and not self.ended:
            time.sleep(0.5)
            if len(self.events) > seen and time.monotonic() - self.last_event > quiet:
                return

    def say(self, text: str) -> None:
        print(f"  >> {text}", flush=True)
        self.participant.send_message(
            ContentType="text/plain", Content=text, ConnectionToken=self.connection_token
        )

    def close(self) -> None:
        if not self.ended:
            try:
                self.participant.disconnect_participant(ConnectionToken=self.connection_token)
            except Exception:
                pass
        self.ended = True
        try:
            self.ws.close()
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("messages", nargs="*")
    parser.add_argument("--token-file", help="file holding an access token for hr-super-agent")
    parser.add_argument("--employee-id", default="spike-employee-1")
    parser.add_argument("--quiet", type=float, default=4.0, help="seconds of silence that end a turn")
    parser.add_argument("--limit", type=float, default=45.0, help="max seconds to wait per turn")
    parser.add_argument("--json", help="write the transcript to this file")
    args = parser.parse_args()

    state = json.loads((ROOT / ".deploy" / "acxd.json").read_text())
    if args.token_file:
        token = Path(args.token_file).expanduser().read_text().strip()
    else:
        token = f"guppi-dummy-{secrets.token_hex(8)}"
    print(f"contact flow {state['contactFlowId']}, token {'from file' if args.token_file else token}")

    chat = Chat(state["contactFlowId"], token, args.employee_id)
    print(f"contact {chat.contact_id}")
    try:
        chat.wait_quiet(args.quiet, args.limit)
        for message in args.messages:
            if chat.ended:
                break
            chat.say(message)
            chat.wait_quiet(args.quiet, args.limit)
    finally:
        chat.close()
    if args.json:
        Path(args.json).write_text(
            json.dumps({"contactId": chat.contact_id, "messages": args.messages, "events": chat.events}, indent=2)
        )
    if not chat.events:
        print("no replies", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
