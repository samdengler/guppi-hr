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
from connect_bridge.turn import HOP_ATTRIBUTES, ESCALATED_LINE, ConnectTurn, Settings, classify, session_key


CLEARED_ALL = {name: "cleared" for name in HOP_ATTRIBUTES}


def jwt(sub: str = "employee-1", exp: float | None = None) -> str:
    payload = {"sub": sub, "exp": int(exp if exp is not None else time.time() + 3600)}
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"eyJhbGciOiJub25lIn0.{body}.sig"


class FakeConnect:
    def __init__(self) -> None:
        self.started: list[dict] = []
        self.updated: list[dict] = []
        self.stopped: list[str] = []

    def start_chat_contact(self, **kwargs):
        self.started.append(kwargs)
        n = len(self.started)
        return {"ContactId": f"contact-{n}", "ParticipantToken": f"pt-{n}"}

    def update_contact_attributes(self, **kwargs):
        self.updated.append(kwargs)

    def stop_contact(self, ContactId, **kwargs):
        self.stopped.append(ContactId)


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
        # The canvas greets once, when the contact's first connection comes up.
        if self.greeting and not self.items:
            self._add(Type="MESSAGE", ParticipantRole="SYSTEM", Content=self.greeting)
        return {
            "ConnectionCredentials": {"ConnectionToken": "ct", "Expiry": "2099-01-01T00:00:00Z"},
            "Websocket": {"Url": "wss://example"},
        }

    def send_message(self, Content, **kwargs):
        self.sent.append(Content)
        self._add(Type="MESSAGE", ParticipantRole="CUSTOMER", Content=Content)
        own = self.items[-1]["Id"]
        for reply in self.script.get(Content, []):
            self._add(**reply)
        return {"Id": own}

    def get_transcript(self, SortOrder="ASCENDING", MaxResults=15, **kwargs):
        # As Connect pages it: the first MaxResults items in the order asked for.
        items = list(self.items) if SortOrder == "ASCENDING" else list(reversed(self.items))
        return {"Transcript": items[:MaxResults]}


class FakeSocket:
    """Pushes the transcript items added after it opened, as Connect's aws/chat frames."""

    def __init__(self, participant: FakeParticipant) -> None:
        self.participant = participant
        self.next = len(participant.items)
        self.sent: list[str] = []
        self.closed = False

    def send(self, frame: str) -> None:
        self.sent.append(frame)

    def close(self) -> None:
        self.closed = True


