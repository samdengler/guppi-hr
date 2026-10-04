import sys
d=sys.argv[1]; label=sys.argv[2]
p=f'{d}/evidence_md.py'; s=open(p).read()
calc='''
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
'''
i=s.index('\nsubs = '); j=s.index('\n', i+1)
s=s[:j+1]+calc+s[j+1:]
R=[
('# Evidence for the V2 latency run of 4 October 2026 (AgentCore Runtime V2, no priming)', f'# Evidence for the {label} latency run of 4 October 2026'),
('# Evidence for the latency timelines of 4 October 2026', f'# Evidence for the {label} latency run of 4 October 2026'),
('''    f"Account `{E['account']}`, region `{E['region']}`. Window {E['window_utc'][0]} to {E['window_utc'][1]}: 29 chats,",
    "52 turns, no deploys (stack update times were the same before and after; every designer event",
    "carried build `7a4c9ca7-9af5-4919-9785-56ff5823d4e8`). All times are UTC on 4 October 2026.",''',
 '''    f"Account `{E['account']}`, region `{E['region']}`. Window {E['window_utc'][0]} to {E['window_utc'][1]}: {N_CHATS} chats,",
    f"{N_TURNS} turns, no deploys inside the window; designer build(s) {', '.join('`' + b + '`' for b in BUILDS)}.",
    "All times are UTC on 4 October 2026.",'''),
('''    "  an instance restored from the version's snapshot, so the stream names the session, not a pooled",
    "  when the microVM boots.",''','''    "  an instance restored from the version's snapshot, so the stream names the session.",'''),
('"  log carries no Lambda request id; they were 13 to 25 ms apart, starts were seconds apart).",','"  log carries no Lambda request id; starts were seconds apart).",'),
('    "Every snapshot read by a sub-agent: 21 calls, 21 different tools runtime microVMs. Delivery is",','    f"Every snapshot read by a sub-agent: {N_TOOL} calls on {N_TOOL_SESS} different tools runtime sessions. Delivery is",'),
('    "Every sub-agent request: 37 requests on 24 sessions, each session on its own microVM. Delivery",','    f"Every sub-agent request: {N_SUB} requests on {N_SUB_SESS} sessions, each session on its own instance. Delivery",'),
('''    "record for all 52 questions (within 2 ms). The designer's messages go through the same",
    "`SendMessage` from an internal AWS client: 29 greetings and 52 replies, which with the 52",
    "questions are the 133 billed messages.",''','''    f"record for the {N_Q} questions. The designer's messages go through the same",
    f"`SendMessage` from an internal AWS client: {N_GREET} greetings and {N_REPLY} replies, which with the {N_Q}",
    f"questions are {N_GREET + N_REPLY + N_Q} billed messages.",'''),
('''p("Connect stamps the greeting 335 ms (median, 284 to 761 ms) after the designer's `NluResponded`,",
  "against 117 ms (87 to 217 ms) for a reply, so the greeting's extra time (report question 6) is",''','''p(f"Connect stamps the greeting {_fmt(_g)} after the designer's `NluResponded`,",
  f"against {_fmt(_r)} for a reply; the greeting's extra time (report question 6) is",'''),
('    "for every request it delivers: 100 calls for 100 requests (37 to the sub-agents, 63 to the",','    f"for every request it delivers ({N_INGRESS} matched here; on 4 Oct V1 it was 100 for 100 requests: 37 to the sub-agents, 63 to the",'),
('''    'fetch spans, from: "2026-10-04T20:16:00Z", to: "2026-10-04T20:35:00Z"',''','''    f'fetch spans, from: "{E["window_utc"][0]}", to: "{E["window_utc"][1]}"','''),
]
for a,b in R:
    if a in s: s=s.replace(a,b)
open(p,'w').write(s)
print('ok')
