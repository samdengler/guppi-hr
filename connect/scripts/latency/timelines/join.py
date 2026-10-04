"""Joins the browser's turn records with every server-side source in raw/, per turn and per
chat start, on one clock (epoch ms, then ms from the click). Writes joined.json.

    python3 join.py
"""
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
RAW = HERE / "raw"
DOMAINS = ("profile", "pay", "travel")
TARGETS = {"AGS0JX5M1V": "travel", "WRADAXMX9A": "profile", "WRBXBB12RO": "pay", "KB8LJT6NRY": "docs", "VODAOVCYZX": "hr"}


def iso(text):
    """ISO time (nanoseconds allowed) to epoch ms as a float."""
    text = text.rstrip("Z").replace("+00:00", "")
    if "." in text:
        base, frac = text.split(".")
    else:
        base, frac = text, "0"
    return datetime.fromisoformat(base + "+00:00").timestamp() * 1000 + int(frac[:6].ljust(6, "0")) / 1000


def load(name):
    p = RAW / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else []


# ---- the browser ----


def browser_chats():
    chats = []
    for f in sorted(HERE.glob("results-*.json")):
        mode = json.loads(f.read_text())["mode"]
        for c in json.loads(f.read_text())["chats"]:
            c["mode"] = mode
            chats.append(c)
    return chats


# ---- CloudWatch: Lambda functions ----


def invocations(events):
    """Lambda invocations from START/REPORT lines per stream, with the JSON lines between."""
    by_stream = defaultdict(list)
    for ts, stream, msg in sorted(events, key=lambda e: e[0]):
        by_stream[stream].append((ts, msg))
    calls = []
    for stream, items in by_stream.items():
        cur = None
        init_start = None
        for ts, msg in items:
            if msg.startswith("INIT_START"):
                init_start = ts
            elif msg.startswith("START RequestId"):
                m = re.search(r"START RequestId: (\S+)", msg)
                cur = {"stream": stream, "start": ts, "lines": [], "init_start": init_start, "rid": m.group(1) if m else None}
                init_start = None
            elif msg.startswith("REPORT RequestId") and cur is not None:
                m = re.search(r"Duration: ([\d.]+) ms", msg)
                cur["duration"] = float(m.group(1)) if m else None
                m = re.search(r"Init Duration: ([\d.]+) ms", msg)
                cur["init"] = float(m.group(1)) if m else None
                m = re.search(r"XRAY TraceId: (\S+)", msg)
                cur["xray"] = m.group(1) if m else None
                cur["end"] = ts
                calls.append(cur)
                cur = None
            elif msg.startswith("{"):
                try:
                    d = json.loads(msg)
                except ValueError:
                    continue
                target = cur if cur is not None else None
                if target is not None:
                    target["lines"].append((ts, d))
                elif d.get("event") == "cold_start":
                    pass
    for c in calls:
        # A REPORT's end is logged after the handler; the handler began `duration` before it.
        c["handler_start"] = c["end"] - (c["duration"] or 0)
    return calls


def issuer_calls():
    out = []
    for c in invocations(load("issuer")):
        tok = next((d for _, d in c["lines"] if "route" in d), None)
        out.append(
            {
                "start": c["handler_start"] - (c["init"] or 0),
                "handler_start": c["handler_start"],
                "end": c["end"],
                "ms": c["duration"],
                "init": c["init"],
                "client": tok.get("client") if tok else None,
                "audience": tok.get("audience") if tok else None,
                "route": tok.get("route") if tok else "jwks/other",
                "cold": bool(c["init"]),
                "rid": c.get("rid"),
                "stream": c["stream"],
            }
        )
    return sorted(out, key=lambda x: x["start"])


def chat_start_calls():
    out = {}
    reports = {}
    for c in invocations(load("chat-start")):
        for ts, d in c["lines"]:
            if d.get("event") == "chat_start" and d.get("contact"):
                out[d["contact"]] = {**c, "line": d, "line_ts": ts}
            elif d.get("event") == "chat_report" and d.get("run"):
                reports[d["run"]] = {"line": d, "start": c["start"], "end": c["end"], "duration": c["duration"], "rid": c.get("rid"), "stream": c["stream"]}
    return out, reports


def xray_spans():
    spans = defaultdict(list)
    for _, _, msg in load("spans"):
        try:
            s = json.loads(msg)
        except ValueError:
            continue
        spans[s.get("traceId")].append(s)
    return spans


