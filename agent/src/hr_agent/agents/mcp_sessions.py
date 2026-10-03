"""MCP sessions to the tools gateway, kept open between a conversation's requests (D38).

AgentCore gives every MCP session on the tools runtime its own microVM, so a sub-agent that
opened a session per request paid a cold start on every tool call, about 1 s, plus the
session's setup and `tools/list` (connect/docs/latency-plan.md). A session's headers carry
the caller's token and the thread id, so a session is kept per (token, thread id) and never
serves another caller or conversation. It closes after five idle minutes (under the
runtime's fifteen), a minute before the token expires, on any error in a run that used it,
and when the pool is full (least recently used first).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

IDLE_SECONDS = 300
TOKEN_MARGIN_SECONDS = 60
MAX_SESSIONS = 32

Key = tuple[str, str]
Opener = Callable[[Key], tuple[Any, list]]


@dataclass
class _Session:
    client: Any
    tools: list
    token_expires_at: float
    last_used: float
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class McpSessions:
    def __init__(
        self,
        open_session: Opener,
        *,
        idle_seconds: float = IDLE_SECONDS,
        max_sessions: int = MAX_SESSIONS,
        clock: Callable[[], float] = time.monotonic,
        wall: Callable[[], float] = time.time,
    ) -> None:
        self._open = open_session
        self._idle = idle_seconds
        self._max = max_sessions
        self._clock = clock
        self._wall = wall
        self._sessions: dict[Key, _Session] = {}

    def _usable(self, session: _Session) -> bool:
        return (
            self._clock() - session.last_used < self._idle
            and self._wall() < session.token_expires_at - TOKEN_MARGIN_SECONDS
        )

    async def _close(self, key: Key) -> None:
        session = self._sessions.pop(key, None)
        if session is None:
            return
        try:
            await asyncio.to_thread(session.client.stop, None, None, None)
        except Exception:  # noqa: BLE001 - a session that will not close is dropped anyway
            log.warning("could not close an MCP session cleanly", exc_info=True)

    async def _sweep(self) -> None:
        for key in [k for k, s in self._sessions.items() if not self._usable(s)]:
            await self._close(key)
        while len(self._sessions) >= self._max:
            oldest = min(self._sessions, key=lambda k: self._sessions[k].last_used)
            await self._close(oldest)

    @asynccontextmanager
    async def lease(self, key: Key, *, token_expires_at: float):
        """The session for `key` and its tool list, opened if there is none."""
        session = self._sessions.get(key)
        if session is None or not self._usable(session):
            if session is not None:
                await self._close(key)
            await self._sweep()
            client, tools = await asyncio.to_thread(self._open, key)
            session = _Session(client, tools, token_expires_at, self._clock())
            self._sessions[key] = session
        async with session.lock:
            try:
                yield session.client, session.tools
            except BaseException:
                await self._close(key)
                raise
            session.last_used = self._clock()
