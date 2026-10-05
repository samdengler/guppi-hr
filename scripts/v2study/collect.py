#!/usr/bin/env python
"""Join the invoker's lines with the runtime's own InvokeAgentRuntime records and print
tables for the Runtime V2 cold start study (docs/runtime-v2-experiments.md).

    uv run --no-project --with 'boto3>=1.43.95' python scripts/v2study/collect.py \
        docs/runtime-v2-evidence/E1/*.jsonl --md docs/runtime-v2-evidence/E1/results.md [--cloudtrail]

For every request: the client's send and end; the runtime's receipt (`timeUnixNano`) and
completion (`event_timestamp`) from `/aws/vendedlogs/bedrock-agentcore/hr-v2-study`; the
handler's own wall clock and work time from the telemetry. Segments reported:

    client_ms            send to end at the client
    to_receipt_ms        client send to the runtime's receipt (network, auth, placement queue)
    receipt_to_handler   runtime receipt to the handler's first line (restore plus delivery)
    work_ms              the handler's own work
    handler_to_done      handler end to the runtime's completion stamp
    record_ms            receipt to completion on the runtime's records
    done_to_client       completion to the client's end

Groups: runtime, kind (new, same-session, followup, burst), step, and for new sessions the
first five against the rest. The clocks of the client, the runtime and the container can
differ by about 0.1 s; `--cloudtrail` adds GetWorkloadAccessTokenForJWT counts per runtime.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import time
from collections import defaultdict

import boto3

REGION = "us-east-1"
LOG_GROUP = "/aws/vendedlogs/bedrock-agentcore/hr-v2-study"
STREAM = "BedrockAgentCoreRuntime_ApplicationLogs"


def load(paths: list[str]) -> list[dict]:
    lines = []
    for path in paths:
        for raw in pathlib.Path(path).read_text().splitlines():
            if raw.strip():
                lines.append(json.loads(raw))
    return lines


def fetch_records(lines: list[dict]) -> dict[str, list[dict]]:
    """Runtime records by session id, within the lines' time window."""
    logs = boto3.client("logs", region_name=REGION)
    start = int((min(ln["t_send"] for ln in lines) - 120) * 1000)
    end = int((max(ln["t_end"] for ln in lines) + 300) * 1000)
    arns = {ln["runtime"] for ln in lines}
    by_session: dict[str, list[dict]] = defaultdict(list)
    for arn_tail in arns:
        token = None
        while True:
            kw = {"nextToken": token} if token else {}
            resp = logs.filter_log_events(
                logGroupName=LOG_GROUP, logStreamNames=[STREAM], startTime=start, endTime=end,
                filterPattern=f'{{ $.resource_arn = "*{arn_tail}" }}', **kw,
            )
            for ev in resp["events"]:
                rec = json.loads(ev["message"])
                by_session[rec["session_id"]].append(rec)
            token = resp.get("nextToken")
            if not token:
                break
    for recs in by_session.values():
        recs.sort(key=lambda r: r["timeUnixNano"])
    return by_session


def join(lines: list[dict], records: dict[str, list[dict]]) -> None:
    for ln in lines:
        recs = records.get(ln["session"], [])
        rec = next((r for r in recs if r["request_id"] == ln.get("request_id")), None)
        if rec is None and recs:
            # match by order: the n-th request on the session
            same = sorted([x for x in lines if x["session"] == ln["session"]], key=lambda x: x["t_send"])
            pos = same.index(ln)
            rec = recs[pos] if pos < len(recs) else None
        if rec is None:
            continue
        receipt = rec["timeUnixNano"] / 1e9
        done = rec["event_timestamp"] / 1e3
        ln["receipt"], ln["done"] = receipt, done
        ln["to_receipt_ms"] = round((receipt - ln["t_send"]) * 1000, 1)
        ln["record_ms"] = round((done - receipt) * 1000, 1)
        if ln.get("t_end"):
            ln["done_to_client_ms"] = round((ln["t_end"] - done) * 1000, 1)
        tel = ln.get("telemetry") or {}
        req = tel.get("request") or {}
        if req.get("wall"):
            ln["receipt_to_handler_ms"] = round((req["wall"] - receipt) * 1000, 1)
            ln["handler_to_done_ms"] = round((done - req["wall"] - (tel.get("work_ms") or 0) / 1000) * 1000, 1)
        ln["record_session_id"] = rec["session_id"]