# ---- the gateways ----


def gateway_requests(name):
    groups = defaultdict(list)
    for ts, _, msg in load(name):
        d = json.loads(msg)
        t = int(d["timeUnixNano"]) / 1e6 if d.get("timeUnixNano") else ts
        rid = d.get("request_id") or d["body"].get("id")
        groups[rid].append((t, d))
    reqs = []
    for rid, lines in groups.items():
        lines.sort(key=lambda x: x[0])
        r = {"id": rid, "trace": next((d.get("trace_id") for _, d in lines if d.get("trace_id")), None)}
        for t, d in lines:
            b = d["body"]
            log = b.get("log") or ""
            if log.startswith("Started processing"):
                r["start"] = t
                body = b.get("requestBody") or ""
                m = re.search(r"method=([\w/]+)", body)
                r["method"] = m.group(1) if m else "invoke"
                m = re.search(r"params=\{name=([\w-]+)", body)
                if m:
                    r["tool"] = m.group(1)
                m = re.search(r"session\.id=([0-9a-f-]+-\w+)", body)
                if m:
                    r["session"] = m.group(1)
            elif log.startswith("Executing tool"):
                r["exec"] = t
                m = re.search(r"Executing tool (\S+) from target (\S+)", log)
                if m:
                    r["tool"], r["target"] = m.group(1), m.group(2)
            elif log.startswith("Executing Http request for target"):
                r["exec"] = t
                m = re.search(r"target (\S+)", log)
                r["target"] = m.group(1) if m else None
            elif log.startswith("Successfully processed") or log.startswith("Failed") or b.get("isError"):
                r.setdefault("end", t)
                if b.get("isError"):
                    r["error"] = log[:120]
            elif log.startswith("Policy evaluation"):
                r["policy_ms"] = (b.get("policy") or {}).get("latencyMs")
            elif log.startswith("Action resolved from session state"):
                r["session_state"] = True
        if "start" in r:
            reqs.append(r)
    return sorted(reqs, key=lambda r: r["start"])


# ---- Dynatrace spans ----


def dt_spans():
    spans = []
    for s in load("dt-spans"):
        s["s"] = iso(s["start_time"])
        s["e"] = iso(s["end_time"])
        spans.append(s)
    return spans


# ---- runtime logs: run lines, microVM streams ----


def runtime_runs():
    runs = []
    for d in DOMAINS:
        for ts, stream, msg in load(f"rt-{d}"):
            if "duration_ms" not in msg or "runtime-logs" not in stream:
                continue
            m = re.search(r"- (\{.*\})$", msg)
            if not m:
                continue
            try:
                rec = json.loads(m.group(1))
            except ValueError:
                continue
            runs.append({"domain": d, "end": ts, "stream": stream.split("]")[-1], **rec})
    return runs


def process_starts():
    starts = defaultdict(dict)
    for d in DOMAINS + ("tools",):
        for ts, stream, msg in load(f"rt-{d}") + load(f"rt-{d}-proc"):
            if "Started server process" in msg:
                starts[d][stream.split("]")[-1]] = ts
    return starts


# ---- the designer ----


def designer(contact):
    p = RAW / "designer" / f"{contact}.jsonl"
    if not p.exists():
        return []
    events = []
    for line in p.read_text().splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        e["t"] = iso(e["eventTime"])
        events.append(e)
    return sorted(events, key=lambda e: e["t"])


