"""Medians of AgentCore's own spans per name, and the runtime's Invoke spans split by a
session's first request against later ones."""
import json, sys, statistics as st
from collections import defaultdict
def summarize(d):
    x = json.load(open(f"{d}/raw/agentcore-spans.json"))
    by = defaultdict(list)
    for s in x:
        if s["end"]:
            key = s["name"] if not s["name"].startswith("AgentCore.Runtime.Invoke") else f"AgentCore.Runtime.Invoke [{s['service']}]"
            by[(key, s["service"] if "Gateway" in s["name"] or "Identity" in s["name"] or "Policy" in s["name"] else "")].append(s["end"] - s["start"])
    rows = []
    for (k, svc), v in sorted(by.items()):
        rows.append((k, svc, round(st.median(v)), round(min(v)), round(max(v)), len(v)))
    inv = [s for s in x if s["name"] == "AgentCore.Runtime.Invoke" and s["end"]]
    sess = defaultdict(list)
    for s in inv:
        sess[(s["service"], s["attributes"].get("session.id"))].append(s)
    first, later = defaultdict(list), defaultdict(list)
    for (svc, sid), v in sess.items():
        v.sort(key=lambda s: s["start"])
        first[svc].append(v[0]["end"] - v[0]["start"])
        for s in v[1:]:
            later[svc].append(s["end"] - s["start"])
    split = {svc: {"first": (round(st.median(first[svc])), len(first[svc])), "later": (round(st.median(later[svc])), len(later[svc])) if later[svc] else None} for svc in first}
    keys = sorted({k for s in inv for k in s["attributes"]})
    return rows, split, keys
if __name__ == "__main__":
    for d in sys.argv[1:]:
        rows, split, keys = summarize(d)
        print("==", d); [print(" ", r) for r in rows]; print("  invoke split", split); print("  invoke attrs", keys)
