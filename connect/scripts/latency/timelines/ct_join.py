"""Adds CloudTrail request ids to evidence.json: Connect and participant calls per contact,
AgentCore Identity calls of the chat start, the tools gateway and the runtimes. CloudTrail
times are to the second, so calls are matched by contact where CloudTrail names one and by
second and caller otherwise.

    python3 ct_join.py
"""
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
ct = json.loads((HERE / "raw" / "cloudtrail.json").read_text())
ev = json.loads((HERE / "evidence.json").read_text())


def t(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def sec(s):
    return t(s).replace(microsecond=0)


def contact_of(e):
    for a in e.get("resources") or []:
        if "/contact/" in a:
            return a.split("/contact/")[1]
    return e["req"].get("InitialContactId") or (e.get("resp") or {}).get("ContactId")


def who(e):
    ua = e.get("userAgent") or ""
    if ua.startswith("aws-internal"):
        return "designer"
    if ua.startswith("aws-sdk-rust"):
        return "chat start function"
    if ua.startswith("Mozilla"):
        return "browser"
    return e.get("username") or "?"


by_contact = defaultdict(list)
for e in ct:
    c = contact_of(e)
    if c:
        by_contact[c].append(e)
for v in by_contact.values():
    v.sort(key=lambda e: ((e.get("resp") or {}).get("absoluteTime") or e["eventTime"]))

used = set()


def take(pred, events):
    for e in events:
        if e["eventID"] not in used and pred(e):
            used.add(e["eventID"])
            return e
    return None


def brief(e, **kw):
    if not e:
        return None
    out = {"event": e["eventName"], "request_id": e["requestID"], "event_id": e["eventID"], "event_time": e["eventTime"], "caller": who(e)}
    r = e.get("resp") or {}
    if r.get("id"):
        out["message_id"] = r["id"]
    if r.get("absoluteTime"):
        out["connect_time"] = r["absoluteTime"]
    if e.get("extra", {}).get("participantId"):
        out["participant_id"] = e["extra"]["participantId"]
    if e.get("username") and who(e) == e.get("username"):
        out["principal_session"] = e["username"]
    out.update(kw)
    return out


AUD = {"hr.tools.policy": None}
identity = [e for e in ct if e["eventSource"].startswith("bedrock-agentcore")]


def near(e, lo, hi, slack=1):
    return sec(lo) - timedelta(seconds=slack) <= sec(e["eventTime"]) <= sec(hi) + timedelta(seconds=slack)


for chat in ev["chats"]:
    cid = chat["contact_id"]
    evs = by_contact.get(cid, [])
    cs = chat["chat_start"]
    cs["cloudtrail"] = {
        "StartChatContact": brief(take(lambda e: e["eventName"] == "StartChatContact", evs)),
        "CreateParticipantConnection (function)": brief(take(lambda e: e["eventName"] == "CreateParticipantConnection" and who(e) == "chat start function", evs)),
        "CreateParticipantConnection (designer)": brief(take(lambda e: e["eventName"] == "CreateParticipantConnection" and who(e) == "designer", evs)),
        "UpdateContactAttributes": brief(take(lambda e: e["eventName"] == "UpdateContactAttributes", evs)),
        "CreateParticipantConnection (browser)": brief(take(lambda e: e["eventName"] == "CreateParticipantConnection" and who(e) == "browser", evs)),
        "GetTranscript (browser)": brief(take(lambda e: e["eventName"] == "GetTranscript", evs)),
        "GetTranscript (browser, second)": brief(take(lambda e: e["eventName"] == "GetTranscript", evs)),
    }
    greet = take(lambda e: e["eventName"] == "SendMessage" and who(e) == "designer", evs)
    cs["greeting"]["connect_message"] = brief(greet)
    lo = cs["lambda_start_utc"]
    hi = (t(lo) + timedelta(milliseconds=cs["lambda_duration_ms"] or 0)).isoformat().replace("+00:00", "Z") if lo else None
    if lo:
        cs["cloudtrail_identity"] = [
            brief(take(lambda e: e["eventName"] == n and e.get("username") == "hr-chat-start" and near(e, lo, hi), identity), provider=None)
            for n in ("GetWorkloadAccessTokenForJWT", "GetResourceOauth2Token", "GetResourceOauth2Token", "GetResourceOauth2Token", "GetResourceOauth2Token")
        ]
    for turn in chat["turns"]:
        q = take(lambda e: e["eventName"] == "SendMessage" and who(e) == "browser", evs)
        turn["connect_question"] = brief(q)
        replies = []
        # Designer messages stamped from the question to 30 s after it, before the next question.
        click = t(turn["click_utc"])
        while True:
            nxt = next((e for e in evs if e["eventID"] not in used and e["eventName"] == "SendMessage"), None)
            if not nxt or who(nxt) != "designer" or t(nxt["resp"]["absoluteTime"]) > click + timedelta(seconds=30):
                break
            used.add(nxt["eventID"])
            replies.append(brief(nxt))
        turn["connect_replies"] = replies
        for d in turn["data_requests"]:
            sa = d.get("sub_agent")
            if not sa:
                continue
            start = (click + timedelta(milliseconds=sa["request_start_ms"])).isoformat().replace("+00:00", "Z")
            end = (click + timedelta(milliseconds=sa["request_end_ms"])).isoformat().replace("+00:00", "Z")
            rt = sa["microvm_log_stream"] and d["gateway_target"]
            wl = {"profile": "hr_super_agent_profile-7IkHmEG40H", "travel": "hr_super_agent_travel-7yhekY3cSf", "pay": "hr_super_agent_pay-7zZl2rCGqo"}[d["gateway_target"]]
            sa["runtime_ingress_identity"] = brief(take(lambda e: e.get("username") == "CustomerSlrValidation" and e["req"].get("workloadName") == wl and near(e, start, start), identity))
            for s in sa["steps"]:
                if s["name"].startswith("workload access token") or s["name"].startswith("on-behalf-of"):
                    name = "GetWorkloadAccessTokenForJWT" if s["name"].startswith("workload") else "GetResourceOauth2Token"
                    m = next((e for e in identity if e["requestID"] == s.get("aws_request_id")), None)
                    if m:
                        used.add(m["eventID"])
                        s["cloudtrail"] = brief(m)
                if s["name"].startswith("MCP tools/call hr___"):
                    s0 = (click + timedelta(milliseconds=s["start_ms"])).isoformat().replace("+00:00", "Z")
                    s1 = (click + timedelta(milliseconds=s["end_ms"])).isoformat().replace("+00:00", "Z")
                    gw_wl = take(lambda e: (e.get("username") or "").startswith("gateway-session-") and e["eventName"] == "GetWorkloadAccessTokenForJWT" and near(e, s0, s1, 2), identity)
                    gw_ex = take(lambda e: gw_wl and e.get("username") == gw_wl["username"] and e["eventName"] == "GetResourceOauth2Token", identity)
                    s["tools_gateway_identity"] = [brief(gw_wl), brief(gw_ex)]
                    s["tools_gateway_principal_session"] = gw_wl["username"] if gw_wl else None
                    s["tools_runtime_ingress_identity"] = [brief(take(lambda e: e.get("username") == "CustomerSlrValidation" and e["req"].get("workloadName") == "hr_super_agent_tools-Ykb6G5FTK1" and near(e, s0, s1), identity)) for _ in range(3)]

left = [e for e in ct if e["eventID"] not in used and e["eventName"] not in ("GetContactAttributes", "StopContact", "ListGateways", "ListAgentRuntimes", "ListGatewayTargets")]
from collections import Counter
print("unmatched:", Counter((e["eventName"], who(e)) for e in left))
ev["cloudtrail_note"] = "CloudTrail management events (eventTime to the second; Connect's absoluteTime to the millisecond). Token values, message content and IP addresses are not kept."
(HERE / "evidence.json").write_text(json.dumps(ev, indent=1))
