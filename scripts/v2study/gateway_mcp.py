#!/usr/bin/env python
"""E12 of the Runtime V2 cold start study (docs/runtime-v2-experiments.md): MCP client
sessions through AgentCore gateways with IAM inbound auth, one JSON line per call.

    gateway_mcp.py run --gw hr-v2-gw-off=URL --gw hr-v2-gw-on=URL --target probe \
        --sessions 5 --calls 5 --round r1 --outdir docs/runtime-v2-evidence/E12
    gateway_mcp.py analyze --runtime-arn ARN docs/runtime-v2-evidence/E12/*.jsonl \
        --md docs/runtime-v2-evidence/E12/results.md

A client session sends `initialize`, `notifications/initialized`, `tools/list` and
`--calls` `tools/call` of `<target>___probe_tool`, each a raw HTTPS POST signed with SigV4
(service `bedrock-agentcore`). The `Mcp-Session-Id` the gateway returns on `initialize` is
sent on every later call, with the protocol version the gateway answered (a gateway created
without `supportedVersions` offers only 2025-03-26 and rejects any other version header). Sessions alternate between the gateways (the order flips on each
session index) and run one call at a time, so every runtime record falls inside exactly one
client call's window. `analyze` reads the target runtime's own records and attributes each
one to the client call whose window holds its receipt.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import sys
import time
import uuid
from collections import Counter, defaultdict

import boto3
import httpx
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

REGION = "us-east-1"
MCP_PROTOCOL = "2025-06-18"
ACCEPT = "application/json, text/event-stream"
LOG_GROUP = "/aws/vendedlogs/bedrock-agentcore/hr-v2-study"
STREAM = "BedrockAgentCoreRuntime_ApplicationLogs"
KEPT_HEADERS = ("mcp-session-id", "x-amzn-requestid", "x-amzn-trace-id", "content-type", "mcp-protocol-version")

_session = boto3.Session(region_name=REGION)


def signed_headers(url: str, body: bytes, headers: dict) -> dict:
    creds = _session.get_credentials().get_frozen_credentials()
    req = AWSRequest(method="POST", url=url, data=body, headers=headers)
    SigV4Auth(creds, "bedrock-agentcore", REGION).add_auth(req)
    return dict(req.headers.items())


def parse_body(raw: bytes, ctype: str) -> dict | None:
    text = raw.decode("utf-8", "replace").strip()
    if not text:
        return None
    if "text/event-stream" in ctype or text.startswith(("event:", "data:", "id:")):
        docs = []
        for line in text.splitlines():
            if line.startswith("data:"):
                try:
                    docs.append(json.loads(line[5:].strip()))
                except json.JSONDecodeError:
                    pass
        with_result = [d for d in docs if isinstance(d, dict) and ("result" in d or "error" in d)]
        return (with_result or docs or [None])[-1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"_raw": text[:400]}


def probe_fields(tel: dict | None) -> dict | None:
    if not tel:
        return None
    req, start = tel.get("request") or {}, tel.get("start") or {}
    return {
        "session_header": req.get("session_header"), "pid": req.get("pid"), "n": req.get("n"),
        "mono_since_start_s": req.get("mono_since_start_s"), "wall_since_start_s": req.get("wall_since_start_s"),
        "req_wall": req.get("wall"), "start_wall": start.get("wall"), "boot_id": req.get("boot_id"),
        "hostname": req.get("hostname"), "first_random": start.get("first_random"), "work_ms": tel.get("work_ms"),
    }


class ClientSession:
    def __init__(self, gateway: str, url: str, target: str, label: str, index: int, out: pathlib.Path):
        self.gateway, self.url, self.target, self.label, self.index, self.out = gateway, url, target, label, index, out
        self.client_session = f"{label}-s{index}-{uuid.uuid4().hex[:6]}"
        self.mcp_session: str | None = None
        self.protocol = MCP_PROTOCOL  # replaced by the version the gateway answers on initialize
        self.http = httpx.Client(timeout=120)
        self.next_id = 1

    def call(self, step: str, method: str, params: dict | None, call_no: int | None = None, notify: bool = False) -> dict:
        body: dict = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            body["params"] = params
        if not notify:
            body["id"] = self.next_id
            self.next_id += 1
        data = json.dumps(body).encode()
        headers = {"Content-Type": "application/json", "Accept": ACCEPT}
        if step != "initialize":
            headers["Mcp-Protocol-Version"] = self.protocol
        sent_session = self.mcp_session
        if sent_session:
            headers["Mcp-Session-Id"] = sent_session
        line: dict = {
            "gateway": self.gateway, "round": self.label, "client_session": self.client_session,
            "session_index": self.index, "step": step, "call_no": call_no, "mcp_session_sent": sent_session,
            "protocol_sent": None if step == "initialize" else self.protocol,
        }
        t_send = time.time()
        try:
            signed = signed_headers(self.url, data, headers)
            with self.http.stream("POST", self.url, content=data, headers=signed) as resp:
                t_first = time.time()
                raw = resp.read()
            t_end = time.time()
            rh = {k: resp.headers.get(k) for k in KEPT_HEADERS if resp.headers.get(k)}
            if step == "initialize" and resp.headers.get("mcp-session-id"):
                self.mcp_session = resp.headers["mcp-session-id"]
            doc = parse_body(raw, resp.headers.get("content-type", ""))
            line.update({
                "t_send": t_send, "t_first": t_first, "t_end": t_end,
                "client_ms": round((t_end - t_send) * 1000, 1), "first_byte_ms": round((t_first - t_send) * 1000, 1),
                "status": resp.status_code, "mcp_session_id": resp.headers.get("mcp-session-id") or self.mcp_session,
                "resp_headers": rh, "error": None,
            })
            if doc and "error" in doc:
                line["error"] = json.dumps(doc["error"])[:400]
            elif resp.status_code >= 400:
                line["error"] = raw.decode("utf-8", "replace")[:400]
            elif step == "initialize" and doc:
                res = doc.get("result") or {}
                line["server"] = {"info": res.get("serverInfo"), "protocol": res.get("protocolVersion")}
                if res.get("protocolVersion"):
                    self.protocol = res["protocolVersion"]
            elif step == "tools/list" and doc:
                line["tools"] = [t.get("name") for t in (doc.get("result") or {}).get("tools", [])]
            elif step == "tools/call" and doc:
                res = doc.get("result") or {}
                if res.get("isError"):
                    line["error"] = json.dumps(res)[:400]
                else:
                    try:
                        tel = json.loads(res["content"][0]["text"])
                        line["probe"] = probe_fields(tel)
                        line["telemetry"] = tel
                    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
                        line["error"] = f"parse {type(exc).__name__}: {json.dumps(doc)[:300]}"
        except Exception as exc:  # noqa: BLE001
            t_end = time.time()
            line.update({"t_send": t_send, "t_end": t_end, "client_ms": round((t_end - t_send) * 1000, 1),
                         "status": None, "error": f"{type(exc).__name__}: {exc}"[:400]})
        with self.out.open("a") as f:
            f.write(json.dumps(line) + "\n")
        return line

    def run(self, calls: int) -> list[dict]:
        lines = [self.call("initialize", "initialize", {
            "protocolVersion": MCP_PROTOCOL, "capabilities": {}, "clientInfo": {"name": "hr-v2-study-e12", "version": "1"}})]
        lines.append(self.call("notifications/initialized", "notifications/initialized", None, notify=True))
        lines.append(self.call("tools/list", "tools/list", {}))
        for k in range(1, calls + 1):
            lines.append(self.call("tools/call", "tools/call", {"name": f"{self.target}___probe_tool", "arguments": {}}, call_no=k))
        self.http.close()
        return lines


def cmd_run(a: argparse.Namespace) -> None:
    gws = []
    for item in a.gw:
        name, _, url = item.partition("=")
        gws.append((name, url))
    outdir = pathlib.Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    for i in range(1, a.sessions + 1):
        order = gws if i % 2 else list(reversed(gws))
        for name, url in order:
            lines = ClientSession(name, url, a.target, a.round, i, outdir / f"{name}.jsonl").run(a.calls)
            calls = [ln for ln in lines if ln["step"] == "tools/call"]
            print(f"{a.round} s{i} {name}: session={lines[0].get('mcp_session_id')} "
                  f"statuses={[ln.get('status') for ln in lines]} calls_ms={[ln.get('client_ms') for ln in calls]} "
                  f"n={[((ln.get('probe') or {}).get('n')) for ln in calls]} "
                  f"errors={[ln['error'][:100] for ln in lines if ln.get('error')]}", flush=True)
            time.sleep(a.pause)


# analysis -------------------------------------------------------------------------------

def load(paths: list[str]) -> list[dict]:
    out = []
    for p in paths:
        for raw in pathlib.Path(p).read_text().splitlines():
            if raw.strip():
                out.append(json.loads(raw))
    return sorted(out, key=lambda ln: ln["t_send"])


def fetch_records(arn: str, start: float, end: float) -> list[dict]:
    logs = boto3.client("logs", region_name=REGION)
    tail = arn.rsplit("/", 1)[-1]
    recs, token = [], None
    while True:
        kw = {"nextToken": token} if token else {}
        resp = logs.filter_log_events(logGroupName=LOG_GROUP, logStreamNames=[STREAM], startTime=int(start * 1000),
                                      endTime=int(end * 1000), filterPattern=f'{{ $.resource_arn = "*{tail}" }}', **kw)
        for ev in resp["events"]:
            r = json.loads(ev["message"])
            body = r.get("body") or {}
            payload = body.get("request_payload") if isinstance(body, dict) else None
            method = payload.get("method") if isinstance(payload, dict) else None
            recs.append({"session_id": r["session_id"], "request_id": r.get("request_id"), "method": method,
                         "receipt": r["timeUnixNano"] / 1e9, "done": r["event_timestamp"] / 1e3})
        token = resp.get("nextToken")
        if not token:
            break
    return sorted(recs, key=lambda r: r["receipt"])


def med(vals: list[float]) -> str:
    return f"{statistics.median(vals):.0f}" if vals else "n/a"


def q(vals: list[float], p: float) -> float:
    s = sorted(vals)
    return s[min(len(s) - 1, int(round(p * (len(s) - 1))))]


def stat(vals: list[float]) -> str:
    if not vals:
        return "n/a"
    return f"{statistics.median(vals):.0f} (p10 {q(vals, 0.1):.0f}, p90 {q(vals, 0.9):.0f}, max {max(vals):.0f}, n={len(vals)})"


def cmd_analyze(a: argparse.Namespace) -> None:
    lines = load(a.paths)
    t0 = min(ln["t_send"] for ln in lines)
    t1 = max(ln["t_end"] for ln in lines)
    recs = fetch_records(a.runtime_arn, t0 - a.before, t1 + 300)
    slack = a.slack
    # attribute each record to the client call whose window holds its receipt; calls run back to
    # back, so slack is used only for a record that falls in no window, toward the nearest one
    for r in recs:
        r["line"] = next((ln for ln in lines if ln["t_send"] <= r["receipt"] <= ln["t_end"]), None)
        if r["line"] is None:
            near = [(min(abs(r["receipt"] - ln["t_send"]), abs(r["receipt"] - ln["t_end"])), i) for i, ln in enumerate(lines)]
            dist, i = min(near)
            if dist <= slack:
                r["line"] = lines[i]
    for ln in lines:
        ln["records"] = [r for r in recs if r["line"] is ln]
    seen_sessions: set[str] = set()
    for r in recs:
        r["new_session"] = r["session_id"] not in seen_sessions
        seen_sessions.add(r["session_id"])
    out: list[str] = []
    w = out.append
    w("# E12 results: gateway MCP sessions on against off\n")
    w(f"Generated by `scripts/v2study/gateway_mcp.py analyze` from {len(lines)} client calls and {len(recs)} runtime "
      f"records of `{a.runtime_arn.rsplit('/', 1)[-1]}` between "
      f"{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(t0 - a.before))} and "
      f"{time.strftime('%H:%M:%S', time.gmtime(t1 + 300))} UTC. Times in ms.\n")
    unattributed = [r for r in recs if r["line"] is None]
    w(f"Runtime records outside every client call's window (the targets' tool sync and anything else): "
      f"{len(unattributed)}, in {len({r['session_id'] for r in unattributed})} runtime sessions, methods "
      f"{dict(Counter(r['method'] for r in unattributed))}.\n")
    gateways = sorted({ln["gateway"] for ln in lines})

    w("## Runtime sessions per gateway\n")
    w("| Gateway | Client sessions | tools/call ok | Runtime records | Distinct runtime sessions | Runtime sessions per client session | Records per runtime session | Methods on the target |")
    w("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for g in gateways:
        gl = [ln for ln in lines if ln["gateway"] == g]
        grecs = [r for ln in gl for r in ln["records"]]
        css = sorted({ln["client_session"] for ln in gl})
        per_cs = [len({r["session_id"] for ln in gl if ln["client_session"] == cs for r in ln["records"]}) for cs in css]
        per_rs = Counter(r["session_id"] for r in grecs)
        ok = sum(1 for ln in gl if ln["step"] == "tools/call" and ln.get("status") == 200 and not ln.get("error"))
        w(f"| {g} | {len(css)} | {ok} | {len(grecs)} | {len(per_rs)} | {dict(sorted(Counter(per_cs).items()))} | "
          f"{dict(sorted(Counter(per_rs.values()).items()))} | {dict(Counter(r['method'] for r in grecs))} |")
    w("\n`Runtime sessions per client session` and `Records per runtime session` are histograms {value: count}.\n")

    w("## Runtime records per client step\n")
    w("| Gateway | Step | Calls | Records per call | Of which on a runtime session not seen before | Methods |")
    w("| --- | --- | --- | --- | --- | --- |")
    for g in gateways:
        for step in ("initialize", "notifications/initialized", "tools/list", "tools/call"):
            sl = [ln for ln in lines if ln["gateway"] == g and ln["step"] == step]
            if not sl:
                continue
            rc = Counter(len(ln["records"]) for ln in sl)
            new = sum(1 for ln in sl for r in ln["records"] if r["new_session"])
            meth = Counter(r["method"] for ln in sl for r in ln["records"])
            w(f"| {g} | {step} | {len(sl)} | {dict(sorted(rc.items()))} | {new} | {dict(meth)} |")
    w("")

    w("## Target records by method\n")
    w("`record_ms` is the target runtime's receipt to completion. `first` is the first record on a runtime "
      "session (the restore); `later` is any other record on a session already open.\n")
    w("| Gateway | Client step | Method on the target | Position | Records | record_ms |")
    w("| --- | --- | --- | --- | --- | --- |")
    for g in gateways:
        groups: dict[tuple, list[float]] = defaultdict(list)
        for ln in lines:
            if ln["gateway"] != g:
                continue
            step = ln["step"] if ln["step"] != "tools/call" else ("tools/call 1" if ln["call_no"] == 1 else "tools/call 2 to 5")
            for r in ln["records"]:
                groups[(step, r["method"], "first" if r["new_session"] else "later")].append((r["done"] - r["receipt"]) * 1000)
        order = ["initialize", "notifications/initialized", "tools/list", "tools/call 1", "tools/call 2 to 5"]
        for key in sorted(groups, key=lambda k: (order.index(k[0]) if k[0] in order else 9, k[2], str(k[1]))):
            w(f"| {g} | {key[0]} | {key[1]} | {key[2]} | {len(groups[key])} | {stat(groups[key])} |")
    w("")
    w("## Restores per client session\n")
    w("New runtime sessions opened on the target during each client session (each one is a restore), "
      "and the sequence of methods the gateway sent for the first tools/call.\n")
    w("| Gateway | Round | Client sessions | New runtime sessions per client session | Methods behind tools/call 1 |")
    w("| --- | --- | --- | --- | --- |")
    for g in gateways:
        for rnd in sorted({ln["round"] for ln in lines}):
            css = [cs for cs in dict.fromkeys(ln["client_session"] for ln in lines if ln["gateway"] == g and ln["round"] == rnd)]
            per = [sum(1 for ln in lines if ln["client_session"] == cs for r in ln["records"] if r["new_session"]) for cs in css]
            seqs = Counter(
                " > ".join(str(r["method"]) for r in ln["records"])
                for ln in lines if ln["gateway"] == g and ln["round"] == rnd and ln["step"] == "tools/call" and ln["call_no"] == 1)
            w(f"| {g} | {rnd} | {len(css)} | {per} | {'; '.join(f'{k} (x{v})' for k, v in seqs.items())} |")
    w("")

    w("## Client latency (client_ms)\n")
    w("| Gateway | Round | initialize | tools/list | tools/call 1 | tools/call 2 to 5 | all tools/call |")
    w("| --- | --- | --- | --- | --- | --- | --- |")
    for g in gateways:
        for rnd in sorted({ln["round"] for ln in lines}) + ["all"]:
            gl = [ln for ln in lines if ln["gateway"] == g and (rnd == "all" or ln["round"] == rnd) and ln.get("status") in (200, 202) and not ln.get("error")]
            init = [ln["client_ms"] for ln in gl if ln["step"] == "initialize"]
            tl = [ln["client_ms"] for ln in gl if ln["step"] == "tools/list"]
            c1 = [ln["client_ms"] for ln in gl if ln["step"] == "tools/call" and ln["call_no"] == 1]
            c25 = [ln["client_ms"] for ln in gl if ln["step"] == "tools/call" and ln["call_no"] and ln["call_no"] > 1]
            call = c1 + c25
            w(f"| {g} | {rnd} | {stat(init)} | {stat(tl)} | {stat(c1)} | {stat(c25)} | {stat(call)} |")
    w("")

    w("## tools/call against the target's records\n")
    w("For each tools/call: the target's records inside the call's window, the tools/call record's receipt to "
      "completion (`record_ms`), the probe's handler start after that receipt (`receipt_to_handler_ms`, the restore "
      "and delivery when the runtime session is new), and the client's time outside the target's records "
      "(`gateway_ms`: client_ms minus the span from the first record's receipt to the last record's completion).\n")
    w("| Gateway | Calls | New runtime session | record_ms of tools/call | receipt_to_handler_ms | target span ms | gateway_ms |")
    w("| --- | --- | --- | --- | --- | --- | --- |")
    for g in gateways:
        for label, pick in (("call 1", lambda ln: ln["call_no"] == 1), ("calls 2 to 5", lambda ln: ln["call_no"] > 1),
                            ("all", lambda ln: True)):
            sl = [ln for ln in lines if ln["gateway"] == g and ln["step"] == "tools/call" and ln.get("status") == 200
                  and not ln.get("error") and pick(ln)]
            rec_ms, r2h, span, gw_ms, new = [], [], [], [], 0
            for ln in sl:
                tc = [r for r in ln["records"] if r["method"] == "tools/call"]
                if ln["records"]:
                    first, last = ln["records"][0], ln["records"][-1]
                    sp = (max(r["done"] for r in ln["records"]) - first["receipt"]) * 1000
                    span.append(sp)
                    gw_ms.append(ln["client_ms"] - sp)
                    new += 1 if any(r["new_session"] for r in ln["records"]) else 0
                if tc:
                    rec_ms.append((tc[-1]["done"] - tc[-1]["receipt"]) * 1000)
                    pw = (ln.get("probe") or {}).get("req_wall")
                    if pw:
                        r2h.append((pw - tc[-1]["receipt"]) * 1000)
            w(f"| {g} | {label} | {new} of {len(sl)} | {stat(rec_ms)} | {stat(r2h)} | {stat(span)} | {stat(gw_ms)} |")
    w("")

    w("## Probe telemetry per client session\n")
    w("`n` is the probe's request counter in the process that answered; a new restore starts at 1. "
      "`sessions` is the number of distinct runtime session ids the probe saw (its `Mcp-Session-Id` header).\n")
    w("| Gateway | Client session | Gateway Mcp-Session-Id | n sequence | sessions seen by the probe | pids | mono_since_start_s | tools/call client_ms |")
    w("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for g in gateways:
        for cs in sorted({ln["client_session"] for ln in lines if ln["gateway"] == g},
                         key=lambda c: min(ln["t_send"] for ln in lines if ln["client_session"] == c)):
            sl = [ln for ln in lines if ln["client_session"] == cs and ln["step"] == "tools/call"]
            pr = [ln.get("probe") or {} for ln in sl]
            gsid = next((ln.get("mcp_session_id") for ln in lines if ln["client_session"] == cs and ln["step"] == "initialize"), None)
            w(f"| {g} | {cs} | {(gsid or 'none')[:20]} | {[p.get('n') for p in pr]} | {len({p.get('session_header') for p in pr})} | "
              f"{sorted({p.get('pid') for p in pr}, key=str)} | {[p.get('mono_since_start_s') for p in pr]} | "
              f"{[ln.get('client_ms') for ln in sl]} |")
    w("")
    w("## Distinct values per gateway\n")
    w("| Gateway | tools/call | distinct pids | distinct session headers | distinct boot_id | distinct first_random | n values |")
    w("| --- | --- | --- | --- | --- | --- | --- |")
    for g in gateways:
        pr = [ln.get("probe") or {} for ln in lines if ln["gateway"] == g and ln["step"] == "tools/call" and ln.get("probe")]
        w(f"| {g} | {len(pr)} | {len({p.get('pid') for p in pr})} | {len({p.get('session_header') for p in pr})} | "
          f"{len({p.get('boot_id') for p in pr})} | {len({p.get('first_random') for p in pr})} | {dict(sorted(Counter(p.get('n') for p in pr).items()))} |")
    w("")
    errs = [ln for ln in lines if ln.get("error") or ln.get("status") not in (200, 202)]
    w(f"## Errors\n\n{len(errs)} calls failed." + ("" if not errs else ""))
    for ln in errs[:20]:
        w(f"- {ln['gateway']} {ln['client_session']} {ln['step']} {ln.get('call_no')}: status {ln.get('status')} {str(ln.get('error'))[:200]}")
    w("")
    if a.dump:
        with open(a.dump, "w") as f:
            for r in recs:
                ln = r.pop("line")
                r["client_session"] = ln["client_session"] if ln else None
                r["gateway"] = ln["gateway"] if ln else None
                r["step"] = ln["step"] if ln else None
                r["call_no"] = ln.get("call_no") if ln else None
                f.write(json.dumps(r) + "\n")
    text = "\n".join(out) + "\n"
    if a.md:
        pathlib.Path(a.md).write_text(text)
    print(text)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--gw", action="append", required=True, help="name=url")
    r.add_argument("--target", required=True)
    r.add_argument("--sessions", type=int, default=5)
    r.add_argument("--calls", type=int, default=5)
    r.add_argument("--round", required=True)
    r.add_argument("--pause", type=float, default=2.0)
    r.add_argument("--outdir", required=True)
    r.set_defaults(fn=cmd_run)
    an = sub.add_parser("analyze")
    an.add_argument("paths", nargs="+")
    an.add_argument("--runtime-arn", required=True)
    an.add_argument("--md")
    an.add_argument("--dump", help="write the attributed runtime records as JSON lines")
    an.add_argument("--slack", type=float, default=0.3, help="seconds of clock slack around a call's window")
    an.add_argument("--before", type=float, default=60, help="seconds before the first call to read records from")
    an.set_defaults(fn=cmd_analyze)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