class FakeClients:
    def __init__(self, participant: FakeParticipant, websocket: bool = True) -> None:
        self.connect = FakeConnect()
        self.participant = participant
        self.touched: list[str] = []
        self.posted: list[dict] = []
        self.websocket = websocket
        self.sockets: list[FakeSocket] = []

    def open_websocket(self, url: str) -> FakeSocket:
        if not self.websocket:
            raise OSError("refused")
        socket = FakeSocket(self.participant)
        self.sockets.append(socket)
        return socket

    @staticmethod
    def receive(ws: FakeSocket, timeout: float) -> str | None:
        items = ws.participant.items
        if ws.next >= len(items):
            return None
        item = items[ws.next]
        ws.next += 1
        return json.dumps({"topic": "aws/chat", "content": json.dumps(item)})

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
    # Without OBO_PROVIDER (tests) the hop tokens pass the token through unchanged.
    for name in ("hrProfileToken", "hrPayToken", "hrTravelToken", "hrToolsToken"):
        assert started["Attributes"][name] == token
    assert "hrToken" not in started["Attributes"]
    assert started["Attributes"]["employeeId"] == "employee-1"
    assert clients.touched == ["wss://example"]
    # The greeting was skipped, and the token left the contact record after the reply.
    assert all("Hi, I'm" not in getattr(e, "delta", "") for e in events)
    assert clients.connect.updated == [
        {"InitialContactId": "contact-1", "InstanceId": "inst", "Attributes": CLEARED_ALL}
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
    assert clients.connect.started[1]["Attributes"]["hrPayToken"] == fresh


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


async def test_the_canvass_end_of_turn_line_ends_the_turn_and_is_never_shown(monkeypatch):
    # A long quiet window: only the marker can end this turn early.
    monkeypatch.setattr(turn_module, "QUIET_AFTER_REPLY", 30.0)
    participant = FakeParticipant({"hello": [bot("Your address is 1 Main St."), bot(turn_module.END_OF_TURN)]})
    clients = FakeClients(participant)
    turn = ConnectTurn(jwt(), MemorySessionStore(), SETTINGS, clients, sleep=no_sleep)
    started = time.monotonic()
    events = await collect(turn, "hello")
    assert time.monotonic() - started < 1.0
    assert [e.delta for e in events if hasattr(e, "delta")] == ["Your address is 1 Main St."]
    assert turn.usage()["connect_end_of_turn"] is True


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


class EndedParticipant(FakeParticipant):
    """Contacts whose participant has left refuse messages and new connections alike; a
    retired connection token is refused while its participant can still reconnect."""

    def __init__(self, script) -> None:
        super().__init__(script)
        self.ended: set[str] = set()
        self.retired: set[str] = set()
        self.owner: dict[str, str] = {}  # connection token -> participant token
        self.refused = 0

    def create_participant_connection(self, ParticipantToken="pt-1", **kwargs):
        if ParticipantToken in self.ended:
            raise client_error("AccessDeniedException")
        conn = super().create_participant_connection(**kwargs)
        token = f"ct-{len(self.owner) + 1}"
        self.owner[token] = ParticipantToken
        conn["ConnectionCredentials"]["ConnectionToken"] = token
        return conn

    def send_message(self, Content, ConnectionToken="", **kwargs):
        if self.owner.get(ConnectionToken) in self.ended or ConnectionToken in self.retired:
            self.refused += 1
            raise client_error("AccessDeniedException")
        return super().send_message(Content)


async def test_an_ended_contact_is_stopped_and_replaced_once():
    participant = EndedParticipant({"hello": [bot("Hi there.")]})
    clients = FakeClients(participant)
    store = MemorySessionStore()
    token = jwt()
    await ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep).warm(warm_input())
    participant.ended.add("pt-1")
    turn = ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep)
    events = await collect(turn, "hello")
    assert participant.refused == 1 and len(clients.connect.started) == 2
    assert "contact-1" in clients.connect.stopped
    assert [e.delta for e in events if hasattr(e, "delta")] == ["Hi there."]
    assert turn.usage()["connect_replaced"] is True


async def test_a_retired_connection_token_gets_a_fresh_one_on_the_same_contact():
    participant = EndedParticipant({"hello": [bot("Hi there.")]})
    clients = FakeClients(participant)
    store = MemorySessionStore()
    token = jwt()
    await ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep).warm(warm_input())
    participant.retired.add(store.get(session_key(token, "t1")).connection_token)
    turn = ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep)
    events = await collect(turn, "hello")
    assert len(clients.connect.started) == 1 and clients.connect.stopped == []
    assert [e.delta for e in events if hasattr(e, "delta")] == ["Hi there."]
    assert turn.usage()["connect_reconnected"] is True


async def test_a_message_the_service_refuses_is_not_taken_for_an_ended_contact():
    class Refusing(FakeParticipant):
        def send_message(self, Content, **kwargs):
            raise client_error("ValidationException")

    clients = FakeClients(Refusing({}))
    store = MemorySessionStore()
    from botocore.exceptions import ClientError

    with pytest.raises(ClientError):
        await collect(ConnectTurn(jwt(), store, SETTINGS, clients, sleep=no_sleep), "hello")
    assert len(clients.connect.started) == 1 and clients.connect.stopped == []


async def test_a_message_over_connects_limit_is_answered_without_sending():
    participant = FakeParticipant({})
    clients = FakeClients(participant)
    turn = ConnectTurn(jwt(), MemorySessionStore(), SETTINGS, clients, sleep=no_sleep)
    events = await collect(turn, "x" * 1500)
    assert [e.delta for e in events if hasattr(e, "delta")] == [turn_module.TOO_LONG_LINE]
    assert participant.sent == [] and clients.connect.started == []


async def test_throttling_is_not_taken_for_an_ended_contact():
    class Throttled(FakeParticipant):
        def send_message(self, Content, **kwargs):
            raise client_error("ThrottlingException")

    clients = FakeClients(Throttled({}))
    from botocore.exceptions import ClientError

    with pytest.raises(ClientError):
        await collect(ConnectTurn(jwt(), MemorySessionStore(), SETTINGS, clients, sleep=no_sleep), "hello")
    assert len(clients.connect.started) == 1 and clients.connect.stopped == []


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


# ---- replies pushed over the customer WebSocket (change 5) ----------------------------


