"""The bridge's timings in debug mode (D54): one guppi.timing event before the run ends on
a debug run, none otherwise, and only names, times and ids in it."""

from __future__ import annotations

import itertools
import json
import threading
import time

import connect_bridge.turn as turn_module
import pytest
from connect_bridge.store import MemorySessionStore
from connect_bridge.timing import EVENT_NAME, Timing
from connect_bridge.turn import ConnectTurn, session_key
from test_turn import (  # noqa: F401 - fast is an autouse fixture
    SETTINGS,
    FakeClients,
    FakeParticipant,
    bot,
    client_error,
    fast,
    jwt,
    no_sleep,
    run_input,
    types,
    warm_input,
)

QUESTION = "What is my home address on file?"
END_MARK = turn_module.END_MARK


@pytest.fixture(autouse=True)
def ticking(monkeypatch):
    """Each read of the timing clock is 5 ms after the last, so every step has a length and
    the order of the marks shows in their times."""
    ticks = itertools.count()
    lock = threading.Lock()

    def clock() -> float:
        with lock:
            return next(ticks) * 0.005

    monkeypatch.setattr(turn_module, "Timing", lambda: Timing(clock=clock))


def debug_input(text: str, thread: str = "t1", debug: object = True):
    run = run_input(text, thread)
    run.forwarded_props = {"project": "hr", "debug": debug}
    return run


async def events_of(turn: ConnectTurn, run) -> list:
    return [event async for event in turn.run(run)]


def timing_events(events) -> list:
    return [e for e in events if getattr(e, "name", None) == EVENT_NAME]


def step(value: dict, name: str) -> dict:
    (found,) = [s for s in value["steps"] if s["name"] == name]
    return found


def assert_well_formed(value: dict) -> None:
    assert set(value) == {"steps", "total_ms", "ids", "notes"}
    total = value["total_ms"]
    for s in value["steps"]:
        assert set(s) == {"name", "start_ms", "end_ms", "lane"}
        assert 0 <= s["start_ms"] <= total
        assert s["end_ms"] is None or s["start_ms"] <= s["end_ms"] <= total
        assert s["lane"] in ("bridge", "exchange", "connect")
    starts = [s["start_ms"] for s in value["steps"] if s["name"] != "total"]
    assert starts == sorted(starts)
    assert value["steps"][-1] == {"name": "total", "start_ms": 0, "end_ms": total, "lane": "bridge"}


async def test_a_debug_run_sends_one_timing_event_just_before_run_finished():
    participant = FakeParticipant({QUESTION: [bot("Your address is on file." + END_MARK)]})
    clients = FakeClients(participant)
    turn = ConnectTurn(jwt(), MemorySessionStore(), SETTINGS, clients, sleep=no_sleep)
    events = await events_of(turn, debug_input(QUESTION))

    assert types(events)[-3:] == ["STEP_FINISHED", "CUSTOM", "RUN_FINISHED"]
    (timing,) = timing_events(events)
    assert events[-2] is timing
    value = timing.value
    assert_well_formed(value)
    names = [s["name"] for s in value["steps"]]
    for name in (
        "starting a contact",
        "StartChatContact",
        "CreateParticipantConnection",
        "flow socket",
        "greeting wait",
        "token blanking",
        "SendMessage",
        "opening the reply stream",
        "reply socket",
        "first reply item",
        "end mark",
        "total",
    ):
        assert name in names, name
    # The tests run with OBO=off: no exchange, and a note says so.
    assert "hop token exchanges" not in names
    assert "contact started by this run" in value["notes"]
    assert "waiting for another run's contact" not in names
    start = step(value, "starting a contact")
    greeting = step(value, "greeting wait")
    sent = step(value, "SendMessage")
    stream = step(value, "opening the reply stream")
    first = step(value, "first reply item")
    end = step(value, "end mark")
    assert start["start_ms"] < greeting["start_ms"] < greeting["end_ms"] <= start["end_ms"]
    assert start["end_ms"] < sent["start_ms"] < sent["end_ms"] <= stream["start_ms"]
    assert stream["end_ms"] < first["start_ms"] <= end["start_ms"] < value["total_ms"]
    assert first["end_ms"] is None and end["end_ms"] is None
    assert value["ids"]["contact"] == "contact-1" and value["ids"]["run"] == "r1"
    assert "trace" in value["ids"]


