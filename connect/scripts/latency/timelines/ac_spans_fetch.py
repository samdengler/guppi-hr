"""AgentCore's own spans (gateway, runtime, identity, policy) from aws/spans for a run window.
Writes <folder>/raw/agentcore-spans.json without access keys or IP addresses."""
import json, sys
import boto3
d, lo, hi = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
logs = boto3.client("logs", region_name="us-east-1")
out = []
for page in logs.get_paginator("filter_log_events").paginate(logGroupName="aws/spans", startTime=lo, endTime=hi, filterPattern='"AgentCore."'):
    for e in page["events"]:
        s = json.loads(e["message"])
        if not s.get("name", "").startswith("AgentCore."):
            continue
        a = {k: v for k, v in (s.get("attributes") or {}).items() if "access_key" not in k and "address" not in k and "ip" != k.split(".")[-1]}
        out.append({"name": s["name"], "traceId": s.get("traceId"), "spanId": s.get("spanId"), "parentSpanId": s.get("parentSpanId"),
                    "start": int(s["startTimeUnixNano"]) / 1e6, "end": int(s["endTimeUnixNano"]) / 1e6 if s.get("endTimeUnixNano") else None,
                    "service": (s.get("resource") or {}).get("attributes", {}).get("service.name"), "attributes": a})
json.dump(out, open(f"{d}/raw/agentcore-spans.json", "w"))
print(d, len(out))