class LateParticipant(FakeParticipant):
    """The canvas answers only after the run's WebSocket is open, as it does in Connect."""

    def __init__(self, script) -> None:
        super().__init__(script)
        self.later: list[dict] = []
        self.connections = 0

    def create_participant_connection(self, **kwargs):
        self.connections += 1
        conn = super().create_participant_connection(**kwargs)
        conn["ConnectionCredentials"]["ConnectionToken"] = f"ct-{self.connections}"
        return conn

    def send_message(self, Content, **kwargs):
        self.sent.append(Content)
        self._add(Type="MESSAGE", ParticipantRole="CUSTOMER", Content=Content)
        self.later.extend(self.script.get(Content, []))


class PushingClients(FakeClients):
    def receive(self, ws, timeout):
        if self.participant.later:
            for reply in self.participant.later:
                self.participant._add(**reply)
            self.participant.later = []
        return FakeClients.receive(ws, timeout)


async def test_replies_arrive_over_the_runs_websocket(monkeypatch):
    monkeypatch.setattr(turn_module, "QUIET_AFTER_REPLY", 0.05)
    participant = LateParticipant({"hello": [bot("First."), bot("Second.")]})
    clients = PushingClients(participant)
    store = MemorySessionStore()
    turn = ConnectTurn(jwt(), store, SETTINGS, clients, sleep=no_sleep)
    events = await collect(turn, "hello")
    assert [e.delta for e in events if hasattr(e, "delta")] == ["First.", "Second."]
    assert turn.usage()["connect_pushed"] is True
    assert len(clients.sockets) == 1 and clients.sockets[0].closed
    # The run's new connection token replaced the stored one.
    assert store.get(session_key(jwt(), "t1")).connection_token == "ct-2"


async def test_without_a_websocket_the_run_polls():
    participant = FakeParticipant({"hello": [bot("Polled.")]})
    clients = FakeClients(participant, websocket=False)
    turn = ConnectTurn(jwt(), MemorySessionStore(), SETTINGS, clients, sleep=no_sleep)
    events = await collect(turn, "hello")
    assert [e.delta for e in events if hasattr(e, "delta")] == ["Polled."]
    assert turn.usage()["connect_pushed"] is False


async def test_a_contact_stored_without_a_participant_token_polls():
    participant = FakeParticipant({"hello": [bot("Polled.")]})
    clients = FakeClients(participant)
    store = MemorySessionStore()
    token = jwt()
    await ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep).warm(warm_input())
    stored = store.get(session_key(token, "t1"))
    stored.participant_token = ""
    store.put(stored)
    turn = ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep)
    events = await collect(turn, "hello")
    assert [e.delta for e in events if hasattr(e, "delta")] == ["Polled."]
    assert clients.sockets == [] and turn.usage()["connect_pushed"] is False


async def test_a_quiet_stream_sends_heartbeats_until_the_turn_limit(monkeypatch):
    monkeypatch.setattr(turn_module, "TURN_LIMIT", 0.05)
    monkeypatch.setattr(turn_module, "HEARTBEAT_SECONDS", 0.001)
    clients = FakeClients(FakeParticipant({}))
    turn = ConnectTurn(jwt(), MemorySessionStore(), SETTINGS, clients, sleep=no_sleep)
    events = await collect(turn, "anyone there?")
    # No reply: the run says so instead of leaving an empty answer (finding 3).
    assert [e.delta for e in events if hasattr(e, "delta")] == [turn_module.NO_REPLY_LINE]
    assert turn.usage()["connect_no_reply"] is True
    assert any("aws/heartbeat" in frame for frame in clients.sockets[0].sent)


def test_chat_item_reads_only_chat_frames():
    item = {"Id": "i1", "Type": "MESSAGE", "Content": "hi"}
    assert turn_module.chat_item(json.dumps({"topic": "aws/chat", "content": json.dumps(item)})) == item
    assert turn_module.chat_item(json.dumps({"topic": "aws/heartbeat"})) is None
    assert turn_module.chat_item("not json") is None


def test_a_new_contact_is_announced_before_its_connection_and_greeting():
    participant = LateParticipant({})
    clients = FakeClients(participant)
    turn = ConnectTurn(jwt(), MemorySessionStore(), SETTINGS, clients, sleep=no_sleep)
    seen = []
    turn.on_contact = lambda contact_id: seen.append((contact_id, participant.connections))
    turn.start_contact("k", time.time() + 3600)
    assert seen == [("contact-1", 0)]


