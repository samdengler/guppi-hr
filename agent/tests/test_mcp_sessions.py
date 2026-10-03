"""The sub-agents' MCP sessions to the tools gateway, kept between requests (D38)."""

from __future__ import annotations

import pytest

from hr_agent.agents.mcp_sessions import McpSessions


class FakeClient:
    def __init__(self, key) -> None:
        self.key = key
        self.stopped = False

    def stop(self, *_args) -> None:
        self.stopped = True


class Opener:
    def __init__(self) -> None:
        self.opened: list[FakeClient] = []

    def __call__(self, key):
        client = FakeClient(key)
        self.opened.append(client)
        return client, [f"tool-for-{key[1]}"]


class Clock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def sessions(opener, clock, **kwargs) -> McpSessions:
    return McpSessions(opener, clock=clock, wall=clock, **kwargs)


async def test_a_conversation_reuses_its_session_and_tool_list():
    opener, clock = Opener(), Clock()
    pool = sessions(opener, clock)
    async with pool.lease(("tok", "thread-1"), token_expires_at=clock() + 3600) as (client, tools):
        first = client
        assert tools == ["tool-for-thread-1"]
    clock.now += 20
    async with pool.lease(("tok", "thread-1"), token_expires_at=clock() + 3600) as (client, _tools):
        assert client is first
    assert len(opener.opened) == 1


async def test_another_caller_or_thread_never_shares_a_session():
    opener, clock = Opener(), Clock()
    pool = sessions(opener, clock)
    for key in [("tok-a", "t1"), ("tok-b", "t1"), ("tok-a", "t2")]:
        async with pool.lease(key, token_expires_at=clock() + 3600):
            pass
    assert [c.key for c in opener.opened] == [("tok-a", "t1"), ("tok-b", "t1"), ("tok-a", "t2")]


async def test_an_idle_session_is_closed_and_reopened():
    opener, clock = Opener(), Clock()
    pool = sessions(opener, clock, idle_seconds=300)
    async with pool.lease(("tok", "t1"), token_expires_at=clock() + 3600):
        pass
    clock.now += 301
    async with pool.lease(("tok", "t1"), token_expires_at=clock() + 3600):
        pass
    assert len(opener.opened) == 2
    assert opener.opened[0].stopped


async def test_a_session_ends_before_its_token_does():
    opener, clock = Opener(), Clock()
    pool = sessions(opener, clock)
    async with pool.lease(("tok", "t1"), token_expires_at=clock() + 90):
        pass
    clock.now += 40  # within a minute of the token's expiry
    async with pool.lease(("tok", "t1"), token_expires_at=clock() + 50):
        pass
    assert len(opener.opened) == 2


async def test_a_failed_run_drops_its_session():
    opener, clock = Opener(), Clock()
    pool = sessions(opener, clock)
    with pytest.raises(RuntimeError):
        async with pool.lease(("tok", "t1"), token_expires_at=clock() + 3600):
            raise RuntimeError("tool call failed")
    assert opener.opened[0].stopped
    async with pool.lease(("tok", "t1"), token_expires_at=clock() + 3600):
        pass
    assert len(opener.opened) == 2


async def test_the_pool_keeps_at_most_its_limit_closing_the_least_recent():
    opener, clock = Opener(), Clock()
    pool = sessions(opener, clock, max_sessions=2)
    for thread in ["t1", "t2", "t3"]:
        clock.now += 1
        async with pool.lease(("tok", thread), token_expires_at=clock() + 3600):
            pass
    assert [c.stopped for c in opener.opened] == [True, False, False]
