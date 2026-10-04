"""Builds the evidence file behind the latency timelines: every id (contact, request, trace,
span, session, microVM log stream) for each chat start, turn, data request, MCP call and
model call, plus the resources' ARNs. Reads joined.json and raw/. Writes evidence.json and
evidence.md. Leaves out tokens, access key ids, IP addresses and reply text.

    python3 evidence.py
"""
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
RAW = HERE / "raw"
ACCOUNT, REGION = "009080466601", "us-east-1"
TARGETS = {"AGS0JX5M1V": "travel", "WRADAXMX9A": "profile", "WRBXBB12RO": "pay", "KB8LJT6NRY": "docs", "VODAOVCYZX": "hr"}


def utc(ms):
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def r0(v):
    return None if v is None else round(v)


def load(name):
    return json.loads((RAW / f"{name}.json").read_text())


# ---- X-Ray: issuer Lambda request id -> API Gateway request id and trace ----
issuer_xray = {}
by_trace = defaultdict(list)
for _, _, m in load("spans"):
    s = json.loads(m)
    by_trace[s["traceId"]].append(s)
for tid, spans in by_trace.items():
    gw = next((s for s in spans if s["name"] == "POST /token"), None)
    fn = next((s for s in spans if s["name"] == "guppi-gpt-obo-issuer/LambdaService" and s["attributes"].get("aws.request_id")), None)
    if fn:
        issuer_xray[fn["attributes"]["aws.request_id"]] = {
            "xray_trace": "1-" + tid[:8] + "-" + tid[8:],
            "apigw_request_id": gw["attributes"].get("aws.request_id") if gw else None,
            "apigw_extended_request_id": gw["attributes"].get("extended_request_id") if gw else None,
        }

# ---- chat start API Gateway access log ----
apigw_start = [(ts, json.loads(m)) for ts, _, m in load("chat-start-apigw")]
apigw_start = [(ts, d) for ts, d in apigw_start if d.get("resourcePath") == "/api/hr/chat/start"]


issuer_streams = {}
for ts, stream, msg in load("issuer"):
    if msg.startswith("START RequestId"):
        issuer_streams[msg.split()[2]] = stream

# Tools runtime MCP lines by trace id, with their time and microVM stream.
tools_lines = defaultdict(list)
for ts, stream, msg in load("rt-tools"):
    if "runtime-logs" in stream and "trace_id=" in msg:
        tid = msg.split("trace_id=")[1][:32]
        tools_lines[tid].append((ts, stream))


def tools_streams(trace, lo, hi):
    return sorted({s for ts, s in tools_lines.get(trace, []) if lo <= ts <= hi})


def issuer_entry(rid, stream=None, **kw):
    x = issuer_xray.get(rid, {})
    return {"lambda_request_id": rid, "log_stream": stream or issuer_streams.get(rid), **x, **kw}


