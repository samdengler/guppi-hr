"""connect/scripts/turn_timeline.py: parsing the four logs and merging one turn.

The fixtures are lines from 4 Oct 2026: the warm start and the PTO question on contact
1b067d05 (12:22 UTC), trimmed to the fields the script reads.
"""

import dataclasses
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "turn_timeline.py"
spec = importlib.util.spec_from_file_location("turn_timeline", SCRIPT)
tt = importlib.util.module_from_spec(spec)
sys.modules["turn_timeline"] = tt
spec.loader.exec_module(tt)

CONTACT = "1b067d05-7df1-479e-bf48-ede5bbdba357"
WARM_TRACE = "6ac24506eb82077dabf8b1e7b611b449"


def ms(clock: str) -> int:
    return tt.iso_ms(f"2026-10-04T{clock}Z")


def run_line(fields: dict) -> str:
    return (
        "2026-10-04 12:22:41,334 INFO [guppi_agent] [app.py:244] [trace_id=x span_id=y "
        "resource.service.name=guppi_connect_bridge.DEFAULT trace_sampled=True] - "
        + json.dumps(fields)
    )


WARM_RUN = {
    "connect_contact": CONTACT,
    "connect_started": True,
    "messages": 0,
    "outcome": "finished",
    "request_id": "3a6c2d54",
    "run": "aa496b6c-652e-4683-b128-d15efa6e7ecb",
    "started_at": "2026-10-04T12:22:32.064Z",
    "total_ms": 7668,
    "trace_id": WARM_TRACE,
    "warm": True,
}
QUESTION_RUN = {
    "connect_contact": CONTACT,
    "connect_replied": True,
    "first_delta_ms": 4133,
    "messages": 1,
    "outcome": "finished",
    "request_id": "3487c872",
    "run": "858cc1b9-1103-4025-bb9f-3b32ca139f80",
    "started_at": "2026-10-04T12:22:36.384Z",
    "total_ms": 4949,
    "trace_id": "6ac2450b50012d562a1db2674df9d262",
}


def report(request: str, duration: float, trace: str, init: float | None = None) -> str:
    init_part = f"\tInit Duration: {init} ms" if init is not None else ""
    return (
        f"REPORT RequestId: {request}\tDuration: {duration} ms\tBilled Duration: 197 ms\t"
        f"Memory Size: 1024 MB\tMax Memory Used: 31 MB{init_part}\t\n"
        f"XRAY TraceId: {trace}\tSampled: true"
    )


def token(client: str, audience: str, jti: str, subject: str, depth: int, cold: bool) -> str:
    return json.dumps(
        {
            "route": "/token",
            "client": client,
            "status": 200,
            "audience": audience,
            "depth": depth,
            "jti": jti,
            "subject_jti": subject,
            "cold": cold,
        }
    )


ISSUER = [
    # A cold exchange by the bridge: cold_start, START, token, END, REPORT on one stream.
    (ms("12:22:32.856"), "s1", "INIT_START Runtime Version: provided:al2023"),
    (ms("12:22:33.042"), "s1", json.dumps({"event": "cold_start", "load_ms": 155})),
    (ms("12:22:33.046"), "s1", "START RequestId: a0a3 Version: $LATEST"),
    (
        ms("12:22:33.055"),
        "s1",
        token("hr-bridge", "api://hr-agents/pay", "hop-pay", "AT.okta", 1, True),
    ),
    (ms("12:22:33.056"), "s1", "END RequestId: a0a3"),
    (ms("12:22:33.056"), "s1", report("a0a3", 9.44, "1-6ac24508-200fb8774417fc62787193ad", 187.19)),
    (
        ms("12:22:33.088"),
        "s2",
        token("hr-bridge", "api://hr-tools", "hop-canvas", "AT.okta", 1, True),
    ),
    (ms("12:22:33.089"), "s2", report("d9ba", 9.79, "1-6ac24508-64a87a6c6d800a870f6e3334", 216.70)),
    # The pay sub-agent's exchange, then the tools gateway's from it, on a warm instance.
    (
        ms("12:22:35.005"),
        "s3",
        token("hr-agent-pay", "api://hr-tools", "pay-tools", "hop-pay", 2, False),
    ),
    (ms("12:22:35.007"), "s3", report("ea21", 8.73, "1-6ac2450a-45ed8e110827c6f11906bc41")),
    (
        ms("12:22:38.219"),
        "s3",
        token("hr-tools-gateway", "api://hr-tools-runtime", "rt", "pay-tools", 3, False),
    ),
    (ms("12:22:38.221"), "s3", report("e138", 9.68, "1-6ac2450e-48b529ad3f3bc5201da402d8")),
    # A JWKS read: no token line, the warm start's trace.
    (ms("12:22:37.817"), "s3", report("5c2b", 1.04, "1-6ac24506-eb82077dabf8b1e7b611b449")),
]


