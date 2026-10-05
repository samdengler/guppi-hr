"""Probe server for the Runtime V2 cold start study (docs/runtime-v2-experiments.md).

One image, three protocols chosen by MODE: http (FastAPI on 8080, POST /invocations), mcp
(FastMCP stateless streamable HTTP on 8000 at /mcp, tool `probe`), a2a (the AgentCore A2A
app on 9000, message/send). Every answer is one JSON document of in-guest telemetry. The
knobs are environment variables read at process start (IMPORTS, LAZY_IMPORTS, PRIME,
TOUCH_MB, TOUCH_ON_REQUEST_MB, OUTBOUND); none of them makes a network call before the
server listens.
"""


import json
import os
import random
import socket
import sys
import threading
import time
import uuid

T0_WALL = time.time()
T0_MONO = time.monotonic()
T0_PERF = time.perf_counter()
FIRST_RANDOM = random.random()  # drawn once at start: identical across restores if seeded in the snapshot
BOOT_ID_AT_START = open("/proc/sys/kernel/random/boot_id").read().strip()
START_UPTIME = float(open("/proc/uptime").read().split()[0])

MODE = os.environ.get("MODE", "http")
IMPORTS = os.environ.get("IMPORTS", "none")
LAZY_IMPORTS = os.environ.get("LAZY_IMPORTS", "0") == "1"
PRIME = os.environ.get("PRIME", "none")
TOUCH_MB = int(os.environ.get("TOUCH_MB", "0"))
TOUCH_ON_REQUEST_MB = int(os.environ.get("TOUCH_ON_REQUEST_MB", "0"))
OUTBOUND = os.environ.get("OUTBOUND", "0") == "1"
VARIANT = os.environ.get("VARIANT", "")

STATE: dict = {"requests": 0, "import_ms": None, "prime_ms": None, "clients": {}, "lock": threading.Lock()}
PAGE = 4096


def procstat() -> dict:
    with open("/proc/self/stat") as f:
        rest = f.read().rsplit(") ", 1)[1].split()
    # after comm: state ppid pgrp session tty tpgid flags minflt cminflt majflt cmajflt ... rss
    with open("/proc/meminfo") as f:
        mem = {}
        for line in f:
            k, v = line.split(":", 1)
            mem[k] = int(v.split()[0])
    return {
        "minflt": int(rest[7]),
        "majflt": int(rest[9]),
        "rss_mb": round(int(rest[21]) * PAGE / 1e6, 1),
        "mem_total_mb": round(mem.get("MemTotal", 0) / 1024, 0),
        "mem_available_mb": round(mem.get("MemAvailable", 0) / 1024, 0),
    }


def heavy_imports() -> float:
    start = time.perf_counter()
    import boto3  # noqa: F401
    import botocore.session  # noqa: F401
    import pydantic  # noqa: F401
    import mcp  # noqa: F401
    import opentelemetry.sdk.trace  # noqa: F401
    import opentelemetry.instrumentation  # noqa: F401
    import strands  # noqa: F401
    from strands.models import BedrockModel  # noqa: F401

    return (time.perf_counter() - start) * 1000


def build_clients() -> float:
    start = time.perf_counter()
    import boto3

    session = boto3.session.Session(region_name=os.environ.get("AWS_REGION", "us-east-1"))
    STATE["clients"] = {
        "sts": session.client("sts"),
        "bedrock-runtime": session.client("bedrock-runtime"),
        "dynamodb": session.client("dynamodb"),
    }
    return (time.perf_counter() - start) * 1000


def touch(mb: int) -> bytearray:
    buf = bytearray(mb * 1024 * 1024)
    for i in range(0, len(buf), PAGE):
        buf[i] = 1
    return buf


def read_pages(buf: bytearray) -> tuple[int, float]:
    start = time.perf_counter()
    total = 0
    for i in range(0, len(buf), PAGE):
        total += buf[i]
    return total, (time.perf_counter() - start) * 1000


KEPT = touch(TOUCH_MB) if TOUCH_MB else None
FAULT_BUF = touch(TOUCH_ON_REQUEST_MB) if TOUCH_ON_REQUEST_MB else None

if IMPORTS == "heavy" and not LAZY_IMPORTS:
    STATE["import_ms"] = heavy_imports()
if PRIME in ("clients", "routes"):
    STATE["prime_ms"] = build_clients()


