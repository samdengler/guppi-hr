"""Startup work for AgentCore Runtime V2, which starts each new session's microVM from a
snapshot taken at the container's first healthy /ping (runtime-v2-optimize.html).

Whatever runs here, before the server listens, is in the snapshot and shared by every
restored instance. Whatever the first request does instead runs in a freshly restored
process, on every new session: measured on 4 Oct 2026, a first Profile answer went from
6.2 s on V1 to 18.3 s on V2 with the imports and clients built inside the handler. So the
heavy imports, the clients and one pass through the app's routes happen here. Nothing here
holds a value that is per user, per request, or that expires: tokens, MCP sessions and
the employee's records stay in the handlers.

The container image sets HR_PRIME=1 (agent/Dockerfile); elsewhere, the tests included, it
is off.
"""

from __future__ import annotations

import logging
import os
import random
import threading
import time
from typing import Any

log = logging.getLogger("hr_agent.prime")

_SESSIONS: dict[str | None, Any] = {}


def enabled() -> bool:
    return os.environ.get("HR_PRIME") == "1"


def boto_session(region: str | None = None) -> Any:
    """One boto3 session per region for the process, so each request's clients reuse its
    loaded service models instead of parsing them again in a restored process."""
    if region not in _SESSIONS:
        import boto3

        _SESSIONS[region] = boto3.session.Session(region_name=region)
    return _SESSIONS[region]


def reseed_after_restore(poll: float = 0.05, jump: float = 1.0) -> threading.Thread:
    """Every instance restored from one snapshot starts with the same `random` state, so
    the OpenTelemetry trace and span ids it draws would repeat across sessions. A restore
    shows as the wall clock jumping ahead of the monotonic clock, which does not advance
    across it; reseed from the operating system when that happens."""

    def watch() -> None:
        wall, mono = time.time(), time.monotonic()
        while True:
            time.sleep(poll)
            now_wall, now_mono = time.time(), time.monotonic()
            if (now_wall - wall) - (now_mono - mono) > jump:
                random.seed(os.urandom(32))
                log.info("restored from a snapshot: random reseeded")
            wall, mono = now_wall, now_mono

    thread = threading.Thread(target=watch, name="restore-watch", daemon=True)
    thread.start()
    return thread


def prime_sub_agent(role: str) -> None:
    """Imports, the Bedrock model and Identity clients, and one pass through the A2A app."""
    started = time.monotonic()
    from mcp.client.streamable_http import streamablehttp_client  # noqa: F401
    from starlette.testclient import TestClient
    from strands import Agent
    from strands.models import BedrockModel
    from strands.tools.mcp import MCPClient  # noqa: F401

    from hr_agent.agents.server import DOMAINS, Settings, build_app, system_prompt
    from hr_agent.obo import _identity_client

    settings = Settings()
    model = BedrockModel(boto_session=boto_session(settings.region), model_id=settings.model_id)
    Agent(model=model, system_prompt=system_prompt(DOMAINS[role]), tools=[], callback_handler=None)
    _identity_client()
    with TestClient(build_app(role)) as client:
        client.get("/ping")
        client.get("/.well-known/agent-card.json")
    log.info("primed %s in %.0f ms", role, (time.monotonic() - started) * 1000)


def prime_tools() -> None:
    """The tools server's DynamoDB store and token verifier, built before the snapshot."""
    started = time.monotonic()
    from hr_agent.tools import server

    server.DEPENDENCIES.store
    server.DEPENDENCIES.verifier
    log.info("primed tools in %.0f ms", (time.monotonic() - started) * 1000)


def prime(role: str) -> None:
    if not enabled():
        return
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    reseed_after_restore()
    try:
        if role == "tools":
            prime_tools()
        elif role in ("profile", "pay", "travel"):
            prime_sub_agent(role)
    except Exception:  # noqa: BLE001 - priming only saves time; the handlers still work without it
        log.exception("priming %s failed", role)