# ---- the critique's failure paths (connect-hardening) ---------------------------------


async def test_the_token_leaves_the_contact_right_after_the_greeting():
    clients = FakeClients(FakeParticipant({}))
    turn = ConnectTurn(jwt(), MemorySessionStore(), SETTINGS, clients, sleep=no_sleep)
    await turn.warm(warm_input())
    # A warm start nobody writes in leaves no token on the record (finding 1).
    assert [u["Attributes"] for u in clients.connect.updated] == [CLEARED_ALL]
    assert clients.connect.started[0]["ChatDurationInMinutes"] == 60


async def test_a_contact_that_never_greets_is_a_failed_start(monkeypatch):
    monkeypatch.setattr(turn_module, "GREETING_LIMIT", 0.01)
    clients = FakeClients(FakeParticipant({}, greeting=None))
    store = MemorySessionStore()
    token = jwt()
    with pytest.raises(turn_module.StartFailed):
        await ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep).warm(warm_input())
    # The contact is ended, its token cleared, and the claim released for the next run.
    assert clients.connect.stopped == ["contact-1"]
    assert clients.connect.updated[0]["Attributes"] == CLEARED_ALL
    assert store.get(session_key(token, "t1")) is None


async def test_a_late_reply_from_the_previous_turn_is_not_shown_as_this_ones(monkeypatch):
    monkeypatch.setattr(turn_module, "QUIET_AFTER_REPLY", 0.0)
    participant = FakeParticipant({"one": [bot("Answer one.")], "two": [bot("Answer two.")]})
    clients = FakeClients(participant)
    store = MemorySessionStore()
    token = jwt()
    await collect(ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep), "one")
    # A second message the canvas sends after the first turn ended.
    participant._add(**bot("A late extra line for turn one."))
    turn = ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep)
    events = await collect(turn, "two")
    assert [e.delta for e in events if hasattr(e, "delta")] == ["Answer two."]
    assert turn.usage()["connect_stale"] == 1


class BreakingClients(FakeClients):
    """The socket opens, then fails on its first read, as a reset connection does."""

    def receive(self, ws, timeout):
        raise ConnectionResetError("reset")


async def test_a_socket_that_fails_mid_turn_falls_back_to_polling(monkeypatch):
    monkeypatch.setattr(turn_module, "QUIET_AFTER_REPLY", 0.05)
    participant = LateParticipant({"hello": [bot("Polled after the reset.")]})
    clients = BreakingClients(participant)

    async def deliver_late(_seconds):
        for reply in participant.later:
            participant._add(**reply)
        participant.later = []

    turn = ConnectTurn(jwt(), MemorySessionStore(), SETTINGS, clients, sleep=deliver_late)
    events = await collect(turn, "hello")
    assert [e.delta for e in events if hasattr(e, "delta")] == ["Polled after the reset."]
    assert turn.usage()["connect_socket_failed"] is True
    assert clients.sockets[0].closed


async def test_relayed_items_are_saved_even_when_the_run_fails(monkeypatch):
    monkeypatch.setattr(turn_module, "QUIET_AFTER_REPLY", 30.0)
    participant = FakeParticipant({"one": [bot("Answer one.")]})
    clients = FakeClients(participant)
    store = MemorySessionStore()
    token = jwt()

    class Boom(Exception):
        pass

    def broken_receive(ws, timeout):
        raise Boom()

    clients.receive = broken_receive
    clients.open_websocket = lambda url: FakeSocket(participant)

    async def boom_sleep(_seconds):
        raise Boom()

    turn = ConnectTurn(token, store, SETTINGS, clients, sleep=boom_sleep)
    with pytest.raises(Boom):
        await collect(turn, "one")
    # "Answer one." was relayed before the failure, and the store knows it.
    seen = store.get(session_key(token, "t1")).seen
    assert any(item["Id"] in seen for item in participant.items if item.get("Content") == "Answer one.")


async def test_a_new_thread_ends_the_contact_of_the_one_the_page_left():
    clients = FakeClients(FakeParticipant({}))
    store = MemorySessionStore()
    token = jwt()
    await ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep).warm(warm_input("t1"))
    second = warm_input("t2")
    second.forwarded_props["previousThreadId"] = "t1"
    await ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep).warm(second)
    assert clients.connect.stopped == ["contact-1"]
    assert store.get(session_key(token, "t1")).closed


