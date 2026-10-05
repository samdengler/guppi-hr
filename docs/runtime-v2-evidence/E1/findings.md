# E1. Protocol and platform: HTTP, MCP and A2A on V1 and V2

Group A, run on 5 October 2026 between 00:52 and 01:04 UTC (4 October in Seattle). The text
was returned to the main session, which saved it here.

## Hypothesis

A new V2 session costs a platform floor of about 2 s regardless of protocol, while V1's warm pool answers in under 1 s. The MCP `initialize` and the A2A `message/send` pay the same restore as HTTP. A follow-up on an existing session costs about 0.2 s on both platforms.

## Runtimes

All six use the `py` image, SigV4, PUBLIC network, the default lifecycle (idle 900 s) and version 1. Times are UTC.

| runtime | id | platform | protocol | created | READY | build |
| --- | --- | --- | --- | --- | --- | --- |
| hr_v2_proto_http_v2 | tVcBJN3RW3 | V2 | HTTP, MODE=http | 00:49:09 | 00:52:14 | 184.9 s |
| hr_v2_proto_http_v1 | 0Y1WTR7hS5 | V1 | HTTP, MODE=http | 00:49:24 | 00:49:31 | 6.6 s |
| hr_v2_proto_mcp_v2 | 0Tqkzs8gHR | V2 | MCP, MODE=mcp | 00:54:25 | 00:57:30 | 185.4 s |
| hr_v2_proto_mcp_v1 | mCaEWr7Ip5 | V1 | MCP, MODE=mcp | 00:54:25 | 00:54:31 | 6.1 s |
| hr_v2_proto_a2a_v2 | J50nbWCJoi | V2 | A2A, MODE=a2a | 00:54:25 | 00:57:30 | 185.4 s |
| hr_v2_proto_a2a_v1 | kAUsY6FeRX | V1 | A2A, MODE=a2a | 00:54:25 | 00:54:31 | 6.1 s |

The main session created the two HTTP runtimes. Group A created the four MCP and A2A runtimes in parallel; all four reached READY on the first try and were deleted at 01:23 to 01:30.

## What was run

Every session was new, sent one at a time one second apart, followed at once by two follow-ups on the same session. MCP sessions send `initialize` and then `tools/call` of `probe_tool`, so an MCP session carries four requests and the others three.

| file | window (UTC) | sessions | requests |
| --- | --- | --- | --- |
| hr_v2_proto_http_v2.after-ready.jsonl (main session) | 00:52:38 to 00:52:53 | 5 | 10 |
| hr_v2_proto_http_v2.later.jsonl | 00:54:32 to 00:55:36 | 20 | 60 |
| hr_v2_proto_http_v1.later.jsonl | 00:54:32 to 00:55:18 | 25 | 75 |
| hr_v2_proto_mcp_v1.after-ready.jsonl | 00:54:41 to 00:55:35 | 25 | 100 |
| hr_v2_proto_a2a_v1.after-ready.jsonl | 00:54:42 to 00:55:38 | 25 | 75 |
| hr_v2_proto_mcp_v2.after-ready.jsonl | 00:57:46 to 00:59:12 | 25 | 100 |
| hr_v2_proto_a2a_v2.after-ready.jsonl | 00:57:46 to 00:59:08 | 25 | 75 |
| hr_v2_proto_a2a_v2.later.jsonl | 01:02:56 to 01:04:17 | 25 | 75 |

There were 570 requests, 0 failures and 0 throttles; 495 joined to the runtime's records. The 75 A2A V2 after-ready lines have no records (see the log delivery failure below), so the A2A V2 `later` run was added after the delivery was fixed.

The first five sessions after READY on `hr_v2_proto_http_v1` went to three smoke sessions by the main session that are not in the evidence, so that runtime has no after-ready set. Its 25 sessions are labelled `later`. `hr_v2_proto_http_v2` has its first five after READY in the main session's `after-ready` file and 20 more in `later`.

## Results

New sessions (first request of the session), median and maximum, ms. For MCP the first request is `initialize`. Its answer carries no telemetry, so `receipt_to_handler` is missing there and `record_ms` (receipt to completion) stands in for it.

| runtime | label | n | receipt_to_handler med / max | record_ms med / max | client_ms med / max |
| --- | --- | --- | --- | --- | --- |
| http_v2 | after-ready | 5 | 1810 / 2083 | 1828 / 2099 | 1922 / 2187 |
| http_v2 | later | 20 | 1753 / 2204 | 1778 / 2221 | 1868 / 2308 |
| mcp_v2 (initialize) | after-ready | 25 | - | 1841 / 2263 | 1915 / 2370 |
| a2a_v2 | after-ready | 25 | no records | no records | 1980 / 2499 |
| a2a_v2 | later | 25 | 1782 / 2146 | 1800 / 2170 | 1873 / 2260 |
| http_v1 | later | 25 | 387 / 828 | 403 / 842 | 486 / 929 |
| mcp_v1 (initialize) | after-ready | 25 | - | 390 / 5319 | 476 / 5487 |
| a2a_v1 | after-ready | 25 | 378 / 7372 | 396 / 7391 | 479 / 7581 |