joined = json.loads((HERE / "joined.json").read_text())
chats = []
for c in joined:
    st = c["start"] or {}
    fn = st.get("fn") or {}
    near = min(apigw_start, key=lambda x: abs(x[0] - fn["start"])) if fn else None
    apigw = near[1]["requestId"] if near and abs(near[0] - fn["start"]) < 500 else None
    greet = st.get("greeting") or {}
    chat = {
        "label": c["label"],
        "mode": c["mode"],
        "contact_id": c["contact"],
        "contact_arn": f"arn:aws:connect:{REGION}:{ACCOUNT}:instance/5665011a-f5fa-40e3-92d0-85ff625d10f6/contact/{c['contact']}",
        "page_navigation_utc": utc(st.get("origin")),
        "chat_start": {
            "apigw_request_id": apigw,
            "lambda_request_id": fn.get("rid"),
            "lambda_log_stream": fn.get("stream"),
            "xray_trace": fn.get("xray"),
            "lambda_start_utc": utc(fn.get("start")),
            "lambda_duration_ms": fn.get("duration"),
            "init_ms": fn.get("init"),
            "cold": fn.get("cold"),
            "browser_ms": r0((st.get("chat_start_http") or {}).get("end", 0) - (st.get("chat_start_http") or {}).get("start", 0)) if st.get("chat_start_http") else None,
            "function_steps": fn.get("steps"),
            "issuer_calls": [issuer_entry(i["rid"], i["stream"], audience=i["audience"], start_utc=utc(i["start"]), handler_ms=i["ms"], cold=i["cold"]) for i in fn.get("issuer_calls", [])],
            "greeting": {"designer_correlation_id": greet.get("cid"), "designer_message_id": greet.get("message_id"), "designer_build_id": greet.get("build"), "designer_received_utc": utc(greet.get("recv")), "designer_responded_utc": utc(greet.get("resp")), "flow": greet.get("flow")},
        },
        "turns": [],
    }
    for t in c["turns"]:
        click = t["click"]
        d = t.get("designer") or {}
        turn = {
            "index": t["i"],
            "question": t["text"],
            "how": t["how"],
            "click_utc": utc(click),
            "first_words_ms": r0(t.get("first")),
            "done_ms": r0(t.get("done")),
            "end_reason": t.get("end_reason"),
            "page_run_id": t.get("run"),
            "report_lambda_request_id": t.get("report_rid"),
            "connect_message_stamped_utc": utc(click + t["connect_sent"]) if t.get("connect_sent") is not None else None,
            "connect_first_reply_utc": utc(click + t["connect_first_item"]) if t.get("connect_first_item") is not None else None,
            "designer": {
                "correlation_id": d.get("cid"),
                "message_id": d.get("message_id"),
                "build_id": d.get("build"),
                "flow": d.get("flow"),
                "received_ms": r0(d.get("recv")),
                "responded_ms": r0(d.get("resp")),
                "routing_model_ms": [[r0(a), r0(b)] for a, b in d.get("models", [])],
                "journey": d.get("journey"),
            },
            "data_requests": [],
        }
        for r in d.get("requests", []):
            gw = r.get("gw") or {}
            dr = {
                "designer_ids": r["ids"],
                "url": r.get("url"),
                "status": r.get("status"),
                "designer_start_ms": r0(r["start"]),
                "designer_end_ms": r0(r["end"]),
                "gateway": "agents" if "-agents-" in (r.get("url") or "") else "tools",
                "gateway_request_id": gw.get("id"),
                "gateway_trace_id": gw.get("trace"),
                "gateway_target_id": gw.get("target"),
                "gateway_target": TARGETS.get(gw.get("target")),
                "gateway_start_ms": r0(gw.get("start")),
                "gateway_end_ms": r0(gw.get("end")),
            }
            if gw.get("issuer_rids"):
                dr["issuer_calls"] = [issuer_entry(x) for x in gw["issuer_rids"]]
            sub = r.get("sub")
            if sub:
                run = sub.get("run") or {}
                dr["first_call_in_chat"] = r.get("first_for_domain")
                dr["sub_agent"] = {
                    "runtime_session_id": sub.get("session"),
                    "dynatrace_trace_id": sub.get("trace"),
                    "root_span_id": sub.get("span"),
                    "service_instance_id": sub.get("instance"),
                    "microvm_log_stream": sub.get("stream_full"),
                    "log_stream_created_utc": utc(sub.get("stream_created")),
                    "process_started_utc": utc(sub.get("process_started")),
                    "request_start_ms": r0(sub["start"]),
                    "request_end_ms": r0(sub["end"]),
                    "runtime_delivery_ms": r0(sub["start"] - gw["exec"]) if gw.get("exec") is not None else None,
                    "run_line": {k: run.get(k) for k in ("duration_ms", "outcome", "tool_calls", "trace_id")} if run else None,
                    "steps": [],
                }
                for s in sub["steps"]:
                    e = {"name": s["name"], "start_ms": r0(s["s"]), "end_ms": r0(s["e"]), "ms": r0(s["e"] - s["s"])}
                    for k in ("span", "aws_request_id", "provider", "model", "ttft", "tokens_in", "tokens_out"):
                        if s.get(k) is not None:
                            e[k] = s[k]
                    if s.get("issuer_rids"):
                        e["issuer_calls"] = [issuer_entry(x) for x in s["issuer_rids"]]
                    g = s.get("gw")
                    if g:
                        e["gateway_request_id"] = g.get("id")
                        e["gateway_trace_id"] = g.get("trace")
                        e["mcp_session_from_client"] = g.get("session")
                        e["policy_ms"] = g.get("policy_ms")
                    inner = s.get("inner")
                    if inner:
                        rt = inner.get("tools_rt") or []
                        e["tools_gateway_start_ms"] = r0(inner.get("gw_start"))
                        e["tools_gateway_exec_ms"] = r0(inner.get("gw_exec"))
                        e["runtime_token_issuer_calls"] = [issuer_entry(x) for x in inner.get("issuer_rids", [])]
                        e["tools_runtime_log_streams"] = [x for x in tools_streams(g.get("trace"), click + rt[0][0] - 50, click + rt[-1][1] + 50)] if rt else []
                        e["tools_runtime_spans"] = [{"span": sp, "start_ms": r0(a), "end_ms": r0(b), "service_instance_id": inst} for sp, (a, b, inst) in zip(inner.get("tools_rt_spans", []), rt)]
                        if rt and inner.get("issuer"):
                            e["delivery_to_tools_runtime_ms"] = r0(rt[0][0] - inner["issuer"][-1][1])
                        if len(rt) == 3:
                            e["handshake_ms"] = r0(rt[2][0] - rt[0][0])
                            e["tool_ms"] = r0(rt[2][1] - rt[2][0])
                    dr["sub_agent"]["steps"].append(e)
            turn["data_requests"].append(dr)
        chat["turns"].append(turn)
    chats.append(chat)