async def test_a_token_near_expiry_restarts_the_conversation_and_says_so():
    participant = FakeParticipant({"hello": [bot("Hi there.")]})
    clients = FakeClients(participant)
    store = MemorySessionStore()
    old = jwt(exp=time.time() + 200)
    await ConnectTurn(old, store, SETTINGS, clients, sleep=no_sleep).warm(warm_input())
    fresh = jwt(exp=time.time() + 3600)
    turn = ConnectTurn(fresh, store, SETTINGS, clients, sleep=no_sleep)
    events = await collect(turn, "hello")
    texts = [e.delta for e in events if hasattr(e, "delta")]
    assert texts == [turn_module.RESTARTED_LINE, "Hi there."]
    assert clients.connect.stopped == ["contact-1"] and len(clients.connect.started) == 2


async def test_a_contact_near_its_chat_duration_is_replaced_before_connect_ends_it():
    participant = FakeParticipant({"hello": [bot("Hi there.")]})
    clients = FakeClients(participant)
    store = MemorySessionStore()
    token = jwt()
    now = [time.time()]
    await ConnectTurn(token, store, SETTINGS, clients, clock=lambda: now[0], sleep=no_sleep).warm(warm_input())
    now[0] += 59 * 60
    await collect(ConnectTurn(token, store, SETTINGS, clients, clock=lambda: now[0], sleep=no_sleep), "hello")
    assert len(clients.connect.started) == 2 and clients.connect.stopped == ["contact-1"]


async def test_a_canvas_error_is_shown_logged_and_closes_the_thread(caplog):
    participant = FakeParticipant(
        {"hello": [bot("[flow] The Agentic CX block returned an error."), {"Type": "EVENT", "ContentType": "application/vnd.amazonaws.connect.event.participant.left"}]}
    )
    clients = FakeClients(participant)
    store = MemorySessionStore()
    token = jwt()
    turn = ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep)
    events = await collect(turn, "hello")
    assert [e.delta for e in events if hasattr(e, "delta")] == [turn_module.CANVAS_ERROR_LINE]
    assert turn.usage()["connect_canvas_error"] is True
    assert "bridge_problem canvas_error" in caplog.text
    assert store.get(session_key(token, "t1")).closed


async def test_a_closing_line_closes_the_thread_and_ends_the_contact_at_once(monkeypatch):
    monkeypatch.setattr(turn_module, "QUIET_AFTER_REPLY", 30.0)
    participant = FakeParticipant(
        {"talk to someone": [bot("I opened HR ticket HR-1. This conversation is now closed."), bot(turn_module.CONVERSATION_CLOSED)]}
    )
    clients = FakeClients(participant)
    store = MemorySessionStore()
    token = jwt()
    turn = ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep)
    started = time.monotonic()
    events = await collect(turn, "talk to someone")
    assert time.monotonic() - started < 1.0
    assert [e.delta for e in events if hasattr(e, "delta")] == ["I opened HR ticket HR-1. This conversation is now closed."]
    assert [e.name for e in events if types([e]) == ["CUSTOM"]] == ["connect/closed"]
    assert store.get(session_key(token, "t1")).closed
    assert clients.connect.stopped == ["contact-1"]


async def test_an_invisible_end_mark_ends_the_turn_and_is_stripped(monkeypatch):
    monkeypatch.setattr(turn_module, "QUIET_AFTER_REPLY", 30.0)
    participant = FakeParticipant({"hello": [bot("Your address is 1 Main St." + turn_module.END_MARK)]})
    clients = FakeClients(participant)
    turn = ConnectTurn(jwt(), MemorySessionStore(), SETTINGS, clients, sleep=no_sleep)
    started = time.monotonic()
    events = await collect(turn, "hello")
    assert time.monotonic() - started < 1.0
    assert [e.delta for e in events if hasattr(e, "delta")] == ["Your address is 1 Main St."]
    assert turn.usage()["connect_end_of_turn"] is True


async def test_an_invisible_closed_mark_closes_the_thread(monkeypatch):
    monkeypatch.setattr(turn_module, "QUIET_AFTER_REPLY", 30.0)
    participant = FakeParticipant({"bye": [bot("Have a good day." + turn_module.CLOSED_MARK)]})
    clients = FakeClients(participant)
    store = MemorySessionStore()
    token = jwt()
    events = await collect(ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep), "bye")
    assert [e.delta for e in events if hasattr(e, "delta")] == ["Have a good day."]
    assert store.get(session_key(token, "t1")).closed and clients.connect.stopped == ["contact-1"]