async def test_a_run_without_debug_sends_none_and_the_run_line_still_has_the_times():
    participant = FakeParticipant({QUESTION: [bot("Your address is on file." + END_MARK)]})
    clients = FakeClients(participant)
    for props in ({}, {"project": "hr"}, {"project": "hr", "debug": "true"}, {"debug": 1}):
        turn = ConnectTurn(jwt(), MemorySessionStore(), SETTINGS, clients, sleep=no_sleep)
        run = run_input(QUESTION)
        run.forwarded_props = props
        events = await events_of(turn, run)
        assert timing_events(events) == [] and types(events)[-1] == "RUN_FINISHED"
        usage = turn.usage()
        assert 0 < usage["connect_ready_ms"] < usage["connect_sent_ms"] < usage["connect_stream_ms"]
        assert (
            usage["connect_stream_ms"] < usage["connect_first_item_ms"] <= usage["connect_end_ms"]
        )


async def test_the_event_carries_no_token_name_or_message_text():
    token = jwt(sub="jane.doe@example.com")
    participant = FakeParticipant({QUESTION: [bot("Jane Doe, 1 Main Street." + END_MARK)]})
    clients = FakeClients(participant)
    turn = ConnectTurn(token, MemorySessionStore(), SETTINGS, clients, sleep=no_sleep)
    (timing,) = timing_events(await events_of(turn, debug_input(QUESTION)))
    text = json.dumps(timing.value)
    for secret in (
        token,
        token.split(".")[1],
        "jane.doe",
        "example.com",
        "Jane",
        "Main Street",
        QUESTION,
        "home address",
    ):
        assert secret not in text


async def test_a_question_after_the_warm_start_sends_and_times_only_its_turn():
    participant = FakeParticipant({QUESTION: [bot("On file."), bot(turn_module.END_OF_TURN)]})
    clients = FakeClients(participant)
    store = MemorySessionStore()
    token = jwt()
    warm = ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep)
    await warm.warm(warm_input())
    assert warm.usage()["connect_ready_ms"] > 0
    turn = ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep)
    (timing,) = timing_events(await events_of(turn, debug_input(QUESTION)))
    names = [s["name"] for s in timing.value["steps"]]
    assert "starting a contact" not in names and "StartChatContact" not in names
    assert names[-1] == "total" and "end mark" in names and "SendMessage" in names
    assert timing.value["notes"] == []


async def test_a_question_that_waits_for_the_warm_starts_contact(monkeypatch):
    participant = FakeParticipant({QUESTION: [bot("On file." + END_MARK)]})
    clients = FakeClients(participant)
    store = MemorySessionStore()
    token = jwt()
    key = session_key(token, "t1")
    assert store.claim(key, time.time() + 20, time.time())
    starter = ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep)
    polls: list[float] = []

    def finish_start(seconds):
        polls.append(seconds)
        if len(polls) == 2:
            store.put(starter.start_contact(key, time.time() + 3600))

    monkeypatch.setattr(turn_module.time, "sleep", finish_start)
    turn = ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep)
    (timing,) = timing_events(await events_of(turn, debug_input(QUESTION)))
    value = timing.value
    assert_well_formed(value)
    wait = step(value, "waiting for another run's contact")
    assert wait["lane"] == "bridge" and wait["end_ms"] > wait["start_ms"]
    assert wait["end_ms"] < step(value, "SendMessage")["start_ms"]
    assert "waited for the warm start's contact" in value["notes"]
    assert "starting a contact" not in [s["name"] for s in value["steps"]]


async def test_hop_token_exchanges_end_where_start_chat_contact_begins(monkeypatch):
    class Exchanger:
        enabled = True

        def __init__(self, cached: bool) -> None:
            self.cached = cached

        def _key(self, subject: str) -> str:
            return "k"

        def _cached(self, key: str):
            return "hop" if self.cached else None

        def exchange(self, subject: str) -> str:
            return subject

    for cached, note in (
        (True, "issuer exchanges cached"),
        (False, "issuer exchanges made by this run"),
    ):
        agents = (
            {d: Exchanger(cached) for d in turn_module.DOMAINS}
            if hasattr(turn_module, "DOMAINS")
            else {}
        )
        monkeypatch.setattr(turn_module, "AGENTS_TOKENS", agents, raising=False)
        monkeypatch.setattr(turn_module, "CANVAS_TOKENS", Exchanger(cached), raising=False)
        if (
            not hasattr(turn_module, "hop_tokens_cached")
            or turn_module.hop_tokens_cached(jwt()) is None
        ):
            pytest.skip("the hops carry no exchanged tokens (rolled back)")
        participant = FakeParticipant({QUESTION: [bot("On file." + END_MARK)]})
        turn = ConnectTurn(
            jwt(), MemorySessionStore(), SETTINGS, FakeClients(participant), sleep=no_sleep
        )
        (timing,) = timing_events(await events_of(turn, debug_input(QUESTION)))
        exchanges = step(timing.value, "hop token exchanges")
        assert exchanges["lane"] == "exchange"
        assert exchanges["start_ms"] == step(timing.value, "starting a contact")["start_ms"]
        assert exchanges["end_ms"] == step(timing.value, "StartChatContact")["start_ms"]
        assert note in timing.value["notes"]
        assert turn.usage()["connect_exchanged_ms"] == exchanges["end_ms"]


