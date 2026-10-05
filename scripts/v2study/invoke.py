#!/usr/bin/env python
"""Send requests to a test runtime of the Runtime V2 cold start study with
`InvokeAgentRuntime` and write one JSON line per request (docs/runtime-v2-experiments.md).

    uv run --no-project --with 'boto3>=1.43.95' --with httpx python scripts/v2study/invoke.py \
        --name hr_v2_proto_http_v2 --protocol http --new 25 --out docs/runtime-v2-evidence/E1/http_v2.jsonl

New sessions are sent one at a time (`--new N`, `--pace` seconds apart); `--burst N
--repeat R --gap G` sends N new sessions at once, R times, G seconds apart; `--followups K`
sends K more requests on each new session right away; `--reuse-waits 30,75,130` sends one
follow-up after each wait (seconds) on each new session; `--jwt-file` sends a bearer token
over HTTPS instead of SigV4. Every line has the client's send, first byte and end times,
the runtime's request id, the status and the parsed in-guest telemetry.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import threading
import time
import urllib.parse
import uuid
from concurrent.futures import ThreadPoolExecutor

import boto3

REGION = "us-east-1"
MCP_PROTOCOL = "2025-06-18"
_lock = threading.Lock()


def session_id() -> str:
    return f"hrv2-{uuid.uuid4()}-{uuid.uuid4().hex[:8]}"


def payloads(protocol: str) -> list[tuple[str, dict, str, str]]:
    """(step name, body, content type, accept) in the order a new session sends them."""
    if protocol == "http":
        return [("invocations", {"prompt": "probe"}, "application/json", "application/json")]
    if protocol == "a2a":
        return [(
            "message/send",
            {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "message/send",
             "params": {"message": {"role": "user", "parts": [{"kind": "text", "text": "probe"}], "messageId": str(uuid.uuid4())}}},
            "application/json", "application/json",
        )]
    if protocol == "mcp":
        accept = "application/json, text/event-stream"
        return [
            ("initialize", {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                            "params": {"protocolVersion": MCP_PROTOCOL, "capabilities": {}, "clientInfo": {"name": "hr-v2-study", "version": "1"}}},
             "application/json", accept),
            ("tools/call", {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "probe_tool", "arguments": {}}},
             "application/json", accept),
        ]
    raise SystemExit(f"unknown protocol {protocol}")


def parse_body(protocol: str, step: str, raw: bytes) -> tuple[dict | None, str | None]:
    text = raw.decode("utf-8", "replace")
    if text.startswith("event:") or text.startswith("data:"):
        datas = [line[5:].strip() for line in text.splitlines() if line.startswith("data:")]
        text = datas[-1] if datas else text
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return None, text[:300]
    try:
        if protocol == "http":
            return doc, None
        if protocol == "a2a":
            if "error" in doc:
                return None, json.dumps(doc["error"])[:300]
            return json.loads(doc["result"]["parts"][0]["text"]), None
        if protocol == "mcp":
            if "error" in doc:
                return None, json.dumps(doc["error"])[:300]
            if step == "initialize":
                return {"server": doc["result"].get("serverInfo")}, None
            return json.loads(doc["result"]["content"][0]["text"]), None
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        return None, f"{type(exc).__name__}: {text[:200]}"
    return doc, None


class Invoker:
    def __init__(self, arn: str, protocol: str, jwt: str | None, label: str, out: pathlib.Path):
        self.arn, self.protocol, self.jwt, self.label, self.out = arn, protocol, jwt, label, out
        self.client = boto3.client("bedrock-agentcore", region_name=REGION) if not jwt else None
        if jwt:
            import httpx

            self.http = httpx.Client(timeout=120)
            self.url = f"https://bedrock-agentcore.{REGION}.amazonaws.com/runtimes/{urllib.parse.quote(arn, safe='')}/invocations?qualifier=DEFAULT"

    def send(self, session: str, step: str, body: dict, ctype: str, accept: str, kind: str, index: int, extra: dict | None = None) -> dict:
        line: dict = {"runtime": self.arn.rsplit("/", 1)[-1], "label": self.label, "session": session, "kind": kind,
                      "index": index, "step": step, "protocol": self.protocol, "auth": "jwt" if self.jwt else "sigv4", **(extra or {})}
        data = json.dumps(body).encode()
        t_send = time.time()
        try:
            if self.jwt:
                headers = {"Authorization": f"Bearer {self.jwt}", "Content-Type": ctype, "Accept": accept,
                           "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session}
                if self.protocol == "mcp":
                    headers["Mcp-Session-Id"] = session
                    headers["Mcp-Protocol-Version"] = MCP_PROTOCOL
                with self.http.stream("POST", self.url, content=data, headers=headers) as resp:
                    t_first = time.time()
                    raw = resp.read()
                    status = resp.status_code
                    request_id = resp.headers.get("x-amzn-requestid")
            else:
                kw = {"agentRuntimeArn": self.arn, "runtimeSessionId": session, "payload": data,
                      "contentType": ctype, "accept": accept, "qualifier": "DEFAULT"}
                if self.protocol == "mcp":
                    kw["mcpSessionId"] = session
                    kw["mcpProtocolVersion"] = MCP_PROTOCOL
                resp = self.client.invoke_agent_runtime(**kw)
                t_first = time.time()
                raw = resp["response"].read()
                status = resp["ResponseMetadata"]["HTTPStatusCode"]
                request_id = resp["ResponseMetadata"].get("RequestId")
            t_end = time.time()
            telemetry, err = parse_body(self.protocol, step, raw)
            line.update({"t_send": t_send, "t_first": t_first, "t_end": t_end, "client_ms": round((t_end - t_send) * 1000, 1),
                         "first_byte_ms": round((t_first - t_send) * 1000, 1), "status": status, "request_id": request_id,
                         "telemetry": telemetry, "error": err})
        except Exception as exc:  # noqa: BLE001
            t_end = time.time()
            line.update({"t_send": t_send, "t_end": t_end, "client_ms": round((t_end - t_send) * 1000, 1), "status": None,
                         "error": f"{type(exc).__name__}: {exc}"[:400]})
        with _lock:
            with self.out.open("a") as f:
                f.write(json.dumps(line) + "\n")
        return line

    def new_session(self, index: int, kind: str = "new", followups: int = 0, reuse_waits: list[int] | None = None, extra: dict | None = None) -> list[dict]:
        session = session_id()
        lines = []
        extra = extra or {}
        steps = payloads(self.protocol)
        for step_no, (step, body, ctype, accept) in enumerate(steps):
            lines.append(self.send(session, step, body, ctype, accept, kind if step_no == 0 else "same-session", index, {"step_no": step_no, **extra}))
        call = steps[-1]
        for k in range(followups):
            lines.append(self.send(session, call[0], call[1], call[2], call[3], "followup", index, {"followup": k + 1, "wait_s": 0, **extra}))
        for wait in reuse_waits or []:
            time.sleep(wait)
            lines.append(self.send(session, call[0], call[1], call[2], call[3], "followup", index, {"wait_s": wait, **extra}))
        return lines


def resolve_arn(name: str | None, arn: str | None) -> str:
    if arn:
        return arn
    ctl = boto3.client("bedrock-agentcore-control", region_name=REGION)
    token = None
    while True:
        kw = {"nextToken": token} if token else {}
        resp = ctl.list_agent_runtimes(maxResults=100, **kw)
        for rt in resp["agentRuntimes"]:
            if rt["agentRuntimeName"] == name:
                return rt["agentRuntimeArn"]
        token = resp.get("nextToken")
        if not token:
            raise SystemExit(f"{name} not found")


def summarize(lines: list[dict]) -> str:
    import statistics

    ok = [ln for ln in lines if ln.get("status") == 200 and not ln.get("error")]
    bad = [ln for ln in lines if ln not in ok]
    parts = [f"{len(ok)} ok, {len(bad)} failed"]
    for kind in ("new", "same-session", "followup", "burst"):
        vals = [ln["client_ms"] for ln in ok if ln["kind"] == kind]
        if vals:
            parts.append(f"{kind}: n={len(vals)} median {statistics.median(vals):.0f} ms min {min(vals):.0f} max {max(vals):.0f}")
    if bad:
        parts.append("errors: " + "; ".join(sorted({str(ln.get('error'))[:120] for ln in bad})[:3]))
    return " | ".join(parts)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--name")
    p.add_argument("--arn")
    p.add_argument("--protocol", required=True, choices=["http", "mcp", "a2a"])
    p.add_argument("--new", type=int, default=0, help="new sessions, one at a time")
    p.add_argument("--pace", type=float, default=1.0, help="seconds between new sessions")
    p.add_argument("--followups", type=int, default=0)
    p.add_argument("--reuse-waits", help="comma separated seconds; one follow-up after each wait")
    p.add_argument("--burst", type=int, default=0)
    p.add_argument("--repeat", type=int, default=1)
    p.add_argument("--gap", type=float, default=60)
    p.add_argument("--jwt-file")
    p.add_argument("--label", default="")
    p.add_argument("--out", required=True)
    a = p.parse_args()
    arn = resolve_arn(a.name, a.arn)
    jwt = pathlib.Path(a.jwt_file).read_text().strip() if a.jwt_file else None
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    inv = Invoker(arn, a.protocol, jwt, a.label, out)
    waits = [int(w) for w in a.reuse_waits.split(",")] if a.reuse_waits else None
    lines: list[dict] = []
    for i in range(a.new):
        lines += inv.new_session(i, "new", a.followups, waits)
        print(f"new {i + 1}/{a.new}: {lines[-1].get('client_ms')} ms {lines[-1].get('error') or ''}", file=sys.stderr)
        if i + 1 < a.new:
            time.sleep(a.pace)
    for r in range(a.repeat if a.burst else 0):
        with ThreadPoolExecutor(max_workers=a.burst) as pool:
            futures = [pool.submit(inv.new_session, i, "burst", a.followups, None, {"burst_size": a.burst, "burst_repeat": r}) for i in range(a.burst)]
            for fut in futures:
                lines += fut.result()
        print(f"burst {a.burst} repeat {r + 1}/{a.repeat} done", file=sys.stderr)
        if r + 1 < a.repeat:
            time.sleep(a.gap)
    print(summarize(lines))


if __name__ == "__main__":
    main()
