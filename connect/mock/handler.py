"""Echo and mock A2A endpoints for Agentic CX designer data requests.

`/echo` answers with the headers a data request sent, each token shortened to a preview
and a length, so a chat transcript can show whether a context variable reached a header.

`/a2a/<domain>/invocations` answers an A2A `message/send` the way an hr-super-agent
sub-agent does (agents/server.py): a message whose parts are the reply text and a data
part with `domain`, `pendingAction` and `committed`. The Profile domain proposes an
address change and commits it on an affirmative reply that carries the pending change,
which is enough to exercise the canvas's confirmation step.
"""

from __future__ import annotations

import base64
import json
import re
import time
import uuid

AFFIRMATIVE = re.compile(r"^\s*(yes|yep|yeah|confirm|confirmed|ok|okay|sure|go ahead|do it)\b", re.I)
NEGATIVE = re.compile(r"^\s*(no|nope|cancel|stop|don't|do not)\b", re.I)
ADDRESS_CHANGE = re.compile(r"address\s+to\s+(.+)$", re.I)
DEPOSIT_CHANGE = re.compile(r"(switch|change|update|move).*(deposit|routing|account)", re.I)


def preview(value: str | None) -> dict:
    """A token's first characters and its length, never the whole value."""
    if not value:
        return {"present": False}
    return {"present": True, "preview": value[:20], "length": len(value)}


TOKEN_KEYS = re.compile(r"token|authorization|secret|password", re.I)


def redact(value):
    """The request body with any token-like field shortened to a preview."""
    if isinstance(value, dict):
        return {
            k: (preview(v) if TOKEN_KEYS.search(k) and isinstance(v, str) else redact(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def body_of(event: dict) -> dict:
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8", "replace")
    try:
        parsed = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {"_unparsed": raw[:500]}
    return parsed if isinstance(parsed, dict) else {"_value": parsed}


def respond(status: int, payload: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(payload),
    }


def echo(headers: dict, body: dict) -> dict:
    auth = headers.get("authorization")
    return respond(
        200,
        {
            "authorization": preview(auth),
            "hrUserToken": preview(headers.get("x-hr-user-token")),
            "hrThreadId": headers.get("x-hr-thread-id", ""),
            "sessionId": headers.get("x-amzn-bedrock-agentcore-runtime-session-id", ""),
            "bearerPrefix": bool(auth and auth.startswith("Bearer ")),
            "summary": (
                f"authorization {'present' if auth else 'missing'}"
                + (f", starts {auth[:20]!r}, {len(auth)} chars" if auth else "")
            ),
            "bodyKeys": sorted(body.keys()),
            "body": json.dumps(redact(body))[:3000],
            "receivedAt": int(time.time()),
        },
    )


def sub_agent_reply(domain: str, text: str, pending: dict | None) -> tuple[str, dict | None, bool]:
    if pending and AFFIRMATIVE.search(text):
        return (f"Done. Your {pending.get('field', 'record')} is now {pending.get('after', '')}.", None, True)
    if pending and NEGATIVE.search(text):
        return ("Okay, I won't make that change.", None, False)
    if domain == "pay" and DEPOSIT_CHANGE.search(text):
        proposal = {
            "proposalId": uuid.uuid4().hex,
            "field": "direct_deposit",
            "before": "checking ending 1234",
            "after": "account ending " + (re.findall(r"\d{4}", text) or ["0000"])[-1],
        }
        return (
            f'I can change your direct deposit from {proposal["before"]} to {proposal["after"]}. Confirm?',
            proposal,
            False,
        )
    match = ADDRESS_CHANGE.search(text)
    if domain == "profile" and match:
        after = match.group(1).strip().rstrip(".")
        proposal = {
            "proposalId": uuid.uuid4().hex,
            "field": "home_address",
            "before": "100 Peachtree St, Atlanta GA 30303",
            "after": after,
        }
        return (
            f'I can change your home address from "{proposal["before"]}" to "{after}". '
            "Shall I go ahead?",
            proposal,
            False,
        )
    return (f"[mock {domain} agent] I received: {text}", pending, False)


def a2a(domain: str, headers: dict, body: dict) -> dict:
    params = body.get("params") or {}
    message = params.get("message") or {}
    parts = message.get("parts") or []
    text = next((p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text")), "")
    metadata = message.get("metadata") or {}
    pending = metadata.get("pendingAction")
    if isinstance(pending, str):
        try:
            pending = json.loads(pending) if pending.strip() else None
        except json.JSONDecodeError:
            pending = None
    if not isinstance(pending, dict) or not pending.get("proposalId"):
        pending = None
    reply, new_pending, committed = sub_agent_reply(domain, text, pending)
    if not reply.startswith("[mock"):
        reply = f"{reply} [mock {domain} agent]"  # every mock reply names its domain, for scoring
    history = metadata.get("history")
    print(json.dumps({"domain": domain, "text": text[:200], "pending": bool(pending),
                      "pendingRaw": metadata.get("pendingAction"), "history": history,
                      "contextId": message.get("contextId"), "employeeId": metadata.get("employeeId"),
                      "committed": committed, "auth": preview(headers.get("authorization")),
                      "session": headers.get("x-amzn-bedrock-agentcore-runtime-session-id", "")}))
    return respond(
        200,
        {
            "jsonrpc": "2.0",
            "id": body.get("id", uuid.uuid4().hex),
            "result": {
                "kind": "message",
                "role": "agent",
                "messageId": uuid.uuid4().hex,
                "contextId": message.get("contextId", ""),
                "parts": [
                    {"kind": "text", "text": reply},
                    {
                        "kind": "data",
                        "data": {
                            "domain": domain,
                            "pendingAction": new_pending,
                            "committed": committed,
                            "authorizationSeen": preview(headers.get("authorization")),
                        },
                    },
                ],
            },
        },
    )


def handler(event: dict, _context) -> dict:
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    path = event.get("rawPath") or "/"
    body = body_of(event)
    print(json.dumps({"path": path, "auth": preview(headers.get("authorization")),
                      "headerNames": sorted(headers.keys())}))
    if path.rstrip("/") == "/echo":
        return echo(headers, body)
    match = re.fullmatch(r"/a2a/([a-z]+)/invocations/?", path)
    if match:
        return a2a(match.group(1), headers, body)
    return respond(404, {"error": f"no route for {path}"})
