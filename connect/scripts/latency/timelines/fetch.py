"""Fetches every server-side source for the latency timeline runs into raw/: CloudWatch log
groups (chat start, issuer, gateways, runtimes), X-Ray spans from aws/spans, log stream
creation times, Dynatrace spans of the runtimes, and the designer's log per contact.

    uv run --with boto3 python fetch.py <since ISO> <until ISO>
"""
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3

HERE = Path(__file__).parent
RAW = HERE / "raw"
RAW.mkdir(exist_ok=True)
REGION = "us-east-1"
logs = boto3.client("logs", region_name=REGION)

GROUPS = {
    "chat-start": ("/aws/lambda/hr-chat-start", ""),
    "chat-start-apigw": ("/aws/apigateway/hr-chat-start", ""),
    "issuer": ("/aws/lambda/guppi-gpt-obo-issuer", ""),
    "issuer-apigw": ("/aws/apigateway/guppi-obo-issuer", ""),
    "agents-gw": ("/aws/vendedlogs/bedrock-agentcore/hr-super-agent-agents", ""),
    "tools-gw": ("/aws/vendedlogs/bedrock-agentcore/hr-super-agent-tools", ""),
    "rt-profile": ("/aws/bedrock-agentcore/runtimes/hr_super_agent_profile-7IkHmEG40H-DEFAULT", '-"GET /ping"'),
    "rt-pay": ("/aws/bedrock-agentcore/runtimes/hr_super_agent_pay-7zZl2rCGqo-DEFAULT", '-"GET /ping"'),
    "rt-travel": ("/aws/bedrock-agentcore/runtimes/hr_super_agent_travel-7yhekY3cSf-DEFAULT", '-"GET /ping"'),
    "rt-tools": ("/aws/bedrock-agentcore/runtimes/hr_super_agent_tools-Ykb6G5FTK1-DEFAULT", '-"GET /ping"'),
    "spans": ("aws/spans", ""),
}


def ms(text: str) -> int:
    return int(datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp() * 1000)


def fetch(group: str, lo: int, hi: int, pattern: str) -> list:
    out = []
    kwargs = {"logGroupName": group, "startTime": lo, "endTime": hi}
    if pattern:
        kwargs["filterPattern"] = pattern
    for page in logs.get_paginator("filter_log_events").paginate(**kwargs):
        out.extend([e["timestamp"], e["logStreamName"], e["message"]] for e in page["events"])
    return out


def streams(group: str, lo: int) -> list:
    out = []
    for page in logs.get_paginator("describe_log_streams").paginate(logGroupName=group, orderBy="LastEventTime", descending=True):
        for s in page["logStreams"]:
            if s.get("lastEventTimestamp", 0) < lo - 3600_000:
                return out
            out.append({k: s.get(k) for k in ("logStreamName", "creationTime", "firstEventTimestamp", "lastEventTimestamp")})
    return out


def dql(query: str) -> list:
    res = subprocess.run([sys.executable, str(HERE / "dql.py"), query], capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


def main() -> None:
    since, until = sys.argv[1], sys.argv[2]
    lo, hi = ms(since), ms(until)
    for name, (group, pattern) in GROUPS.items():
        events = fetch(group, lo, hi, pattern)
        (RAW / f"{name}.json").write_text(json.dumps(events))
        print(name, len(events))
    # Process starts of the microVMs that served the runs, from up to 3 hours before.
    for name in ("rt-profile", "rt-pay", "rt-travel", "rt-tools"):
        events = fetch(GROUPS[name][0], lo - 3 * 3600_000, hi, '"Started server process"')
        (RAW / f"{name}-proc.json").write_text(json.dumps(events))
        print(name, "process starts", len(events))
    st = {name: streams(GROUPS[name][0], lo) for name in ("rt-profile", "rt-pay", "rt-travel", "rt-tools")}
    (RAW / "streams.json").write_text(json.dumps(st))
    # Dynatrace spans: dtfetch.py, which splits windows under the MCP record cap.
    # The designer's log, per contact seen in the results.
    contacts = set()
    for f in HERE.glob("results-*.json"):
        for chat in json.loads(f.read_text())["chats"]:
            if chat.get("contact"):
                contacts.add(chat["contact"])
    span_ms = str(int(time.time() * 1000) - lo + 600_000)
    ddir = RAW / "designer"
    ddir.mkdir(exist_ok=True)
    acxd = Path.home() / "src/github.com/samdengler/guppi-hr/connect/acxd"
    for c in sorted(contacts):
        res = subprocess.run(["node", "logs.js", c, span_ms, "--json"], cwd=acxd, capture_output=True, text=True)
        (ddir / f"{c}.jsonl").write_text(res.stdout)
        print("designer", c[:8], len(res.stdout.splitlines()), res.stderr.strip()[:200])


if __name__ == "__main__":
    main()
