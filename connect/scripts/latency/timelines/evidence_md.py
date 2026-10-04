"""Writes evidence.md from evidence.json: the ids behind every number in the latency
timelines report, grouped by the question each table answers.

    python3 evidence_md.py
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
E = json.loads((HERE / "evidence.json").read_text())
L = []


def p(*lines):
    L.extend(lines)


def table(head, rows):
    p("| " + " | ".join(head) + " |", "| " + " | ".join("---" for _ in head) + " |")
    for r in rows:
        p("| " + " | ".join("" if v is None else str(v).replace("|", "/") for v in r) + " |")
    p("")


def code(v):
    return f"`{v}`" if v else ""


def stream_id(s):
    return s.split("]")[-1] if s else None


def hms(u):
    return u[11:23] if u else None


def at(click_utc, ms):
    """UTC time of an offset from the click."""
    from datetime import datetime, timedelta

    if click_utc is None or ms is None:
        return None
    t = datetime.fromisoformat(click_utc.replace("Z", "+00:00")) + timedelta(milliseconds=ms)
    return t.strftime("%H:%M:%S.%f")[:-3]


chats = E["chats"]
turns = [(c, t) for c in chats for t in c["turns"]]
subs = [(c, t, d) for c, t in turns for d in t["data_requests"] if d.get("sub_agent")]

import statistics as _st
from datetime import datetime as _dt
_T = lambda x: _dt.fromisoformat(x.replace("Z", "+00:00")).timestamp() * 1000
N_CHATS, N_TURNS = len(chats), len(turns)
BUILDS = sorted({t["designer"].get("build_id") for c, t in turns if t["designer"].get("build_id")})
_tool_steps = [s for c, t, d in subs for s in d["sub_agent"]["steps"] if s["name"].startswith("MCP tools/call hr___")]
N_TOOL = len(_tool_steps)
N_TOOL_SESS = len({x["session_id"] for s in _tool_steps for x in s.get("tools_runtime_records", [])} or {tuple(s.get("tools_runtime_log_streams") or []) for s in _tool_steps})
N_SUB = len(subs)
N_SUB_SESS = len({d["sub_agent"]["runtime_session_id"] for c, t, d in subs})
N_Q = sum(1 for c, t in turns if t.get("connect_question"))
N_GREET = sum(1 for c in chats if c["chat_start"]["greeting"].get("connect_message"))
N_REPLY = sum(len(t.get("connect_replies") or []) for c, t in turns)
_g = [_T(c["chat_start"]["greeting"]["connect_message"]["connect_time"]) - _T(c["chat_start"]["greeting"]["designer_responded_utc"]) for c in chats if c["chat_start"]["greeting"].get("connect_message") and c["chat_start"]["greeting"].get("designer_responded_utc")]
_r = [_T(t["connect_replies"][0]["connect_time"]) - (_T(t["click_utc"]) + t["designer"]["responded_ms"]) for c, t in turns if t.get("connect_replies") and t["designer"].get("responded_ms") is not None]
_fmt = lambda xs: f"{round(_st.median(xs))} ms (median, {round(min(xs))} to {round(max(xs))} ms)" if xs else "n/a"
N_INGRESS = sum(1 for c, t, d in subs if d["sub_agent"].get("runtime_ingress_identity")) + sum(1 for s in _tool_steps for y in (s.get("tools_runtime_ingress_identity") or []) if y)

p(
    "# Evidence for the AgentCore Runtime V2 with priming latency run of 4 October 2026",
    "",
    "The ids behind every number in `latency-timelines-2026-10-04.md`: Connect contacts, the designer's",
    "correlation ids, API Gateway and Lambda request ids, X-Ray and Dynatrace trace and span ids,",
    "AgentCore Gateway request ids, runtime session ids, the log stream of each microVM, and the",
    "request ids of the AgentCore Identity calls. The same data, with every step of every turn, is",
    "in `latency-timelines-2026-10-04-evidence.json`.",
    "",
    f"Account `{E['account']}`, region `{E['region']}`. Window {E['window_utc'][0]} to {E['window_utc'][1]}: {N_CHATS} chats,",
    f"{N_TURNS} turns, no deploys inside the window; designer build(s) {', '.join('`' + b + '`' for b in BUILDS)}.",
    "All times are UTC on 4 October 2026.",
    "Offsets in ms are from the click that sent the question, or from the page's navigation for a",
    "chat start. Tokens, access key ids, IP addresses and reply text are left out.",
    "",
    "## Joining the sources",
    "",
    "- The Connect contact id ties the browser, the chat start function, the designer's log and the",
    "  sub-agents: the designer calls a sub-agent with runtime session id `{contactId}-{domain}`.",
    "- The agents gateway's `trace_id` is its own; the sub-agent's spans start a new trace (the",
    "  Dynatrace trace id below). The tools gateway logs the sub-agent's trace id, and the tools",
    "  runtime logs the same `trace_id` on its MCP lines, so a tool call is joined to its microVM by",
    "  trace id and time. A follow-up's MCP spans carry the first request's trace id (the MCP",
    "  client's thread keeps its first context), so time decides between them.",
    "- A runtime's microVM is its `[runtime-logs]<id>` log stream: one stream per microVM, created",
    "  when the microVM boots.",
    "- Identity's on-behalf-of exchanges call the token issuer through API Gateway; X-Ray links each",
    "  issuer Lambda request id to the API Gateway request id and extended request id.",
    "- The chat start's API Gateway request is matched to its Lambda invocation by time (the access",
    "  log carries no Lambda request id; starts were seconds apart).",
    "",
    "## Resources",
    "",
)
table(["Resource", "ARN or id"], [(n, code(a)) for n, a in E["resources"]])
p("## Log sources", "")
table(["Source", "Where", "Ids it carries"], [(a, code(b), c) for a, b, c in E["log_sources"]])

# ---- A23: tool calls ----
p(
    "## Tool calls through the tools gateway (A23, time sink 1)",
    "",
    f"Every snapshot read by a sub-agent: {N_TOOL} calls on {N_TOOL_SESS} different tools runtime sessions. Delivery is",
    "from the issuer's answer (the gateway's runtime token) to the tools server's first span;",
    "handshake from that first span to the `tools/call` span; total is the sub-agent's MCP span.",
    "",
)
rows = []
for c, t, d in subs:
    for s in d["sub_agent"]["steps"]:
        if s["name"].startswith("MCP tools/call hr___"):
            rows.append((
                at(t["click_utc"], s["start_ms"]), code(c["contact_id"]), s["name"].split()[-1],
                code(s.get("gateway_request_id")), code(s.get("gateway_trace_id")),
                code(stream_id((s.get("tools_runtime_log_streams") or [None])[0])),
                s.get("policy_ms"), s.get("delivery_to_tools_runtime_ms"), s.get("handshake_ms"), s.get("tool_ms"), s["ms"],
            ))
rows.sort()
table(["Time", "Contact", "Tool", "Tools gateway request id", "Trace id", "Tools runtime microVM (log stream)", "Policy ms", "Delivery ms", "Handshake ms", "Tool ms", "Total ms"], rows)
p("The runtime token exchange for each call (Identity to the issuer):", "")
rows = []
for c, t, d in subs:
    for s in d["sub_agent"]["steps"]:
        if s["name"].startswith("MCP tools/call hr___"):
            for i in s.get("runtime_token_issuer_calls") or []:
                rows.append((at(t["click_utc"], s["start_ms"]), code(s.get("gateway_request_id")), code(i.get("apigw_request_id")), code(i["lambda_request_id"]), code(i.get("xray_trace"))))
rows.sort()
table(["Time", "Tools gateway request id", "Issuer API Gateway request id", "Issuer Lambda request id", "X-Ray trace"], rows)

# ---- runtime sessions ----
p(
    "## Sub-agent runtime sessions and microVMs (A21, time sink 2)",
    "",
    f"Every sub-agent request: {N_SUB} requests on {N_SUB_SESS} sessions, each session on its own instance. Delivery",
    "is from the agents gateway's \"Executing Http request for target\" to the sub-agent's `POST /` span.",
    "",
)
rows = []
for c, t, d in subs:
    sa = d["sub_agent"]
    rows.append((
        at(t["click_utc"], sa["request_start_ms"]), "first" if d["first_call_in_chat"] else "follow-up",
        code(sa["runtime_session_id"]), code(d["gateway_request_id"]), code(d["gateway_trace_id"]),
        code(sa["dynatrace_trace_id"]), code(sa["root_span_id"]), code(stream_id(sa["microvm_log_stream"])),
        hms(sa["process_started_utc"]), sa["runtime_delivery_ms"], sa["request_end_ms"] - sa["request_start_ms"],
    ))
rows.sort()
table(["Request time", "Call", "Runtime session id", "Agents gateway request id", "Gateway trace id", "Sub-agent trace id (Dynatrace)", "Root span id", "MicroVM (log stream)", "Process started", "Delivery ms", "Request ms"], rows)

reuse = [c for c in chats if c["mode"] == "reuse"]
if reuse:
    p("### The reuse pairs", "", "Pairs of chats 66 s apart, same question, same employee. Each chat got its own session and microVM.", "")
    rows = []
    for c in reuse:
        for t in c["turns"]:
            for d in t["data_requests"]:
                if d.get("sub_agent"):
                    sa = d["sub_agent"]
                    rows.append((t["click_utc"][11:23], code(c["contact_id"]), c["label"], code(stream_id(sa["microvm_log_stream"])), sa["runtime_delivery_ms"], sa["request_end_ms"] - sa["request_start_ms"]))
    rows.sort()
    table(["Click", "Contact", "Chat", "MicroVM (log stream)", "Delivery ms", "Sub-agent request ms"], rows)

# ---- Identity in the sub-agents ----
p(
    "## AgentCore Identity calls in the sub-agents (time sink 4)",
    "",
    "The first request on each session: the workload access token, then the on-behalf-of exchange",
    "for the tools token. Request ids are AgentCore Identity's `aws.request_id` from the botocore spans.",
    "",
)
rows = []
for c, t, d in subs:
    sa = d["sub_agent"]
    w = next((s for s in sa["steps"] if s["name"].startswith("workload access token")), None)
    o = next((s for s in sa["steps"] if s["name"].startswith("on-behalf-of")), None)
    if not w and not o:
        continue
    iss = (o or {}).get("issuer_calls") or [{}]
    rows.append((
        at(t["click_utc"], (w or o)["start_ms"]), code(sa["runtime_session_id"]),
        code((w or {}).get("aws_request_id")), (w or {}).get("ms"),
        code((o or {}).get("aws_request_id")), (o or {}).get("provider"), (o or {}).get("ms"),
        code(iss[0].get("apigw_request_id")), code(iss[0].get("lambda_request_id")),
    ))
rows.sort()
table(["Time", "Runtime session id", "GetWorkloadAccessTokenForJWT request id", "ms", "GetResourceOauth2Token request id", "Credential provider", "ms", "Issuer API Gateway request id", "Issuer Lambda request id"], rows)

# ---- MCP setup ----
p("## MCP setup calls through the tools gateway (time sink 4)", "", "The `initialize`, `notifications/initialized` and `tools/list` of each new session.", "")
rows = []
for c, t, d in subs:
    for s in d["sub_agent"]["steps"]:
        if s["name"] in ("MCP initialize", "MCP notifications/initialized", "MCP tools/list"):
            rows.append((at(t["click_utc"], s["start_ms"]), code(d["sub_agent"]["runtime_session_id"]), s["name"][4:], code(s.get("gateway_request_id")), code(s.get("span")), s["ms"]))
rows.sort()
table(["Time", "Runtime session id", "Method", "Tools gateway request id", "Sub-agent span id", "ms"], rows)

# ---- model calls ----
p("## Sub-agent model calls (time sink 3)", "", "One Bedrock `ConverseStream` per sub-agent request, from the Strands `chat` spans.", "")
rows = []
for c, t, d in subs:
    for s in d["sub_agent"]["steps"]:
        if s["name"].startswith("model call"):
            rows.append((at(t["click_utc"], s["start_ms"]), code(d["sub_agent"]["runtime_session_id"]), code(d["sub_agent"]["dynatrace_trace_id"]), code(s.get("span")), s.get("model"), s.get("tokens_in"), s.get("tokens_out"), r if (r := s.get("ttft")) is None else round(r), s["ms"]))
rows.sort()
table(["Time", "Runtime session id", "Trace id", "Span id", "Model", "Input tokens", "Output tokens", "Time to first token ms", "Call ms"], rows)

# ---- designer turns ----
p(
    "## Turns in the designer (routing, time sinks 3, 5, 6)",
    "",
    "Each question as Connect and the designer saw it. Routing is the designer's `ModelStart` to",
    "`ModelEnd`; \"Connect in\" is the click to the designer's `NluRequestReceived`.",
    "",
)
rows = []
for c, t in turns:
    d = t["designer"]
    rm = d["routing_model_ms"]
    rows.append((
        t["click_utc"][11:23], code(c["contact_id"]), t["question"], d["flow"], code(d["correlation_id"]), code(d["message_id"]),
        code(t["page_run_id"]), d["received_ms"], (rm[0][1] - rm[0][0]) if rm else None, t["first_words_ms"],
    ))
rows.sort()
table(["Click", "Contact", "Question", "Flow", "Designer correlation id", "Designer message id", "Page run id", "Connect in ms", "Routing ms", "First words ms"], rows)

p("### Data requests from the designer", "", "Every data request with its gateway request. PolicySearch and Travel's search go to the knowledge base target through the tools gateway.", "")
rows = []
for c, t in turns:
    for d in t["data_requests"]:
        rows.append((at(t["click_utc"], d["designer_start_ms"]), code(c["contact_id"]), ", ".join(d["designer_ids"]), d["gateway"], d.get("gateway_target") or d.get("gateway_target_id"), code(d["gateway_request_id"]), code(d["gateway_trace_id"]), d["designer_end_ms"] - d["designer_start_ms"]))
for c, t, d in subs:
    for s in d["sub_agent"]["steps"]:
        if s["name"] == "MCP tools/call docs___Retrieve":
            rows.append((at(t["click_utc"], s["start_ms"]), code(c["contact_id"]), "travel sub-agent search", "tools", "docs", code(s.get("gateway_request_id")), code(s.get("gateway_trace_id")), s["ms"]))
rows.sort()
table(["Time", "Contact", "Request", "Gateway", "Target", "Gateway request id", "Trace id", "ms"], rows)

# ---- chat starts ----
p(
    "## Chat starts (time sink 9, question 6)",
    "",
    "One per page load. The greeting columns are the designer's WelcomeFlow; the function's own steps",
    "and the four hop token exchanges of each start are in the JSON file.",
    "",
)
rows = []
for c in chats:
    s = c["chat_start"]
    g = s["greeting"]
    rows.append((
        (c["page_navigation_utc"] or "")[11:23], code(c["contact_id"]), code(s["apigw_request_id"]), code(s["lambda_request_id"]), code(s["xray_trace"]),
        code(stream_id(s["lambda_log_stream"])), "cold" if s["init_ms"] else "warm", round(s["lambda_duration_ms"]) if s["lambda_duration_ms"] else None, s["browser_ms"],
        code(g["designer_correlation_id"]), (g["designer_responded_utc"] or "")[11:23],
    ))
rows.sort()
table(["Navigation", "Contact", "API Gateway request id", "Lambda request id", "X-Ray trace", "Lambda log stream", "Instance", "Function ms", "Browser ms", "Greeting correlation id", "Designer greeted"], rows)

p("### Hop token exchanges at chat start", "", "The four on-behalf-of exchanges of each start, at the issuer (credential provider `guppi-obo-hr-bridge`).", "")
rows = []
for c in chats:
    for i in c["chat_start"]["issuer_calls"]:
        rows.append(((i.get("start_utc") or "")[11:23], code(c["contact_id"][:8]), i["audience"], code(i.get("apigw_request_id")), code(i["lambda_request_id"]), code(i.get("xray_trace")), i["handler_ms"], "cold" if i["cold"] else ""))
rows.sort()
table(["Time", "Contact", "Audience", "Issuer API Gateway request id", "Issuer Lambda request id", "X-Ray trace", "Handler ms", "Instance"], rows)


# ---- CloudTrail ----
def rid(x):
    return code(x["request_id"]) if x else ""


p(
    "## Connect calls from CloudTrail",
    "",
    "CloudTrail records every Connect and participant call of a chat with its request id; the",
    "participant calls carry the contact in `resources`, and `SendMessage` returns the message id",
    "and Connect's own time to the millisecond. The browser's `SendMessage` time matched the page's",
    f"record for the {N_Q} questions. The designer's messages go through the same",
    f"`SendMessage` from an internal AWS client: {N_GREET} greetings and {N_REPLY} replies, which with the {N_Q}",
    f"questions are {N_GREET + N_REPLY + N_Q} billed messages.",
    "",
    "### Per chat",
    "",
)
rows = []
for c in chats:
    k = c["chat_start"].get("cloudtrail") or {}
    g = c["chat_start"]["greeting"].get("connect_message")
    rows.append(((c["page_navigation_utc"] or "")[11:23], code(c["contact_id"]), rid(k.get("StartChatContact")), rid(k.get("CreateParticipantConnection (function)")),
                 rid(k.get("CreateParticipantConnection (designer)")), code((k.get("CreateParticipantConnection (designer)") or {}).get("participant_id")),
                 rid(k.get("UpdateContactAttributes")), rid(k.get("CreateParticipantConnection (browser)")), rid(k.get("GetTranscript (browser)")),
                 code(g and g.get("message_id")), (g or {}).get("connect_time", "")[11:23]))
rows.sort()
table(["Navigation", "Contact", "StartChatContact", "CreateParticipantConnection (function)", "CreateParticipantConnection (designer)", "Designer participant id", "UpdateContactAttributes", "CreateParticipantConnection (browser)", "GetTranscript (browser)", "Greeting message id", "Greeting stamped"], rows)
p(f"Connect stamps the greeting {_fmt(_g)} after the designer's `NluResponded`,",
  f"against {_fmt(_r)} for a reply; the greeting's extra time (report question 6) is",
  "spent before Connect posts the first message of a contact, not on the way to the function's socket.", "")
p("### Per turn", "")
rows = []
for c, t in turns:
    q = t.get("connect_question")
    rs = t.get("connect_replies") or []
    rows.append((t["click_utc"][11:23], code(c["contact_id"][:8]), t["question"], rid(q), code(q and q.get("message_id")), (q or {}).get("connect_time", "")[11:23],
                 " ".join(code(r["message_id"]) for r in rs), " ".join(code(r["request_id"]) for r in rs), " ".join(r["connect_time"][11:23] for r in rs)))
rows.sort()
table(["Click", "Contact", "Question", "SendMessage request id", "Question message id", "Connect stamp", "Reply message ids", "Reply SendMessage request ids", "Reply stamps"], rows)

p(
    "## AgentCore Identity calls from CloudTrail",
    "",
    "Three callers that no span shows. The runtime itself calls `GetWorkloadAccessTokenForJWT`",
    "(as `AWSServiceRoleForBedrockAgentCoreRuntimeIdentity`, session `CustomerSlrValidation`) once",
    f"for every request it delivers ({N_INGRESS} matched here; on 4 Oct V1 it was 100 for 100 requests: 37 to the sub-agents, 63 to the",
    "tools runtime, three per tool call). The tools gateway takes a new role session",
    "(`gateway-session-<id>`) for every tool call and calls Identity twice in it. CloudTrail times",
    "are to the second, so these rows are matched by caller and second.",
    "",
    "### Runtime ingress",
    "",
)
rows = []
for c, t, d in subs:
    sa = d["sub_agent"]
    x = sa.get("runtime_ingress_identity")
    rows.append((at(t["click_utc"], sa["request_start_ms"]), code(sa["runtime_session_id"]), "sub-agent request", rid(x), (x or {}).get("event_time", "")[11:19]))
    for s in sa["steps"]:
        for i, y in enumerate(s.get("tools_runtime_ingress_identity") or []):
            rows.append((at(t["click_utc"], s["start_ms"]), code(sa["runtime_session_id"]), f"tools runtime request {i + 1} of 3 ({s['name'].split()[-1]})", rid(y), (y or {}).get("event_time", "")[11:19]))
rows.sort()
table(["Time", "Calling session", "Request delivered", "GetWorkloadAccessTokenForJWT request id", "CloudTrail second"], rows)
p("### Tools gateway, per tool call", "")
rows = []
for c, t, d in subs:
    for s in d["sub_agent"]["steps"]:
        if s.get("tools_gateway_identity"):
            a, b = s["tools_gateway_identity"]
            rows.append((at(t["click_utc"], s["start_ms"]), code(s.get("gateway_request_id")), code(s.get("tools_gateway_principal_session")), rid(a), rid(b)))
rows.sort()
table(["Time", "Tools gateway request id", "Gateway role session", "GetWorkloadAccessTokenForJWT request id", "GetResourceOauth2Token request id"], rows)
p("### Chat start", "")
rows = []
for c in chats:
    xs = c["chat_start"].get("cloudtrail_identity") or []
    rows.append(((c["page_navigation_utc"] or "")[11:23], code(c["contact_id"]), rid(xs[0] if xs else None), " ".join(rid(x) for x in xs[1:] if x)))
rows.sort()
table(["Navigation", "Contact", "GetWorkloadAccessTokenForJWT request id", "GetResourceOauth2Token request ids (four hop tokens)"], rows)

p(
    "## Ids still missing",
    "",
    "| Gap | Why | Fix | Whose |",
    "| --- | --- | --- | --- |",
    "| Which runtime session id the tools gateway used for each call, and the runtime's request id | Neither the gateway's log nor the runtime's logs name them; the runtime's own `InvokeAgentRuntime` spans and application logs (request id, session id, `latency_ms`) are not turned on for our runtimes | Turn on the runtimes' observability; log the session and request headers in the tools server and the sub-agents | ours (config, code) |",
    "| The parent of the sub-agent's root span, and the agents gateway's trace inside the runtime | The agents gateway's trace does not continue into the runtime (TC10); the parent span is in no backend we can read (TC9) | Ask AWS | AWS |",
    "| Identity's own timing for the runtime's per-request token call | Only CloudTrail records it, to the second; no span or vended log | Ask AWS for spans or vended logs | AWS |",
    "| The trace of each token exchange back to its caller | Identity starts a new trace at the token endpoint (TC10) | Ask AWS; meanwhile the issuer can log Identity's request headers | AWS (ours for a workaround) |",
    "| 4 of 116 hop exchanges have no issuer API Gateway request id | X-Ray sampled them out | The issuer logs its API Gateway request id | ours (code) |",
    "| The chat start's Lambda request id in the API's access log | The access log format leaves out `$context.integration.requestId` and `$context.xrayTraceId`; the stage has no X-Ray | Add both fields and turn on X-Ray for the stage | ours (config) |",
    "| Request ids of the Connect calls in the chat start's own log | The function does not log them (CloudTrail has them, above) | Log the SDK's request id per call | ours (code) |",
    "| Bedrock request id of each sub-agent model call | No botocore span for Bedrock Runtime; the Strands `chat` span has none | Log `ResponseMetadata.RequestId` from a botocore event hook | ours (code) |",
    "| The designer's routing model call and its data requests | The designer emits no trace and no request ids for its model calls (A19); its log gives a correlation id per turn | Ask AWS | AWS |",
    "| Connect's time from a stamped question to the designer, and from the designer's response to the stamp | No Connect span or log between `SendMessage` and the designer | Ask AWS (C15) | AWS |",
    "",
)
p(
    "## Queries to reproduce",
    "",
    "CloudWatch Logs Insights, the tools gateway's requests for one trace:",
    "",
    "```",
    "fields @timestamp, request_id, body.log, body.requestBody",
    "| filter trace_id = '6ac2b5126beb7ad13c8c647f2041850a'",
    "| sort @timestamp asc",
    "```",
    "",
    "on `/aws/vendedlogs/bedrock-agentcore/hr-super-agent-tools`. The same trace id in",
    "`/aws/bedrock-agentcore/runtimes/hr_super_agent_tools-Ykb6G5FTK1-DEFAULT` shows the tools runtime",
    "microVM (log stream) that served the call:",
    "",
    "```",
    "fields @timestamp, @logStream, @message",
    "| filter @message like '6ac2b5126beb7ad13c8c647f2041850a' and @logStream like 'runtime-logs'",
    "| sort @timestamp asc",
    "```",
    "",
    "Dynatrace (tenant `zfr04910`), every span of one sub-agent session:",
    "",
    "```",
    f'fetch spans, from: "{E["window_utc"][0]}", to: "{E["window_utc"][1]}"',
    '| filter session.id == "48e7b0a1-5754-40ef-93a1-4998ae7f8fdd-profile"',
    "| fields start_time, end_time, span.name, trace.id, span.id, service.instance.id, aws.request_id",
    "| sort start_time asc",
    "```",
    "",
    "The designer's events for one contact: `node connect/acxd/logs.js <contactId> 3600000 --json`",
    "in guppi-hr.",
    "",
)
text = "\n".join(L)
assert "—" not in text and "–" not in text
(HERE / "evidence.md").write_text(text)
print(len(text), "chars", text.count("\n"), "lines")
