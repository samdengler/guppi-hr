import random

from hr_agent import __main__ as entrypoint
from hr_agent import prime


def test_the_entrypoint_primes_before_it_serves(monkeypatch):
    order = []
    monkeypatch.setattr(prime, "prime", lambda role: order.append(("prime", role)))
    monkeypatch.setattr(entrypoint.uvicorn, "run", lambda target, **kw: order.append(("serve", target)))
    monkeypatch.setenv("AGENT_ROLE", "tools")
    entrypoint.main()
    assert order == [("prime", "tools"), ("serve", "hr_agent.tools.server:app")]


def test_priming_is_off_when_disabled(monkeypatch):
    called = []
    monkeypatch.setattr(prime, "reseed_after_restore", lambda: called.append(True))
    prime.prime("tools")
    assert called == []


def test_a_sub_agent_primes_without_a_network_call(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    prime.prime_sub_agent("profile")
    assert prime.boto_session("us-east-1") is prime.boto_session("us-east-1")


def test_the_tools_server_builds_its_dependencies(monkeypatch):
    from hr_agent.tools import server

    built = []

    class Deps:
        @property
        def store(self):
            built.append("store")

        @property
        def verifier(self):
            built.append("verifier")

    monkeypatch.setattr(server, "DEPENDENCIES", Deps())
    prime.prime_tools()
    assert built == ["store", "verifier"]


def test_a_clock_jump_reseeds_random(monkeypatch):
    clock = {"wall": 1000.0, "mono": 50.0}
    seeds = []
    monkeypatch.setattr(prime.time, "time", lambda: clock["wall"])
    monkeypatch.setattr(prime.time, "monotonic", lambda: clock["mono"])

    def sleep(_seconds):
        if seeds:
            raise SystemExit  # ends the watcher loop once it has reseeded
        clock["wall"] += 3600  # a restore: wall time moves, monotonic time does not

    monkeypatch.setattr(prime.time, "sleep", sleep)
    monkeypatch.setattr(prime.random, "seed", lambda value: seeds.append(value))
    thread = prime.reseed_after_restore()
    thread.join(timeout=2)
    assert len(seeds) == 1 and len(seeds[0]) == 32
    assert random.random() is not None