async def test_early_endings_send_the_event_before_they_finish():
    clients = FakeClients(FakeParticipant({}))
    turn = ConnectTurn(jwt(), MemorySessionStore(), SETTINGS, clients, sleep=no_sleep)
    events = await events_of(turn, debug_input("x" * (turn_module.MAX_MESSAGE_CHARS + 1)))
    assert types(events)[-2:] == ["CUSTOM", "RUN_FINISHED"]
    (timing,) = timing_events(events)
    assert [s["name"] for s in timing.value["steps"]] == ["total"]
    assert timing.value["notes"] == ["message too long: nothing sent"]

    turn = ConnectTurn(jwt(), MemorySessionStore(), SETTINGS, clients, sleep=no_sleep)
    events = await events_of(turn, debug_input("   "))
    assert types(events) == ["RUN_STARTED", "CUSTOM", "RUN_ERROR"]


async def test_an_exchange_failure_sends_the_event_before_run_finished(monkeypatch):
    error = getattr(turn_module, "ExchangeError", None)
    if error is None:
        pytest.skip("no token exchange (rolled back)")

    def refuse(self):
        raise error("issuer down")

    monkeypatch.setattr(ConnectTurn, "hop_tokens", refuse)
    turn = ConnectTurn(
        jwt(), MemorySessionStore(), SETTINGS, FakeClients(FakeParticipant({})), sleep=no_sleep
    )
    events = await events_of(turn, debug_input(QUESTION))
    assert types(events)[-2:] == ["CUSTOM", "RUN_FINISHED"]
    value = timing_events(events)[0].value
    assert "starting a contact (failed)" in [s["name"] for s in value["steps"]]
    assert "token exchange failed: no contact started" in value["notes"]


async def test_an_error_the_kit_reports_still_gets_the_event_first():
    class Throttled(FakeParticipant):
        def send_message(self, Content, **kwargs):
            raise client_error("ThrottlingException")

    turn = ConnectTurn(
        jwt(), MemorySessionStore(), SETTINGS, FakeClients(Throttled({})), sleep=no_sleep
    )
    seen = []
    with pytest.raises(Exception, match="ThrottlingException"):
        async for event in turn.run(debug_input(QUESTION)):
            seen.append(event)
    assert types(seen)[-1] == "CUSTOM" and len(timing_events(seen)) == 1
    names = [s["name"] for s in seen[-1].value["steps"]]
    assert "SendMessage (failed)" in names


async def test_the_kit_streams_the_event_before_run_finished(monkeypatch):
    import connect_bridge.app as app_module
    from guppi_agent import create_app
    from httpx import ASGITransport, AsyncClient

    clients = FakeClients(FakeParticipant({QUESTION: [bot("On file." + END_MARK)]}))
    monkeypatch.setattr(app_module, "_store", MemorySessionStore())
    monkeypatch.setattr(
        app_module,
        "ConnectTurn",
        lambda token, s: ConnectTurn(token, s, SETTINGS, clients, sleep=no_sleep),
    )
    body = debug_input(QUESTION).model_dump(by_alias=True)
    async with AsyncClient(
        transport=ASGITransport(app=create_app(app_module.build_agent)), base_url="http://t"
    ) as client:
        response = await client.post(
            "/invocations", json=body, headers={"authorization": f"Bearer {jwt()}"}
        )
    data = [json.loads(line[5:]) for line in response.text.splitlines() if line.startswith("data:")]
    assert [d["type"] for d in data][-2:] == ["CUSTOM", "RUN_FINISHED"]
    assert data[-2]["name"] == EVENT_NAME and data[-2]["value"]["ids"]["contact"] == "contact-1"


async def test_a_journey_answer_ends_on_silence_and_a_closed_conversation_on_its_event():
    participant = FakeParticipant(
        {
            QUESTION: [bot("PTO is 20 days.")],
            "bye": [bot("Ticket opened."), bot(turn_module.CONVERSATION_CLOSED)],
        }
    )
    clients = FakeClients(participant)
    store = MemorySessionStore()
    token = jwt()
    (timing,) = timing_events(
        await events_of(
            ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep), debug_input(QUESTION)
        )
    )
    assert "quiet after the reply" in [s["name"] for s in timing.value["steps"]]
    turn = ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep)
    (timing,) = timing_events(await events_of(turn, debug_input("bye")))
    names = [s["name"] for s in timing.value["steps"]]
    assert "closing event" in names and "StopContact" in names
    assert names.index("first reply item") < names.index("closing event")