def outbound() -> dict:
    start = time.perf_counter()
    try:
        client = STATE["clients"].get("sts")
        if client is None:
            import boto3

            client = boto3.client("sts", region_name=os.environ.get("AWS_REGION", "us-east-1"))
            STATE["clients"]["sts"] = client
        client_ms = (time.perf_counter() - start) * 1000
        call_start = time.perf_counter()
        ident = client.get_caller_identity()
        return {
            "client_ms": round(client_ms, 1),
            "call_ms": round((time.perf_counter() - call_start) * 1000, 1),
            "arn_tail": ident["Arn"].rsplit("/", 1)[-1][:40],
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"[:200], "ms": round((time.perf_counter() - start) * 1000, 1)}


def probe(request_headers: dict | None = None) -> dict:
    req_wall = time.time()
    req_mono = time.monotonic()
    before = procstat()
    work_start = time.perf_counter()
    with STATE["lock"]:
        STATE["requests"] += 1
        n = STATE["requests"]
    out: dict = {}
    if IMPORTS == "heavy" and LAZY_IMPORTS and STATE["import_ms"] is None:
        STATE["import_ms"] = heavy_imports()
        out["lazy_import_ms"] = round(STATE["import_ms"], 1)
    if FAULT_BUF is not None:
        total, ms = read_pages(FAULT_BUF)
        out["fault_read_mb"] = TOUCH_ON_REQUEST_MB
        out["fault_read_ms"] = round(ms, 1)
    if OUTBOUND:
        out["outbound"] = outbound()
    payload = json.dumps({"n": n, "ts": req_wall}) * 50  # a little JSON work, like a real answer
    out["json_len"] = len(payload)
    after = procstat()
    headers = {k.lower(): v for k, v in (request_headers or {}).items()}
    return {
        "variant": VARIANT,
        "mode": MODE,
        "python": sys.version.split()[0],
        "knobs": {
            "imports": IMPORTS, "lazy": LAZY_IMPORTS, "prime": PRIME, "touch_mb": TOUCH_MB,
            "fault_mb": TOUCH_ON_REQUEST_MB, "outbound": OUTBOUND, "pyc": sys.flags.dont_write_bytecode == 0,
        },
        "start": {
            "wall": T0_WALL, "mono": T0_MONO, "uptime": START_UPTIME, "boot_id": BOOT_ID_AT_START,
            "import_ms": None if STATE["import_ms"] is None else round(STATE["import_ms"], 1),
            "prime_ms": None if STATE["prime_ms"] is None else round(STATE["prime_ms"], 1),
            "first_random": FIRST_RANDOM,
        },
        "request": {
            "n": n,
            "wall": req_wall,
            "mono": req_mono,
            "uptime": float(open("/proc/uptime").read().split()[0]),
            "wall_since_start_s": round(req_wall - T0_WALL, 3),
            "mono_since_start_s": round(req_mono - T0_MONO, 3),
            "boot_id": open("/proc/sys/kernel/random/boot_id").read().strip(),
            "kernel_uuid": open("/proc/sys/kernel/random/uuid").read().strip(),
            "random": random.random(),
            "urandom": os.urandom(4).hex(),
            "uuid4": str(uuid.uuid4()),
            "hostname": socket.gethostname(),
            "pid": os.getpid(),
            "cpus": os.cpu_count(),
            "env_count": len(os.environ),
            "session_header": headers.get("x-amzn-bedrock-agentcore-runtime-session-id") or headers.get("mcp-session-id"),
        },
        "before": before,
        "after": after,
        "work": out,
        "work_ms": round((time.perf_counter() - work_start) * 1000, 1),
    }


def main() -> None:
    import uvicorn

    if MODE == "http":
        from fastapi import FastAPI, Request
        from fastapi.responses import JSONResponse

        app = FastAPI()

        @app.get("/ping")
        async def ping() -> dict:
            return {"status": "Healthy"}

        @app.post("/invocations")
        async def invocations(request: Request) -> JSONResponse:
            await request.body()
            return JSONResponse(probe(dict(request.headers)))

        if PRIME == "routes":
            from starlette.testclient import TestClient

            start = time.perf_counter()
            with TestClient(app) as client:
                client.get("/ping")
                client.post("/invocations", json={"prime": True})
            STATE["prime_ms"] = (STATE["prime_ms"] or 0) + (time.perf_counter() - start) * 1000
            STATE["requests"] = 0
        uvicorn.run(app, host="0.0.0.0", port=8080, log_level="warning")
    elif MODE == "mcp":
        from mcp.server.fastmcp import Context, FastMCP

        def build_mcp_app():
            mcp = FastMCP("probe", host="0.0.0.0", stateless_http=True, json_response=True)

            @mcp.tool()
            def probe_tool(ctx: Context) -> str:
                """Return in-guest telemetry for the cold start study."""
                request = ctx.request_context.request
                return json.dumps(probe(dict(request.headers) if request is not None else None))

            return mcp.streamable_http_app()

        if PRIME == "routes":
            # The session manager of a FastMCP app runs once, so the priming pass uses an
            # app of its own; the code paths and pages it touches are what the snapshot keeps.
            from starlette.testclient import TestClient

            start = time.perf_counter()
            with TestClient(build_mcp_app()) as client:
                client.post(
                    "/mcp",
                    json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "prime", "version": "0"}}},
                    headers={"accept": "application/json, text/event-stream", "content-type": "application/json"},
                )
                client.post(
                    "/mcp",
                    json={"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "probe_tool", "arguments": {}}},
                    headers={"accept": "application/json, text/event-stream", "content-type": "application/json"},
                )
            STATE["prime_ms"] = (STATE["prime_ms"] or 0) + (time.perf_counter() - start) * 1000
            STATE["requests"] = 0
        uvicorn.run(build_mcp_app(), host="0.0.0.0", port=8000, log_level="warning")
    elif MODE == "a2a":
        from a2a.server.agent_execution import AgentExecutor, RequestContext
        from a2a.server.events import EventQueue
        from a2a.types import AgentCapabilities, AgentCard, AgentSkill
        from a2a.utils import new_agent_text_message
        from bedrock_agentcore.runtime.a2a import build_a2a_app

        class ProbeExecutor(AgentExecutor):
            async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
                headers = None
                try:
                    headers = dict(context.call_context.state.get("headers", {})) if context.call_context else None
                except Exception:  # noqa: BLE001
                    headers = None
                await event_queue.enqueue_event(new_agent_text_message(json.dumps(probe(headers))))

            async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
                raise NotImplementedError

        card = AgentCard(
            name="probe", description="cold start probe", url="http://localhost:9000/", version="0.1.0",
            capabilities=AgentCapabilities(streaming=False), defaultInputModes=["text"], defaultOutputModes=["text"],
            skills=[AgentSkill(id="probe", name="probe", description="telemetry", tags=["probe"])],
        )
        app = build_a2a_app(ProbeExecutor(), card)
        uvicorn.run(app, host="0.0.0.0", port=9000, log_level="warning")
    else:
        raise SystemExit(f"unknown MODE {MODE}")


if __name__ == "__main__":
    main()