RES = {
    "account": ACCOUNT,
    "region": REGION,
    "window_utc": ["2026-10-04T21:58:00Z", "2026-10-04T22:09:40Z"],
    "resources": [
        ("Amazon Connect instance guppi-connect", f"arn:aws:connect:{REGION}:{ACCOUNT}:instance/5665011a-f5fa-40e3-92d0-85ff625d10f6"),
        ("Contact flow (chat, Agentic CX block)", f"arn:aws:connect:{REGION}:{ACCOUNT}:instance/5665011a-f5fa-40e3-92d0-85ff625d10f6/contact-flow/79627021-74ad-4417-83ab-fa84d8258c63"),
        ("Agentic CX designer build (all turns)", "buildId 7a4c9ca7-9af5-4919-9785-56ff5823d4e8"),
        ("Chat start Lambda hr-chat-start (Rust, arm64, 1024 MB)", f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:hr-chat-start"),
        ("Chat start REST API hr-chat-start, stage prod", f"arn:aws:apigateway:{REGION}::/restapis/ng11tjce58/stages/prod"),
        ("Token issuer Lambda guppi-gpt-obo-issuer (Rust)", f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:guppi-gpt-obo-issuer"),
        ("Token issuer REST API guppi-obo-issuer, stage prod", f"arn:aws:apigateway:{REGION}::/restapis/kdkmszmwge/stages/prod"),
        ("Agents gateway hr-super-agent-agents (HTTP targets profile WRADAXMX9A, travel AGS0JX5M1V, pay WRBXBB12RO)", f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT}:gateway/hr-super-agent-agents-rfkdgz7314"),
        ("Tools gateway hr-super-agent-tools (MCP; targets hr VODAOVCYZX, docs KB8LJT6NRY)", f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT}:gateway/hr-super-agent-tools-7bi54dgr6g"),
        ("Policy engine on the tools gateway (ENFORCE)", f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT}:policy-engine/hr_super_agent_tools_policy-gfigp9no2v"),
        ("Runtime hr_super_agent_profile, endpoint DEFAULT (version 21)", f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT}:runtime/hr_super_agent_profile-7IkHmEG40H/runtime-endpoint/DEFAULT"),
        ("Runtime hr_super_agent_travel, endpoint DEFAULT (version 21)", f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT}:runtime/hr_super_agent_travel-7yhekY3cSf/runtime-endpoint/DEFAULT"),
        ("Runtime hr_super_agent_pay, endpoint DEFAULT (version 21)", f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT}:runtime/hr_super_agent_pay-7zZl2rCGqo/runtime-endpoint/DEFAULT"),
        ("Runtime hr_super_agent_tools (MCP server), endpoint DEFAULT (version 26)", f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT}:runtime/hr_super_agent_tools-Ykb6G5FTK1/runtime-endpoint/DEFAULT"),
        ("Workload identity of the chat start", f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT}:workload-identity-directory/default/workload-identity/hr-chat-start"),
        ("Credential provider for the hop tokens (chat start)", f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT}:token-vault/default/oauth2credentialprovider/guppi-obo-hr-bridge"),
        ("Credential providers for the sub-agents' tools tokens", f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT}:token-vault/default/oauth2credentialprovider/guppi-obo-hr-agent-profile (also -travel, -pay)"),
        ("Credential provider for the tools gateway's runtime token", f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT}:token-vault/default/oauth2credentialprovider/guppi-obo-hr-tools-gateway"),
        ("Sub-agent model (cross-region inference profile)", "us.anthropic.claude-haiku-4-5-20251001-v1:0"),
    ],
    "log_sources": [
        ("Chat start function", "/aws/lambda/hr-chat-start", "chat_start and chat_report JSON lines; START/REPORT with RequestId and XRAY TraceId"),
        ("Chat start API access log", "/aws/apigateway/hr-chat-start", "requestId per request"),
        ("Token issuer function", "/aws/lambda/guppi-gpt-obo-issuer", "one line per exchange: client, audience, route"),
        ("Token issuer API access log", "/aws/apigateway/guppi-obo-issuer", "requestId"),
        ("Agents gateway", "/aws/vendedlogs/bedrock-agentcore/hr-super-agent-agents", "request_id, trace_id, target"),
        ("Tools gateway", "/aws/vendedlogs/bedrock-agentcore/hr-super-agent-tools", "request_id, trace_id, MCP method, tool, policy latency"),
        ("Sub-agent runtimes", "/aws/bedrock-agentcore/runtimes/hr_super_agent_{profile,travel,pay}-*-DEFAULT", "[runtime-logs]<id> stream per microVM on V1; runtime-logs-<session id> stream per session on V2; run lines with duration_ms and trace_id"),
        ("Tools runtime", "/aws/bedrock-agentcore/runtimes/hr_super_agent_tools-Ykb6G5FTK1-DEFAULT", "runtime-logs-<session id> stream per session on V2; trace_id on each MCP line"),
        ("X-Ray spans", "aws/spans", "chat start and issuer Lambda spans, issuer API Gateway spans"),
        ("Dynatrace", "tenant zfr04910, fetch spans where service.name starts with hr_super_agent", "sub-agent and tools runtime spans: trace.id, span.id, session.id, aws.request_id of Identity calls, gen_ai.* model fields"),
        ("Agentic CX designer", "connect/acxd/logs.js <contactId> --json", "per-turn correlationId, messageId, buildId, model and data request events"),
    ],
}
out = {**RES, "chats": chats}
(HERE / "evidence.json").write_text(json.dumps(out, indent=1))
print(len(chats), "chats", sum(len(c["turns"]) for c in chats), "turns")
