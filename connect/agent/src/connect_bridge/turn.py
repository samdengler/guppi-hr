"""One AG-UI run as one Connect chat turn (docs/platform-plan.md, "Bridge design").

A thread's first run starts a Connect chat contact on the contact flow that holds the
Agentic CX block, with the caller's token and subject as contact attributes, opens the
customer's WebSocket once (the flow runs only after it connects), closes it, and skips the
canvas's greeting. Every run then sends the latest user message with the participant API
and polls the transcript, relaying each canvas message as an AG-UI text message until the
canvas has been quiet for a moment. After the first reply the token attribute is blanked,
so the employee's token does not stay on the contact record (phase 0); a token close to
expiry gets a new contact, since a running designer session never sees a changed one.

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

from connect_bridge.store import Session

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
        await asyncio.to_thread(self.send, session, text)
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
        self.stats = {"contact": session.contact_id, "replied": replied, "closed": session.closed}
        yield StepFinishedEvent(type=EventType.STEP_FINISHED, step_name=STEP_NAME)
        yield RunFinishedEvent(type=EventType.RUN_FINISHED, thread_id=thread, run_id=run)

    def usage(self) -> dict[str, Any]:
        """Fields for the kit's run log line."""
        return {f"connect_{k}": v for k, v in self.stats.items()}

    # ---- the contact -----------------------------------------------------------------

    def session_for(self, thread_id: str) -> Session:
        key = session_key(self.token, thread_id)
        session = self.store.get(key)
        now = self.clock()
        token_exp = float(claims(self.token).get("exp", now + 3600))
        if session and not session.closed and session.connection_expires_at > now + 60:
            near_expiry = session.token_expires_at - now < TOKEN_REFRESH_MARGIN
            refreshed = token_exp > session.token_expires_at
            if not (near_expiry and refreshed):
                return session
            log.info("token near expiry for contact %s; starting a new contact", session.contact_id)
        return self.start_contact(key, token_exp)

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
