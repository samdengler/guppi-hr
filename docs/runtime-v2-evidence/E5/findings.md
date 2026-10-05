# E5. Python import depth and bytecode: findings

Run on 5 October 2026 between 00:55 and 01:09 UTC by the group D sub-agent (the text was
returned to the main session, which saved it here).

## Hypothesis

From the plan: imports done before the snapshot cost nothing at restore beyond the pages the request touches, so `IMPORTS=heavy` is within 0.2 s of the baseline; the same imports done in the first request cost seconds on every new session (the 18.3 s Profile answer of 4 October before priming); bytecode in the image matters only when imports run after the restore.

## Runtimes and runs

All four are platform V2, protocol HTTP, `MODE=http`, SigV4, PUBLIC network, idle timeout 900 s, version 1. Created in parallel at 00:55:18 UTC; all four were READY at 00:58:24 UTC.

| runtime | id | image | knobs | build_s |
| --- | --- | --- | --- | --- |
| hr_v2_imp_heavy | hr_v2_imp_heavy-muybFRGjav | py | `IMPORTS=heavy` | 185.9 |
| hr_v2_imp_lazy | hr_v2_imp_lazy-MKv81S771R | py | `IMPORTS=heavy`, `LAZY_IMPORTS=1` | 185.3 |
| hr_v2_imp_nopyc | hr_v2_imp_nopyc-QT67113d95 | py-nopyc | `IMPORTS=none` | 185.5 |
| hr_v2_imp_heavy_nopyc | hr_v2_imp_heavy_nopyc-WrPON0BKVG | py-nopyc | `IMPORTS=heavy` | 185.7 |

The baseline `hr_v2_proto_http_v2` (group A) took 184.9 s. The heavy imports and the compilation without bytecode run before `/ping` and did not lengthen the build: every snapshot was taken 66 to 78 s after the process started (`mono_since_start_s`), whatever the imports cost.

Each run is 25 new sessions sent one at a time (pace 1 s), with 2 follow-ups per session (50 follow-ups):

- `after-ready` on all four, 00:58:27 to 01:00:27 UTC, started 3 s after READY.
- `rerun` on `hr_v2_imp_nopyc` and `hr_v2_imp_heavy`, 01:05:07 to 01:06:33 UTC. `hr_v2_imp_nopyc` had no log delivery until 01:03 UTC (see the failures below), so its `after-ready` lines have no runtime records; the rerun supplies them. `hr_v2_imp_heavy` was rerun in the same window as a control.

Collected at 01:08 UTC: 450 requests, 0 failed, 375 joined to runtime records. The 75 not joined are the `hr_v2_imp_nopyc` `after-ready` lines. Runtimes deleted at 01:19 UTC. The baseline rows come from `docs/runtime-v2-evidence/E1/results.md`.

## Results

New sessions and follow-ups, from `results.md` (medians, p10 to p90):