Requests on an existing session, ms. For MCP, `same-session` is the `tools/call` right after `initialize` and `followup` is the two calls after that.

| runtime | kind | n | receipt_to_handler med / max | record_ms med / max | client_ms med / max |
| --- | --- | --- | --- | --- | --- |
| http_v2 | followup (later) | 40 | 75 / 128 | 95 / 142 | 178 / 234 |
| mcp_v2 | same-session tools/call | 25 | 76 / 110 | 93 / 128 | 178 / 217 |
| mcp_v2 | followup | 50 | 72 / 104 | 91 / 120 | 175 / 211 |
| a2a_v2 | followup (later) | 50 | 76 / 104 | 94 / 190 | 175 / 256 |
| http_v1 | followup | 50 | 53 / 100 | 69 / 114 | 154 / 230 |
| mcp_v1 | same-session tools/call | 25 | 55 / 104 | 73 / 120 | 163 / 206 |
| mcp_v1 | followup | 50 | 53 / 494 | 71 / 514 | 158 / 591 |
| a2a_v1 | followup | 50 | 52 / 80 | 70 / 96 | 152 / 179 |

First five new sessions against the rest (from results.md), median (p10 to p90):

| runtime | label | first 5 | rest | first 5 client_ms | rest client_ms |
| --- | --- | --- | --- | --- | --- |
| hr_v2_proto_a2a_v1 | after-ready | 410 (332 to 3325, n=5) | 374 (334 to 477, n=20) | 522 (425 to 3468, n=5) | 478 (426 to 573, n=20) |
| hr_v2_proto_a2a_v2 | after-ready | - | - | 2061 (1923 to 2378, n=5) | 1930 (1685 to 2298, n=20) |
| hr_v2_proto_a2a_v2 | later | 1789 (1638 to 2023, n=5) | 1766 (1535 to 1986, n=20) | 1885 (1735 to 2172, n=5) | 1859 (1639 to 2077, n=20) |
| hr_v2_proto_http_v1 | later | 804 (616 to 819, n=5) | 370 (322 to 443, n=20) | 900 (772 to 920, n=5) | 474 (416 to 550, n=20) |
| hr_v2_proto_http_v2 | after-ready | 1810 (1672 to 1980, n=5) | - | 1922 (1897 to 2086, n=5) | - |
| hr_v2_proto_http_v2 | later | 1738 (1518 to 2077, n=5) | 1755 (1492 to 1991, n=15) | 1834 (1621 to 2233, n=5) | 1877 (1592 to 2086, n=15) |
| hr_v2_proto_mcp_v1 | after-ready | - | - | 477 (441 to 3496, n=5) | 475 (430 to 551, n=20) |
| hr_v2_proto_mcp_v2 | after-ready | - | - | 1843 (1723 to 2130, n=5) | 1938 (1702 to 2295, n=20) |

## Conclusion

The hypothesis holds. A new V2 session costs 1.75 to 1.85 s on the runtime's records for HTTP, MCP `initialize` and A2A alike (protocol differences under 0.15 s, so none), against 0.39 to 0.40 s on V1. The gap of about 1.4 s sits between the runtime's receipt and the handler's first line; the handler's own work is under 1 ms. On an existing session both platforms deliver in 0.15 to 0.18 s at the client; V2 adds about 20 ms on the records, which counts as none by the study's rule. The first five V2 sessions after READY cost the same as later ones.

## MCP session ids and record counts

The invoker passes `runtimeSessionId` and `mcpSessionId` with the same value, so the records cannot show which of the two the runtime keys on. Every record's `session_id` and `attributes.session.id` carry that shared value, and the container's `X-Amzn-Bedrock-AgentCore-Runtime-Session-Id` header equals it on all 300 MCP answers. The records count each MCP request separately: `initialize` and `tools/call` each get their own record and request id, so a new MCP session shows two records before the follow-ups (100 records for 100 requests on `hr_v2_proto_mcp_v2`). The restore lands on `initialize` (1841 ms on the records); the `tools/call` right after it costs 93 ms, so the first tool result of a new MCP session on V2 arrives about 2.1 s after the client starts.

## Surprises and AWS behavior

