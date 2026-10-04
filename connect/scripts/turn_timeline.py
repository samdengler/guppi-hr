# /// script
# requires-python = ">=3.12"
# dependencies = ["boto3>=1.35"]
# ///
"""One merged latency timeline per chat turn on /p/hr/, the Connect project.

A slow answer on /p/hr/ crosses four logs with no shared trace: the bridge's run lines,
the Agentic CX designer's runtime log (reachable only through its own QueryLogs API, keyed
by the Connect contact id), the token issuer's Lambda log, and the sub-agents' run lines.
This script reads all four for a time window and prints, for each bridge run, the steps on
one clock in milliseconds from the moment the bridge received the run:

- a question: the Connect hand-off (the designer's NluRequestReceived), the routing model,
  each data request, the journey agent, sub-agent calls, the designer's NluResponded and the
  bridge's first delta, then a split of the first delta into those parts;
- a warm start: the hop token exchanges (issuer cold or warm), the designer's greeting, the
  contact start and each sub-agent's warm-up with its own exchanges.

Work of the same contact from another run (the warm start still running under a question)
is listed after the run's own steps. Steps at one level that run at the same time are
marked. The time SendMessage finished comes from the run line's `connect_sent_ms` (D54); a
run line from before it has none, and its SendMessage span is in the bridge's trace, whose
id is printed so the trace can be opened in Dynatrace.

    uv run connect/scripts/turn_timeline.py --since 30m
    uv run connect/scripts/turn_timeline.py --contact 1b067d05-7df1-479e-bf48-ede5bbdba357
    uv run connect/scripts/turn_timeline.py --since 2026-10-04T12:20 --until 2026-10-04T12:25

The designer's log comes from `node logs.js <contactId> <spanMs> --json`, run in
connect/acxd with the ACXD key from ~/.config/guppi-connect (the key never reaches this
process). The designer's log arrives some time after a turn and is kept for a limited
time; a turn outside that prints without the designer's steps. AWS access is the default
profile in us-east-1.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
ACXD = ROOT / "acxd"
REGION = "us-east-1"
BRIDGE_PREFIX = "/aws/bedrock-agentcore/runtimes/guppi_connect_bridge-"
SUB_AGENT_PREFIX = "/aws/bedrock-agentcore/runtimes/hr_super_agent_"
ISSUER_GROUP = "/aws/lambda/guppi-gpt-obo-issuer"
DOMAINS = ("profile", "pay", "travel")
# A contact lives at most 60 minutes (CHAT_DURATION_MINUTES in the bridge), so a question's
# warm start is never further back than this.
CONTACT_LOOKBACK_MS = 65 * 60 * 1000
MARGIN_MS = 5000

STARTED_CONTACT = re.compile(r"started contact ([0-9a-f-]{36})")
REPORT_DURATION = re.compile(r"RequestId: \S+\s+Duration: ([\d.]+) ms")
REPORT_INIT = re.compile(r"Init Duration: ([\d.]+) ms")
REPORT_XRAY = re.compile(r"XRAY TraceId: (\S+)")


# Times are integers: milliseconds since the epoch, UTC.


def iso_ms(text: str) -> int:
    return round(datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp() * 1000)


def stamp(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, UTC).strftime("%Y-%m-%d %H:%M:%S")


def clock(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, UTC).strftime("%H:%M:%S.%f")[:-3]


def log_json(message: str) -> dict | None:
    """The JSON object after " - " on a Python logging line. The OTel copy of the same line
    (a JSON document in the otel-rt-logs stream) and every other line give None."""
    if message.startswith("{"):
        return None
    _, sep, tail = message.partition(" - ")
    if not sep:
        return None
    try:
        value = json.loads(tail)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


@dataclass(eq=False)
class Run:
    """One AG-UI run of the bridge, from its run line (the kit's app.py)."""

    start: int
    total_ms: int
    contact: str
    messages: int
    warm: bool
    trace_id: str
    run_id: str
    first_delta_ms: int | None
    fields: dict

    @property
    def end(self) -> int:
        return self.start + self.total_ms

    @property
    def is_warm_start(self) -> bool:
        return self.warm or self.messages == 0


def parse_run(message: str) -> Run | None:
    d = log_json(message)
    if not d or "connect_contact" not in d or "started_at" not in d:
        return None
    return Run(
        start=iso_ms(d["started_at"]),
        total_ms=int(d.get("total_ms") or 0),
        contact=d["connect_contact"],
        messages=int(d.get("messages") or 0),
        warm=bool(d.get("warm")),
        trace_id=d.get("trace_id", ""),
        run_id=d.get("run", ""),
        first_delta_ms=d.get("first_delta_ms"),
        fields=d,
    )


def parse_runs(events: list[tuple[int, str, str]]) -> list[Run]:
    runs: dict[str, Run] = {}
    for _, _, message in events:
        run = parse_run(message)
        if run is not None:
            runs.setdefault(run.fields.get("request_id") or run.run_id, run)
    return sorted(runs.values(), key=lambda r: r.start)


def parse_contact_starts(events: list[tuple[int, str, str]]) -> dict[str, int]:
    """The bridge's "started contact" line: the contact is up and its greeting was seen."""
    starts: dict[str, int] = {}
    for ts, _, message in events:
        if message.startswith("{"):
            continue
        match = STARTED_CONTACT.search(message)
        if match:
            starts.setdefault(match.group(1), ts)
    return starts


@dataclass(eq=False)
class IssuerCall:
    """One invocation of the token issuer Lambda, from its REPORT line and, for a token
    exchange, its JSON line."""

    end: int
    duration_ms: float
    init_ms: float | None = None
    xray: str | None = None
    token: dict | None = None
    load_ms: int | None = None

    @property
    def start(self) -> int:
        return round(self.end - self.duration_ms - (self.init_ms or 0))

    @property
    def trace_id(self) -> str | None:
        return self.xray.replace("1-", "", 1).replace("-", "") if self.xray else None

    def label(self) -> str:
        if not self.token:
            return "issuer request with no token line (a JWKS read)"
        return f"token exchange {self.token.get('client')} for {self.token.get('audience')}"

    def detail(self) -> str:
        if self.init_ms is not None:
            load = f", load {self.load_ms} ms" if self.load_ms is not None else ""
            return (
                f"issuer cold: init {self.init_ms:.0f} ms{load}, handler {self.duration_ms:.0f} ms"
            )
        warm = "issuer warm" if self.token else "issuer"
        return f"{warm}, {self.duration_ms:.0f} ms"


def parse_issuer(events: list[tuple[int, str, str]]) -> list[IssuerCall]:
    """Joins each invocation's lines within its log stream: the cold_start line and the
    token line come before the REPORT line that closes the invocation."""
    by_stream: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for ts, stream, message in sorted(events, key=lambda e: e[0]):
        by_stream[stream].append((ts, message))
    calls = []
    for items in by_stream.values():
        current: dict = {}
        for ts, message in items:
            if message.startswith("REPORT RequestId"):
                duration = REPORT_DURATION.search(message)
                init = REPORT_INIT.search(message)
                xray = REPORT_XRAY.search(message)
                calls.append(
                    IssuerCall(
                        end=ts,
                        duration_ms=float(duration.group(1)) if duration else 0.0,
                        init_ms=float(init.group(1)) if init else None,
                        xray=xray.group(1) if xray else None,
                        token=current.get("token"),
                        load_ms=current.get("load_ms"),
                    )
                )
                current = {}
            elif message.startswith("{"):
                try:
                    d = json.loads(message)
                except ValueError:
                    continue
                if d.get("event") == "cold_start":
                    current["load_ms"] = d.get("load_ms")
                elif "route" in d:
                    current["token"] = d
    return sorted(calls, key=lambda c: c.end)


def audience_branch(audience: str) -> str:
    """The branch of a hop token: a sub-agent's domain, or "canvas" for the canvas's tools
    token."""
    if audience.startswith("api://hr-agents/"):
        return audience.rsplit("/", 1)[1]
    if audience == "api://hr-tools":
        return "canvas"
    return audience


def branches(calls: list[IssuerCall]) -> dict[IssuerCall, str | None]:
    """The branch of every exchange: the bridge's hop tokens are named by their audience,
    and every later exchange names the token it was exchanged from (subject_jti). A
    sub-agent's exchange whose hop token was minted before the window is named by its
    client (hr-agent-<domain>)."""
    branch_of: dict[str, str] = {}
    result: dict[IssuerCall, str | None] = {}
    for call in calls:
        token = call.token or {}
        client = token.get("client", "")
        if client == "hr-bridge":
            branch = audience_branch(token.get("audience", ""))
        elif token.get("subject_jti") in branch_of:
            branch = branch_of[token["subject_jti"]]
        elif client.startswith("hr-agent-"):
            branch = client.removeprefix("hr-agent-")
        else:
            branch = None
        result[call] = branch
        if branch and token.get("jti"):
            branch_of[token["jti"]] = branch
    return result


def contact_calls(
    calls: list[IssuerCall], runs: list[Run], subs: list[SubAgentCall]
) -> dict[IssuerCall, str | None]:
    """The issuer calls of one contact, each with its branch. The bridge keeps hop tokens per
    Okta token (connect_bridge/obo.py), so a hop token can serve several contacts; a call is
    tied by time instead: the bridge's exchanges and the canvas's during one of the contact's
    runs, a sub-agent's during that sub-agent's run for the contact. A call with no token
    line (a JWKS read) is tied when its X-Ray trace is one of the contact's runs."""
    tied: dict[IssuerCall, str | None] = {}
    traces = {run.trace_id for run in runs}
    for call, branch in branches(sorted(calls, key=lambda c: c.end)).items():
        if call.token is None:
            if call.trace_id in traces:
                tied[call] = None
            continue
        if branch in DOMAINS and call.token.get("client") != "hr-bridge":
            inside = any(s.domain == branch and s.start <= call.end <= s.end + 50 for s in subs)
        else:
            inside = any(run.start <= call.end <= run.end + 1000 for run in runs)
        if inside:
            tied[call] = branch
    return tied


@dataclass(eq=False)
class SubAgentCall:
    """A sub-agent's run line (hr_agent/agents/server.py), logged when the run ends."""

    end: int
    domain: str
    duration_ms: int
    outcome: str
    tool_calls: int
    contact: str
    trace_id: str

    @property
    def start(self) -> int:
        return self.end - self.duration_ms


def parse_sub_agent(ts: int, message: str) -> SubAgentCall | None:
    d = log_json(message)
    if not d or not {"context", "domain", "duration_ms", "outcome"} <= d.keys():
        return None
    return SubAgentCall(
        end=ts,
        domain=d["domain"],
        duration_ms=int(d["duration_ms"]),
        outcome=d["outcome"],
        tool_calls=int(d.get("tool_calls") or 0),
        contact=d["context"],
        trace_id=d.get("trace_id", ""),
    )


@dataclass
class DesignerTurn:
    """The designer's events for one request (one correlation id): the greeting or a
    question."""

    correlation: str
    events: list[dict] = field(default_factory=list)

    @property
    def request(self) -> dict | None:
        return next((e for e in self.events if e["eventType"] == "NluRequestReceived"), None)

    @property
    def responded(self) -> dict | None:
        return next((e for e in self.events if e["eventType"] == "NluResponded"), None)

    @property
    def utterance(self) -> str | None:
        request = self.request
        return (request or {}).get("properties", {}).get("utterance")

    @property
    def is_greeting(self) -> bool:
        return self.request is not None and self.utterance is None


def designer_turns(events: list[dict]) -> list[DesignerTurn]:
    """Groups the designer's events by correlation id. Events with none (ConditionEvaluated)
    carry nothing for the timeline and are left out."""
    turns: dict[str, DesignerTurn] = {}
    for event in sorted(events, key=lambda e: iso_ms(e["eventTime"])):
        correlation = event.get("correlationId")
        if not correlation:
            continue
        event = {**event, "ms": iso_ms(event["eventTime"])}
        turns.setdefault(correlation, DesignerTurn(correlation)).events.append(event)
    return [t for t in turns.values() if t.request is not None]


@dataclass(eq=False)
class Step:
    start: int
    end: int | None
    label: str
    detail: str = ""
    background: bool = False
    parent: Step | None = None
    untimed: bool = False
    kind: str = ""  # "run" (another run), "sub-agent", "data request"
    domain: str | None = None  # a sub-agent call or a delegation to one
    tools_gateway: bool = False
    trace_id: str | None = None  # another run's trace

    def overlaps(self, other: Step) -> bool:
        if self.end is None or other.end is None:
            return False
        return self.start < other.end and other.start < self.end


def gateway_of(url: str) -> tuple[str, str | None, bool]:
    """A data request's target as a label, the sub-agent domain it delegates to, and whether
    it is the tools gateway."""
    parsed = urlparse(url or "")
    host, path = parsed.hostname or "", parsed.path
    if "-agents-" in host:
        domain = path.strip("/").split("/")[0] or None
        return f"agents gateway {path}", domain, False
    if "-tools-" in host:
        return f"tools gateway {path}", None, True
    return host or "external", None, False


def designer_steps(turn: DesignerTurn, request_label: str) -> list[Step]:
    """The designer's own steps for one request: the hand-off, the routing model, each data
    request, each journey agent, and the response."""
    steps: list[Step] = []
    open_model: int | None = None
    open_requests: dict[tuple, dict] = {}
    open_agents: dict[str, dict] = {}
    journey_flow: dict[str, str] = {}
    for event in turn.events:
        kind, props, ms = event["eventType"], event.get("properties", {}), event["ms"]
        if kind == "NluRequestReceived":
            steps.append(Step(ms, None, request_label))
        elif kind == "ModelStart":
            open_model = ms
        elif kind == "ModelEnd" and open_model is not None:
            steps.append(Step(open_model, ms, "routing model"))
            open_model = None
        elif kind == "DataRequestsRequested":
            open_requests[tuple(props.get("dataRequestIds") or [])] = event
        elif kind == "DataRequestsReturned":
            key = tuple(props.get("dataRequestIds") or [])
            started = open_requests.pop(key, None)
            if started is None:
                continue
            target, domain, tools = gateway_of(started.get("properties", {}).get("url", ""))
            response = number(props.get("responseTime"))
            detail = f"responseTime {response} ms, status {props.get('statusCode')}"
            if props.get("isTimeout"):
                detail += ", timed out"
            label = f"data request {', '.join(key)} ({target})"
            steps.append(
                Step(
                    started["ms"],
                    ms,
                    label,
                    detail,
                    kind="data request",
                    domain=domain,
                    tools_gateway=tools,
                )
            )
        elif kind == "GenerativeJourneyStarted":
            journey_flow[props.get("nodeId", "")] = event.get("flowId") or ""
        elif kind == "AgentStarted":
            open_agents[props.get("nodeId", "")] = event
        elif kind == "AgentEnded":
            node = props.get("nodeId", "")
            started = open_agents.pop(node, None)
            if started is None:
                continue
            flow = journey_flow.get(node)
            tools = started.get("properties", {}).get("mcpToolCount")
            detail = f"{tools} MCP tools" if tools is not None else ""
            steps.append(
                Step(
                    started["ms"],
                    ms,
                    f"journey agent ({flow})" if flow else "journey agent",
                    detail,
                )
            )
        elif kind == "NluResponded":
            detail = f"responseTime {number(props.get('responseTime'))} ms"
            steps.append(Step(ms, None, f"designer NluResponded ({event.get('flowId')})", detail))
        elif re.search(r"Fail|Error|Timeout", kind):
            steps.append(Step(ms, None, f"designer {kind}"))
    if open_model is not None:
        steps.append(Step(open_model, None, "routing model start, no end logged"))
    for key, started in open_requests.items():
        steps.append(
            Step(started["ms"], None, f"data request {', '.join(key)} sent, no return logged")
        )
    for started in open_agents.values():
        steps.append(Step(started["ms"], None, "journey agent start, no end logged"))
    return steps


@dataclass
class Sources:
    """Everything read for one contact."""

    runs: list[Run]
    contact_started: int | None
    designer: list[DesignerTurn] | None
    sub_agents: list[SubAgentCall]
    issuer: dict[IssuerCall, str | None]


def number(value) -> str:
    return f"{value:,}" if isinstance(value, int) else str(value)


def overlapping_runs(steps: list[Step], src: Sources, run: Run) -> None:
    """The contact's other runs at the same time, as background steps that hold their own
    work (a question's view shows the warm start still running under it)."""
    for other in src.runs:
        if other is run or not (other.start < run.end and run.start < other.end):
            continue
        what = "warm start" if other.is_warm_start else "question"
        label = f"{what} of the same contact, run {other.run_id[:8]}"
        steps.append(
            Step(
                other.start, other.end, label, background=True, kind="run", trace_id=other.trace_id
            )
        )


def holder(steps: list[Step], start: int, end: int) -> Step | None:
    """The other run whose time holds this interval."""
    return next((s for s in steps if s.kind == "run" and s.start <= start and end <= s.end), None)


def place(step: Step, parent: Step | None) -> Step:
    if parent is not None:
        step.parent, step.background = parent, parent.background
    return step


def greeting_steps(steps: list[Step], src: Sources, run: Run) -> None:
    """The designer's greeting and the bridge's "started contact" line. They belong to the
    run that started the contact; in another run's view they sit under that run."""
    ours = bool(run.fields.get("connect_started") or run.fields.get("connect_restarted"))
    for turn in src.designer or []:
        request, responded = turn.request, turn.responded
        if not turn.is_greeting or not (run.start <= request["ms"] <= run.end):
            continue
        end = responded["ms"] if responded else None
        detail = (
            f"responseTime {number(responded['properties'].get('responseTime'))} ms"
            if responded
            else ""
        )
        step = Step(
            request["ms"],
            end,
            "designer greeting (the flow started; the canvas read the tokens)",
            detail,
        )
        steps.append(place(step, None if ours else holder(steps, step.start, end or step.start)))
    if src.contact_started is not None and run.start <= src.contact_started <= run.end:
        step = Step(src.contact_started, None, "contact started, the bridge saw the greeting")
        steps.append(place(step, None if ours else holder(steps, step.start, step.start)))


def sub_agent_steps(steps: list[Step], src: Sources, run: Run) -> None:
    """Sub-agent runs of the contact during this run: warm-ups belong to a warm start, calls
    to the question whose data request delegated them."""
    for call in src.sub_agents:
        if not (call.start < run.end and run.start < call.end):
            continue
        warm = call.outcome == "warm"
        label = f"sub-agent {call.domain} {'warm-up' if warm else 'call'}"
        detail = f"outcome {call.outcome}, {call.tool_calls} tool calls"
        if call.trace_id and not warm and call.trace_id != run.trace_id:
            detail += f", trace {call.trace_id}"
        step = Step(call.start, call.end, label, detail, kind="sub-agent", domain=call.domain)
        if warm == run.is_warm_start:
            parent = next(
                (
                    s
                    for s in steps
                    if s.kind == "data request" and s.domain == call.domain and s.overlaps(step)
                ),
                None,
            )
        else:
            parent = holder(steps, call.start, call.end)
            step.background = parent is None
        steps.append(place(step, parent))


def issuer_steps(steps: list[Step], src: Sources, run: Run) -> None:
    """The contact's issuer calls during this run, each under the sub-agent run of its
    branch, the tools gateway data request (the canvas's branch), or the run it came from."""
    for call, branch in src.issuer.items():
        if call.end < run.start or call.start > run.end:
            continue
        step = Step(call.start, call.end, call.label(), call.detail())
        parent = next(
            (s for s in steps if s.kind == "sub-agent" and s.domain == branch and s.overlaps(step)),
            None,
        )
        if parent is None and branch == "canvas":
            parent = next((s for s in steps if s.tools_gateway and s.overlaps(step)), None)
        if parent is None and call.token is None and call.trace_id != run.trace_id:
            parent = next(
                (s for s in steps if s.kind == "run" and s.trace_id == call.trace_id), None
            )
        if (
            parent is None
            and (call.token or {}).get("client") == "hr-bridge"
            and call.end > run.end + 1000
        ):
            parent = holder(steps, call.start, call.end)
        steps.append(place(step, parent))


def warm_start_steps(run: Run, src: Sources) -> list[Step]:
    detail = "ended the previous chat's contact first" if run.fields.get("connect_ended") else ""
    steps = [Step(run.start, None, "bridge receives the warm start", detail)]
    overlapping_runs(steps, src, run)
    greeting_steps(steps, src, run)
    sub_agent_steps(steps, src, run)
    issuer_steps(steps, src, run)
    if not any(
        (c.token or {}).get("client") == "hr-bridge" and run.start <= c.end <= run.end
        for c in src.issuer
    ):
        steps.append(
            Step(
                run.start,
                None,
                "no hop token exchange in this run: the bridge holds hop tokens per Okta token",
                untimed=True,
            )
        )
    steps.append(Step(run.end, None, "bridge run ends", run.fields.get("outcome", "")))
    return steps


def turn_steps(run: Run, turn: DesignerTurn | None, src: Sources) -> list[Step]:
    steps = [Step(run.start, None, "bridge receives the question")]
    overlapping_runs(steps, src, run)
    if (
        run.fields.get("connect_waited")
        and src.contact_started
        and run.start < src.contact_started <= run.end
    ):
        steps.append(
            Step(run.start, src.contact_started, "waits for the warm start to start the contact")
        )
    steps.append(send_step(run))
    greeting_steps(steps, src, run)
    if turn is not None:
        steps.extend(designer_steps(turn, "designer NluRequestReceived, the Connect hand-off"))
    if run.first_delta_ms is not None:
        steps.append(Step(run.start + run.first_delta_ms, None, "bridge first delta"))
    sub_agent_steps(steps, src, run)
    for step in steps:
        parent = step.parent
        if step.kind == "sub-agent" and parent is not None and parent.kind == "data request":
            before, after = step.start - parent.start, parent.end - step.end
            parent.detail += f"; {before:,} ms before the sub-agent, {after:,} ms after"
    issuer_steps(steps, src, run)
    steps.append(Step(run.end, None, "bridge run ends", run.fields.get("outcome", "")))
    return steps


def sent_ms(run: Run) -> int | None:
    """When SendMessage finished, from the bridge receiving the run (connect_sent_ms, D54)."""
    value = run.fields.get("connect_sent_ms")
    return round(value) if isinstance(value, (int, float)) else None


def send_step(run: Run) -> Step:
    sent = sent_ms(run)
    if sent is None:
        return Step(
            run.start,
            None,
            "SendMessage done: not in these logs; its span is in the bridge's trace",
            untimed=True,
        )
    return Step(run.start + sent, None, "SendMessage done")


def split_line(run: Run, turn: DesignerTurn | None, src: Sources, steps: list[Step]) -> str | None:
    """The first delta in parts: the contact's start when it happened during the run (this
    run started the contact, or waited for the warm start to), Connect's hand-off to the
    designer, the designer's steps, and Connect's reply to the bridge."""
    if turn is None or run.first_delta_ms is None or turn.request is None or turn.responded is None:
        return None
    received, responded = turn.request["ms"], turn.responded["ms"]
    ready = run.start
    parts = []
    started = src.contact_started
    if started is not None and run.start < started < received:
        ready = started
        what = (
            "waiting for the contact"
            if run.fields.get("connect_waited")
            else "starting the contact"
        )
        parts.append(f"{what} {ready - run.start:,}")
    sent = sent_ms(run)
    if sent is not None and ready <= run.start + sent <= received:
        parts.append(f"SendMessage {run.start + sent - ready:,}")
        ready = run.start + sent
    parts.append(f"Connect hand-off {received - ready:,}")
    own = [
        s
        for s in steps
        if s.parent is None and not s.background and s.end is not None and s.kind != "run"
    ]
    sums: dict[str, int] = defaultdict(int)
    for s in own:
        if received <= s.start and s.end <= responded:
            kind = "data requests" if s.kind == "data request" else s.label.split(" (")[0]
            sums[kind] += s.end - s.start
    inner = ", ".join(f"{k} {v:,}" for k, v in sums.items())
    rest = responded - received - sum(sums.values())
    inner = f"{inner}, the rest {rest:,}" if inner else ""
    parts.append(f"designer {responded - received:,}" + (f" ({inner})" if inner else ""))
    parts.append(
        f"Connect to the bridge's first delta {run.start + run.first_delta_ms - responded:,}"
    )
    return f"first delta {run.first_delta_ms:,} ms: " + "; ".join(parts)


def mark_parallel(steps: list[Step]) -> set[Step]:
    """Steps that run at the same time as another step with the same parent and the same
    side (the run's own steps, or another run's)."""
    marked: set[Step] = set()
    for i, a in enumerate(steps):
        for b in steps[i + 1 :]:
            if a.parent is b.parent and a.background == b.background and a.overlaps(b):
                marked.update((a, b))
    return marked


def relative(ms: int, t0: int) -> str:
    return f"{ms - t0:+,}"


def render_steps(steps: list[Step], t0: int) -> list[str]:
    marked = mark_parallel(steps)
    order = {id(s): i for i, s in enumerate(steps)}
    children: dict[int | None, list[Step]] = defaultdict(list)
    for s in steps:
        children[id(s.parent) if s.parent is not None else None].append(s)
    lines: list[str] = []

    def walk(step: Step, depth: int) -> None:
        mark = "=" if step.background else ("*" if step in marked else " ")
        start = "." if step.untimed else relative(step.start, t0)
        end = relative(step.end, t0) if step.end is not None else ""
        span = f"{step.end - step.start:,}" if step.end is not None else ""
        text = "  " * depth + step.label + (f"; {step.detail}" if step.detail else "")
        lines.append(f"  {mark} {start:>9} {end:>9} {span:>7}  {text}")
        for child in sorted(children[id(step)], key=lambda c: (c.start, order[id(c)])):
            walk(child, depth + 1)

    roots = sorted(children[None], key=lambda c: (c.start, order[id(c)]))
    for root in [r for r in roots if not r.background]:
        walk(root, 0)
    background = [r for r in roots if r.background]
    if background:
        lines.append("    same contact, another run, at the same time:")
        for root in background:
            walk(root, 0)
    return lines


HEADER = "        start       end      ms  step (ms from the bridge receiving the run)"
LEGEND = (
    "  * runs at the same time as another step at its level;"
    " = work of the same contact from another run"
)


def render_run(run: Run, src: Sources) -> list[str]:
    lines = []
    if run.is_warm_start:
        lines.append(f"Warm start at {clock(run.start)} UTC, contact {run.contact}")
        lines.append(
            f"  bridge run {run.run_id[:8]}, trace {run.trace_id}, total {run.total_ms:,} ms"
        )
        steps = warm_start_steps(run, src)
        turn = None
    else:
        turn = None
        for candidate in src.designer or []:
            request = candidate.request
            if not candidate.is_greeting and run.start <= request["ms"] <= run.end:
                turn = candidate
                break
        lines.append(f"Question at {clock(run.start)} UTC, contact {run.contact}")
        if turn is not None:
            lines.append(f'  "{turn.utterance}"')
        first = (
            f"first delta {run.first_delta_ms:,} ms, "
            if run.first_delta_ms is not None
            else "no reply, "
        )
        lines.append(
            f"  bridge run {run.run_id[:8]}, trace {run.trace_id}, {first}total {run.total_ms:,} ms"
        )
        steps = turn_steps(run, turn, src)
    if src.designer is None:
        lines.append("  designer log: not read (logs.js failed; see the message above)")
    elif not src.designer:
        lines.append(
            "  designer log: nothing for this contact (it arrives some time after a turn,"
            " and the designer keeps it for a limited time)"
        )
    elif not run.is_warm_start and turn is None:
        lines.append("  designer log: no request inside this run")
    lines.append("")
    lines.append(HEADER)
    lines.extend(render_steps(steps, run.start))
    if not run.is_warm_start:
        split = split_line(run, turn, src, steps)
        if split:
            lines.append("")
            lines.append(f"  {split}")
    if any(line[2] in "*=" for line in lines if len(line) > 2 and line.startswith("  ")):
        lines.append(LEGEND)
    return lines


# Reading the logs.


def parse_when(text: str, now_ms: int) -> int:
    """A duration back from now (30m, 2h, 1d, 90s) or an ISO time in UTC."""
    match = re.fullmatch(r"(\d+)([smhd])", text)
    if match:
        unit = {"s": 1, "m": 60, "h": 3600, "d": 86400}[match.group(2)]
        return now_ms - int(match.group(1)) * unit * 1000
    value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return round(value.timestamp() * 1000)


def merge_windows(windows: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for lo, hi in sorted(windows):
        if merged and lo <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
        else:
            merged.append((lo, hi))
    return merged


def find_group(logs, prefix: str) -> str | None:
    for page in logs.get_paginator("describe_log_groups").paginate(logGroupNamePrefix=prefix):
        for group in page["logGroups"]:
            if group["logGroupName"].endswith("-DEFAULT"):
                return group["logGroupName"]
    return None


def fetch(logs, group: str, lo: int, hi: int, pattern: str = "") -> list[tuple[int, str, str]]:
    kwargs = {"logGroupName": group, "startTime": lo, "endTime": hi}
    if pattern:
        kwargs["filterPattern"] = pattern
    events = []
    for page in logs.get_paginator("filter_log_events").paginate(**kwargs):
        events.extend((e["timestamp"], e["logStreamName"], e["message"]) for e in page["events"])
    return events


def read_designer(contact: str, span_ms: int) -> list[dict] | None:
    try:
        out = subprocess.run(
            ["node", "logs.js", contact, str(span_ms), "--json"],
            cwd=ACXD,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"designer log for {contact}: {type(error).__name__}", file=sys.stderr)
        return None
    if out.returncode:
        print(f"designer log for {contact}: {out.stderr.strip()[:300]}", file=sys.stderr)
        return None
    return [json.loads(line) for line in out.stdout.splitlines() if line.startswith("{")]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--since", help="30m, 2h, 1d, or an ISO time in UTC (default 1h, or 1d with --contact)"
    )
    parser.add_argument("--until", help="an ISO time in UTC (default now)")
    parser.add_argument("--contact", help="only the runs of this Connect contact id")
    parser.add_argument("--questions-only", action="store_true", help="leave out the warm starts")
    args = parser.parse_args()

    import boto3

    now = round(time.time() * 1000)
    since = parse_when(args.since or ("1d" if args.contact else "1h"), now)
    until = parse_when(args.until, now) if args.until else now
    logs = boto3.client("logs", region_name=REGION)
    bridge = find_group(logs, BRIDGE_PREFIX)
    if bridge is None:
        sys.exit(f"no log group under {BRIDGE_PREFIX}")

    pattern = '"connect_contact"' + (f' "{args.contact}"' if args.contact else "")
    runs = parse_runs(fetch(logs, bridge, since - CONTACT_LOOKBACK_MS, until + 60_000, pattern))
    if args.contact:
        runs = [r for r in runs if r.contact == args.contact]
    selected = [r for r in runs if since <= r.start <= until]
    if args.questions_only:
        selected = [r for r in selected if not r.is_warm_start]
    if not selected:
        print(f"No bridge runs between {stamp(since)} and {stamp(until)} UTC")
        return

    contacts = list(dict.fromkeys(r.contact for r in selected))
    by_contact = {c: [r for r in runs if r.contact == c] for c in contacts}
    windows = merge_windows(
        [
            (min(r.start for r in rs) - MARGIN_MS, max(r.end for r in rs) + MARGIN_MS)
            for rs in by_contact.values()
        ]
    )
    starts = {}
    issuer_events, sub_events = [], []
    sub_groups = [g for d in DOMAINS if (g := find_group(logs, f"{SUB_AGENT_PREFIX}{d}-"))]
    for lo, hi in windows:
        starts.update(parse_contact_starts(fetch(logs, bridge, lo, hi, '"started contact"')))
        issuer_events += fetch(logs, ISSUER_GROUP, lo, hi)
        for group in sub_groups:
            sub_events += fetch(logs, group, lo, hi, '"outcome" "context"')
    issuer = parse_issuer(issuer_events)
    sub_agents = [c for ts, _, m in sub_events if (c := parse_sub_agent(ts, m))]

    print(
        f"Bridge runs: {len(selected)}, contacts: {len(contacts)},"
        f" {stamp(since)} to {stamp(until)} UTC\n"
    )
    for contact in contacts:
        rs = by_contact[contact]
        span = now - min(r.start for r in rs) + 10 * 60 * 1000
        events = read_designer(contact, span)
        src = Sources(
            runs=rs,
            contact_started=starts.get(contact),
            designer=designer_turns(events) if events is not None else None,
            sub_agents=[c for c in sub_agents if c.contact == contact],
            issuer=contact_calls(issuer, rs, [c for c in sub_agents if c.contact == contact]),
        )
        for run in [r for r in selected if r.contact == contact]:
            print("\n".join(render_run(run, src)))
            print()


if __name__ == "__main__":
    main()
