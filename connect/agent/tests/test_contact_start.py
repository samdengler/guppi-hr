"""A contact's start as a waiting run sees it (L27, D53): the greeting over the flow's
socket, the contact stored before its token attributes are blanked, and the left thread's
contact ended beside the new start."""

from __future__ import annotations

import threading
import time

import connect_bridge.turn as turn_module
from connect_bridge.store import MemorySessionStore
from connect_bridge.turn import ConnectTurn, session_key
from test_turn import (  # noqa: F401 - fast is an autouse fixture
    SETTINGS,
    FakeClients,
    FakeConnect,
    FakeParticipant,
    FakeSocket,
    bot,
    collect,
    fast,
    jwt,
    no_sleep,
    warm_input,
)


def blanked(update: dict) -> bool:
    """An UpdateContactAttributes call that blanks every token attribute it names; the names
    are the on-behalf-of ones (D47) or, after a rollback, hrToken."""
    values = set(update["Attributes"].values())
    return bool(values) and values == {turn_module.CLEARED}


class GreetsOnTheSocket(FakeParticipant):
    """The canvas greets once the flow's socket has subscribed, and Connect pushes it."""

    def __init__(self, script) -> None:
        super().__init__(script, greeting=None)
        self.reads = 0

    def get_transcript(self, **kwargs):
        self.reads += 1
        return super().get_transcript(**kwargs)


class PushingClients(FakeClients):
    def start_flow(self, url: str) -> FakeSocket:
        self.touched.append(url)
        socket = FakeSocket(self.participant)
        joined = "application/vnd.amazonaws.connect.event.participant.joined"
        self.participant._add(Type="EVENT", ContentType=joined)
        self.participant._add(Type="MESSAGE", ParticipantRole="SYSTEM", Content="Hi, I'm HR.")
        self.flow_socket = socket
        return socket


async def test_the_greeting_pushed_over_the_flow_socket_ends_the_wait_without_a_transcript_read():
    participant = GreetsOnTheSocket({"hello": [bot("Hi there.")]})
    clients = PushingClients(participant)
    store = MemorySessionStore()
    token = jwt()
    await ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep).warm(warm_input())
    assert participant.reads == 0
    assert clients.flow_socket.closed
    # The greeting is marked seen, so the first message's turn never shows it.
    events = await collect(ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep), "hello")
    assert [e.delta for e in events if hasattr(e, "delta")] == ["Hi there."]


async def test_a_flow_socket_that_fails_leaves_the_greeting_to_the_transcript():
    class Broken(FakeClients):
        @staticmethod
        def receive(ws, timeout):
            raise OSError("socket closed")

    clients = Broken(FakeParticipant({}))
    store = MemorySessionStore()
    token = jwt()
    turn = ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep)
    await turn.warm(warm_input())
    assert turn.usage()["connect_started"] is True
    assert not store.get(session_key(token, "t1")).closed


async def test_the_contact_is_stored_before_its_token_is_blanked_and_the_warm_start_waits():
    order: list[str] = []

    class Store(MemorySessionStore):
        def put(self, session):
            order.append("put")
            super().put(session)

    class Connect(FakeConnect):
        def update_contact_attributes(self, **kwargs):
            order.append("blank")
            super().update_contact_attributes(**kwargs)

    clients = FakeClients(FakeParticipant({}))
    clients.connect = Connect()
    store = Store()
    token = jwt()
    await ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep).warm(warm_input())
    assert order == ["put", "blank"]
    assert len(clients.connect.updated) == 1 and blanked(clients.connect.updated[0])
    assert store.get(session_key(token, "t1")).token_cleared