def q(vals: list[float], p: float) -> float:
    if not vals:
        return float("nan")
    s = sorted(vals)
    k = (len(s) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def stat(vals: list[float]) -> str:
    vals = [v for v in vals if v is not None]
    if not vals:
        return "-"
    if len(vals) == 1:
        return f"{vals[0]:.0f}"
    return f"{statistics.median(vals):.0f} ({q(vals, 0.1):.0f} to {q(vals, 0.9):.0f}, n={len(vals)})"


FIELDS = ["client_ms", "to_receipt_ms", "receipt_to_handler_ms", "work_ms", "handler_to_done_ms", "record_ms", "done_to_client_ms"]


def group_key(ln: dict) -> tuple:
    return (ln["runtime"].split("-")[0], ln.get("label") or "", ln["kind"], ln.get("step", ""), ln.get("burst_size", ""), ln.get("wait_s", ""))


def tables(lines: list[dict]) -> str:
    ok = [ln for ln in lines if ln.get("status") == 200 and not ln.get("error")]
    bad = [ln for ln in lines if ln not in ok]
    for ln in ok:
        tel = ln.get("telemetry") or {}
        ln["work_ms"] = tel.get("work_ms")
    out = []
    out.append(f"{len(ok)} requests ok, {len(bad)} failed, {sum(1 for ln in ok if 'receipt' in ln)} joined to runtime records.\n")
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for ln in ok:
        groups[group_key(ln)].append(ln)
    out.append("| runtime | label | kind | step | burst | wait | " + " | ".join(FIELDS) + " |")
    out.append("|" + " --- |" * (6 + len(FIELDS)))
    for key in sorted(groups, key=lambda k: tuple(str(x) for x in k)):
        g = groups[key]
        out.append("| " + " | ".join(str(x) for x in key) + " | " + " | ".join(stat([ln.get(f) for ln in g]) for f in FIELDS) + " |")
    # first five new sessions against the rest, per runtime
    out.append("\nFirst five new sessions of a runtime (after READY or a deploy) against the rest, receipt_to_handler_ms:\n")
    out.append("| runtime | label | first 5 | rest | first 5 client_ms | rest client_ms |")
    out.append("| --- | --- | --- | --- | --- | --- |")
    per_rt: dict[tuple, list[dict]] = defaultdict(list)
    for ln in ok:
        if ln["kind"] == "new" and ln.get("step_no", 0) == 0:
            per_rt[(ln["runtime"].split("-")[0], ln.get("label") or "")].append(ln)
    for key, g in sorted(per_rt.items()):
        g.sort(key=lambda x: x["t_send"])
        first, rest = g[:5], g[5:]
        out.append(f"| {key[0]} | {key[1]} | {stat([x.get('receipt_to_handler_ms') for x in first])} | {stat([x.get('receipt_to_handler_ms') for x in rest])} | {stat([x['client_ms'] for x in first])} | {stat([x['client_ms'] for x in rest])} |")
    # telemetry facts per runtime
    out.append("\nWhat the restored instances report, per runtime (distinct values across answers):\n")
    out.append("| runtime | answers | boot_id | hostname | pid | first_random | random at request | mem_total_mb | cpus | rss_mb (median) | minflt delta (median) | mono_since_start_s | wall_since_start_s (snapshot age) |")
    out.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    per: dict[str, list[dict]] = defaultdict(list)
    for ln in ok:
        tel = ln.get("telemetry") or {}
        if tel.get("request"):
            per[ln["runtime"].split("-")[0]].append(tel)
    for rt, tels in sorted(per.items()):
        reqs = [t["request"] for t in tels]
        starts = [t.get("start", {}) for t in tels]
        rng = lambda vals: f"{min(vals):.1f} to {max(vals):.1f}" if vals else "-"  # noqa: E731
        out.append("| " + " | ".join([
            rt, str(len(tels)),
            str(len({r.get("boot_id") for r in reqs})), str(len({r.get("hostname") for r in reqs})), str(len({r.get("pid") for r in reqs})),
            str(len({s.get("first_random") for s in starts})), str(len({r.get("random") for r in reqs})),
            str(sorted({(t.get("before") or {}).get("mem_total_mb") for t in tels})), str(sorted({r.get("cpus") for r in reqs})),
            f"{statistics.median([(t.get('after') or {}).get('rss_mb') or 0 for t in tels]):.0f}",
            f"{statistics.median([((t.get('after') or {}).get('minflt') or 0) - ((t.get('before') or {}).get('minflt') or 0) for t in tels]):.0f}",
            rng([r.get("mono_since_start_s") for r in reqs if r.get("mono_since_start_s") is not None]),
            rng([r.get("wall_since_start_s") for r in reqs if r.get("wall_since_start_s") is not None]),
        ]) + " |")
    if bad:
        out.append("\nFailures:\n")
        errs: dict[str, int] = defaultdict(int)
        for ln in bad:
            errs[f"{ln['runtime'].split('-')[0]} {ln['kind']} {ln.get('status')} {str(ln.get('error'))[:160]}"] += 1
        for k, n in sorted(errs.items(), key=lambda kv: -kv[1]):
            out.append(f"- {n}: {k}")
    return "\n".join(out)


def cloudtrail_counts(lines: list[dict]) -> str:
    ct = boto3.client("cloudtrail", region_name=REGION)
    start = min(ln["t_send"] for ln in lines) - 60
    end = max(ln["t_end"] for ln in lines) + 60
    counts: dict[str, int] = defaultdict(int)
    token = None
    while True:
        kw = {"NextToken": token} if token else {}
        resp = ct.lookup_events(LookupAttributes=[{"AttributeKey": "EventName", "AttributeValue": "GetWorkloadAccessTokenForJWT"}],
                                StartTime=start, EndTime=end, MaxResults=50, **kw)
        for ev in resp["Events"]:
            doc = json.loads(ev["CloudTrailEvent"])
            counts[(doc.get("requestParameters") or {}).get("workloadName", "?")] += 1
        token = resp.get("NextToken")
        if not token:
            break
    reqs: dict[str, int] = defaultdict(int)
    sessions: dict[str, set] = defaultdict(set)
    for ln in lines:
        reqs[ln["runtime"]] += 1
        sessions[ln["runtime"]].add(ln["session"])
    out = ["\nCloudTrail GetWorkloadAccessTokenForJWT in the window (CloudTrail lags up to 15 minutes):\n",
           "| runtime | requests sent | sessions | Identity calls |", "| --- | --- | --- | --- |"]
    for rt in sorted(reqs):
        out.append(f"| {rt.split('-')[0]} | {reqs[rt]} | {len(sessions[rt])} | {counts.get(rt, 0)} |")
    return "\n".join(out)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("lines", nargs="+")
    p.add_argument("--md", help="write the tables here")
    p.add_argument("--joined", help="write the joined lines here (jsonl)")
    p.add_argument("--cloudtrail", action="store_true")
    p.add_argument("--no-records", action="store_true", help="client side only")
    a = p.parse_args()
    lines = load(a.lines)
    if not lines:
        raise SystemExit("no lines")
    if not a.no_records:
        join(lines, fetch_records(lines))
    text = f"Collected {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())} from {', '.join(a.lines)}.\n\n" + tables(lines)
    if a.cloudtrail:
        text += "\n" + cloudtrail_counts(lines)
    if a.md:
        pathlib.Path(a.md).write_text(text + "\n")
    if a.joined:
        with open(a.joined, "w") as f:
            for ln in lines:
                f.write(json.dumps(ln) + "\n")
    print(text)


if __name__ == "__main__":
    main()
