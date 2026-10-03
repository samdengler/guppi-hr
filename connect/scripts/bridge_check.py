"""One or more turns through chat.dengler.io's /api/hr/invocations (plan phase 2).

The platform test session's access token comes from guppi-gpt's scripts/test-token.sh,
read from its stdout and sent only as the Authorization header; it is never printed. Each
argument is one turn on the same thread, and the script prints the event types and the
canvas's text for each.

    uv run --with httpx python scripts/bridge_check.py "How do buddy passes work?"
"""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path

import httpx

SITE = "https://chat.dengler.io"
TOKEN_SCRIPT = Path(__file__).resolve().parents[3] / "guppi-gpt" / "scripts" / "test-token.sh"


def platform_token() -> str:
    return subprocess.run([str(TOKEN_SCRIPT)], check=True, capture_output=True, text=True).stdout.strip()


def turn(client: httpx.Client, token: str, thread: str, history: list[dict], text: str) -> str:
    history.append({"id": uuid.uuid4().hex, "role": "user", "content": text})
    body = {
        "threadId": thread,
        "runId": uuid.uuid4().hex,
        "messages": history,
        "tools": [],
        "context": [],
        "state": {},
        "forwardedProps": {"project": "hr"},
    }
    types, reply = [], []
    with client.stream(
        "POST",
        f"{SITE}/api/hr/invocations",
        json=body,
        headers={"authorization": f"Bearer {token}", "accept": "text/event-stream"},
    ) as response:
        print(f"HTTP {response.status_code}")
        for line in response.iter_lines():
            if not line.startswith("data:"):
                continue
            event = json.loads(line[5:])
            types.append(event["type"])
            if event["type"] == "TEXT_MESSAGE_CONTENT":
                reply.append(event["delta"])
            elif event["type"] in ("CUSTOM", "RUN_ERROR"):
                print(f"  {event['type']}: {event.get('name') or event.get('message')}")
    text_reply = "\n".join(reply)
    history.append({"id": uuid.uuid4().hex, "role": "assistant", "content": text_reply})
    print("  events:", " ".join(types))
    print("  reply:", text_reply or "(none)")
    return text_reply


def main(turns: list[str]) -> int:
    token = platform_token()
    thread = f"bridge-check-{uuid.uuid4().hex[:8]}"
    history: list[dict] = []
    with httpx.Client(timeout=90) as client:
        for text in turns or ["How do buddy passes work?"]:
            print(f"> {text}")
            turn(client, token, thread, history, text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
