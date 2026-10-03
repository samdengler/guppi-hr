"""One AG-UI run as one Connect chat turn (docs/platform-plan.md, "Bridge design").

A thread's first run starts a Connect chat contact on the contact flow that holds the
Agentic CX block, with the caller's token and subject as contact attributes, opens the
customer's WebSocket once (the flow runs only after it connects), closes it, and skips the
canvas's greeting. Every run then sends the latest user message with the participant API
and polls the transcript, relaying each canvas message as an AG-UI text message until the
canvas has been quiet for a moment. After the first reply the token attribute is blanked,
so the employee's token does not stay on the contact record (phase 0); a token close to
expiry gets a new contact, since a running designer session never sees a changed one.

A warm start (the page's run with no messages when a thread starts, kit-v0.3.0) does the
contact's start ahead of the first message, so that message only sends and polls
(D39). A run that finds another run starting the contact waits for it, and a stored contact
that refuses the message is replaced once. A warm start that opened a new contact also sends
each sub-agent a warm message through the agents gateway, on the runtime session and thread
the canvas will use, so the first message finds both open (D41).

Nothing here holds state between runs; the session store does.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import time
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

from ag_ui.core import (
    BaseEvent,
    CustomEvent,
    EventType,
    RunAgentInput,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    StepFinishedEvent,
    StepStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
)

from botocore.exceptions import ClientError

from connect_bridge.store import Pending, Session

log = logging.getLogger("connect_bridge")

STEP_NAME = "Amazon Connect"
CLEARED = "cleared"
# A contact whose token expires within this many seconds is replaced by a new one.
TOKEN_REFRESH_MARGIN = 300
# The canvas's data request nodes time out at 30 s, so a turn never waits longer.
TURN_LIMIT = 32.0
# Each canvas turn arrives as one message, so a short quiet window ends the turn; the
# contact flow's escalation notice follows the canvas's hand-off line by about 1.5 s, so
# that line waits longer (docs/latency-plan.md, change 2).
QUIET_AFTER_REPLY = 0.8
ESCALATION_QUIET = 3.0
ESCALATION_HINT = "Connecting you to the HR service desk"
POLL_INTERVAL = 0.3
# The canvas drops a message sent before it greets, so a new contact waits for the
# greeting, and only for it (change 3).
GREETING_LIMIT = 12.0
# A run starting a contact claims the thread this long: the API calls plus the greeting.
START_LIMIT = 20.0
# SendMessage's errors that say the stored contact cannot take the message; the other two
# it documents, throttling and an internal error, are not about the contact.
CONTACT_GONE_CODES = ("AccessDeniedException", "ValidationException")
# The sub-agents the canvas delegates to; hr.js names each runtime session
# "{conversationId}-{domain}", and the conversation id is the contact id.
WARM_DOMAINS = ("profile", "pay", "travel")
SUB_AGENT_WARM_TIMEOUT = 15.0
# The spike's contact flow says this before transferring to a queue.
ESCALATION_PREFIX = "[flow] Escalation"
# Closing lines for a thread whose contact left the canvas. The page renders no CUSTOM
# event itself, so each also goes out as a text message.
ESCALATED_LINE = (
    "The HR service desk queue has this conversation now. "
    "A new message here starts over with the assistant."
)
ENDED_LINE = "The conversation ended. A new message here starts a new one."
FLOW_MESSAGE_PREFIX = "[flow]"
ENDED_CONTENT_TYPES = (
    "application/vnd.amazonaws.connect.event.chat.ended",
    "application/vnd.amazonaws.connect.event.participant.left",
)


@dataclass
class Settings:
    instance_id: str = field(default_factory=lambda: os.environ.get("CONNECT_INSTANCE_ID", ""))
    contact_flow_id: str = field(default_factory=lambda: os.environ.get("CONTACT_FLOW_ID", ""))
    region: str = field(default_factory=lambda: os.environ.get("AWS_REGION", "us-east-1"))
    agents_gateway_url: str = field(
        default_factory=lambda: os.environ.get("AGENTS_GATEWAY_URL", "").rstrip("/")
    )


def claims(token: str) -> dict:
    """The JWT payload, unverified: the runtime's authorizer verified it before this runs."""
    try:
        payload = token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except Exception:
        return {}


