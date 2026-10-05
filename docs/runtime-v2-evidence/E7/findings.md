# E7. First restores after a deploy against later restores and after idle: findings

Run by the main session on 5 October 2026 on a dedicated runtime, `hr_v2_cache_v2`
(id `hr_v2_cache_v2-M5sHrk6eJD`, V2, HTTP, image `py`, `MODE=http`, SigV4, PUBLIC, idle
900 s). Lines: `hr_v2_cache_v2.*.jsonl`; tables: `results.md` (80 requests, 76 joined; the
first two after-ready requests landed before the log delivery existed).

## Hypothesis

The first sessions after a deploy are the slowest (snapshot chunks come from S3 or the AZ
cache, not the host cache), later sessions are faster as hosts hold the chunks, and a
snapshot idle for hours slows down again.

## What was run

| label | sent (UTC) | what | new sessions |
| --- | --- | --- | --- |
| after-ready | 00:58 to 00:59 | version 1, 3 to 70 s after READY (build 185 s) | 5 |
| idle-30min | 01:29 | version 1 after 30 idle minutes | 5 |
| idle-2h | 02:59 | version 1 after 90 more idle minutes | 5 |
| after-redeploy | 03:03 | version 2 (an environment variable added, build 189 s), 3 to 20 s after READY | 5 |
| after-redeploy-later | 03:04 to 03:05 | version 2, 20 to 80 s after READY | 20 |

Every session had one follow-up right after.

## Results

New sessions, median (p10 to p90), ms:

| label | client_ms | receipt_to_handler_ms | follow-up client_ms |
| --- | --- | --- | --- |
| after-ready (version 1) | 1782 (1729 to 2188, n=5) | 1886 (1649 to 2165, n=3) | 167 |
| idle-30min | 2150 (1750 to 2312, n=5) | 2054 (1634 to 2190, n=5) | 178 |
| idle-2h | 1734 (1645 to 2084, n=5) | 1638 (1539 to 1897, n=5) | 188 |
| after-redeploy (version 2, first five) | 2093 (1864 to 2225, n=5) | 1944 (1757 to 2026, n=5) | 185 |
| after-redeploy-later (version 2) | 1972 (1740 to 2285, n=20) | 1832 (1612 to 2071, n=20) | 182 |

Across the study the same holds on every runtime: the "first five" after READY against the
rest differ by under 0.15 s (E1 to E6 tables), and the 108 burst sessions of E8 restored
from snapshots 5 to 17 minutes old at the same speed.

## Conclusion

The hypothesis is not supported for the restore itself. The first five sessions after a
deploy, the sessions after 30 minutes and 2 hours of idle, and the later ones all restore in
1.6 to 2.1 s, with the differences inside the two-snapshot spread (A32) and the sample noise.
There is no visible snapshot cache warmth on V2's restore, so the "first minute after a
deploy" cost the HR path showed (A21, 7.5 to 9.6 s) and the 18.3 s Profile answer of 4 Oct
are not a slow restore. They are the slow window inside the restored instance: for 20 to
35 s after READY, and on the first sessions after an idle hour, file reads and outbound
calls are ten to twenty times slower (E5: lazy imports 6.7 to 8.1 s against 0.65 s; E14: a
first STS call 0.74 to 1.02 s against 37 ms; E15: 1.0 and 2.4 s on the first two sessions
after an idle hour, 40 ms on the next six). A probe whose handler does no I/O, like this one,
does not see it. For the HR agents the work done after the restore (model calls, Identity,
the gateway) is what that window slows, and only waiting it out or doing nothing in the
first request helps.

## For AWS

The restore is stable over time (good), and the slow I/O window after READY and after idle
is the thing to document and shorten (A31, A37).

## Commands

```
PY=<scratch venv python>
$PY scripts/v2study/create.py create hr_v2_cache_v2 --image py --protocol HTTP --platform V2 --env MODE=http --experiment E7
$PY scripts/v2study/invoke.py --name hr_v2_cache_v2 --protocol http --new 5 --followups 1 --label after-ready --out docs/runtime-v2-evidence/E7/hr_v2_cache_v2.after-ready.jsonl
sleep 1800; ... --label idle-30min ...
sleep 7200; ... --label idle-2h ...
$PY scripts/v2study/create.py update hr_v2_cache_v2 --env BUMP=1
... --new 5 --label after-redeploy ...; ... --new 20 --label after-redeploy-later ...
$PY scripts/v2study/collect.py docs/runtime-v2-evidence/E7/*.jsonl --md docs/runtime-v2-evidence/E7/results.md
$PY scripts/v2study/create.py delete hr_v2_cache_v2 --wait
```
