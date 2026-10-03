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
        self.posted: list[dict] = []

    def touch_websocket(self, url: str) -> None:
        self.touched.append(url)

    def post_json(self, url: str, headers: dict, body: dict, timeout: float) -> int:
        self.posted.append({"url": url, "headers": headers, "body": body})
        if "pay" in url and getattr(self, "pay_down", False):
            raise OSError("timed out")
        return 200


async def no_sleep(_seconds: float) -> None:
    return None


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(turn_module, "QUIET_AFTER_REPLY", 0.0)
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


# ---- Latency plan, changes 2 and 3 (docs/latency-plan.md) ------------------------------


class LateGreeting(FakeParticipant):
    """The greeting appears only after a few transcript reads, as the flow takes ~1.3 s."""

    def __init__(self, script, reads_before_greeting: int = 3) -> None:
        super().__init__(script, greeting=None)
        self.reads = 0
        self.reads_before_greeting = reads_before_greeting
        self.sent_after_reads: list[int] = []

    def get_transcript(self, **kwargs):
        self.reads += 1
        if self.reads == self.reads_before_greeting:
            self._add(Type="MESSAGE", ParticipantRole="SYSTEM", Content="Hi, I'm the HR assistant.")
        return super().get_transcript(**kwargs)

    def send_message(self, Content, **kwargs):
        self.sent_after_reads.append(self.reads)
        super().send_message(Content, **kwargs)


async def test_a_new_contact_sends_the_message_as_soon_as_the_greeting_arrives():
    # The canvas ignores a message sent before it greets, so the bridge waits for the
    # greeting, and only for it: no quiet period after it.
    participant = LateGreeting({"hello": [bot("Hi from Connect.")]}, reads_before_greeting=3)
    clients = FakeClients(participant)
    events = await collect(ConnectTurn(jwt(), MemorySessionStore(), SETTINGS, clients, sleep=no_sleep), "hello")
    assert participant.sent_after_reads == [3]
    texts = [e.delta for e in events if types([e]) == ["TEXT_MESSAGE_CONTENT"]]
    assert texts == ["Hi from Connect."]


def test_a_turn_ends_soon_after_its_reply_except_for_the_escalation_line():
    assert turn_module.quiet_after("Your address on file is 1 Main St.") == turn_module.QUIET_AFTER_REPLY
    assert turn_module.QUIET_AFTER_REPLY <= 1.0 or turn_module.QUIET_AFTER_REPLY == 0.0
    # The contact flow's escalation notice follows the canvas's line by about 1.5 s.
    assert turn_module.quiet_after("Connecting you to the HR service desk.") == turn_module.ESCALATION_QUIET
    assert turn_module.ESCALATION_QUIET >= 3.0


def test_the_websocket_closes_once_connect_acknowledges_with_no_fixed_wait(monkeypatch):
    calls = []

    class FakeSocket:
        def send(self, payload):
            calls.append(("send", json.loads(payload)["topic"]))

        def recv(self):
            calls.append(("recv",))
            return json.dumps({"topic": "aws/subscribe", "content": {"status": 200}})

        def close(self):
            calls.append(("close",))

    import types as pytypes

    fake_module = pytypes.SimpleNamespace(create_connection=lambda url, timeout: FakeSocket())
    monkeypatch.setitem(__import__("sys").modules, "websocket", fake_module)

    def no_fixed_wait(_seconds):
        raise AssertionError("touch_websocket must not sleep")

    monkeypatch.setattr(turn_module.time, "sleep", no_fixed_wait)
    turn_module.ConnectClients.touch_websocket("wss://example")
    assert calls == [("send", "aws/subscribe"), ("recv",), ("close",)]


# ---- warm start and start claims (D39) ----------------------------------------------


def warm_input(thread: str = "t1") -> RunAgentInput:
    return RunAgentInput(
        thread_id=thread, run_id="w1", messages=[], tools=[], context=[], state={},
        forwarded_props={"warm": True},
    )


async def test_a_warm_start_opens_the_contact_and_the_first_message_only_sends():
    participant = FakeParticipant({"hello": [bot("Hi there.")]})
    clients = FakeClients(participant)
    store = MemorySessionStore()
    token = jwt()
    warm = ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep)
    await warm.warm(warm_input())
    assert len(clients.connect.started) == 1 and warm.usage()["connect_started"] is True

    turn = ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep)
    events = await collect(turn, "hello")
    assert len(clients.connect.started) == 1
    assert [e.delta for e in events if hasattr(e, "delta")] == ["Hi there."]
    assert "connect_started" not in turn.usage()


async def test_a_run_waits_for_a_contact_another_run_is_starting(monkeypatch):
    participant = FakeParticipant({"hello": [bot("Hi there.")]})
    clients = FakeClients(participant)
    store = MemorySessionStore()
    token = jwt()
    # A warm start on another microVM holds the claim; it finishes during the second poll.
    starter = ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep)
    key = session_key(token, "t1")
    assert store.claim(key, time.time() + 20, time.time())
    polls = []

    def finish_start(_seconds):
        polls.append(_seconds)
        if len(polls) == 2:
            store.put(starter.start_contact(key, time.time() + 3600))

    monkeypatch.setattr(turn_module.time, "sleep", finish_start)
    turn = ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep)
    events = await collect(turn, "hello")
    assert len(clients.connect.started) == 1
    assert [e.delta for e in events if hasattr(e, "delta")] == ["Hi there."]
    assert turn.usage()["connect_waited"] is True