def designer_turns(events):
    turns = defaultdict(list)
    for e in events:
        if e.get("correlationId"):
            turns[e["correlationId"]].append(e)
    out = []
    for cid, evs in turns.items():
        req = next((e for e in evs if e["eventType"] == "NluRequestReceived"), None)
        if not req:
            continue
        t = {"cid": cid, "recv": req["t"], "utterance": (req.get("properties") or {}).get("utterance"), "message_id": (req.get("properties") or {}).get("messageId"), "build": (req.get("properties") or {}).get("buildId"), "models": [], "requests": [], "agents": []}
        open_model = None
        open_req = {}
        open_agent = {}
        for e in evs:
            k, p = e["eventType"], e.get("properties") or {}
            if k == "ModelStart":
                open_model = e["t"]
            elif k == "ModelEnd" and open_model is not None:
                t["models"].append((open_model, e["t"]))
                open_model = None
            elif k == "DataRequestsRequested":
                open_req[tuple(p.get("dataRequestIds") or [])] = (e["t"], p.get("url"))
            elif k == "DataRequestsReturned":
                key = tuple(p.get("dataRequestIds") or [])
                if key in open_req:
                    s, url = open_req.pop(key)
                    t["requests"].append({"ids": list(key), "start": s, "end": e["t"], "responseTime": p.get("responseTime"), "url": url, "status": p.get("statusCode")})
            elif k == "AgentStarted":
                open_agent[p.get("nodeId")] = (e["t"], p.get("mcpToolCount"))
            elif k == "AgentEnded":
                if p.get("nodeId") in open_agent:
                    s, n = open_agent.pop(p.get("nodeId"))
                    t["agents"].append({"start": s, "end": e["t"], "tools": n})
            elif k == "NluResponded":
                t["resp"] = e["t"]
                t["flow"] = e.get("flowId")
                t["responseTime"] = p.get("responseTime")
            elif k == "GenerativeJourneyStarted":
                t["journey"] = True
            elif re.search(r"Fail|Error|Timeout", k):
                t.setdefault("errors", []).append(k)
        out.append(t)
    return sorted(out, key=lambda x: x["recv"])


# ---- joining ----


def within(t, lo, hi):
    return t is not None and lo <= t <= hi


def sub_agent_detail(root, spans_by_session, tools_reqs, issuer, tools_rt):
    """The steps inside one sub-agent request, from its Dynatrace trace."""
    trace = root["trace.id"]
    # By session and time: the MCP client's thread keeps the context of the request that
    # opened it, so a later request's MCP spans carry the first request's trace id.
    kids = [s for s in spans_by_session[root.get("session.id")] if root["s"] - 1 <= s["s"] <= root["e"] + 1 and s["service.name"] == root["service.name"] and s is not root]
    kids.sort(key=lambda s: s["s"])
    out = {"start": root["s"], "end": root["e"], "trace": trace, "span": root.get("span.id"), "instance": root.get("service.instance.id"), "session": root.get("session.id"), "steps": []}

    def add(name, s, e, owner, **kw):
        out["steps"].append({"name": name, "s": s, "e": e, "owner": owner, **kw})

    used = set()
    imds = [s for s in kids if "169.254.169.254" in (s.get("http.url") or "")]
    if imds:
        # Credential reads from the instance metadata service, in bursts of three.
        bursts = []
        for s in imds:
            if bursts and s["s"] - bursts[-1][1] < 20:
                bursts[-1][1] = s["e"]
            else:
                bursts.append([s["s"], s["e"]])
        for b in bursts:
            add("instance credentials (IMDS)", b[0], b[1], "runtime")
    for s in kids:
        n = s["span.name"]
        if n == "Bedrock AgentCore.GetWorkloadAccessTokenForJWT":
            add("workload access token (Identity)", s["s"], s["e"], "identity", span=s.get("span.id"), aws_request_id=s.get("aws.request_id"))
        elif n == "Bedrock AgentCore.GetResourceOauth2Token":
            iss = [c for c in issuer if c["client"] and c["client"].startswith("hr-agent-") and within(c["handler_start"], s["s"] - 5, s["e"] + 5)]
            add("on-behalf-of exchange for the tools token (Identity, issuer)", s["s"], s["e"], "identity", issuer=[(c["client"], c["ms"], c["cold"], c["init"]) for c in iss], span=s.get("span.id"), aws_request_id=s.get("aws.request_id"), provider=s.get("aws.auth.credential_provider"), issuer_rids=[c.get("rid") for c in iss])
        elif n == "POST" and "gateway.bedrock-agentcore" in (s.get("http.url") or ""):
            gw = next((r for r in tools_reqs if within(r["start"], s["s"] - 5, s["e"]) and id(r) not in used), None)
            if gw:
                used.add(id(r) if False else id(gw))
            method = gw.get("method") if gw else "?"
            label = f"MCP {method}" + (f" {gw.get('tool')}" if gw and gw.get("tool") else "")
            step = {"gw": gw, "span": s.get("span.id")}
            if gw and method == "tools/call":
                ex = gw.get("exec")
                iss = [c for c in issuer if c["client"] == "hr-tools-gateway" and within(c["handler_start"], s["s"], s["e"])]
                rt = [x for x in tools_rt if within(x["s"], s["s"], s["e"])]
                step["inner"] = {
                    "gw_start": gw["start"],
                    "gw_exec": ex,
                    "gw_end": gw.get("end"),
                    "policy_ms": gw.get("policy_ms"),
                    "issuer": [(c["handler_start"], c["end"], c["ms"], c["cold"]) for c in iss],
                    "tools_rt": [(x["s"], x["e"], x.get("service.instance.id")) for x in rt],
                    "issuer_rids": [c.get("rid") for c in iss],
                    "tools_rt_streams": sorted(TOOLS_STREAMS.get(gw.get("trace"), ())),
                    "tools_rt_spans": [x.get("span.id") for x in rt],
                }
            add(label, s["s"], s["e"], "gateway", **step)
        elif n == "invoke_agent Strands Agents":
            add("Strands agent invocation", s["s"], s["e"], "ours", span=s.get("span.id"), tokens_in=s.get("gen_ai.usage.input_tokens"), tokens_out=s.get("gen_ai.usage.output_tokens"))
        elif n == "chat":
            add(
                "model call (Haiku 4.5, ConverseStream)",
                s["s"],
                s["e"],
                "model",
                span=s.get("span.id"),
                model=s.get("gen_ai.request.model"),
                ttft=float(s.get("gen_ai.server.time_to_first_token") or 0) or None,
                server_ms=float(s.get("gen_ai.server.request.duration") or 0) or None,
                tokens_in=int(s.get("gen_ai.usage.input_tokens") or 0),
                tokens_out=int(s.get("gen_ai.usage.output_tokens") or 0),
            )
        elif n.startswith("execute_tool"):
            add(n, s["s"], s["e"], "ours")
    out["steps"].sort(key=lambda x: x["s"])
    return out


