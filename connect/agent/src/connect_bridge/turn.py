"""One AG-UI run as one Connect chat turn (docs/platform-plan.md, "Bridge design").

A thread's first run, or the page's warm start before it, starts a Connect chat contact on
the contact flow that holds the Agentic CX block, with the caller's token and subject as
contact attributes and a 60-minute chat duration. The bridge opens the customer's WebSocket
once (the flow runs only after it connects), waits for the canvas's greeting, and then
blanks the token attribute: the designer session keeps the value it read at its start
(phase 0), so the token is on the contact record for a few seconds at most (D42).

Every run sends the latest user message with the participant API and relays each canvas
message as an AG-UI text message. The canvas ends each turn with a hidden END_OF_TURN line,
or ends the conversation, which Connect reports as an event; only a generative journey's
answer, which no node can follow, ends on a short silence instead (D42). Messages come over
a customer WebSocket the run opens after its send, from a fresh URL for the stored
participant token (change 5); when that fails the run polls the transcript. Items older
than the run's own message are a previous turn's and are not shown. The relayed items are
saved however the run ends.

A warm start does the contact's start ahead of the first message (D39) and warms each
sub-agent through the agents gateway on the runtime session and thread the canvas will use
(D41). A run that finds another run starting the contact waits for it. A stored contact
that refuses the message gets a fresh connection, and then, if it has ended, one new
contact. The bridge ends the contacts it leaves behind: a replaced one, and the previous
thread's when the page starts a new one.

Nothing here holds state between runs; the session store does.
"""

from __future__ import annotations

import asyncio
import base64
import concurrent.futures
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
# Connect's minimum; the default is 25 hours, which held every page's chat that long
# against the instance's concurrent-chat quota (critique finding 2).
CHAT_DURATION_MINUTES = 60
# The canvas's data request nodes time out at 30 s, so a turn never waits longer.
TURN_LIMIT = 32.0
# The canvas ends a turn's last message with END_MARK, and the message before it ends the
# conversation (a ticket, a goodbye) with CLOSED_MARK: one invisible character on the
# reply itself, since Connect bills chat by the message (connect/acxd/hr.js). The bridge
# strips it. The separate hidden lines of the first version are still understood.
END_MARK = "\u2063"  # INVISIBLE SEPARATOR
CLOSED_MARK = "\u2064"  # INVISIBLE PLUS
END_OF_TURN = "[flow] end"
CONVERSATION_CLOSED = "[flow] closed"
# A generative journey's answer has no END_OF_TURN after it; this much silence ends it.
QUIET_AFTER_REPLY = 0.8
POLL_INTERVAL = 0.3
# The canvas drops a message sent before it greets, so a new contact waits for the
# greeting, and only for it (change 3); no greeting in this long is a failed start.
GREETING_LIMIT = 12.0
# A run starting a contact claims the thread this long, longer than the slowest start:
# the API calls, a WebSocket connect (10 s at most) and the greeting.
START_LIMIT = 45.0
# SendMessage refuses a connection that is no longer the participant's this way; a
# ValidationException is about the message, and the other two errors it documents,
# throttling and an internal error, are not about the contact.
CONTACT_GONE_CODES = ("AccessDeniedException",)
# SendMessage takes at most this much text/plain content (the participant service model);
# the kit accepts longer messages, so the bridge says so instead of failing the contact.
MAX_MESSAGE_CHARS = 1024
TOO_LONG_LINE = (
    "That message is too long for the HR assistant: keep it under 1,024 characters, "
    "or split it into two messages."
)
NO_REPLY_LINE = "No answer came back from the HR assistant. Try again in a moment."
# Shown when the thread's contact was replaced (its token or its chat duration ran out),
# since the canvas's state, a pending change included, did not carry over (finding 8).
RESTARTED_LINE = "(The assistant started a new conversation, so it may ask for details again.)"
# The sub-agents the canvas delegates to; hr.js names each runtime session
# "{conversationId}-{domain}", and the conversation id is the contact id. The stack sets
# WARM_DOMAINS from connect/acxd/domains.json, the list hr.js checks itself against.
WARM_DOMAINS = tuple(
    d for d in os.environ.get("WARM_DOMAINS", "profile,pay,travel").split(",") if d.strip()
)
SUB_AGENT_WARM_TIMEOUT = 15.0
# Connect closes an idle customer WebSocket; a run that waits longer than this sends a
# heartbeat.
HEARTBEAT_SECONDS = 10.0
# The contact flow says this before its queue transfer, which the canvas no longer takes
# (EscalationFlow opens a ticket and ends); kept for a contact flow that still does.
ESCALATION_PREFIX = "[flow] Escalation"
# Closing lines for a thread whose contact left the canvas. The page renders no CUSTOM
# event itself, so each also goes out as a text message.
ESCALATED_LINE = (
    "The HR service desk queue has this conversation now. "
    "A new message here starts over with the assistant."
)
ENDED_LINE = "The conversation ended. A new message here starts a new one."
# The contact flow says this when the Agentic CX block fails, then disconnects
# (scripts/contact_flow.py); before, the bridge hid it and the run looked fine.
CANVAS_ERROR_PREFIX = "[flow] The Agentic CX block returned an error"
CANVAS_ERROR_LINE = (
    "The HR assistant ran into an error and ended this conversation. "
    "A new message here starts a new one."
)
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


