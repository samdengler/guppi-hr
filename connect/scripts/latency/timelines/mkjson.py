"""Writes ../latency-timelines.json from paths.json (agg.py's output)."""
import json
P = json.load(open('paths.json'))['paths']
OWN = {"internet", "connect", "designer", "model", "gateway", "runtime", "identity", "ours"}
names = {"clarify": "ClarifyFlow: \"Update my information\" (fixed question)", "policy-first": "PolicyFlow first turn: \"PTO policy\"", "policy-follow": "PolicyFlow journey follow-up: \"Does unused PTO carry over?\"", "profile-first": "ProfileFlow, first call to the Profile sub-agent in a chat (\"Change my address\", \"my home address\" after ClarifyFlow, reuse pairs)", "profile-follow": "ProfileFlow follow-up: \"And what is my emergency contact?\"", "travel-first": "TravelFlow first call: \"Buddy passes\"", "travel-follow": "TravelFlow follow-up: \"Can my parents use them?\"", "pay-first": "PayFlow first call (typed): \"When was my last paycheck and how much was it?\"", "pay-follow": "PayFlow follow-up: \"And the one before that?\"", "chat-start": "Chat start at page load, warm function instance", "chat-start-cold": "Chat start at page load, cold function instance and cold issuer (one sample)"}
out = {"generated": "2026-10-04 lt-v2p", "report": "latency-timelines.md", "clock": "ms from the click for turns; ms from the page's navigation start for chat start", "owners": sorted(OWN), "paths": {}}
for k, v in P.items():
    steps = []
    for r in v["steps"]:
        assert r["owner"] in OWN, r
        st = {"name": r["name"], "owner": r["owner"], "start_ms": r["start_ms"], "end_ms": r["end_ms"]}
        if "p10_ms" in r:
            st["p10_ms"], st["p90_ms"] = r["p10_ms"], r["p90_ms"]
        if r.get("parallel_group"):
            st["parallel_group"] = r["parallel_group"]
        for x in ("dur_ms", "dur_p10_ms", "dur_p90_ms", "dur_min_ms", "dur_max_ms", "level", "container", "n"):
            if x in r:
                st[x] = r[x]
        steps.append(st)
    out["paths"][k] = {"title": names.get(k, k), "summary": v["summary"], "steps": steps}
out["notes"] = [
    "start_ms and end_ms are medians of each step's own start and end across the path's turns, so dur_ms (the median duration) can differ from end_ms minus start_ms.",
    "p10_ms and p90_ms are the 10th and 90th percentiles of the step's end time.",
    "level 0 rows are the turn's critical path; deeper rows sit inside the container row above them (container: true).",
    "parallel_group marks rows that run at the same time as each other or overlap the critical path.",
]
json.dump(out, open('latency-timelines.json', 'w'), indent=1)
print(list(out["paths"]))
