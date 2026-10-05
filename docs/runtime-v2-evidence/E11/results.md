Collected 2026-10-05 01:22 UTC from docs/runtime-v2-evidence/E11/hr_v2_idle_60.waits.jsonl.

20 requests ok, 0 failed, 20 joined to runtime records.

| runtime | label | kind | step | burst | wait | client_ms | to_receipt_ms | receipt_to_handler_ms | work_ms | handler_to_done_ms | record_ms | done_to_client_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hr_v2_idle_60 | waits | followup | invocations |  | 130 | 1960 (1722 to 2430, n=5) | 62 (59 to 70, n=5) | 1852 (1628 to 2324, n=5) | 0 (0 to 0, n=5) | 18 (14 to 23, n=5) | 1872 (1643 to 2346, n=5) | 18 (16 to 23, n=5) |
| hr_v2_idle_60 | waits | followup | invocations |  | 30 | 176 (163 to 190, n=5) | 60 (54 to 69, n=5) | 82 (68 to 85, n=5) | 0 (0 to 0, n=5) | 16 (15 to 27, n=5) | 100 (90 to 104, n=5) | 19 (16 to 19, n=5) |
| hr_v2_idle_60 | waits | followup | invocations |  | 75 | 7274 (6902 to 11549, n=5) | 61 (58 to 77, n=5) | 7102 (6810 to 11442, n=5) | 0 (0 to 0, n=5) | 15 (15 to 63, n=5) | 7195 (6827 to 11457, n=5) | 18 (17 to 19, n=5) |
| hr_v2_idle_60 | waits | new | invocations |  |  | 1897 (1837 to 2101, n=5) | 59 (54 to 108, n=5) | 1801 (1726 to 1944, n=5) | 0 (0 to 0, n=5) | 21 (16 to 48, n=5) | 1822 (1743 to 1992, n=5) | 20 (18 to 38, n=5) |

First five new sessions of a runtime (after READY or a deploy) against the rest, receipt_to_handler_ms:

| runtime | label | first 5 | rest | first 5 client_ms | rest client_ms |
| --- | --- | --- | --- | --- | --- |
| hr_v2_idle_60 | waits | 1801 (1726 to 1944, n=5) | - | 1897 (1837 to 2101, n=5) | - |

What the restored instances report, per runtime (distinct values across answers):

| runtime | answers | boot_id | hostname | pid | first_random | random at request | mem_total_mb | cpus | rss_mb (median) | minflt delta (median) | mono_since_start_s | wall_since_start_s (snapshot age) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hr_v2_idle_60 | 20 | 2 | 1 | 1 | 2 | 4 | [8017.0] | [2] | 51 | 1 | 67.5 to 106.4 | 122.2 to 1362.9 |