def subject(token: str) -> str:
    """The caller's stable id: Okta's `uid` when the token has one (an Okta access token's
    `sub` is the login, an email address), else `sub` (D46)."""
    found = claims(token)
    return str(found.get("uid") or found.get("sub", ""))


def session_key(token: str, thread_id: str) -> str:
    return f"{hashlib.sha256(subject(token).encode()).hexdigest()[:24]}#{thread_id}"


def last_user_text(run_input: RunAgentInput) -> str:
    for message in reversed(run_input.messages):
        if message.role == "user" and isinstance(message.content, str):
            return message.content
    return ""


@dataclass
class Reply:
    kind: str  # "text", "end" (END_OF_TURN), "closed", "escalated", "error" or "ended"
    text: str = ""
    # For a text reply that carried a mark: "end" (the turn is over) or "closed".
    mark: str = ""


class StartFailed(RuntimeError):
    """A new contact never greeted; the canvas would drop the message."""


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
    def open_websocket(url: str) -> Any:
        """A customer WebSocket, subscribed to the chat and acknowledged by Connect."""
        import websocket

        ws = websocket.create_connection(url, timeout=10)
        try:
            ws.send(json.dumps({"topic": "aws/subscribe", "content": {"topics": ["aws/chat"]}}))
            ws.recv()
        except BaseException:
            ws.close()
            raise
        return ws

    @staticmethod
    def receive(ws: Any, timeout: float) -> str | None:
        """The next frame, or None when none came within `timeout` seconds."""
        import websocket

        ws.settimeout(timeout)
        try:
            return ws.recv()
        except websocket.WebSocketTimeoutException:
            return None

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
        # Set by a warm start: called with the contact id as soon as a new contact exists.
        self.on_contact: Callable[[str], None] | None = None

    # ---- the run ---------------------------------------------------------------------

    async def run(self, run_input: RunAgentInput) -> AsyncIterator[BaseEvent]:
        thread, run = run_input.thread_id, run_input.run_id
        yield RunStartedEvent(type=EventType.RUN_STARTED, thread_id=thread, run_id=run)
        text = last_user_text(run_input)
        if not text.strip():
            yield RunErrorEvent(type=EventType.RUN_ERROR, message="no user message", code="BAD_INPUT")
            return
        yield StepStartedEvent(type=EventType.STEP_STARTED, step_name=STEP_NAME)
        if len(text) > MAX_MESSAGE_CHARS:
            self.stats["too_long"] = True
            for event in text_events(TOO_LONG_LINE):
                yield event
            yield StepFinishedEvent(type=EventType.STEP_FINISHED, step_name=STEP_NAME)
            yield RunFinishedEvent(type=EventType.RUN_FINISHED, thread_id=thread, run_id=run)
            return
        session = await asyncio.to_thread(self.session_for, thread)
        mark_span(session.contact_id)
        try:
            if self.stats.get("restarted"):
                for event in text_events(RESTARTED_LINE):
                    yield event
            session, own_id = await asyncio.to_thread(self.deliver, session, thread, text)
            # The stream opens after the send, so a new connection never races it; the
            # canvas takes longer than the open to answer, and the relay's first read of
            # the transcript catches anything sooner.
            stream = await asyncio.to_thread(self.open_stream, session)
            self.stats["pushed"] = stream is not None
            replied = False
            async for reply in self.relay(session, own_id, stream):
                if reply.kind == "text":
                    replied = True
                else:
                    session.closed = True
                    if reply.kind == "error":
                        self.stats["canvas_error"] = True
                        problem("canvas_error", session.contact_id)
                    yield CustomEvent(type=EventType.CUSTOM, name=f"connect/{reply.kind}", value={"text": reply.text})
                if reply.text:
                    for event in text_events(reply.text):
                        yield event
            if not replied and not session.closed:
                self.stats["no_reply"] = True
                problem("no_reply", session.contact_id)
                for event in text_events(NO_REPLY_LINE):
                    yield event
            if session.closed:
                await asyncio.to_thread(self.end_contact, session)
        finally:
            # The relayed items and the newest connection token are kept however the run
            # ends, so a later run never shows this turn's replies again (finding 4).
            self.save(session)
        self.stats.update({"contact": session.contact_id, "replied": replied, "closed": session.closed})
        yield StepFinishedEvent(type=EventType.STEP_FINISHED, step_name=STEP_NAME)
        yield RunFinishedEvent(type=EventType.RUN_FINISHED, thread_id=thread, run_id=run)

    def deliver(self, session: Session, thread: str, text: str) -> tuple[Session, str | None]:
        """Sends the message; returns the session it went to and the message's id.

        A refused connection gets a fresh one on the participant token first; if that is
        refused too, the contact has ended, and one new contact takes the message."""
        try:
            return session, self.send(session, text)
        except ClientError as error:
            if error_code(error) not in CONTACT_GONE_CODES:
                raise
        if session.participant_token and self.reconnect(session):
            try:
                return session, self.send(session, text)
            except ClientError as error:
                if error_code(error) not in CONTACT_GONE_CODES:
                    raise
        log.info("contact %s refused the message; starting a new contact", session.contact_id)
        self.end_contact(session)
        self.save(session)
        self.stats["replaced"] = True
        session = self.session_for(thread)
        return session, self.send(session, text)

    async def warm(self, run_input: RunAgentInput) -> None:
        """A warm start: the thread's contact, started and past its greeting, in the store,
        each sub-agent warmed while the greeting is awaited, and the contact of the thread
        the page just left ended."""
        props = run_input.forwarded_props if isinstance(run_input.forwarded_props, dict) else {}
        previous = props.get("previousThreadId")
        if isinstance(previous, str) and previous and previous != run_input.thread_id:
            await asyncio.to_thread(self.end_thread, previous)
        warming: list[concurrent.futures.Future] = []
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=len(WARM_DOMAINS))

        def warm_sub_agents(contact_id: str) -> None:
            warming.extend(pool.submit(self.warm_sub_agent, contact_id, d) for d in WARM_DOMAINS)

        if self.settings.agents_gateway_url:
            self.on_contact = warm_sub_agents
        try:
            session = await asyncio.to_thread(self.session_for, run_input.thread_id)
            mark_span(session.contact_id)
            self.stats.update({"contact": session.contact_id})
            if warming:
                done = await asyncio.gather(*(asyncio.wrap_future(f) for f in warming), return_exceptions=True)
                self.stats["sub_agents_warmed"] = sum(1 for result in done if result is True)
        finally:
            self.on_contact = None
            pool.shutdown(wait=False)

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
        replaced: Session | None = None
        while True:
            found = self.store.get(key)
            now = self.clock()
            if isinstance(found, Session):
                if self.usable(found, token_exp, now):
                    return found
                if not found.closed:
                    replaced = found
            waiting = isinstance(found, Pending) and found.until >= now
            if waiting and time.monotonic() < deadline:
                self.stats["waited"] = True
                time.sleep(POLL_INTERVAL)
                continue
            if time.monotonic() >= deadline or self.store.claim(key, now + START_LIMIT, now):
                break
        if replaced is not None:
            # A live contact this thread is leaving (its token is about to expire): end it
            # rather than leave it open for the rest of its hour.
            self.stats["restarted"] = True
            self.end_contact(replaced)
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
        if session.started_at and now - session.started_at > CHAT_DURATION_MINUTES * 60 - 120:
            # Connect ends the chat at its duration; a new one before that, not mid-turn.
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
            Attributes={"hrToken": self.token, "employeeId": subject(self.token)},
            SupportedMessagingContentTypes=["text/plain"],
            ChatDurationInMinutes=CHAT_DURATION_MINUTES,
        )
        if self.on_contact is not None:
            # The sub-agents need only the contact id, so they warm during the greeting.
            self.on_contact(started["ContactId"])
        session = Session(
            key=key,
            contact_id=started["ContactId"],
            connection_token="",
            connection_expires_at=0.0,
            token_expires_at=token_exp,
            participant_token=started["ParticipantToken"],
            started_at=self.clock(),
        )
        try:
            conn = self.clients.participant.create_participant_connection(
                Type=["WEBSOCKET", "CONNECTION_CREDENTIALS"], ParticipantToken=started["ParticipantToken"]
            )
            self.take_credentials(session, conn["ConnectionCredentials"])
            # The flow runs only once the customer's WebSocket connects; after that the
            # participant API alone carries the conversation (phase 0).
            self.clients.touch_websocket(conn["Websocket"]["Url"])
            self.skip_greeting(session)
        except Exception:
            self.end_contact(session)
            raise
        finally:
            # The designer read the token when the flow started; the contact record no
            # longer needs it, whatever happens next (finding 1).
            self.clear_token(session)
        log.info("started contact %s", session.contact_id)
        return session

    def skip_greeting(self, session: Session) -> None:
        """Waits for the canvas's greeting and marks it seen; the page has its own empty
        state. The canvas ignores a message sent before it greets, so a contact that never
        greets is a failed start (finding 3)."""
        start = time.monotonic()
        while time.monotonic() - start < GREETING_LIMIT:
            if any(classify(item) for item in self.new_items(session)):
                return
            time.sleep(POLL_INTERVAL)
        problem("no_greeting", session.contact_id)
        raise StartFailed(f"contact {session.contact_id} did not greet in {GREETING_LIMIT:.0f} s")

    def send(self, session: Session, text: str) -> str | None:
        """Sends the message; returns its transcript id."""
        response = self.clients.participant.send_message(
            ContentType="text/plain", Content=text, ConnectionToken=session.connection_token
        )
        return (response or {}).get("Id")

    def clear_token(self, session: Session) -> None:
        try:
            self.clients.connect.update_contact_attributes(
                InitialContactId=session.contact_id,
                InstanceId=self.settings.instance_id,
                Attributes={"hrToken": CLEARED},
            )
            session.token_cleared = True
        except Exception as error:  # noqa: BLE001 - logged; the run goes on
            problem("token_not_cleared", session.contact_id, type(error).__name__)
            self.stats["token_not_cleared"] = True

    def end_contact(self, session: Session) -> None:
        """Ends the contact in Connect (an ended one stays ended) and marks it closed."""
        session.closed = True
        try:
            self.clients.connect.stop_contact(ContactId=session.contact_id, InstanceId=self.settings.instance_id)
            self.stats["ended"] = self.stats.get("ended", 0) + 1
        except Exception as error:  # noqa: BLE001 - already ended, or not found
            log.info("stop_contact %s: %s", session.contact_id, type(error).__name__)

    def end_thread(self, thread_id: str) -> None:
        """Ends the contact of a thread the page has left."""
        found = self.store.get(session_key(self.token, thread_id))
        if isinstance(found, Session) and not found.closed:
            self.end_contact(found)
            self.save(found)

    def save(self, session: Session) -> None:
        try:
            self.store.put(session)
        except Exception:  # noqa: BLE001 - the next run reads what was saved before
            log.exception("could not save contact %s", session.contact_id)

    # ---- the stream ------------------------------------------------------------------

    @staticmethod
    def take_credentials(session: Session, credentials: dict) -> None:
        session.connection_token = credentials["ConnectionToken"]
        expiry = credentials.get("Expiry")
        session.connection_expires_at = _epoch(expiry) if expiry else time.time() + 3600

    def reconnect(self, session: Session) -> bool:
        """A fresh connection token for the stored participant token."""
        try:
            conn = self.clients.participant.create_participant_connection(
                Type=["CONNECTION_CREDENTIALS"], ParticipantToken=session.participant_token
            )
        except Exception as error:  # noqa: BLE001 - the participant has left
            log.info("no new connection for contact %s: %s", session.contact_id, type(error).__name__)
            return False
        self.take_credentials(session, conn["ConnectionCredentials"])
        self.stats["reconnected"] = True
        return True

    def open_stream(self, session: Session) -> Any:
        """A WebSocket for this run's messages, or None to poll instead."""
        if not session.participant_token:
            return None
        try:
            conn = self.clients.participant.create_participant_connection(
                Type=["WEBSOCKET", "CONNECTION_CREDENTIALS"], ParticipantToken=session.participant_token
            )
            # A new connection may retire the stored connection token, so the new one
            # replaces it and is saved with the session at the end of the run.
            self.take_credentials(session, conn["ConnectionCredentials"])
            return self.clients.open_websocket(conn["Websocket"]["Url"])
        except Exception as error:  # noqa: BLE001 - polling still works
            log.warning("no WebSocket for contact %s (%s); polling", session.contact_id, type(error).__name__)
            return None

    async def relay(self, session: Session, own_id: str | None, ws: Any) -> AsyncIterator[Reply]:
        """The canvas's replies to the message just sent, until END_OF_TURN, the end of the
        conversation, a journey answer's silence, or the turn limit."""
        start = time.monotonic()
        quiet_until: float | None = None
        try:
            # The first read covers anything that came before the socket was listening,
            # and finds this run's own message: items before it are a previous turn's.
            items = await asyncio.to_thread(self.new_items, session)
            ids = [item.get("Id") for item in items]
            if own_id and own_id in ids:
                stale = items[: ids.index(own_id)]
                if any(classify(item) for item in stale):
                    self.stats["stale"] = sum(1 for item in stale if classify(item))
                items = items[ids.index(own_id) + 1 :]
            while True:
                for item in items:
                    reply = classify(item)
                    if reply is None:
                        continue
                    if reply.kind == "end":
                        self.stats["end_of_turn"] = True
                        return
                    yield reply
                    if reply.kind != "text":
                        return
                    if reply.mark == "end":
                        self.stats["end_of_turn"] = True
                        return
                    if reply.mark == "closed":
                        yield Reply("closed")
                        return
                    quiet_until = time.monotonic() + QUIET_AFTER_REPLY
                now = time.monotonic()
                wait = TURN_LIMIT - (now - start)
                if quiet_until is not None:
                    wait = min(wait, quiet_until - now)
                if wait <= 0:
                    return
                if ws is not None:
                    try:
                        items = await self.pushed_items(session, ws, wait)
                        continue
                    except Exception as error:  # noqa: BLE001 - the rest of the turn polls
                        problem("socket_failed", session.contact_id, type(error).__name__)
                        self.stats["socket_failed"] = True
                        await asyncio.to_thread(close_quietly, ws)
                        ws = None
                await self.sleep(min(POLL_INTERVAL, wait))
                items = await asyncio.to_thread(self.new_items, session)
        finally:
            if ws is not None:
                await asyncio.to_thread(close_quietly, ws)

    async def pushed_items(self, session: Session, ws: Any, wait: float) -> list[dict]:
        """The next new item Connect pushes within `wait` seconds, as a list (or empty)."""
        frame = await asyncio.to_thread(self.clients.receive, ws, min(wait, HEARTBEAT_SECONDS))
        if frame is None:
            if HEARTBEAT_SECONDS < wait:
                await asyncio.to_thread(ws.send, json.dumps({"topic": "aws/heartbeat"}))
            return []
        item = chat_item(frame)
        if not item or item.get("Id") in session.seen:
            return []
        session.remember([item["Id"]] if item.get("Id") else [])
        return [item]

    # ---- the transcript --------------------------------------------------------------

    def new_items(self, session: Session) -> list[dict]:
        """Transcript items not seen before, oldest first, from the newest 100."""
        items = self.clients.participant.get_transcript(
            ConnectionToken=session.connection_token, SortOrder="DESCENDING", MaxResults=100
        ).get("Transcript", [])
        items = list(reversed(items))
        fresh = [item for item in items if item.get("Id") not in session.seen]
        session.remember([item["Id"] for item in fresh if item.get("Id")])
        return fresh


