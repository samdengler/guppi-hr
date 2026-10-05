# E11. Idle timeout and session reuse: findings

## Hypothesis

From the plan: a follow-up within the idle timeout reuses the microVM (about 0.2 s), a
follow-up after the 120 s memory reclaim pays page-ins but no restore, and a follow-up after
the idle timeout restores a new microVM with the same session id and the full first-request
cost. A long idle timeout costs little under V2 pricing because idle memory is reclaimed.

## What was run

- Runtime `hr_v2_idle_60` (`hr_v2_idle_60-FrtEc49DAQ`, version 1): V2, HTTP, image `py`,
  `MODE=http`, SigV4, PUBLIC, `idleRuntimeSessionTimeout` 60 s (the minimum), maxLifetime
  28800 s. Created 00:55:33 UTC, READY 00:58:38 UTC, build 185.4 s (baseline 184.9 s).
- Runs on 5 October 2026 UTC. Each new session gets one request, then one follow-up on the same
  session id after each listed wait (the wait is counted from the end of the previous request,
  so it is the session's idle time):
  - `waits`: 5 sessions, follow-ups after 30, 75 and 130 s, 00:58:57 to 01:19:40 (20 requests).
  - Single-wait sweeps, 3 sessions each, four processes at a time on separate sessions:
    `sweep-45`, `sweep-65`, `sweep-90`, `sweep-105` (01:22:19 to 01:28:08), then `sweep-55`,
    `sweep-65b`, `sweep-115`, `sweep-125` (01:28:31 to 01:35:09). Added after the first run showed
    the 75 s follow-ups at 7 s, to find where the cost starts and stops.
  - `sweep-65-retry`: 4 sessions, a follow-up after 65 s and another 1 s later, 01:35:42 to
    01:41:11, to see what a retry after a failure costs.
- 80 requests, 73 ok, 7 failed with HTTP 502; the 73 successful ones all joined to runtime
  records, and the 7 failures were found in the runtime records by session id (see below).
- The baseline part was not run (see "Not run" below).

## Results

All `hr_v2_idle_60` follow-ups by idle time (medians with min to max, in ms). "Same process"
means the answer shows `request.n` 2, the same process start time and the same `boot_id` as the
session's first answer; "new restore" means `request.n` 1 and a monotonic clock back at the
snapshot's value (`mono_since_start_s` 67 to 78 s).

| idle before the follow-up (s) | follow-ups | same process | new restore | 502 after 4.2 to 4.3 s | client_ms, same process | client_ms, restores | receipt_to_handler_ms, restores |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | 5 | 5 | 0 | 0 | 176 (155 to 195) | - | - |
| 45 | 3 | 3 | 0 | 0 | 190 (168 to 199) | - | - |
| 55 | 3 | 3 | 0 | 0 | 174 (171 to 179) | - | - |
| 65 | 10 | 0 | 3 | 7 | - | 11367 (6962 to 14754) | 11268 (6854 to 14593) |
| 75 | 5 | 0 | 5 | 0 | - | 7274 (6895 to 14334) | 7102 (6804 to 14237) |
| 90 | 3 | 0 | 3 | 0 | - | 6999 (6880 to 7057) | 6896 (6788 to 6963) |
| 105 | 3 | 0 | 3 | 0 | - | 7174 (1938 to 7923) | 7007 (1745 to 7720) |
| 115 | 3 | 0 | 3 | 0 | - | 6857 (1607 to 7186) | 6741 (1513 to 7093) |
| 125 | 3 | 0 | 3 | 0 | - | 1976 (1800 to 2284) | 1892 (1719 to 2186) |
| 130 | 5 | 0 | 5 | 0 | - | 1960 (1693 to 2639) | 1852 (1598 to 2528) |

New sessions on the same runtime in the same period: client 1897 ms (1515 to 2756, n=33),
receipt to handler 1761 ms (1421 to 2596).

From `results.md`, the `waits` run (p10 to p90):

| label | kind | wait | client_ms | to_receipt_ms | receipt_to_handler_ms | record_ms |
| --- | --- | --- | --- | --- | --- | --- |
| waits | new | | 1897 (1837 to 2101, n=5) | 59 (54 to 108, n=5) | 1801 (1726 to 1944, n=5) | 1822 (1743 to 1992, n=5) |
| waits | followup | 30 | 176 (163 to 190, n=5) | 60 (54 to 69, n=5) | 82 (68 to 85, n=5) | 100 (90 to 104, n=5) |
| waits | followup | 75 | 7274 (6902 to 11549, n=5) | 61 (58 to 77, n=5) | 7102 (6810 to 11442, n=5) | 7195 (6827 to 11457, n=5) |
| waits | followup | 130 | 1960 (1722 to 2430, n=5) | 62 (59 to 70, n=5) | 1852 (1628 to 2324, n=5) | 1872 (1643 to 2346, n=5) |

The 502 failures: `RuntimeClientError ... Received error (502) from runtime. Please check your
CloudWatch logs for more information.` after 4.29 to 4.42 s at the client. The runtime recorded
each one (receipt to completion 4210 to 4284 ms, `response_payload` null, severity INFO). The
container log of those sessions has no line at the time of the 502; every restore that reached
the server logs one uvicorn `WARNING: Invalid HTTP request received.`, and the 502 requests did
not, so they never reached a running server.

Retries 1 s after the 65 s follow-up (`sweep-65-retry`): after a 502, the retry restored and
took 16207 ms and 7079 ms; after a successful 65 s follow-up (6962 ms and 14754 ms), the retry
reused that process in 238 ms and 181 ms.

Telemetry of the same-process follow-ups: the monotonic and wall clocks both advanced by the
wait (30.2, 45.2, 55.2 s), so the microVM ran through the idle time; 2 minor faults and no major
fault between the two requests. Restores came from the version's two snapshots (two `boot_id`
values, two `first_random` values), as on every V2 runtime in the study.

