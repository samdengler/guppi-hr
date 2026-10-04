"""CloudTrail events for the run window from Connect, the Connect participant service and
AgentCore, with token-bearing fields dropped. Writes raw/cloudtrail.json."""
import json
from datetime import datetime, timezone
import boto3

ct = boto3.client("cloudtrail", region_name="us-east-1")
lo = datetime(2026, 10, 4, 21, 58, 0, tzinfo=timezone.utc)
hi = datetime(2026, 10, 4, 22, 9, 40, tzinfo=timezone.utc)
KEEP_REQ = {"contentType", "clientToken", "type", "InstanceId", "ContactFlowId", "InitialContactId", "ContactId", "ContentType", "Type", "resourceCredentialProviderName", "scopes", "oauth2Flow", "workloadName", "MaxResults", "ScanDirection", "SortOrder"}
KEEP_RESP = {"id", "absoluteTime", "participantId", "ContactId", "ParticipantId", "Id", "AbsoluteTime", "InitialContactId"}
out = []
for src in ("connect.amazonaws.com", "participant-connect.amazonaws.com", "bedrock-agentcore.amazonaws.com"):
    for page in ct.get_paginator("lookup_events").paginate(LookupAttributes=[{"AttributeKey": "EventSource", "AttributeValue": src}], StartTime=lo, EndTime=hi):
        for e in page["Events"]:
            c = json.loads(e["CloudTrailEvent"])
            ui = c.get("userIdentity") or {}
            out.append({
                "eventTime": c["eventTime"], "eventSource": c["eventSource"], "eventName": c["eventName"],
                "requestID": c.get("requestID"), "eventID": c.get("eventID"), "username": e.get("Username"),
                "principal": (ui.get("arn") or "").split(":")[-1], "invokedBy": ui.get("invokedBy"),
                "errorCode": c.get("errorCode"),
                "userAgent": (c.get("userAgent") or "")[:80],
                "extra": {k: v for k, v in (c.get("additionalEventData") or {}).items() if k in ("participantId", "instanceId", "contactId")},
                "resources": [r.get("ARN") for r in (c.get("resources") or []) if r.get("ARN")],
                "req": {k: v for k, v in (c.get("requestParameters") or {}).items() if k in KEEP_REQ},
                "resp": {k: v for k, v in (c.get("responseElements") or {}).items() if k in KEEP_RESP} if isinstance(c.get("responseElements"), dict) else None,
            })
json.dump(out, open("raw/cloudtrail.json", "w"))
from collections import Counter
print(len(out)); print(Counter((x["eventSource"].split(".")[0], x["eventName"], x["username"] if not (x["username"] or "").startswith("gateway-session") else "gateway-session-*") for x in out).most_common(30))