async def test_a_run_waiting_on_the_claim_can_send_while_the_token_is_blanked():
    # The blanking holds until the waiting run has sent: neither waits for the other.
    sent = threading.Event()

    class SlowBlank(FakeConnect):
        def update_contact_attributes(self, **kwargs):
            assert sent.wait(2), "the waiting run did not send while the token was blanked"
            super().update_contact_attributes(**kwargs)

    class Participant(FakeParticipant):
        def send_message(self, Content, **kwargs):
            sent.set()
            return super().send_message(Content, **kwargs)

    clients = FakeClients(Participant({"hello": [bot("Hi there.")]}))
    clients.connect = SlowBlank()
    store = MemorySessionStore()
    token = jwt()
    warm = ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep)
    session = warm.session_for("t1")
    events = await collect(ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep), "hello")
    warm.finish_blanking()
    assert [e.delta for e in events if hasattr(e, "delta")] == ["Hi there."]
    assert session.token_cleared and blanked(clients.connect.updated[0])


async def test_a_failed_blanking_is_logged_and_stored(caplog):
    class Refusing(FakeConnect):
        def update_contact_attributes(self, **kwargs):
            raise RuntimeError("throttled")

    clients = FakeClients(FakeParticipant({}))
    clients.connect = Refusing()
    store = MemorySessionStore()
    token = jwt()
    turn = ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep)
    await turn.warm(warm_input())
    assert turn.usage()["connect_token_not_cleared"] is True
    assert "bridge_problem token_not_cleared" in caplog.text
    assert not store.get(session_key(token, "t1")).token_cleared


async def test_a_run_that_starts_its_own_contact_saves_the_blanking():
    clients = FakeClients(FakeParticipant({"hello": [bot("Hi there.")]}))
    store = MemorySessionStore()
    token = jwt()
    await collect(ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep), "hello")
    assert len(clients.connect.updated) == 1 and blanked(clients.connect.updated[0])
    assert clients.connect.updated[0]["InitialContactId"] == "contact-1"
    assert store.get(session_key(token, "t1")).token_cleared


async def test_the_left_threads_contact_ends_beside_the_new_start():
    started = threading.Event()

    class Connect(FakeConnect):
        def start_chat_contact(self, **kwargs):
            started.set()
            return super().start_chat_contact(**kwargs)

        def stop_contact(self, ContactId, **kwargs):
            # Ending the old contact waits until the new one is starting: in sequence, this
            # would time out.
            assert started.wait(2), "the new contact did not start while the old one was ending"
            super().stop_contact(ContactId, **kwargs)

    clients = FakeClients(FakeParticipant({}))
    store = MemorySessionStore()
    token = jwt()
    await ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep).warm(warm_input("t1"))
    started.clear()
    clients.connect = Connect()
    second = warm_input("t2")
    second.forwarded_props["previousThreadId"] = "t1"
    await ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep).warm(second)
    assert clients.connect.stopped == ["contact-1"]
    assert store.get(session_key(token, "t1")).closed


async def test_a_failure_ending_the_left_contact_is_reported_and_the_new_one_starts(caplog):
    class Store(MemorySessionStore):
        def get(self, key):
            if key.endswith("#t1"):
                raise RuntimeError("store down")
            return super().get(key)

    clients = FakeClients(FakeParticipant({}))
    store = Store()
    token = jwt()
    second = warm_input("t2")
    second.forwarded_props["previousThreadId"] = "t1"
    turn = ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep)
    await turn.warm(second)
    assert turn.usage()["connect_started"] is True
    assert "bridge_problem contact_not_ended" in caplog.text


def test_a_waiting_run_reads_the_store_every_tenth_of_a_second(monkeypatch):
    clients = FakeClients(FakeParticipant({}))
    store = MemorySessionStore()
    token = jwt()
    key = session_key(token, "t1")
    assert store.claim(key, time.time() + 20, time.time())
    starter = ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep)
    sleeps: list[float] = []

    def finish_start(seconds):
        sleeps.append(seconds)
        store.put(starter.start_contact(key, time.time() + 3600))

    monkeypatch.setattr(turn_module.time, "sleep", finish_start)
    ConnectTurn(token, store, SETTINGS, clients, sleep=no_sleep).session_for("t1")
    assert sleeps == [turn_module.CLAIM_POLL_INTERVAL] and turn_module.CLAIM_POLL_INTERVAL == 0.1