## Conclusion

Within the idle timeout a follow-up reuses the process at the cost of a zero-wait follow-up
(174 to 190 ms at the client, 82 ms receipt to handler), confirming the first part of the
hypothesis. After the idle timeout the same session id restores a new microVM, but for about
a minute after the timeout that restore usually costs 7 to 15 s instead of 1.9 s, and 5 s after the
timeout 7 of 10 follow-ups failed with a 502 after 4.2 s; only from about 65 s past the timeout
(125 and 130 s idle on this runtime) did the follow-up cost a plain restore (1.96 s). The 120 s
memory reclaim could not be observed here, because a 60 s runtime ends the session first.

## Surprises and notes for AWS

- A session id used shortly after its idle timeout fails with HTTP 502 after about 4.25 s (7
  of 10 at 5 s past the timeout), with nothing in the container log. A client retry then pays
  7 to 16 s. Total for the user: 11 to 20 s, or an error if the client does not retry.
- From 15 s to 55 s past the timeout (75 to 115 s idle), 12 of 14 first requests on the old
  session id cost 6.9 to 14.3 s (median about 7 s) and 2 cost a plain restore (1.6 and 1.9 s),
  while a new session id at the same moment costs 1.9 s. The 3 that succeeded at 5 s past the
  timeout took 7.0, 11.4 and 14.8 s. The extra 5 s (sometimes 9 to 13 s) looks like a wait for
  the old microVM before the platform restores a new one. The window closes between 45 and 65 s past the timeout (mixed results at 105 and
  115 s idle, clean at 125 and 130 s).
