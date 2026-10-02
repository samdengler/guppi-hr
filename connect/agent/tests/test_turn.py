"""ConnectTurn with fake Connect clients: no AWS, no network."""

from __future__ import annotations

import base64
import json
import time

import pytest
from ag_ui.core import RunAgentInput
from httpx import ASGITransport, AsyncClient

import connect_bridge.turn as turn_module
from connect_bridge.store import MemorySessionStore
from connect_bridge.turn import ESCALATED_LINE, ConnectTurn, Settings, classify, session_key


def jwt(sub: str = "employee-1", exp: float | None = None) -> str:
    payload = {"sub": sub, "exp": int(exp if exp is not None else time.time() + 3600)}
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"eyJhbGciOiJub25lIn0.{body}.sig"


class FakeConnect:
    def __init__(self) -> None:
        self.started: list[dict] = []
        self.updated: list[dict] = []

    def start_chat_contact(self, **kwargs):
        self.started.append(kwargs)
        return {"ContactId": f"contact-{len(self.started)}", "ParticipantToken": "pt"}

    def update_contact_attributes(self, **kwargs):
        self.updated.append(kwargs)


class FakeParticipant:
    """A transcript that answers each sent message with the scripted replies."""

    def __init__(self, script: dict[str, list[dict]], greeting: str | None = "Hi, I'm the HR assistant.") -> None:
        self.script = script
        self.items: list[dict] = []
        self.sent: list[str] = []
        self.greeting = greeting

    def _add(self, **item) -> None:
        item.setdefault("Id", f"i{len(self.items)}")
        self.items.append(item)

    def create_participant_connection(self, **kwargs):
        if self.greeting:
            self._add(Type="MESSAGE", ParticipantRole="SYSTEM", Content=self.greeting)
        return {
            "ConnectionCredentials": {"ConnectionToken": "ct", "Expiry": "2099-01-01T00:00:00Z"},
            "Websocket": {"Url": "wss://example"},
        }

    def send_message(self, Content, **kwargs):
        self.sent.append(Content)
        self._add(Type="MESSAGE", ParticipantRole="CUSTOMER", Content=Content)
        for reply in self.script.get(Content, []):
            self._add(**reply)

    def get_transcript(self, **kwargs):
        return {"Transcript": list(self.items)}


class FakeClients:
    def __init__(self, participant: FakeParticipant) -> None:
        self.connect = FakeConnect()
        self.participant = participant
        self.touched: list[str] = []

    def touch_websocket(self, url: str) -> None:
        self.touched.append(url)


async def no_sleep(_seconds: float) -> None:
    return None


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(turn_module, "QUIET_AFTER_REPLY", 0.0)
    monkeypatch.setattr(turn_module, "GREETING_QUIET", 0.0)
    monkeypatch.setattr(turn_module, "POLL_INTERVAL", 0.0)
    monkeypatch.setattr(turn_module.time, "sleep", lambda _s: None)


def run_input(text: str, thread: str = "t1") -> RunAgentInput:
    return RunAgentInput(
        thread_id=thread,
        run_id="r1",
        messages=[{"id": "m1", "role": "user", "content": text}],
        tools=[],
        context=[],
        state={},
        forwarded_props={},
    )


def bot(text: str) -> dict:
    return {"Type": "MESSAGE", "ParticipantRole": "SYSTEM", "Content": text}


SETTINGS = Settings(instance_id="inst", contact_flow_id="flow", region="us-east-1")


async def collect(turn: ConnectTurn, text: str, thread: str = "t1") -> list:
    return [event async for event in turn.run(run_input(text, thread))]


def types(events) -> list[str]:
    return [e.type.value if hasattr(e.type, "value") else str(e.type) for e in events]


async def test_first_run_starts_a_contact_relays_the_reply_and_clears_the_token():
    participant = FakeParticipant({"hello": [bot("I can help with your profile.")]})
    clients = FakeClients(participant)
    store = MemorySessionStore()
    token = jwt()
    events = await collect(ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep), "hello")

    assert types(events) == [
        "RUN_STARTED",
        "STEP_STARTED",
        "TEXT_MESSAGE_START",
        "TEXT_MESSAGE_CONTENT",
        "TEXT_MESSAGE_END",
        "STEP_FINISHED",
        "RUN_FINISHED",
    ]
    assert events[3].delta == "I can help with your profile."
    started = clients.connect.started[0]
    assert started["Attributes"]["hrToken"] == token
    assert started["Attributes"]["employeeId"] == "employee-1"
    assert clients.touched == ["wss://example"]
    # The greeting was skipped, and the token left the contact record after the reply.
    assert all("Hi, I'm" not in getattr(e, "delta", "") for e in events)
    assert clients.connect.updated == [
        {"InitialContactId": "contact-1", "InstanceId": "inst", "Attributes": {"hrToken": "cleared"}}
    ]
    saved = store.get(session_key(token, "t1"))
    assert saved.contact_id == "contact-1" and saved.token_cleared