| runtime | label | kind | client_ms | receipt_to_handler_ms | work_ms | record_ms |
| --- | --- | --- | --- | --- | --- | --- |
| hr_v2_proto_http_v2 (baseline) | after-ready | new | 1922 (1897 to 2086, n=5) | 1810 (1672 to 1980, n=5) | 0 | 1828 (1690 to 1997, n=5) |
| hr_v2_proto_http_v2 (baseline) | later | new | 1868 (1599 to 2121, n=20) | 1753 (1496 to 1999, n=20) | 0 | 1778 (1513 to 2013, n=20) |
| hr_v2_imp_heavy | after-ready | new | 1892 (1679 to 2104, n=25) | 1772 (1569 to 2007, n=25) | 0 | 1786 (1587 to 2023, n=25) |
| hr_v2_imp_heavy | rerun | new | 1985 (1737 to 2193, n=25) | 1879 (1637 to 2084, n=25) | 0 | 1895 (1655 to 2103, n=25) |
| hr_v2_imp_heavy_nopyc | after-ready | new | 1903 (1624 to 2190, n=25) | 1804 (1522 to 2090, n=25) | 0 | 1819 (1541 to 2106, n=25) |
| hr_v2_imp_nopyc | after-ready | new | 1926 (1610 to 2428, n=25) | no records | 0 | no records |
| hr_v2_imp_nopyc | rerun | new | 1904 (1609 to 2347, n=25) | 1789 (1512 to 2232, n=25) | 0 | 1811 (1532 to 2249, n=25) |
| hr_v2_imp_lazy | after-ready | new | 2706 (2313 to 6745, n=25) | 1786 (1551 to 2148, n=25) | 670 (607 to 4370, n=25) | 2623 (2230 to 6616, n=25) |
| hr_v2_proto_http_v2 (baseline) | after-ready | followup | 174 (168 to 181, n=5) | 73 (67 to 75, n=5) | 0 | 86 (82 to 91, n=5) |
| hr_v2_imp_heavy | after-ready | followup | 169 (152 to 194, n=50) | 70 (63 to 83, n=50) | 0 | 86 (79 to 102, n=50) |
| hr_v2_imp_heavy_nopyc | after-ready | followup | 166 (156 to 184, n=50) | 71 (65 to 79, n=50) | 0 | 87 (81 to 100, n=50) |
| hr_v2_imp_nopyc | rerun | followup | 174 (157 to 203, n=50) | 74 (66 to 84, n=50) | 0 | 92 (82 to 103, n=50) |
| hr_v2_imp_lazy | after-ready | followup | 165 (155 to 197, n=50) | 69 (64 to 85, n=50) | 0 | 87 (79 to 110, n=50) |

Telemetry from the probe's answers (new sessions):

| runtime | start.import_ms (snapshot A / B) | rss_mb at request | minflt delta in handler | majflt delta in handler |
| --- | --- | --- | --- | --- |
| baseline | none | 50.6 | 0 | 0 |
| hr_v2_imp_heavy | 645.6 / 878.1 (before the snapshot) | 84.1 | 2 | 0 |
| hr_v2_imp_heavy_nopyc | 2252.9 / 2661.9 (before the snapshot) | 87.7 | 0 | 0 |
| hr_v2_imp_nopyc | none | 53.3 | 0 | 0 |
| hr_v2_imp_lazy | done in the first request | 50.6 before, 84.0 after | 8431 | 43 to 44 |

Lazy imports (`work.lazy_import_ms`) by order after READY:

| new sessions | sent (UTC) | lazy_import_ms |
| --- | --- | --- |
| 1st to 3rd | 00:58:28 to 00:58:50 | 7178, 8062, 6652 |
| 4th to 25th | 00:59:01 to 01:00:20 | 658 (606 to 938, n=22), min 596, max 947 |

Follow-ups on `hr_v2_imp_lazy` did no import work (`work_ms` 0.3).

Each runtime was served from two snapshots (two `boot_id` and two `first_random` values). On snapshot B the guest took about 1.5 s longer to reach Python start and the imports ran 25 to 35 percent slower during its build. B also restores slower. Receipt to handler per snapshot, new sessions:

| runtime | label | snapshot A | snapshot B |
| --- | --- | --- | --- |
| hr_v2_imp_heavy | after-ready | 1608 (n=13) | 1890 (n=12) |
| hr_v2_imp_heavy | rerun | 1745 (n=12) | 1924 (n=13) |
| hr_v2_imp_heavy_nopyc | after-ready | 1786 (n=13) | 1875 (n=12) |
| hr_v2_imp_nopyc | rerun | 1708 (n=19) | 1980 (n=6) |
| hr_v2_imp_lazy | after-ready | 1652 (n=16) | 1944 (n=9) |

## Conclusion

