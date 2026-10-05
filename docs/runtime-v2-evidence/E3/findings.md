# E3: memory touched before the snapshot

Hypothesis: memory dirtied before the snapshot but never read costs nothing at restore; the same memory read on the first request costs page faults of 50 to 200 microseconds per 4 KB page, so 128 MB read would take about 1.6 to 6 s.

Run: hr_v2_touch_64 (TOUCH_MB=64), hr_v2_touch_256 (TOUCH_MB=256), hr_v2_fault_32 (TOUCH_ON_REQUEST_MB=32), hr_v2_fault_128 (TOUCH_ON_REQUEST_MB=128); image py, V2, HTTP, version 1, build_s 186.0, 185.6, 185.7, 185.5. Invoked 00:58 to 01:00 UTC (25 new sessions, 2 follow-ups each, label after-ready). Collected with 2-minute wait.

Log delivery problem: hr_v2_fault_32 and hr_v2_touch_256 had no CloudWatch delivery on first run (create.py swallowed a ConflictException when six creates ran in parallel), so their original runs have no runtime records, only client and handler telemetry. After attaching deliveries (01:03 UTC) both were rerun with 25 new sessions and 2 follow-ups, label after-ready-rerun, and those joined (24 or 25 of 25 new). Handler telemetry (work, faults, rss) is complete for all runs.

## Result

| runtime | label | new receipt_to_handler_ms | new client_ms | follow-up client_ms | work_ms new | rss_mb |
| --- | --- | --- | --- | --- | --- | --- |
| baseline hr_v2_proto_http_v2 (E1, n=5) | after-ready | 1810 | 1922 | 174 | 0 | 51 |
| hr_v2_touch_64 | after-ready | 1812 (1660 to 2105) | 1914 | 169 | 0 | 118 |
| hr_v2_touch_256 | after-ready-rerun | 1866 (1579 to 2285) | 1960 | 170 | 0 | 319 |
| hr_v2_fault_32 | after-ready-rerun | 1816 (1550 to 2154) | 1913 | 171 | 1 | 84 |
| hr_v2_fault_128 | after-ready | 1803 (1574 to 2064) | 1905 | 172 | 2 | 185 |

Original runs without records: touch_256 client_ms new 2046, fault_32 new 1965.

Fault telemetry (first request of each new session vs follow-up, 25 and 50 samples per fault_128 and 25 and 50 for fault_32 in the first run):

| runtime | fault_read_ms new (median, max) | fault_read_ms follow-up | minflt delta first request | minflt delta follow-up | majflt delta |
| --- | --- | --- | --- | --- | --- |
| hr_v2_fault_32 | 0.8, 1.1 | 0.5, 0.8 | 0 (max 2) | 0 | 0 |
| hr_v2_fault_128 | 2.0, 3.4 | 2.0, 3.4 | 1 (max 2) | 0 | 0 |

## Cost per MB read

Reading 128 MB on the first request took 2.0 ms median, which is 16 microseconds per MB, or 0.06 microseconds per 4 KB page. Reading 32 MB took 0.8 ms, 25 microseconds per MB. The follow-up read took the same time (2.0 ms for 128 MB; 0.5 ms for 32 MB). The guest saw 0 to 2 minor faults and 0 major faults across the loop, for 8192 to 32768 pages, so the guest kernel recorded no page faults at all. The predicted 50 to 200 microseconds per page would have been 1.6 to 6.5 s for 128 MB; the measured cost is about 3000 times lower.

## Conclusion

Neither dirtying memory before the snapshot nor reading it on the first request moves the restore or the handler: receipt to handler stays 1.80 to 1.87 s for 64, 256, 32 and 128 MB variants, equal to the baseline within 0.06 s, and the first-request read loop costs at most 3 ms. The hypothesis half about unread pages costing nothing holds; the half about read pages costing 50 to 200 microseconds each does not hold in the guest's view. Either guest memory is fully resident when the instance resumes (the cost sits in the roughly 1.8 s restore, which does not grow with 256 MB of extra RSS: 1866 vs 1810 ms, within noise), or faults are served below the guest and invisible to /proc.

## Notes

- Restore does not scale with snapshot memory from 51 MB to 319 MB RSS. A larger test (1 to 4 GB) would show whether a size dependency exists beyond this range.
- The fault loop reads one byte per page presumably; 32768 pages in 2 ms is 60 ns per page, consistent with resident memory.
- AWS feedback item: the create_delivery ConflictException seen under parallel creation silently dropped log delivery for 2 of 6 runtimes; this is a tool bug in create.py, not an AWS defect, but worth noting for parallel runs.

## Commands

    $PY scripts/v2study/create.py create hr_v2_touch_64 --image py --protocol HTTP --platform V2 --env MODE=http --env TOUCH_MB=64 --experiment E3
    (same for hr_v2_touch_256 TOUCH_MB=256, hr_v2_fault_32 TOUCH_ON_REQUEST_MB=32, hr_v2_fault_128 TOUCH_ON_REQUEST_MB=128)
    aws logs create-delivery --delivery-source-name hr-v2-study-<name> --delivery-destination-arn arn:aws:logs:us-east-1:009080466601:delivery-destination:hr-v2-study-logs
    $PY scripts/v2study/invoke.py --name <name> --protocol http --new 25 --followups 2 --label after-ready[-rerun] --out docs/runtime-v2-evidence/E3/<name>.<label>.jsonl
    $PY scripts/v2study/collect.py docs/runtime-v2-evidence/E3/*.jsonl --md docs/runtime-v2-evidence/E3/results.md
    $PY scripts/v2study/create.py delete <name> --wait
