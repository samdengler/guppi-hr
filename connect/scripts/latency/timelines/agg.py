"""Builds per-turn step lists from joined.json, classifies each turn's path, and aggregates
medians, p10 and p90 per path and step. Writes turn-steps.json, the waterfall JSON and
tables.md (Markdown tables for the report).

    python3 agg.py
"""
import json
import statistics
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
SCRATCH = HERE.parent
J = json.loads((HERE / "joined.json").read_text())


def pct(values, q):
    v = sorted(x for x in values if x is not None)
    if not v:
        return None
    if len(v) == 1:
        return v[0]
    k = (len(v) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def med(values):
    return pct(values, 0.5)


# ---- per-turn steps ----


def classify(t):
    d = t.get("designer") or {}
    reqs = d.get("requests") or []
    for r in reqs:
        if r.get("domain"):
            return f"{r['domain']}-{'first' if r.get('first_for_domain') else 'follow'}"
    if d.get("flow") == "PolicyFlow" or d.get("agents"):
        return "policy-first" if any("PolicySearch" in r["ids"] for r in reqs) else "policy-follow"
    if d.get("flow") == "ClarifyFlow":
        return "clarify"
    return f"other-{d.get('flow')}"


def turn_steps(t):
    """Ordered steps of one turn in ms from the click: (name, owner, start, end, level)."""
    S = []

    def add(name, owner, s, e, level=0, **kw):
        if s is None or e is None:
            return
        S.append({"name": name, "owner": owner, "start_ms": s, "end_ms": e, "level": level, **kw})

    d = t.get("designer") or {}
    add("Browser to Connect: SendMessage until Connect stamps the message", "connect", 0, t.get("connect_sent"))
    add("SendMessage request as the browser sees it (overlaps)", "connect", t["send_start"], t["send_end"], parallel_group="sendmessage")
    add("Connect hands the message to the designer", "connect", t.get("connect_sent"), d.get("recv"))
    models = d.get("models") or []
    cursor = d.get("recv")
    if models:
        add("Designer before the routing model", "designer", cursor, models[0][0])
        add("Routing model (designer, Bedrock)", "model", models[0][0], models[0][1])
        cursor = models[0][1]
    for r in d.get("requests") or []:
        add("Designer flow to the data request", "designer", cursor, r["start"])
        name = "+".join(r["ids"])
        add(f"Data request {name} (designer's view)", "designer", r["start"], r["end"], container=True)
        gw = r.get("gw") or {}
        if r.get("domain"):
            add("Designer to the agents gateway", "designer", r["start"], gw.get("start"), 1)
            add("Agents gateway: authorizer and target", "gateway", gw.get("start"), gw.get("exec"), 1)
            sub = r.get("sub")
            if sub:
                add("Runtime: session and delivery to the sub-agent", "runtime", gw.get("exec"), sub["start"], 1)
                add(f"Sub-agent {r['domain']} (POST / on the runtime)", "ours", sub["start"], sub["end"], 1, container=True)
                steps = sub["steps"]
                # Level-2 rows in order; the time between them is our code, named by what follows.
                imds_n = 0
                prev_end = sub["start"]
                for st in steps:
                    nm = st["name"]
                    if nm == "Strands agent invocation":
                        continue
                    gap_name = None
                    if nm.startswith("MCP initialize"):
                        gap_name = "Sub-agent: MCP client start (session thread, connection)"
                    elif nm.startswith("model call"):
                        gap_name = "Sub-agent: agent build (Strands Agent, Bedrock client)"
                    elif prev_end == sub["start"]:
                        gap_name = "Sub-agent: A2A request handling before the first call"
                    else:
                        gap_name = f"Sub-agent: our code before: {nm.split(' (')[0]}"
                    if st["s"] - prev_end > 15:
                        add(gap_name, "ours", prev_end, st["s"], 2)
                    if nm.startswith("model call"):
                        ttft = st.get("ttft")
                        if ttft:
                            add("Model: time to first token (Haiku 4.5)", "model", st["s"], st["s"] + ttft, 2, tokens_in=st.get("tokens_in"))
                            add("Model: generation", "model", st["s"] + ttft, st["e"], 2, tokens_out=st.get("tokens_out"))
                        else:
                            add("Model call (Haiku 4.5)", "model", st["s"], st["e"], 2)
                    elif nm.startswith("MCP tools/call"):
                        tool = nm.split()[-1]
                        add(f"MCP tools/call {tool} through the tools gateway", "gateway", st["s"], st["e"], 2, container=True)
                        inner = st.get("inner") or {}
                        gs, gx, ge = inner.get("gw_start"), inner.get("gw_exec"), inner.get("gw_end")
                        add(f"Sub-agent to the tools gateway ({tool})", "gateway", st["s"], gs, 3)
                        add(f"Tools gateway: authorizer, Cedar Policy, routing ({tool})", "gateway", gs, gx, 3)
                        iss = inner.get("issuer") or []
                        rts = sorted(inner.get("tools_rt") or [])
                        if iss:
                            add(f"Identity and the issuer: on-behalf-of exchange for the runtime token ({tool})", "identity", gx, iss[0][1], 3, issuer_ms=iss[0][2], cold=iss[0][3])
                            after = iss[0][1]
                        else:
                            after = gx
                        if rts:
                            add(f"Runtime: delivery of MCP initialize to the tools runtime ({tool})", "runtime", after, rts[0][0], 3)
                            if len(rts) >= 3:
                                add(f"Tools gateway: initialize and initialized round trips to the target ({tool})", "runtime", rts[0][0], rts[-1][0], 3)
                            add(f"Tools runtime: the tool call (JWT check, DynamoDB) ({tool})", "ours", rts[-1][0], rts[-1][1], 3)
                            add(f"Tools gateway and the sub-agent: the answer back ({tool})", "gateway", rts[-1][1], st["e"], 3)
                        elif gx and ge:
                            add(f"Tools gateway: target call (knowledge base) ({tool})", "gateway", gx, ge, 3)
                            add(f"Tools gateway and the sub-agent: the answer back ({tool})", "gateway", ge, st["e"], 3)
                    elif nm.startswith("MCP"):
                        add(f"{nm} (tools gateway)", "gateway", st["s"], st["e"], 2)
                    elif nm.startswith("instance credentials"):
                        imds_n += 1
                        add(f"Instance credentials from IMDS (read {imds_n})", "runtime", st["s"], st["e"], 2)
                    else:
                        add(nm, st["owner"], st["s"], st["e"], 2)
                    prev_end = st["e"]
                model_end = max((x["e"] for x in steps if x["name"].startswith("model call")), default=None)
                add("Sub-agent: after the model to the A2A answer", "ours", model_end, sub["end"], 2)
                add("Runtime and agents gateway return the answer", "runtime", sub["end"], gw.get("end"), 1)
            add("Agents gateway to the designer", "designer", gw.get("end"), r["end"], 1)
        else:
            add("Designer to the tools gateway", "designer", r["start"], gw.get("start"), 1)
            add("Tools gateway: authorizer, Cedar Policy, routing", "gateway", gw.get("start"), gw.get("exec"), 1)
            add("Tools gateway: knowledge base Retrieve (Bedrock Knowledge Bases)", "gateway", gw.get("exec"), gw.get("end"), 1)
            add("Tools gateway to the designer", "designer", gw.get("end"), r["end"], 1)
        cursor = r["end"]
    for a in d.get("agents") or []:
        add("Designer to the generative journey", "designer", cursor, a["start"])
        add("Generative journey agent (Haiku 4.5, in the designer)", "model", a["start"], a["end"])
        cursor = a["end"]
    add("Designer to its response (NluResponded)", "designer", cursor, d.get("resp"))
    add("Connect posts the reply to the transcript", "connect", d.get("resp"), t.get("connect_first_item"))
    add("Connect pushes the reply to the browser, the page shows it", "connect", t.get("connect_first_item"), t.get("first"))
    if t.get("done") is not None and t.get("first") is not None and t["done"] - t["first"] > 50:
        add("Page waits for quiet to end the turn (no end mark)", "ours", t["first"], t["done"])
    return S


def main():
    turns = []
    for c in J:
        for t in c["turns"]:
            if not t.get("designer"):
                continue
            path = classify(t)
            t["path"] = path
            t["steps"] = turn_steps(t)
            t["contact"] = c["contact"]
            t["label"] = c["label"]
            t["mode"] = c["mode"]
            turns.append(t)
    (HERE / "turn-steps.json").write_text(json.dumps(turns, indent=1, default=str))

    by_path = defaultdict(list)
    for t in turns:
        by_path[t["path"]].append(t)

    out = {"generated": "2026-10-04", "clock": "ms from the click (or from the page's navigation start for chat start)", "paths": {}}
    md = []
    order = ["clarify", "policy-first", "policy-follow", "profile-first", "profile-follow", "travel-first", "travel-follow", "pay-first", "pay-follow"]
    for path in order + [p for p in by_path if p not in order]:
        ts = by_path.get(path)
        if not ts:
            continue
        names = []
        for t in ts:
            for s in t["steps"]:
                if s["name"] not in names:
                    names.append(s["name"])
        rows = []
        for n in names:
            occ = [s for t in ts for s in t["steps"] if s["name"] == n]
            first_occ = occ[0]
            starts = [s["start_ms"] for s in occ]
            ends = [s["end_ms"] for s in occ]
            durs = [s["end_ms"] - s["start_ms"] for s in occ]
            rows.append(
                {
                    "name": n,
                    "owner": first_occ["owner"],
                    "start_ms": round(med(starts)),
                    "end_ms": round(med(ends)),
                    "dur_ms": round(med(durs)),
                    "dur_p10_ms": round(pct(durs, 0.1)),
                    "dur_p90_ms": round(pct(durs, 0.9)),
                    "dur_min_ms": round(min(durs)),
                    "dur_max_ms": round(max(durs)),
                    "p10_ms": round(pct(ends, 0.1)),
                    "p90_ms": round(pct(ends, 0.9)),
                    "level": first_occ["level"],
                    "parallel_group": first_occ.get("parallel_group"),
                    "container": bool(first_occ.get("container")),
                    "n": len(occ),
                }
            )
        rows.sort(key=lambda r: (r["start_ms"], -r["end_ms"]))
        firsts = [t["first"] for t in ts if t.get("first") is not None]
        dones = [t["done"] for t in ts if t.get("done") is not None]
        summary = {
            "turns": len(ts),
            "first_words_ms": {"median": round(med(firsts)), "p10": round(pct(firsts, 0.1)), "p90": round(pct(firsts, 0.9)), "min": round(min(firsts)), "max": round(max(firsts))},
            "done_ms": {"median": round(med(dones)), "min": round(min(dones)), "max": round(max(dones))},
            "contacts": sorted({t["contact"][:8] for t in ts}),
        }
        owners = defaultdict(list)
        for t in ts:
            tot = defaultdict(float)
            for st in t["steps"]:
                if st.get("container") or st.get("parallel_group") or st["start_ms"] >= (t["first"] or 0) - 1:
                    continue
                # leaf rows only: a row is a leaf when no deeper row lies inside it
                inner = [x for x in t["steps"] if x is not st and x["level"] > st["level"] and x["start_ms"] >= st["start_ms"] - 1 and x["end_ms"] <= st["end_ms"] + 1 and not x.get("parallel_group")]
                if inner:
                    continue
                tot[st["owner"]] += st["end_ms"] - st["start_ms"]
            tot["unattributed"] = (t["first"] or 0) - sum(tot.values())
            for k, v in tot.items():
                owners[k].append(v)
        summary["owner_ms_median"] = {k: round(med(v + [0] * (len(ts) - len(v)))) for k, v in owners.items()}
        out["paths"][path] = {"summary": summary, "steps": rows}
        md.append(f"\n### {path} ({len(ts)} turns)\n")
        md.append(f"First words median {summary['first_words_ms']['median']} ms (p10 {summary['first_words_ms']['p10']}, p90 {summary['first_words_ms']['p90']}, range {summary['first_words_ms']['min']} to {summary['first_words_ms']['max']}); done median {summary['done_ms']['median']} ms.\n")
        md.append("| Step | Owner | Start | End | Duration median | p10 to p90 | n |")
        md.append("| --- | --- | ---: | ---: | ---: | --- | ---: |")
        for r in rows:
            ind = "  " * r["level"]
            nm = ("&nbsp;&nbsp;" * r["level"]) + r["name"]
            md.append(f"| {nm} | {r['owner']} | {r['start_ms']} | {r['end_ms']} | {r['dur_ms']} | {r['dur_p10_ms']} to {r['dur_p90_ms']} | {r['n']} |")
    (HERE / "tables.md").write_text("\n".join(md))
    (HERE / "paths.json").write_text(json.dumps(out, indent=1))
    for p, v in out["paths"].items():
        print(p, v["summary"]["turns"], v["summary"]["first_words_ms"])


if __name__ == "__main__":
    main()


# ---- chat start, from the page's navigation start ----


def start_steps(st):
    S = []
    o = st.get("origin")
    if not o:
        return S

    def add(name, owner, s, e, level=0, group=None, **kw):
        if s is None or e is None:
            return
        S.append({"name": name, "owner": owner, "start_ms": s - o, "end_ms": e - o, "level": level, "parallel_group": group, **kw})

    add("Page HTML (navigation)", "internet", o, st.get("nav_response_end"))
    add("Page scripts to DOMContentLoaded", "ours", st.get("nav_response_end"), st.get("dom_content_loaded"))
    c = st.get("config") or {}
    add("config.json through CloudFront", "internet", c.get("start"), c.get("end"))
    k = st.get("okta_refresh") or {}
    add("Okta refresh token grant", "identity", k.get("start"), k.get("end"))
    h = st.get("chat_start_http") or {}
    fn = st.get("fn") or {}
    add("POST /api/hr/chat/start (browser's view)", "ours", h.get("start"), h.get("end"), container=True)
    if fn:
        fstart = fn["start"]
        if fn.get("init"):
            init_begin = fstart - fn["init"]
            add("Browser to the function: CloudFront, API Gateway, Lambda placement", "internet", h.get("requestStart") or h.get("start"), init_begin, 1)
            add("Lambda init (Rust, cold instance)", "ours", init_begin, fstart, 1)
        else:
            add("Browser to the function: CloudFront, API Gateway, Lambda invoke", "internet", h.get("requestStart") or h.get("start"), fstart, 1)
        steps = {s["name"]: s for s in fn.get("steps") or []}
        hop = steps.get("hop token exchanges")
        if hop:
            add("Okta token check in the function (RS256, built-in keys)", "ours", fstart, fstart + hop["start_ms"], 1)
            add("Hop token exchanges (workload token, then 4 at once)", "identity", fstart + hop["start_ms"], fstart + hop["end_ms"], 1, cached=fn.get("exchange_cached"))
            calls = sorted(fn.get("issuer") or [], key=lambda x: x[2])
            if calls:
                first_rel = calls[0][2]
                add("Identity before the issuer (workload access token, Identity's own work)", "identity", fstart + hop["start_ms"], fstart + first_rel, 2)
                for client, aud, rel, ms, cold, init in calls:
                    short = aud.replace("api://", "")
                    add(f"Issuer exchange for {short} (Lambda handler{', cold' if cold else ''})", "identity", fstart + rel, fstart + rel + ms, 2, group="issuer exchanges")
                last_end = max(rel + ms for _, _, rel, ms, _, _ in calls)
                add("Identity after the issuer (API Gateway return, Identity to the function)", "identity", fstart + last_end, fstart + hop["end_ms"], 2)
        for name, owner in (("StartChatContact", "connect"), ("CreateParticipantConnection", "connect"), ("flow socket", "connect")):
            s = steps.get(name)
            if s:
                add(f"{name} (function to Connect)" if name != "flow socket" else "Flow WebSocket open and subscribe (function)", owner, fstart + s["start_ms"], fstart + s["end_ms"], 1)
        g = steps.get("greeting wait")
        gr = st.get("greeting") or {}
        if g:
            gs, ge = fstart + g["start_ms"], fstart + g["end_ms"]
            add("Greeting wait (function)", "connect", gs, ge, 1, container=True)
            if gr.get("recv") and gs <= gr["recv"] <= ge + 50:
                add("Connect runs the contact flow to the Agentic CX block", "connect", gs, gr["recv"], 2)
                add("Designer greets (WelcomeFlow)", "designer", gr["recv"], gr.get("resp"), 2)
                add("Connect delivers the greeting to the function's WebSocket", "connect", gr.get("resp"), ge, 2)
        b = steps.get("token blanking")
        if b:
            add("Token attribute blanking (UpdateContactAttributes)", "connect", fstart + b["start_ms"], fstart + b["end_ms"], 1)
        tot = fn.get("total_ms")
        if tot is not None:
            add("Function answers; API Gateway and CloudFront to the browser", "internet", fstart + tot, h.get("end"), 1)
    p = st.get("participant_connection") or {}
    add("chatjs CreateParticipantConnection (browser)", "connect", p.get("start"), p.get("end"))
    w = st.get("ws") or {}
    add("chatjs WebSocket open", "connect", w.get("created"), w.get("open"), group="chatjs after the connection")
    add("WebSocket first frame (subscribe acknowledgement)", "connect", w.get("open"), w.get("first_frame"))
    tr = st.get("transcript") or {}
    add("chatjs GetTranscript (browser)", "connect", tr.get("start"), tr.get("end"), group="chatjs after the connection")
    return S


def chat_start_main():
    rows_all = []
    starts = []
    for c in J:
        st = c.get("start") or {}
        S = start_steps(st)
        if not S:
            continue
        fn = st.get("fn") or {}
        starts.append({"contact": c["contact"], "label": c["label"], "cold": fn.get("cold"), "init": fn.get("init"), "cached": fn.get("exchange_cached"), "issuer": fn.get("issuer"), "steps": S})
    (HERE / "start-steps.json").write_text(json.dumps(starts, indent=1, default=str))
    cold = [x for x in starts if x["cold"]]
    starts = [x for x in starts if not x["cold"]]
    names = []
    for s in starts:
        for r in s["steps"]:
            if r["name"] not in names:
                names.append(r["name"])
    rows = []
    for n in names:
        occ = [r for s in starts for r in s["steps"] if r["name"] == n]
        durs = [r["end_ms"] - r["start_ms"] for r in occ]
        rows.append({
            "name": n, "owner": occ[0]["owner"], "start_ms": round(med([r["start_ms"] for r in occ])), "end_ms": round(med([r["end_ms"] for r in occ])),
            "dur_ms": round(med(durs)), "dur_p10_ms": round(pct(durs, .1)), "dur_p90_ms": round(pct(durs, .9)), "dur_min_ms": round(min(durs)), "dur_max_ms": round(max(durs)),
            "p10_ms": round(pct([r["end_ms"] for r in occ], .1)), "p90_ms": round(pct([r["end_ms"] for r in occ], .9)),
            "level": occ[0]["level"], "container": bool(occ[0].get("container")), "parallel_group": occ[0].get("parallel_group"), "n": len(occ)})
    rows.sort(key=lambda r: (r["start_ms"], -r["end_ms"]))
    md = [f"\n### chat start ({len(starts)} page loads on a warm function instance)\n", "| Step | Owner | Start | End | Duration median | p10 to p90 | min to max | n |", "| --- | --- | ---: | ---: | ---: | --- | --- | ---: |"]
    for r in rows:
        md.append(f"| {'&nbsp;&nbsp;' * r['level']}{r['name']} | {r['owner']} | {r['start_ms']} | {r['end_ms']} | {r['dur_ms']} | {r['dur_p10_ms']} to {r['dur_p90_ms']} | {r['dur_min_ms']} to {r['dur_max_ms']} | {r['n']} |")
    (HERE / "tables-start.md").write_text("\n".join(md))
    paths = json.loads((HERE / "paths.json").read_text())
    paths["paths"]["chat-start"] = {"summary": {"page_loads": len(starts), "clock": "ms from the page's navigation start", "note": "warm chat start function instances only; the one cold start is chat-start-cold"}, "steps": rows}
    for c in cold:
        paths["paths"]["chat-start-cold"] = {"summary": {"page_loads": 1, "contact": c["contact"], "clock": "ms from the page's navigation start"}, "steps": [{**r, "start_ms": round(r["start_ms"]), "end_ms": round(r["end_ms"]), "n": 1} for r in c["steps"]]}
    (HERE / "paths.json").write_text(json.dumps(paths, indent=1))


chat_start_main()
