"""Joins the runtimes' InvokeAgentRuntime records into evidence.json and splits each delivery
into the runtime's part (gateway to the runtime's receipt) and the microVM's part (receipt to
our server's first span)."""
import json, statistics as st
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
recs = json.loads((HERE / "raw" / "rt-app.json").read_text())
for r in recs:
    r["recv"] = int(r["received_ns"]) / 1e6
ev = json.loads((HERE / "evidence.json").read_text())
T = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000
used = set()
sub_first, sub_follow, tool_first, tool_next, sess_per_call = [], [], [], [], []
for c in ev["chats"]:
    for t in c["turns"]:
        click = T(t["click_utc"])
        for d in t["data_requests"]:
            sa = d.get("sub_agent")
            if not sa:
                continue
            s_abs = click + sa["request_start_ms"]
            m = min((r for r in recs if r["session_id"] == sa["runtime_session_id"] and r["request_id"] not in used), key=lambda r: abs(r["recv"] - s_abs), default=None)
            if m and abs(m["recv"] - s_abs) < 3000:
                used.add(m["request_id"])
                gw_exec = click + d["gateway_start_ms"] + 0  # replaced below if exec known
                sa["runtime_record"] = {"request_id": m["request_id"], "session_id": m["session_id"], "trace_id": m["trace_id"], "span_id": m["span_id"], "runtime_received_utc": datetime.utcfromtimestamp(m["recv"] / 1000).isoformat(timespec="milliseconds") + "Z",
                                        "runtime_to_container_ms": round(s_abs - m["recv"])}
                if sa.get("runtime_delivery_ms") is not None:
                    exec_abs = s_abs - sa["runtime_delivery_ms"]
                    sa["runtime_record"]["gateway_to_runtime_ms"] = round(m["recv"] - exec_abs)
                    (sub_first if d["first_call_in_chat"] else sub_follow).append((round(m["recv"] - exec_abs), round(s_abs - m["recv"])))
            for s in sa["steps"]:
                rt = s.get("tools_runtime_spans")
                if not s["name"].startswith("MCP tools/call hr___") or not rt:
                    continue
                calls = []
                for i, sp in enumerate(rt):
                    a = click + sp["start_ms"]
                    m = min((r for r in recs if r["runtime"] == "hr_super_agent_tools" and r["request_id"] not in used and r["trace_id"] == s.get("gateway_trace_id")), key=lambda r: abs(r["recv"] - a), default=None)
                    if m and abs(m["recv"] - a) < 2000:
                        used.add(m["request_id"])
                        calls.append({"request_id": m["request_id"], "session_id": m["session_id"], "span_id": m["span_id"], "runtime_received_utc": datetime.utcfromtimestamp(m["recv"] / 1000).isoformat(timespec="milliseconds") + "Z", "runtime_to_container_ms": round(a - m["recv"])})
                s["tools_runtime_records"] = calls
                if calls:
                    sess_per_call.append(len({x["session_id"] for x in calls}))
                    iss_end = None
                    if s.get("delivery_to_tools_runtime_ms") is not None:
                        iss_end = click + rt[0]["start_ms"] - s["delivery_to_tools_runtime_ms"]
                        first_recv = T(calls[0]["runtime_received_utc"])
                        s["issuer_to_runtime_ms"] = round(first_recv - iss_end)
                        tool_first.append((round(first_recv - iss_end), calls[0]["runtime_to_container_ms"]))
                    for x in calls[1:]:
                        tool_next.append(x["runtime_to_container_ms"])
sessions = [x["session_id"] for c in ev["chats"] for t in c["turns"] for d in t["data_requests"] if d.get("sub_agent") for s in d["sub_agent"]["steps"] for x in s.get("tools_runtime_records", [])]
print("matched", len(used), "of", len(recs))
print("tool calls", len(sess_per_call), "sessions per call", set(sess_per_call), "distinct tool sessions", len(set(sessions)))
md = lambda xs: (st.median(xs), min(xs), max(xs)) if xs else None
print("sub first: gateway->runtime", md([a for a, b in sub_first]), "runtime->container", md([b for a, b in sub_first]))
print("sub follow: gateway->runtime", md([a for a, b in sub_follow]), "runtime->container", md([b for a, b in sub_follow]))
print("tool first req: issuer->runtime", md([a for a, b in tool_first]), "runtime->container", md([b for a, b in tool_first]))
print("tool req 2,3: runtime->container", md(tool_next))
(HERE / "evidence.json").write_text(json.dumps(ev, indent=1))