async def test_a_later_run_reuses_the_contact_and_does_not_clear_again():
    participant = FakeParticipant({"one": [bot("first")], "two": [bot("second"), bot("third")]})
    clients = FakeClients(participant)
    store = MemorySessionStore()
    token = jwt()
    await collect(ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep), "one")
    events = await collect(ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep), "two")
    deltas = [e.delta for e in events if getattr(e, "delta", None)]
    assert deltas == ["second", "third"]
    assert len(clients.connect.started) == 1
    assert len(clients.connect.updated) == 1
    assert participant.sent == ["one", "two"]


async def test_escalation_becomes_a_closing_line_and_a_custom_event_and_closes_the_thread():
    participant = FakeParticipant(
        {"talk to someone": [bot("Connecting you to the HR service desk."), bot("[flow] Escalation: transferring you.")]}
    )
    clients = FakeClients(participant)
    store = MemorySessionStore()
    token = jwt()
    events = await collect(ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep), "talk to someone")
    custom = [e for e in events if types([e]) == ["CUSTOM"]]
    assert [c.name for c in custom] == ["connect/escalated"]
    # The page renders no CUSTOM event itself, so the closing line also arrives as text.
    texts = [e.delta for e in events if types([e]) == ["TEXT_MESSAGE_CONTENT"]]
    assert texts == ["Connecting you to the HR service desk.", ESCALATED_LINE]
    assert store.get(session_key(token, "t1")).closed
    # A closed thread gets a new contact on its next run.
    participant.script["again"] = [bot("hello again")]
    await collect(ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep), "again")
    assert len(clients.connect.started) == 2


async def test_a_token_near_expiry_with_a_fresher_one_gets_a_new_contact():
    participant = FakeParticipant({"one": [bot("a")], "two": [bot("b")]})
    clients = FakeClients(participant)
    store = MemorySessionStore()
    now = time.time()
    old = jwt(exp=now + 120)
    await collect(ConnectTurn(old, store, SETTINGS, clients, sleep=no_sleep), "one")
    fresh = jwt(exp=now + 3600)
    await collect(ConnectTurn(fresh, store, SETTINGS, clients, sleep=no_sleep), "two")
    assert len(clients.connect.started) == 2
    assert clients.connect.started[1]["Attributes"]["hrToken"] == fresh


async def test_threads_and_users_do_not_share_contacts():
    participant = FakeParticipant({"x": [bot("ok")]})
    clients = FakeClients(participant)
    store = MemorySessionStore()
    await collect(ConnectTurn(jwt("a"), store, SETTINGS, clients, sleep=no_sleep), "x", thread="t1")
    await collect(ConnectTurn(jwt("a"), store, SETTINGS, clients, sleep=no_sleep), "x", thread="t2")
    await collect(ConnectTurn(jwt("b"), store, SETTINGS, clients, sleep=no_sleep), "x", thread="t1")
    assert len(clients.connect.started) == 3


def test_classify_keeps_canvas_text_and_drops_the_rest():
    assert classify({"Type": "MESSAGE", "ParticipantRole": "CUSTOMER", "Content": "hi"}) is None
    assert classify(bot("[flow] The conversation ended.")) is None
    assert classify(bot("Done.")).text == "Done."
    assert classify(bot("[flow] Escalation: transferring you.")).kind == "escalated"
    ended = {"Type": "EVENT", "ContentType": "application/vnd.amazonaws.connect.event.chat.ended"}
    assert classify(ended).kind == "ended"


async def test_the_kit_app_streams_the_bridge(monkeypatch):
    import connect_bridge.app as app_module

    participant = FakeParticipant({"hello": [bot("Hi from Connect.")]})
    clients = FakeClients(participant)
    store = MemorySessionStore()
    monkeypatch.setattr(app_module, "_store", store)
    monkeypatch.setattr(
        app_module, "ConnectTurn", lambda token, s: ConnectTurn(token, s, SETTINGS, clients, sleep=no_sleep)
    )
    from guppi_agent import create_app

    app = create_app(app_module.build_agent)
    body = run_input("hello").model_dump(by_alias=True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.post(
            "/invocations", json=body, headers={"authorization": f"Bearer {jwt()}"}
        )
    data = [json.loads(line[5:]) for line in response.text.splitlines() if line.startswith("data:")]
    assert [d["type"] for d in data][0] == "RUN_STARTED"
    assert any(d.get("delta") == "Hi from Connect." for d in data)
    assert data[-1]["type"] == "RUN_FINISHED"
