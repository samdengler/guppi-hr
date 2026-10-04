"""The runtimes' own InvokeAgentRuntime records (vended APPLICATION_LOGS) for the run window,
without payloads. Writes raw/rt-app.json."""
import json
import boto3

logs = boto3.client("logs", region_name="us-east-1")
lo, hi = 1791151100000, 1791151800000
out = []
for name in ("hr_super_agent_tools", "hr_super_agent_profile", "hr_super_agent_travel", "hr_super_agent_pay"):
    for page in logs.get_paginator("filter_log_events").paginate(logGroupName=f"/aws/vendedlogs/bedrock-agentcore/{name}", startTime=lo, endTime=hi):
        for e in page["events"]:
            x = json.loads(e["message"])
            out.append({"runtime": name, "request_id": x.get("request_id"), "session_id": x.get("session_id"), "trace_id": x.get("trace_id"), "span_id": x.get("span_id"),
                        "received_ns": x.get("timeUnixNano"), "logged_ms": x.get("event_timestamp"), "operation": x.get("operation"),
                        "attributes": {k: v for k, v in (x.get("attributes") or {}).items() if k not in ("aws.account.id",)}})
json.dump(out, open("raw/rt-app.json", "w"))
from collections import Counter
print(len(out), Counter(o["runtime"] for o in out), Counter(k for o in out for k in o["attributes"]))