def mark_span(contact_id: str) -> None:
    """The contact id on the run's span: the sub-agents' spans carry it as hr.thread_id,
    which joins the two traces the canvas splits (aws-feedback TC1, finding 14)."""
    try:
        from opentelemetry import trace

        trace.get_current_span().set_attribute("connect.contact_id", contact_id)
    except Exception:  # noqa: BLE001 - tracing never fails a run
        pass


def problem(kind: str, contact_id: str, detail: str = "") -> None:
    """One line the stack's alarm counts (connect/infra, BridgeAlarms): the word
    bridge_problem, then the kind."""
    log.error("bridge_problem %s contact=%s %s", kind, contact_id, detail)


def text_events(text: str) -> list[BaseEvent]:
    message_id = uuid.uuid4().hex
    return [
        TextMessageStartEvent(type=EventType.TEXT_MESSAGE_START, message_id=message_id, role="assistant"),
        TextMessageContentEvent(type=EventType.TEXT_MESSAGE_CONTENT, message_id=message_id, delta=text),
        TextMessageEndEvent(type=EventType.TEXT_MESSAGE_END, message_id=message_id),
    ]


def error_code(error: ClientError) -> str:
    return error.response.get("Error", {}).get("Code", "")


def close_quietly(ws: Any) -> None:
    try:
        ws.close()
    except Exception:  # noqa: BLE001
        pass