- V1 does not have its pool ready at READY. On both fresh V1 runtimes the first session (10 s after READY) booted a new container: 5.3 s on the records, with the process starting 4.6 s after the client sent. `hr_v2_proto_a2a_v1` booted another one on its 16th session (7.4 s, process started 5.4 s after the send), so its pool ran dry within 40 s of READY at one session every two seconds.
- V1 pool instances are pre-started and paused. Each V1 session has its own process (25 distinct first random values in 25 sessions), started up to 318 s before the request by the wall clock but only 3 to 6 s by the monotonic clock. On `hr_v2_proto_http_v1`, sessions served by instances paused about 5 minutes took 0.6 to 0.8 s from receipt to handler, against 0.35 s for instances paused about 12 s (n=9 against n=16; suggestive only).
- Each V2 runtime has two snapshots. Every answer comes from one of two processes started 1 to 2 s apart, each on its own `boot_id`. The same two `boot_id` values appear on all three V2 runtimes, and the three V1 runtimes share two other `boot_id` values, so the guest kernel is booted once and shared across runtimes. The container then runs about 66 s before the snapshot, and READY follows about 35 s later.
- Python's `random` module is not reseeded on restore. Across 75 answers per V2 runtime there are 6 distinct `random.random()` values: every session restored from the same snapshot draws the same sequence (3 requests per session, 2 snapshots). `os.urandom`, `uuid4` and the kernel's random UUID differ on every answer. The kernel pool is reseeded; user-space generators seeded before the snapshot are not. E13 covers this; it is worth telling AWS.
- Log delivery failure. `create.py` creates the `APPLICATION_LOGS` delivery after READY and ignored a `ConflictException` from `CreateDelivery`. For `hr_v2_proto_a2a_v2` the delivery source was created and the delivery was not, so its after-ready requests left no records. The delivery was added by hand at 01:02:23 (`aws logs create-delivery`) and the 25 `later` sessions were run at 01:02:56. Six other study runtimes had the same gap at 01:03 (reported to the main session). With several creates finishing at once, CloudWatch Logs appears to answer one `CreateDelivery` with a conflict and drop it. Deleting four runtimes in parallel hit the same conflict on `DeleteDelivery`; a sequential rerun removed the deliveries and sources.

## Commands

```
PY=<scratch venv python>
$PY scripts/v2study/create.py create hr_v2_proto_mcp_v2 --image py --protocol MCP --platform V2 --env MODE=mcp --experiment E1
$PY scripts/v2study/create.py create hr_v2_proto_mcp_v1 --image py --protocol MCP --platform V1 --env MODE=mcp --experiment E1
$PY scripts/v2study/create.py create hr_v2_proto_a2a_v2 --image py --protocol A2A --platform V2 --env MODE=a2a --experiment E1
$PY scripts/v2study/create.py create hr_v2_proto_a2a_v1 --image py --protocol A2A --platform V1 --env MODE=a2a --experiment E1
$PY scripts/v2study/invoke.py --name hr_v2_proto_http_v2 --protocol http --new 20 --followups 2 --label later --out docs/runtime-v2-evidence/E1/hr_v2_proto_http_v2.later.jsonl
$PY scripts/v2study/invoke.py --name hr_v2_proto_http_v1 --protocol http --new 25 --followups 2 --label later --out docs/runtime-v2-evidence/E1/hr_v2_proto_http_v1.later.jsonl
$PY scripts/v2study/invoke.py --name hr_v2_proto_mcp_v1 --protocol mcp --new 25 --followups 2 --label after-ready --out docs/runtime-v2-evidence/E1/hr_v2_proto_mcp_v1.after-ready.jsonl
$PY scripts/v2study/invoke.py --name hr_v2_proto_a2a_v1 --protocol a2a --new 25 --followups 2 --label after-ready --out docs/runtime-v2-evidence/E1/hr_v2_proto_a2a_v1.after-ready.jsonl
$PY scripts/v2study/invoke.py --name hr_v2_proto_mcp_v2 --protocol mcp --new 25 --followups 2 --label after-ready --out docs/runtime-v2-evidence/E1/hr_v2_proto_mcp_v2.after-ready.jsonl
$PY scripts/v2study/invoke.py --name hr_v2_proto_a2a_v2 --protocol a2a --new 25 --followups 2 --label after-ready --out docs/runtime-v2-evidence/E1/hr_v2_proto_a2a_v2.after-ready.jsonl
aws logs create-delivery --region us-east-1 --delivery-source-name hr-v2-study-hr_v2_proto_a2a_v2 --delivery-destination-arn arn:aws:logs:us-east-1:009080466601:delivery-destination:hr-v2-study-logs --tags hr-v2-study=2026-10-04
$PY scripts/v2study/invoke.py --name hr_v2_proto_a2a_v2 --protocol a2a --new 25 --followups 2 --label later --out docs/runtime-v2-evidence/E1/hr_v2_proto_a2a_v2.later.jsonl
$PY scripts/v2study/collect.py docs/runtime-v2-evidence/E1/*.jsonl --md docs/runtime-v2-evidence/E1/results.md
for n in hr_v2_proto_mcp_v2 hr_v2_proto_mcp_v1 hr_v2_proto_a2a_v2 hr_v2_proto_a2a_v1; do $PY scripts/v2study/create.py delete $n --wait; done
```