- Nothing survives the timeout: the restored process is fresh from the snapshot, so reusing the
  old session id after the timeout brings no state, only this penalty. A client that knows the
  session has idled past the timeout could start a new session id and pay the plain restore.
  Whether the same window exists at 900 s (the HR runtimes' setting) is not measured; if it
  does, a user returning 15 to 16 minutes after the last message meets it.

## Not run

The baseline part of the procedure (on `hr_v2_proto_http_v2`, idle 900 s: 5 sessions with
follow-ups after 30, 75 and 130 s, then 3 sessions with a follow-up after 960 s) was not run.
At 01:41 UTC the agent's permission check refused invocations of the baseline, which belongs to
group A, as interference with another workload. A stand-in runtime with the baseline's settings
(`hr_v2_idle_900-nlHmoN61QS`, created 01:42 UTC) was then refused too; it was deleted at 01:45
UTC without receiving a request. So the 120 s reclaim question (a 130 s follow-up on a 900 s
runtime) and the cost after a 900 s timeout remain open. Commands for whoever runs them,
with three extra waits that would show whether the post-timeout window scales with the timeout:

```
$PY scripts/v2study/invoke.py --name hr_v2_proto_http_v2 --protocol http --new 5 --reuse-waits 30,75,130 --label waits \
  --out docs/runtime-v2-evidence/E11/hr_v2_proto_http_v2.waits.jsonl
$PY scripts/v2study/invoke.py --name hr_v2_proto_http_v2 --protocol http --new 3 --reuse-waits 960 --label idle-16min \
  --out docs/runtime-v2-evidence/E11/hr_v2_proto_http_v2.idle-16min.jsonl
# optional: 5 s, 30 s and 120 s past the 900 s timeout
$PY scripts/v2study/invoke.py --name hr_v2_proto_http_v2 --protocol http --new 3 --reuse-waits 905 --label idle-905s \
  --out docs/runtime-v2-evidence/E11/hr_v2_proto_http_v2.idle-905s.jsonl
$PY scripts/v2study/invoke.py --name hr_v2_proto_http_v2 --protocol http --new 3 --reuse-waits 930 --label idle-930s \
  --out docs/runtime-v2-evidence/E11/hr_v2_proto_http_v2.idle-930s.jsonl
$PY scripts/v2study/invoke.py --name hr_v2_proto_http_v2 --protocol http --new 3 --reuse-waits 1020 --label idle-1020s \
  --out docs/runtime-v2-evidence/E11/hr_v2_proto_http_v2.idle-1020s.jsonl
$PY scripts/v2study/collect.py docs/runtime-v2-evidence/E11/*.jsonl --md docs/runtime-v2-evidence/E11/results.md
```

## Commands used

```
PY=<scratchpad>/venv/bin/python
$PY scripts/v2study/create.py create hr_v2_idle_60 --image py --protocol HTTP --platform V2 --env MODE=http --idle 60 --experiment E11
$PY scripts/v2study/invoke.py --name hr_v2_idle_60 --protocol http --new 5 --reuse-waits 30,75,130 --label waits \
  --out docs/runtime-v2-evidence/E11/hr_v2_idle_60.waits.jsonl
for w in 45 65 90 105; do   # then 55, 65 (label sweep-65b), 115, 125
  $PY scripts/v2study/invoke.py --name hr_v2_idle_60 --protocol http --new 3 --reuse-waits $w --label sweep-$w \
    --out docs/runtime-v2-evidence/E11/hr_v2_idle_60.sweep-$w.jsonl &
done; wait
$PY scripts/v2study/invoke.py --name hr_v2_idle_60 --protocol http --new 4 --reuse-waits 65,1 --label sweep-65-retry \
  --out docs/runtime-v2-evidence/E11/hr_v2_idle_60.sweep-65-retry.jsonl
$PY scripts/v2study/collect.py docs/runtime-v2-evidence/E11/*.jsonl --md docs/runtime-v2-evidence/E11/results.md
# 502 records: filter_log_events on /aws/vendedlogs/bedrock-agentcore/hr-v2-study by session id;
# container logs: /aws/bedrock-agentcore/runtimes/hr_v2_idle_60-FrtEc49DAQ-DEFAULT, stream runtime-logs-<session id>
$PY scripts/v2study/create.py delete hr_v2_idle_60 --wait
```

## Addendum by the main session: the baseline (idle 900 s), 01:47 to 02:06 UTC

Run from the main session on `hr_v2_proto_http_v2` (idle timeout 900 s), one new session per
process in parallel; lines in `hr_v2_proto_http_v2.waits.*.jsonl`, `.idle-920s.*.jsonl` and
`.idle-16min.*.jsonl`, tables in `results-baseline.md` (30 requests, 30 joined).

| idle before the follow-up | n | same process | client_ms | receipt_to_handler_ms | to_receipt_ms |
| --- | --- | --- | --- | --- | --- |
| 30 s | 5 | 5 of 5 | 181 (175 to 195) | 74 | 73 |
| 75 s | 5 | 5 of 5 | 177 (164 to 201) | 83 | 64 |
| 130 s | 5 | 5 of 5 | 174 (164 to 180) | 70 | 62 |
| 920 s (20 s past the timeout) | 2 | 0 of 2 | 2867 and 7552 | 2420 and 6258 | 750 and 876 |
| 960 s (60 s past the timeout) | 3 | 0 of 3 | 2381, 2408, 2975 | 1866 to 2018 | 382 to 839 |

- Within the 900 s timeout a follow-up costs the same at 30, 75 and 130 s idle. The 120 s
  memory reclaim the pricing page describes has no visible cost: the 130 s follow-up is 70 ms
  receipt to handler and 2 minor faults, the same as at 30 s.
- Past the timeout the same session id restores a fresh process, as on the 60 s runtime. 20 s
  past the timeout one of two follow-ups took 7.6 s (the window the 60 s runtime showed) and
  one 2.9 s; 60 s past the timeout all three took 2.4 to 3.0 s, which is a plain restore plus
  0.4 to 0.8 s more between the client's send and the runtime's receipt stamp (`to_receipt_ms`
  382 to 876 ms against about 60 for a new session id). So the HR runtimes' setting has the same
  shape: a user whose session idled past 15 minutes pays at least a restore and, in the first
  minute after the timeout, sometimes 7 s or more.