def designer_event(clock: str, kind: str, correlation: str = "q", flow=None, **props) -> dict:
    return {
        "eventTime": f"2026-10-04T{clock}Z",
        "eventType": kind,
        "flowId": flow,
        "correlationId": correlation,
        "properties": props,
    }


TOOLS_URL = (
    "https://hr-super-agent-tools-7bi54dgr6g.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
)
DESIGNER = [
    designer_event("12:22:35.255", "NluRequestReceived", "g", "NLX.Welcome", type="structured"),
    designer_event("12:22:35.294", "NluResponded", "g", "WelcomeFlow", responseTime=76),
    designer_event(
        "12:22:36.877", "NluRequestReceived", utterance="How much PTO do I earn per year?"
    ),
    designer_event("12:22:36.957", "ModelStart"),
    designer_event("12:22:37.320", "ModelEnd"),
    designer_event("12:22:37.326", "ConditionEvaluated", ""),
    designer_event(
        "12:22:37.368", "DataRequestsRequested", url=TOOLS_URL, dataRequestIds=["PolicySearch"]
    ),
    designer_event(
        "12:22:38.198",
        "DataRequestsReturned",
        responseTime=750,
        statusCode="200",
        dataRequestIds=["PolicySearch"],
    ),
    designer_event("12:22:38.201", "GenerativeJourneyStarted", flow="PolicyFlow", nodeId="j"),
    designer_event("12:22:38.201", "AgentStarted", nodeId="j", mcpToolCount=4),
    designer_event("12:22:40.264", "AgentEnded", nodeId="j"),
    designer_event("12:22:40.306", "NluResponded", flow="PolicyFlow", responseTime=3430),
]


def sub_line(contact: str, domain: str, duration: int, outcome: str, trace: str) -> str:
    fields = {
        "context": contact,
        "domain": domain,
        "duration_ms": duration,
        "outcome": outcome,
        "tool_calls": 0,
        "trace_id": trace,
    }
    return (
        "2026-10-04 12:22:39,697 INFO [hr_agent.agents] [server.py:389] [trace_id=x] - "
        + json.dumps(fields)
    )


@pytest.fixture
def sources():
    runs = tt.parse_runs([(0, "rt", run_line(WARM_RUN)), (0, "rt", run_line(QUESTION_RUN))])
    subs = [
        tt.parse_sub_agent(ms("12:22:39.697"), sub_line(CONTACT, "pay", 4929, "warm", WARM_TRACE))
    ]
    return tt.Sources(
        runs=runs,
        contact_started=ms("12:22:36.237"),
        designer=tt.designer_turns(DESIGNER),
        sub_agents=subs,
        issuer=tt.contact_calls(tt.parse_issuer(ISSUER), runs, subs),
    )