def chat_item(frame: str) -> dict | None:
    """The transcript item an `aws/chat` frame carries, or None for any other frame."""
    try:
        message = json.loads(frame)
        if message.get("topic") != "aws/chat":
            return None
        content = message.get("content")
        item = json.loads(content) if isinstance(content, str) else content
        return item if isinstance(item, dict) else None
    except (TypeError, ValueError):
        return None


def classify(item: dict) -> Reply | None:
    """A transcript item as a reply to relay, the end of a turn, or None for the
    customer's own message and the rest."""
    if item.get("Type") == "EVENT" and item.get("ContentType") in ENDED_CONTENT_TYPES:
        return Reply("ended", ENDED_LINE)
    if item.get("Type") != "MESSAGE" or item.get("ParticipantRole") == "CUSTOMER":
        return None
    content = item.get("Content", "")
    if content.strip() == END_OF_TURN:
        return Reply("end")
    if content.strip() == CONVERSATION_CLOSED:
        return Reply("closed")
    if content.startswith(ESCALATION_PREFIX):
        return Reply("escalated", ESCALATED_LINE)
    if content.startswith(CANVAS_ERROR_PREFIX):
        return Reply("error", CANVAS_ERROR_LINE)
    if content.startswith(FLOW_MESSAGE_PREFIX):
        return None
    if content.endswith(END_MARK):
        return Reply("text", content.rstrip(END_MARK), mark="end")
    if content.endswith(CLOSED_MARK):
        return Reply("text", content.rstrip(CLOSED_MARK), mark="closed")
    return Reply("text", content)


def _epoch(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    from datetime import datetime

    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