TOOLS_STREAMS = defaultdict(set)


def tools_streams():
    for _, stream, msg in load("rt-tools"):
        if "runtime-logs" not in stream:
            continue
        m = re.search(r"trace_id=([0-9a-f]{32})", msg)
        if m:
            TOOLS_STREAMS[m.group(1)].add(stream.split("]")[-1])


def main():
    tools_streams()
    chats = browser_chats()
    starts, reports = chat_start_calls()
    issuer = issuer_calls()
    agents_reqs = gateway_requests("agents-gw")
    tools_reqs = gateway_requests("tools-gw")
    spans = dt_spans()
    spans_by_session = defaultdict(list)
    for s in spans:
        spans_by_session[s.get("session.id")].append(s)
    roots = [s for s in spans if s["span.name"] == "POST /" and s["service.name"].startswith(("hr_super_agent_profile", "hr_super_agent_pay", "hr_super_agent_travel"))]
    tools_rt = [s for s in spans if s["service.name"].startswith("hr_super_agent_tools") and s["span.name"] == "POST /mcp"]
    runs = runtime_runs()
    pstarts = process_starts()
    streams = json.loads((RAW / "streams.json").read_text()) if (RAW / "streams.json").exists() else {}
    stream_created = {}
    for k, v in streams.items():
        for s in v:
            stream_created[s["logStreamName"].split("]")[-1]] = s["creationTime"]
    xr = xray_spans()

    joined = []
    for chat in chats:
        contact = chat.get("contact")
        if not contact:
            continue
        dturns = designer_turns(designer(contact))
        seen_domains = set()
        rec = {"label": chat["label"], "mode": chat["mode"], "contact": contact, "turns": [], "start": None}
        # ---- chat start ----
        cs = starts.get(contact)
        load = chat.get("load") or {}
        origin = load.get("timeOrigin")
        res = {r["name"].split("/")[-1] if "participant" in r["name"] else r["name"].split("/", 3)[-1]: r for r in load.get("res", [])}
        st = {"contact": contact}
        if origin:
            def ep(v):
                return origin + v if v else None
            for r in load.get("res", []):
                n = r["name"]
                key = None
                if n.endswith("/v1/token"):
                    key = "okta_refresh"
                elif n.endswith("/api/hr/chat/start"):
                    key = "chat_start_http"
                elif n.endswith("/participant/connection") and "participant_connection" not in st:
                    key = "participant_connection"
                elif n.endswith("/participant/transcript") and "transcript" not in st:
                    key = "transcript"
                elif n.endswith("config.json"):
                    key = "config"
                if key and key not in st:
                    st[key] = {"start": ep(r["start"]), "requestStart": ep(r["requestStart"]), "responseStart": ep(r["responseStart"]), "end": ep(r["responseEnd"]) or ep(r["start"] + r["duration"]), "connect": (r["connectEnd"] - r["connectStart"]) if r["connectEnd"] else None}
            ws = (load.get("ws") or [None])[0]
            if ws:
                st["ws"] = {"created": ep(ws["created"]), "open": ep(ws["open"]), "first_frame": ep(ws["firstFrame"])}
            nav = load.get("nav") or {}
            st["nav_response_end"] = ep(nav.get("responseEnd"))
            st["dom_content_loaded"] = ep(nav.get("domContentLoaded"))
            st["origin"] = origin
            st["visible"] = chat.get("visibleEpoch")
        if cs:
            line = cs["line"]
            st["fn"] = {
                "start": cs["start"],
                "handler_start": cs["handler_start"],
                "end": cs["end"],
                "duration": cs["duration"],
                "init": cs["init"],
                "init_start": cs.get("init_start"),
                "cold": line.get("cold"),
                "exchange_cached": line.get("exchange_cached"),
                "total_ms": line.get("total_ms"),
                "steps": line.get("steps"),
                "xray": cs.get("xray"),
                "rid": cs.get("rid"),
                "stream": cs["stream"],
            }
            # The hop token exchanges at the issuer during the start.
            lo = cs["start"]
            hi = cs["end"]
            st["fn"]["issuer"] = [(c["client"], c["audience"], round(c["handler_start"] - lo), c["ms"], c["cold"], c["init"]) for c in issuer if c["client"] == "hr-bridge" and within(c["handler_start"], lo - 50, hi)]
            st["fn"]["issuer_calls"] = [{"rid": c["rid"], "stream": c["stream"], "audience": c["audience"], "start": c["handler_start"], "ms": c["ms"], "cold": c["cold"]} for c in issuer if c["client"] == "hr-bridge" and within(c["handler_start"], lo - 50, hi)]
            tid = (cs.get("xray") or "").replace("1-", "", 1).replace("-", "")
            st["fn"]["xray_spans"] = [(s.get("name"), s.get("startTimeUnixNano"), s.get("endTimeUnixNano")) for s in xr.get(tid, [])]
        greet = next((d for d in dturns if not d.get("utterance")), None)
        if greet:
            st["greeting"] = {"recv": greet["recv"], "resp": greet.get("resp"), "flow": greet.get("flow"), "cid": greet["cid"], "message_id": greet.get("message_id"), "build": greet.get("build")}
        rec["start"] = st
        # ---- turns ----
        for i, turn in enumerate(chat.get("turns") or []):
            click = turn["clickEpoch"]
            t = {
                "i": i,
                "text": turn["text"],
                "how": turn["how"],
                "click": click,
                "send_start": turn.get("msgReqStartMs") if turn.get("msgReqStartMs") is not None else turn.get("sendStartMs"),
                "send_end": turn.get("msgReqEndMs") if turn.get("msgReqEndMs") is not None else turn.get("sendEndMs"),
                "page_send": (turn.get("sendStartMs"), turn.get("sendEndMs")),
                "first": turn.get("firstMs"),
                "done": turn.get("doneMs"),
                "reply": (turn.get("texts") or [""])[-1][:160],
                "run": (turn.get("ids") or {}).get("run"),
            }
            rep = reports.get(t["run"])
            if rep:
                L = rep["line"]
                t["connect_sent"] = iso(L["sent_at"]) - click if L.get("sent_at") else None
                t["connect_first_item"] = iso(L["first_item_at"]) - click if L.get("first_item_at") else None
                t["connect_last_item"] = iso(L["last_item_at"]) - click if L.get("last_item_at") else None
                t["end_reason"] = L.get("end_reason")
                t["report_fn_ms"] = rep["duration"]
                t["report_rid"] = rep.get("rid")
                t["report_line_ms"] = L.get("ms")
            # The designer's turn: the first request received after the click.
            dt = next((d for d in dturns if d["recv"] >= click - 200 and d.get("utterance")), None)
            if dt:
                dturns = [d for d in dturns if d is not dt]
                rel = lambda v: (v - click) if v is not None else None  # noqa: E731
                t["designer"] = {
                    "recv": rel(dt["recv"]),
                    "resp": rel(dt.get("resp")),
                    "flow": dt.get("flow"),
                    "responseTime": dt.get("responseTime"),
                    "models": [(rel(a), rel(b)) for a, b in dt["models"]],
                    "requests": [{**r, "start": rel(r["start"]), "end": rel(r["end"])} for r in dt["requests"]],
                    "agents": [{**a, "start": rel(a["start"]), "end": rel(a["end"])} for a in dt["agents"]],
                    "journey": dt.get("journey", False),
                    "cid": dt["cid"],
                    "message_id": dt.get("message_id"),
                    "build": dt.get("build"),
                    "errors": dt.get("errors"),
                    "utterance": dt.get("utterance"),
                }
                # Data requests: the gateway and the sub-agent behind each.
                for r in t["designer"]["requests"]:
                    url = r.get("url") or ""
                    s_abs, e_abs = r["start"] + click, r["end"] + click
                    if "-agents-" in url:
                        domain = url.rstrip("/").split("/")[-2]
                        r["domain"] = domain
                        r["first_for_domain"] = domain not in seen_domains
                        seen_domains.add(domain)
                        gw = next((g for g in agents_reqs if within(g["start"], s_abs - 50, e_abs) and TARGETS.get(g.get("target")) == domain), None)
                        if gw:
                            r["gw"] = {k: (gw[k] - click if k in ("start", "exec", "end") and gw.get(k) else gw.get(k)) for k in ("start", "exec", "end", "target", "session_state", "trace", "id")}
                        root = next((s for s in roots if s.get("session.id") == f"{contact}-{domain}" and within(s["s"], s_abs, e_abs)), None)
                        if root:
                            det = sub_agent_detail(root, spans_by_session, tools_reqs, issuer, tools_rt)
                            run = next((x for x in runs if x["context"] == contact and x["domain"] == domain and within(x["end"], root["e"] - 100, root["e"] + 500)), None)
                            det["run"] = run
                            if run:
                                stream = run["stream"]
                                det["stream"] = stream
                                det["stream_created"] = stream_created.get(stream)
                                det["stream_full"] = next((s["logStreamName"] for v in streams.values() for s in v if s["logStreamName"].endswith(stream)), None)
                                det["process_started"] = pstarts[domain].get(stream)
                            # relative times
                            det["start"] -= click
                            det["end"] -= click
                            for step in det["steps"]:
                                step["s"] -= click
                                step["e"] -= click
                                inner = step.get("inner")
                                if inner:
                                    for k in ("gw_start", "gw_exec", "gw_end"):
                                        if inner.get(k):
                                            inner[k] -= click
                                    inner["issuer"] = [(a - click, b - click, ms, cold) for a, b, ms, cold in inner["issuer"]]
                                    inner["tools_rt"] = [(a - click, b - click, inst) for a, b, inst in inner["tools_rt"]]
                                if step.get("gw"):
                                    g = step["gw"]
                                    step["gw"] = {k: (g[k] - click if k in ("start", "exec", "end") and g.get(k) else g.get(k)) for k in ("start", "exec", "end", "method", "tool", "policy_ms", "id", "trace", "session")}
                            r["sub"] = det
                    elif "-tools-" in url:
                        gw = next((g for g in tools_reqs if within(g["start"], s_abs - 50, e_abs) and g.get("method") == "tools/call"), None)
                        if gw:
                            r["gw"] = {k: (gw[k] - click if k in ("start", "exec", "end") and gw.get(k) else gw.get(k)) for k in ("start", "exec", "end", "tool", "target", "policy_ms", "trace", "id")}
                            iss = [c for c in issuer if c["client"] == "hr-tools-gateway" and within(c["handler_start"], gw["start"], gw.get("end") or e_abs)]
                            r["gw"]["issuer"] = [(c["handler_start"] - click, c["ms"], c["cold"]) for c in iss]
                            r["gw"]["issuer_rids"] = [c.get("rid") for c in iss]
            rec["turns"].append(t)
        joined.append(rec)
    (HERE / "joined.json").write_text(json.dumps(joined, indent=1, default=str))
    print(f"{len(joined)} chats, {sum(len(c['turns']) for c in joined)} turns")


if __name__ == "__main__":
    main()