Imports done before the snapshot cost nothing at restore. `heavy`, `heavy_nopyc` and `nopyc` restore in 1772 to 1879 ms receipt to handler against 1753 to 1810 ms for the baseline, and the handler faults in 0 to 2 pages. The same imports done in the first request cost 0.6 to 0.95 s on every new session once the runtime has been READY for about half a minute, and 6.7 to 8.1 s on the first three new sessions after READY. "Seconds on every new session" therefore holds only right after a deploy. Shipping without bytecode moved 1.6 to 1.8 s into the build (2.25 to 2.66 s of imports against 0.65 to 0.88 s) and 3.6 MB into RSS, and changed nothing at restore. A lazy import without bytecode was not run, so its cost after a restore is not measured here.

## Surprising

- The lazy imports on the first three new sessions took ten times as long as later ones, with the same page fault counts (8431 minor, 43 to 44 major). The storage behind the image's files on a restored instance is slow for 20 to 35 s after READY and fast afterwards. E14 shows the same pattern for the first outbound call. The 18.3 s Profile answer is consistent with lazy work landing in that window.
- `build_s` stayed at 185.3 to 185.9 s with 0.6 to 2.7 s of imports before `/ping`. The snapshot is taken more than a minute after process start regardless.
- The snapshot a session lands on moves receipt to handler by 0.1 to 0.3 s (A against B), more than any knob in this experiment. Medians of runtimes with different A to B mixes differ by up to 0.2 s for that reason alone. The `rerun` of `hr_v2_imp_heavy` (1879 ms) against its `after-ready` run (1772 ms) is that effect.
- `random at request` has 6 distinct values across 75 answers on every runtime: restored instances of one snapshot draw the same sequence from Python's `random` (E13).
- On the very first request to `hr_v2_imp_heavy`, the runtime's receipt stamp is 2070 ms after the client sent the request and 111 ms after the handler started (`receipt_to_handler_ms` of -111). The record therefore did not cover that restore. It is the low end (567 ms p10) of that runtime's "first five" receipt to handler.

## Failures and AWS behavior

- No request failed.
- `hr_v2_imp_nopyc` was created without a log delivery, as were `hr_v2_prime_clients` and `hr_v2_prime_routes` in E6. `create.py` swallowed a `ConflictException` from `create_delivery` when seven runtimes attached at once. The deliveries were added at 01:03 UTC, and the runtime records for requests before then are lost. The rerun covers the gap.
- For AWS: file reads on a restored instance are about ten times slower for the first 20 to 35 s after READY (lazy imports 6.7 to 8.1 s against 0.6 to 0.95 s). One runtime record also stamped its receipt after the handler had started.

## Commands

```
PY=<scratch venv python>
B="--protocol HTTP --platform V2 --env MODE=http"
$PY scripts/v2study/create.py create hr_v2_imp_heavy --image py $B --env IMPORTS=heavy --experiment E5
$PY scripts/v2study/create.py create hr_v2_imp_lazy --image py $B --env IMPORTS=heavy --env LAZY_IMPORTS=1 --experiment E5
$PY scripts/v2study/create.py create hr_v2_imp_nopyc --image py-nopyc $B --experiment E5
$PY scripts/v2study/create.py create hr_v2_imp_heavy_nopyc --image py-nopyc $B --env IMPORTS=heavy --experiment E5
# after READY, in parallel per runtime:
$PY scripts/v2study/invoke.py --name <name> --protocol http --new 25 --followups 2 --label after-ready --out docs/runtime-v2-evidence/E5/<name>.after-ready.jsonl
# 01:05 UTC, hr_v2_imp_nopyc and hr_v2_imp_heavy:
$PY scripts/v2study/invoke.py --name <name> --protocol http --new 25 --followups 2 --label rerun --out docs/runtime-v2-evidence/E5/<name>.rerun.jsonl
# 2 minutes after the last request:
$PY scripts/v2study/collect.py docs/runtime-v2-evidence/E5/*.jsonl --md docs/runtime-v2-evidence/E5/results.md
$PY scripts/v2study/create.py delete <name> --wait
```
