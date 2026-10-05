# E4: Language (Python, Node, Go)

## Hypothesis

A compiled server touches fewer pages per request, so Go restores a few hundred ms faster than Python on V2, but not below the platform floor. Node sits between. On V1 the language makes no difference.

## What was run

Runtimes (HTTP, MODE=http, experiment E4), created 2026-10-05 00:54 UTC:

| runtime | image | platform | build_s |
| --- | --- | --- | --- |
| hr_v2_lang_node_v2 | node (v24.21.0) | V2 | 185.6 |
| hr_v2_lang_go_v2 | go (go1.25.14) | V2 | 185.5 |
| hr_v2_lang_go_v1 | go | V1 | 6.1 |

Each: 25 new sessions, 2 follow-ups each (75 requests), label after-ready, 0 failures. Go V1 ran about 00:58 UTC, Go V2 and the Node first run about 01:00 UTC. The Node runtime had no CloudWatch log delivery during its first run (create.py swallowed a conflict); the delivery was added and Node was rerun at 01:03 UTC. The first Node run (client numbers only: new median 1961 ms, follow-up 173 ms) is kept as `hr_v2_lang_node_v2.first-run-nologs.txt`; the Node rows below are from the rerun, which kept the label after-ready. 307 of 310 requests joined to runtime records (Node: 1 new session and 2 follow-ups unjoined, 24 of 25 new sessions joined). Delivery confirmed for all three runtimes.

Python comparison: E1 `hr_v2_proto_http_v2.after-ready` (5 sessions, V2) and `hr_v2_proto_http_v1.later` (25 sessions, V1; the V1 runtime has no after-ready file). Collected 2026-10-05 01:07 UTC. Full table: `results.md`.

## Results (median, ms)

New sessions:

| runtime | n | client_ms | receipt_to_handler_ms | work_ms |
| --- | --- | --- | --- | --- |
| Python V2 (E1) | 5 | 1922 | 1810 | 0.3 |
| Node V2 | 25 | 1972 | 1796 | 3 |
| Go V2 | 25 | 1803 | 1690 | 0.1 |
| Python V1 (E1, later) | 25 | 486 | 387 | 0.3 |
| Go V1 | 25 | 456 | 344 | 0.1 |

Follow-ups: Python V2 174 client / 73 receipt_to_handler; Node V2 171 / 73; Go V2 168 / 71; Python V1 154 / 53; Go V1 149 / 51.

Memory and faults (telemetry): rss_mb Python 51, Node 51, Go 5 (both platforms). minflt delta across the handler's work: Go 10, Node 10, Python 0 (the Python probe differs in what it touches, so this column is not a language comparison). majflt delta 0 everywhere. work_ms: Node new sessions 3 ms (max 3.2), follow-ups 0.5 ms; Go 0.1 ms; Python 0.3 ms.

## Conclusion

Language does not move the restore time. On V2, Go is 120 ms below Python in receipt_to_handler (within the 0.15 s "none" band, and Python's n is 5) and Node matches Python; all three sit near 1.7 to 1.8 s. The hypothesis of a few hundred ms from a compiled server is not supported: the V2 restore cost is independent of the 5 MB Go process against the 51 MB Node and Python processes. On V1 Go is 43 ms below Python (none). The first five V1 sessions after READY were slower for Go by the same small margin as for Python (364 vs 343 ms).

## Telemetry

- boot_id: 2 distinct values per runtime across 75 answers (one per snapshot generation, shared by restored instances); the 25 V1 sessions also show 2.
- pid is 1 and hostname localhost everywhere. kernel_uuid is distinct for every answer (75 of 75) on all runtimes.
- first_random (drawn before the snapshot): 2 distinct on Go V2 and Node V2, 25 distinct on Go V1. Go 1.25 seeds math/rand per process, so on V2 the repeats show that the value comes from the snapshot, not from a fresh process.
- Random draws at request time: on V1 all 75 are distinct. On V2 Go math/rand yields 29 distinct of 75 and Node Math.random, crypto-derived urandom and uuid4 yield 6 distinct of 75 (Python E1: 4 of 10). Restored instances therefore share generator state taken at snapshot time. Go's urandom and uuid4 (from the OS) stayed distinct (75 of 75), so the sharing is in userspace generators; the Node urandom/uuid4 repeats also point at a userspace-held pool.
- Monotonic clock is frozen at the snapshot (V2 mono_since_start 69 to 79 s, V1 3 to 4 s); wall_since_start (snapshot age) 111 to 540 s on V2.

## Surprising or worth telling AWS

Random state is duplicated across independent restored sessions on V2 in all three languages (any token or id derived from userspace random state after restore can collide between users). Go and Node built images took the same 185 s on V2 regardless of image size.

## Commands

    PY=<scratchpad>/venv/bin/python
    $PY scripts/v2study/create.py create hr_v2_lang_node_v2 --image node --protocol HTTP --platform V2 --env MODE=http --experiment E4
    $PY scripts/v2study/create.py create hr_v2_lang_go_v2 --image go --protocol HTTP --platform V2 --env MODE=http --experiment E4
    $PY scripts/v2study/create.py create hr_v2_lang_go_v1 --image go --protocol HTTP --platform V1 --env MODE=http --experiment E4
    $PY scripts/v2study/invoke.py --name <name> --protocol http --new 25 --followups 2 --label after-ready --out docs/runtime-v2-evidence/E4/<name>.after-ready.jsonl
    $PY scripts/v2study/collect.py docs/runtime-v2-evidence/E4/*.jsonl docs/runtime-v2-evidence/E1/hr_v2_proto_http_v2.after-ready.jsonl docs/runtime-v2-evidence/E1/hr_v2_proto_http_v1.later.jsonl --md docs/runtime-v2-evidence/E4/results.md
    $PY scripts/v2study/create.py delete <name> --wait