def session_key(token: str, thread_id: str) -> str:
    sub = str(claims(token).get("sub", ""))
    return f"{hashlib.sha256(sub.encode()).hexdigest()[:24]}#{thread_id}"


def last_user_text(run_input: RunAgentInput) -> str:
    for message in reversed(run_input.messages):
        if message.role == "user" and isinstance(message.content, str):
            return message.content
    return ""


@dataclass
class Reply:
    kind: str  # "text", "escalated" or "ended"
    text: str = ""


class ConnectClients:
    """The AWS clients and the WebSocket opener, injectable for tests."""

    def __init__(self, region: str) -> None:
        import boto3

        self.connect = boto3.client("connect", region_name=region)
        self.participant = boto3.client("connectparticipant", region_name=region)

    @staticmethod
    def post_json(url: str, headers: dict[str, str], body: dict, timeout: float) -> int:
        import urllib.request

        request = urllib.request.Request(
            url, data=json.dumps(body).encode(), method="POST", headers=headers
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read()
            return response.status

    @staticmethod
    def touch_websocket(url: str) -> None:
        import websocket

        # The flow starts once the customer's WebSocket has connected and subscribed;
        # Connect's acknowledgement says so, and the socket can close at once.
        ws = websocket.create_connection(url, timeout=20)
        try:
            ws.send(json.dumps({"topic": "aws/subscribe", "content": {"topics": ["aws/chat"]}}))
            ws.recv()
        finally:
            ws.close()


class ConnectTurn:
    def __init__(
        self,
        token: str,
        store: Any,
        settings: Settings | None = None,
        clients: Any = None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], Any] = asyncio.sleep,
    ) -> None:
        self.token = token
        self.store = store
        self.settings = settings or Settings()
        self.clients = clients or ConnectClients(self.settings.region)
        self.clock = clock
        self.sleep = sleep
        self.stats: dict[str, Any] = {}

    # ---- the run ---------------------------------------------------------------------

    async def run(self, run_input: RunAgentInput) -> AsyncIterator[BaseEvent]:
        thread, run = run_input.thread_id, run_input.run_id
        yield RunStartedEvent(type=EventType.RUN_STARTED, thread_id=thread, run_id=run)
        text = last_user_text(run_input)
        if not text.strip():
            yield RunErrorEvent(type=EventType.RUN_ERROR, message="no user message", code="BAD_INPUT")
            return
        yield StepStartedEvent(type=EventType.STEP_STARTED, step_name=STEP_NAME)
        session = await asyncio.to_thread(self.session_for, thread)
        try:
            await asyncio.to_thread(self.send, session, text)
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") not in CONTACT_GONE_CODES:
                raise
            # A contact that sat unused (a warm start nobody wrote in for a while) may have
            # ended without the bridge seeing it; one new contact takes the message.
            log.info("contact %s refused the message; starting a new contact", session.contact_id)
            session.closed = True
            await asyncio.to_thread(self.store.put, session)
            session = await asyncio.to_thread(self.session_for, thread)
            await asyncio.to_thread(self.send, session, text)
            self.stats["replaced"] = True
        replied = False
        async for reply in self.replies(session):
            if reply.kind == "text":
                replied = True
            else:
                session.closed = True
                yield CustomEvent(type=EventType.CUSTOM, name=f"connect/{reply.kind}", value={"text": reply.text})
            message_id = uuid.uuid4().hex
            yield TextMessageStartEvent(type=EventType.TEXT_MESSAGE_START, message_id=message_id, role="assistant")
            yield TextMessageContentEvent(
                type=EventType.TEXT_MESSAGE_CONTENT, message_id=message_id, delta=reply.text
            )
            yield TextMessageEndEvent(type=EventType.TEXT_MESSAGE_END, message_id=message_id)
        if replied and not session.token_cleared:
            await asyncio.to_thread(self.clear_token, session)
        await asyncio.to_thread(self.store.put, session)
        self.stats.update({"contact": session.contact_id, "replied": replied, "closed": session.closed})
        yield StepFinishedEvent(type=EventType.STEP_FINISHED, step_name=STEP_NAME)
        yield RunFinishedEvent(type=EventType.RUN_FINISHED, thread_id=thread, run_id=run)

    async def warm(self, run_input: RunAgentInput) -> None:
        """A warm start: the thread's contact, started and past its greeting, in the store."""
        session = await asyncio.to_thread(self.session_for, run_input.thread_id)
        self.stats.update({"contact": session.contact_id})
        if self.stats.get("started") and self.settings.agents_gateway_url:
            results = await asyncio.gather(
                *(asyncio.to_thread(self.warm_sub_agent, session.contact_id, d) for d in WARM_DOMAINS),
                return_exceptions=True,
            )
            self.stats["sub_agents_warmed"] = sum(1 for result in results if result is True)

    def warm_sub_agent(self, contact_id: str, domain: str) -> bool:
        """One sub-agent's warm message, as the canvas would address it; False on failure."""
        body = {
            "jsonrpc": "2.0",
            "id": f"warm-{domain}",
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "messageId": uuid.uuid4().hex,
                    "contextId": contact_id,
                    "parts": [{"kind": "text", "text": "warm"}],
                    "metadata": {"warm": True},
                }
            },
        }
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": f"{contact_id}-{domain}",
        }
        url = f"{self.settings.agents_gateway_url}/{domain}/invocations"
        try:
            status = self.clients.post_json(url, headers, body, SUB_AGENT_WARM_TIMEOUT)
        except Exception as error:  # noqa: BLE001 - a warm start never fails the run
            log.warning("warm start of the %s sub-agent failed: %s", domain, type(error).__name__)
            return False
        return status == 200

    def usage(self) -> dict[str, Any]:
        """Fields for the kit's run log line."""
        return {f"connect_{k}": v for k, v in self.stats.items()}

    # ---- the contact -----------------------------------------------------------------

    def session_for(self, thread_id: str) -> Session:
        """The thread's usable contact: the stored one, the one another run is starting,
        or a new one this run starts under a claim."""
        key = session_key(self.token, thread_id)
        token_exp = float(claims(self.token).get("exp", self.clock() + 3600))
        deadline = time.monotonic() + START_LIMIT
        while True:
            found = self.store.get(key)
            now = self.clock()
            if isinstance(found, Session) and self.usable(found, token_exp, now):
                return found
            waiting = isinstance(found, Pending) and found.until >= now
            if waiting and time.monotonic() < deadline:
                self.stats["waited"] = True
                time.sleep(POLL_INTERVAL)
                continue
            if time.monotonic() >= deadline or self.store.claim(key, now + START_LIMIT, now):
                break
        try:
            session = self.start_contact(key, token_exp)
        except Exception:
            self.store.release(key)
            raise
        self.store.put(session)
        self.stats["started"] = True
        return session

    def usable(self, session: Session, token_exp: float, now: float) -> bool:
        if session.closed or session.connection_expires_at <= now + 60:
            return False
        near_expiry = session.token_expires_at - now < TOKEN_REFRESH_MARGIN
        refreshed = token_exp > session.token_expires_at
        if near_expiry and refreshed:
            log.info("token near expiry for contact %s; starting a new contact", session.contact_id)
            return False
        return True

    def start_contact(self, key: str, token_exp: float) -> Session:
        settings = self.settings
        started = self.clients.connect.start_chat_contact(
            InstanceId=settings.instance_id,
            ContactFlowId=settings.contact_flow_id,
            ParticipantDetails={"DisplayName": "Employee"},
            Attributes={"hrToken": self.token, "employeeId": str(claims(self.token).get("sub", ""))},
            SupportedMessagingContentTypes=["text/plain"],
        )
        conn = self.clients.participant.create_participant_connection(
            Type=["WEBSOCKET", "CONNECTION_CREDENTIALS"], ParticipantToken=started["ParticipantToken"]
        )
        credentials = conn["ConnectionCredentials"]
        expiry = credentials.get("Expiry")
        expires_at = _epoch(expiry) if expiry else self.clock() + 3600
        # The flow runs only once the customer's WebSocket connects; after that the
        # participant API alone carries the conversation (phase 0).
        self.clients.touch_websocket(conn["Websocket"]["Url"])
        session = Session(
            key=key,
            contact_id=started["ContactId"],
            connection_token=credentials["ConnectionToken"],
            connection_expires_at=expires_at,
            token_expires_at=token_exp,
        )
        self.skip_greeting(session)
        log.info("started contact %s", session.contact_id)
        return session

    def skip_greeting(self, session: Session) -> None:
        """Waits for the canvas's greeting and marks it seen; the page has its own empty
        state. The canvas ignores a message sent before it greets."""
        start = time.monotonic()
        while time.monotonic() - start < GREETING_LIMIT:
            if any(classify(item) for item in self.new_items(session)):
                return
            time.sleep(POLL_INTERVAL)

    def send(self, session: Session, text: str) -> None:
        self.clients.participant.send_message(
            ContentType="text/plain", Content=text, ConnectionToken=session.connection_token
        )

    def clear_token(self, session: Session) -> None:
        self.clients.connect.update_contact_attributes(
            InitialContactId=session.contact_id,
            InstanceId=self.settings.instance_id,
            Attributes={"hrToken": CLEARED},
        )
        session.token_cleared = True

    # ---- the transcript --------------------------------------------------------------

    def new_items(self, session: Session) -> list[dict]:
        items = self.clients.participant.get_transcript(
            ConnectionToken=session.connection_token, SortOrder="ASCENDING", MaxResults=100
        ).get("Transcript", [])
        fresh = [item for item in items if item.get("Id") not in session.seen]
        session.remember([item["Id"] for item in fresh if item.get("Id")])
        return fresh

    async def replies(self, session: Session) -> AsyncIterator[Reply]:
        """Canvas replies to the message just sent, until it goes quiet or the turn limit."""
        start = last = time.monotonic()
        got_reply = False
        quiet = QUIET_AFTER_REPLY
        while time.monotonic() - start < TURN_LIMIT:
            await self.sleep(POLL_INTERVAL)
            fresh = await asyncio.to_thread(self.new_items, session)
            for item in fresh:
                reply = classify(item)
                if reply is None:
                    continue
                got_reply = True
                last = time.monotonic()
                quiet = quiet_after(reply.text)
                yield reply
                if reply.kind != "text":
                    return
            if got_reply and time.monotonic() - last > quiet:
                return


def quiet_after(text: str) -> float:
    """How long the bridge waits for more after a reply before it ends the turn."""
    return ESCALATION_QUIET if ESCALATION_HINT in text else QUIET_AFTER_REPLY


def classify(item: dict) -> Reply | None:
    """A transcript item as a reply to relay, or None for the customer's own and the rest."""
    if item.get("Type") == "EVENT" and item.get("ContentType") in ENDED_CONTENT_TYPES:
        return Reply("ended", ENDED_LINE)
    if item.get("Type") != "MESSAGE" or item.get("ParticipantRole") == "CUSTOMER":
        return None
    content = item.get("Content", "")
    if content.startswith(ESCALATION_PREFIX):
        return Reply("escalated", ESCALATED_LINE)
    if content.startswith(FLOW_MESSAGE_PREFIX):
        return None
    return Reply("text", content)


def _epoch(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    from datetime import datetime

    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