class FakeExchanger:
    """Stands in for AgentCore Identity: an agents or canvas token per Okta token."""

    def __init__(self, kind: str, fail: bool = False) -> None:
        self.kind, self.fail, self.enabled, self.subjects = kind, fail, True, []

    def exchange(self, subject: str) -> str:
        from connect_bridge.obo import ExchangeError

        if self.fail:
            raise ExchangeError("ValidationException")
        self.subjects.append(subject)
        return jwt(f"{self.kind}-token", exp=time.time() + 1800)


@pytest.fixture
def hop_tokens(monkeypatch):
    import connect_bridge.turn as turn_module

    agents = {d: FakeExchanger(f"{d}-agents") for d in turn_module.DOMAINS}
    canvas = FakeExchanger("canvas")
    monkeypatch.setattr(turn_module, "AGENTS_TOKENS", agents)
    monkeypatch.setattr(turn_module, "CANVAS_TOKENS", canvas)
    return agents, canvas


async def test_the_contact_carries_hop_tokens_and_never_the_okta_token(hop_tokens):
    agents, canvas = hop_tokens
    clients = FakeClients(FakeParticipant({"hello": [bot("Hi.")]}))
    token = jwt()
    await collect(ConnectTurn(token, MemorySessionStore(), SETTINGS, clients, sleep=no_sleep), "hello")
    (started,) = clients.connect.started
    attributes = started["Attributes"]
    assert token not in attributes.values()
    for domain in ("profile", "pay", "travel"):
        assert subject_of_fake(attributes[f"hr{domain.capitalize()}Token"]) == f"{domain}-agents-token"
        assert agents[domain].subjects == [token]
    assert subject_of_fake(attributes["hrToolsToken"]) == "canvas-token" and canvas.subjects == [token]


async def test_the_warm_calls_send_the_agents_token(hop_tokens):
    clients = FakeClients(FakeParticipant({}))
    token = jwt()
    turn = ConnectTurn(token, MemorySessionStore(), GATEWAY, clients, sleep=no_sleep)
    await turn.warm(warm_input())
    assert len(clients.posted) == 3
    for posted in clients.posted:
        # Each sub-agent is warmed with its own agents token.
        domain = posted["url"].split("/")[-2]
        bearer = posted["headers"]["Authorization"].removeprefix("Bearer ")
        assert bearer != token and subject_of_fake(bearer) == f"{domain}-agents-token"


async def test_a_failed_exchange_starts_no_contact_and_says_so(monkeypatch):
    import connect_bridge.turn as turn_module

    monkeypatch.setattr(turn_module, "AGENTS_TOKENS",
                        {d: FakeExchanger("agents", fail=(d == "pay")) for d in turn_module.DOMAINS})
    monkeypatch.setattr(turn_module, "CANVAS_TOKENS", FakeExchanger("canvas"))
    clients = FakeClients(FakeParticipant({}))
    events = await collect(ConnectTurn(jwt(), MemorySessionStore(), SETTINGS, clients, sleep=no_sleep), "hello")
    assert clients.connect.started == []
    text = "".join(getattr(e, "delta", "") for e in events)
    assert text == turn_module.SIGNIN_LINE
    assert events[-1].type == "RUN_FINISHED"


def subject_of_fake(token: str) -> str:
    from connect_bridge.turn import claims

    return claims(token)["sub"]


async def test_a_missing_provider_setting_never_puts_the_okta_token_on_a_contact(monkeypatch):
    # Critique of the build, finding 4: fail closed, not pass-through.
    import connect_bridge.turn as turn_module
    from connect_bridge.obo import TokenExchanger

    monkeypatch.delenv("OBO", raising=False)
    monkeypatch.delenv("OBO_PROVIDER", raising=False)
    monkeypatch.setattr(turn_module, "AGENTS_TOKENS", {d: TokenExchanger([f"hr.agents.{d}"]) for d in turn_module.DOMAINS})
    monkeypatch.setattr(turn_module, "CANVAS_TOKENS", TokenExchanger(["hr.tools.policy"]))
    clients = FakeClients(FakeParticipant({}))
    events = await collect(ConnectTurn(jwt(), MemorySessionStore(), SETTINGS, clients, sleep=no_sleep), "hello")
    assert clients.connect.started == []
    assert "".join(getattr(e, "delta", "") for e in events) == turn_module.SIGNIN_LINE