def test_run_line_and_its_otel_copy():
    run = tt.parse_run(run_line(QUESTION_RUN))
    assert (run.start, run.end, run.first_delta_ms) == (
        ms("12:22:36.384"),
        ms("12:22:41.333"),
        4133,
    )
    assert not run.is_warm_start
    otel_copy = json.dumps({"body": run_line(QUESTION_RUN)})
    assert tt.parse_run(otel_copy) is None
    assert tt.parse_run('INFO:     127.0.0.1:36724 - "POST /invocations HTTP/1.1" 200 OK') is None


def test_contact_start_line():
    line = (
        "2026-10-04 12:22:36,237 INFO [connect_bridge] [turn.py:549] [trace_id=x] - "
        + f"started contact {CONTACT}"
    )
    assert tt.parse_contact_starts([(ms("12:22:36.237"), "rt", line)]) == {
        CONTACT: ms("12:22:36.237")
    }


def test_issuer_invocations_are_joined_per_stream():
    calls = tt.parse_issuer(ISSUER)
    cold = calls[0]
    assert cold.token["audience"] == "api://hr-agents/pay"
    assert (cold.init_ms, cold.load_ms) == (187.19, 155)
    assert cold.start == ms("12:22:32.859")  # the REPORT less handler and init
    assert cold.detail() == "issuer cold: init 187 ms, load 155 ms, handler 9 ms"
    jwks = next(c for c in calls if c.token is None)
    assert jwks.trace_id == WARM_TRACE
    assert jwks.label() == "issuer request with no token line (a JWKS read)"


def test_issuer_calls_are_tied_through_the_token_chain(sources):
    branches = {c.token["jti"] if c.token else "jwks": b for c, b in sources.issuer.items()}
    assert branches == {
        "hop-pay": "pay",
        "hop-canvas": "canvas",
        "pay-tools": "pay",
        "rt": "pay",
        "jwks": None,
    }


def test_a_cached_hop_token_is_tied_through_the_sub_agent_run():
    """The bridge keeps hop tokens per Okta token, so a second contact's sub-agent exchanges
    from a hop token minted for the first; its own sub-agent run ties them."""
    other = tt.parse_run(
        run_line({**WARM_RUN, "connect_contact": "c2", "started_at": "2026-10-04T12:22:57.066Z"})
    )
    sub = tt.parse_sub_agent(ms("12:23:04.777"), sub_line("c2", "pay", 5094, "warm", "t2"))
    later = [
        (
            ms("12:22:59.927"),
            "s4",
            token("hr-agent-pay", "api://hr-tools", "pay-2", "hop-pay", 2, False),
        ),
        (ms("12:22:59.929"), "s4", report("6693", 9.06, "1-6ac24523-2b6d2a8f2490f87565589c0b")),
    ]
    tied = tt.contact_calls(tt.parse_issuer(later), [other], [sub])
    assert [(c.token["jti"], b) for c, b in tied.items()] == [("pay-2", "pay")]


def test_designer_events_group_by_correlation():
    turns = tt.designer_turns(DESIGNER)
    assert [t.is_greeting for t in turns] == [True, False]
    assert turns[1].utterance == "How much PTO do I earn per year?"
    steps = tt.designer_steps(turns[1], "hand-off")
    assert [(s.label, s.end - s.start if s.end else None) for s in steps] == [
        ("hand-off", None),
        ("routing model", 363),
        ("data request PolicySearch (tools gateway /mcp)", 830),
        ("journey agent (PolicyFlow)", 2063),
        ("designer NluResponded (PolicyFlow)", None),
    ]


def test_the_pto_turn(sources):
    question = sources.runs[1]
    lines = tt.render_run(question, sources)
    text = "\n".join(lines)
    assert '"How much PTO do I earn per year?"' in text
    assert "+493                    designer NluRequestReceived, the Connect hand-off" in text
    assert "     +984    +1,814     830  data request PolicySearch" in text
    assert "   +4,133                    bridge first delta" in text
    # The warm start was still running: its run and the pay warm-up sit under it, marked.
    assert "  =    -4,320    +3,348   7,668  warm start of the same contact, run aa496b6c" in text
    assert "  =    -1,616    +3,313   4,929    sub-agent pay warm-up" in text
    assert "token exchange hr-tools-gateway for api://hr-tools-runtime" in text
    assert (
        "first delta 4,133 ms: Connect hand-off 493; designer 3,429 (routing model 363,"
        " data requests 830, journey agent 2,063, the rest 173);"
        " Connect to the bridge's first delta 211"
    ) in text