async def test_a_stale_claim_is_taken_over():
    participant = FakeParticipant({"hello": [bot("Hi there.")]})
    clients = FakeClients(participant)
    store = MemorySessionStore()
    token = jwt()
    store.claim(session_key(token, "t1"), time.time() - 1, time.time() - 21)
    await collect(ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep), "hello")
    assert len(clients.connect.started) == 1


async def test_a_failed_start_releases_its_claim():
    class Refusing(FakeConnect):
        def start_chat_contact(self, **kwargs):
            raise RuntimeError("quota")

    clients = FakeClients(FakeParticipant({}))
    clients.connect = Refusing()
    store = MemorySessionStore()
    token = jwt()
    with pytest.raises(RuntimeError):
        await ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep).warm(warm_input())
    assert store.get(session_key(token, "t1")) is None


def client_error(code: str):
    from botocore.exceptions import ClientError

    return ClientError({"Error": {"Code": code, "Message": code}}, "SendMessage")


class EndedOnce(FakeParticipant):
    """The first contact's connection refuses messages, as an ended contact would."""

    def __init__(self, script, code: str = "AccessDeniedException") -> None:
        super().__init__(script)
        self.code = code
        self.connections = 0
        self.refused = 0

    def create_participant_connection(self, **kwargs):
        self.connections += 1
        conn = super().create_participant_connection(**kwargs)
        conn["ConnectionCredentials"]["ConnectionToken"] = f"ct-{self.connections}"
        return conn

    def send_message(self, Content, ConnectionToken, **kwargs):
        if ConnectionToken == "ct-1":
            self.refused += 1
            raise client_error(self.code)
        super().send_message(Content)


async def test_a_contact_that_refuses_the_message_is_replaced_once():
    participant = EndedOnce({"hello": [bot("Hi there.")]})
    clients = FakeClients(participant)
    store = MemorySessionStore()
    token = jwt()
    await ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep).warm(warm_input())
    turn = ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep)
    events = await collect(turn, "hello")
    assert participant.refused == 1 and len(clients.connect.started) == 2
    assert [e.delta for e in events if hasattr(e, "delta")] == ["Hi there."]
    assert turn.usage()["connect_replaced"] is True


async def test_throttling_is_not_taken_for_an_ended_contact():
    participant = EndedOnce({"hello": [bot("Hi there.")]}, code="ThrottlingException")
    clients = FakeClients(participant)
    store = MemorySessionStore()
    token = jwt()
    await ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep).warm(warm_input())
    from botocore.exceptions import ClientError

    with pytest.raises(ClientError):
        await collect(ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep), "hello")
    assert len(clients.connect.started) == 1


def test_the_dynamo_store_claims_only_when_no_live_claim_is_held():
    from connect_bridge.store import DynamoSessionStore, Pending

    class Table:
        def __init__(self) -> None:
            self.items: dict = {}

        def get_item(self, Key, **kwargs):
            item = self.items.get(Key["pk"])
            return {"Item": item} if item else {}

        def put_item(self, Item, ConditionExpression=None, ExpressionAttributeValues=None):
            current = self.items.get(Item["pk"], {})
            if ConditionExpression and current.get("startingUntil", -1) >= ExpressionAttributeValues[":now"]:
                raise client_error("ConditionalCheckFailedException")
            self.items[Item["pk"]] = Item

        def delete_item(self, Key, ConditionExpression=None):
            if "startingUntil" not in self.items.get(Key["pk"], {}):
                raise client_error("ConditionalCheckFailedException")
            del self.items[Key["pk"]]

    store = DynamoSessionStore(Table())
    assert store.claim("k", until=1020, now=1000)
    assert isinstance(store.get("k"), Pending)
    assert not store.claim("k", until=1030, now=1010)
    assert store.claim("k", until=1050, now=1030)
    store.release("k")
    assert store.get("k") is None
    store.release("k")  # nothing to release is fine


# ---- sub-agent warm messages (D41) ----------------------------------------------------

GATEWAY = Settings(
    instance_id="inst", contact_flow_id="flow", region="us-east-1",
    agents_gateway_url="https://agents.example",
)


async def test_a_warm_start_warms_each_sub_agent_on_the_canvass_session():
    clients = FakeClients(FakeParticipant({}))
    token = jwt()
    turn = ConnectTurn(token, MemorySessionStore(), GATEWAY, clients, sleep=no_sleep)
    await turn.warm(warm_input())
    assert sorted(p["url"] for p in clients.posted) == [
        "https://agents.example/pay/invocations",
        "https://agents.example/profile/invocations",
        "https://agents.example/travel/invocations",
    ]
    profile = next(p for p in clients.posted if "profile" in p["url"])
    assert profile["headers"]["Authorization"] == f"Bearer {token}"
    assert profile["headers"]["X-Amzn-Bedrock-AgentCore-Runtime-Session-Id"] == "contact-1-profile"
    message = profile["body"]["params"]["message"]
    assert message["contextId"] == "contact-1" and message["metadata"] == {"warm": True}
    assert turn.usage()["connect_sub_agents_warmed"] == 3


async def test_a_failed_sub_agent_warm_does_not_fail_the_warm_start():
    clients = FakeClients(FakeParticipant({}))
    clients.pay_down = True
    turn = ConnectTurn(jwt(), MemorySessionStore(), GATEWAY, clients, sleep=no_sleep)
    await turn.warm(warm_input())
    assert turn.usage()["connect_sub_agents_warmed"] == 2


async def test_no_sub_agent_warm_for_a_contact_already_running():
    clients = FakeClients(FakeParticipant({}))
    store = MemorySessionStore()
    token = jwt()
    await ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep).warm(warm_input())
    again = ConnectTurn(token, store, GATEWAY, clients, sleep=no_sleep)
    await again.warm(warm_input())
    assert clients.posted == []