def test_the_warm_start(sources):
    text = "\n".join(tt.render_run(sources.runs[0], sources))
    assert (
        "  *      +795      +992     197  token exchange hr-bridge for api://hr-agents/pay;"
        " issuer cold" in text
    )
    assert (
        "designer greeting (the flow started; the canvas read the tokens); responseTime 76 ms"
        in text
    )
    assert "+4,173                    contact started, the bridge saw the greeting" in text
    assert "no hop token exchange" not in text


def test_a_delegation_holds_its_sub_agent_call():
    agents = (
        "https://hr-super-agent-agents-rfkdgz7314.gateway.bedrock-agentcore.us-east-1.amazonaws.com"
    )
    events = [
        designer_event(
            "11:59:51.130", "NluRequestReceived", utterance="I need to change my home address"
        ),
        designer_event(
            "11:59:51.708",
            "DataRequestsRequested",
            url=f"{agents}/profile/invocations",
            dataRequestIds=["DelegateProfile"],
        ),
        designer_event(
            "11:59:52.969",
            "DataRequestsReturned",
            responseTime=1229,
            statusCode="200",
            dataRequestIds=["DelegateProfile"],
        ),
        designer_event("11:59:52.999", "NluResponded", flow="ProfileFlow", responseTime=1871),
    ]
    run = tt.parse_run(
        run_line(
            {
                **QUESTION_RUN,
                "started_at": "2026-10-04T11:59:50.531Z",
                "first_delta_ms": 2763,
                "total_ms": 2776,
            }
        )
    )
    sub = tt.parse_sub_agent(
        ms("11:59:52.911"), sub_line(CONTACT, "profile", 787, "finished", "6ac23fb7")
    )
    src = tt.Sources([run], None, tt.designer_turns(events), [sub], {})
    steps = tt.turn_steps(run, src.designer[0], src)
    call = next(s for s in steps if s.kind == "sub-agent")
    assert call.parent.label == "data request DelegateProfile (agents gateway /profile/invocations)"
    assert call.parent.detail.endswith("416 ms before the sub-agent, 58 ms after")
    assert "trace 6ac23fb7" in call.detail


def test_parallel_steps_at_one_level_are_marked():
    a, b, c = tt.Step(0, 10, "a"), tt.Step(5, 15, "b"), tt.Step(20, 30, "c")
    child = tt.Step(6, 8, "child", parent=a)
    assert tt.mark_parallel([a, b, c, child]) == {a, b}


def test_when():
    now = ms("12:30:00.000")
    assert tt.parse_when("30m", now) == ms("12:00:00.000")
    assert tt.parse_when("2026-10-04T12:20", now) == ms("12:20:00.000")
    assert tt.merge_windows([(5, 9), (0, 6), (20, 30)]) == [(0, 9), (20, 30)]


def test_the_send_message_mark_from_the_run_line(sources):
    """A run line with connect_sent_ms (D54) times SendMessage and splits the hand-off; one
    from before it still says where the span is."""
    old = tt.turn_steps(sources.runs[1], None, sources)
    assert any(s.untimed and s.label.startswith("SendMessage done: not in these logs") for s in old)
    question = tt.parse_run(run_line({**QUESTION_RUN, "connect_sent_ms": 61}))
    src = dataclasses.replace(sources, runs=[sources.runs[0], question])
    text = "\n".join(tt.render_run(question, src))
    assert "      +61                    SendMessage done\n" in text
    assert "not in these logs" not in text
    assert "first delta 4,133 ms: SendMessage 61; Connect hand-off 432; designer 3,429" in text
