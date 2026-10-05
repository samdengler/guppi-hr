Collected 2026-10-05 01:08 UTC from docs/runtime-v2-evidence/E14/hr_v2_out_sts.after-ready.jsonl.

75 requests ok, 0 failed, 75 joined to runtime records.

| runtime | label | kind | step | burst | wait | client_ms | to_receipt_ms | receipt_to_handler_ms | work_ms | handler_to_done_ms | record_ms | done_to_client_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hr_v2_out_sts | after-ready | followup | invocations |  | 0 | 173 (153 to 194, n=50) | 58 (50 to 68, n=50) | 70 (65 to 84, n=50) | 6 (5 to 6, n=50) | 16 (14 to 22, n=50) | 94 (85 to 106, n=50) | 18 (16 to 24, n=50) |
| hr_v2_out_sts | after-ready | new | invocations |  |  | 1940 (1690 to 2922, n=25) | 58 (53 to 77, n=25) | 1728 (1565 to 2207, n=25) | 38 (35 to 784, n=25) | 16 (14 to 21, n=25) | 1843 (1616 to 2782, n=25) | 19 (16 to 23, n=25) |

First five new sessions of a runtime (after READY or a deploy) against the rest, receipt_to_handler_ms:

| runtime | label | first 5 | rest | first 5 client_ms | rest client_ms |
| --- | --- | --- | --- | --- | --- |
| hr_v2_out_sts | after-ready | 1872 (1711 to 2475, n=5) | 1711 (1557 to 2036, n=20) | 3088 (2631 to 3354, n=5) | 1846 (1680 to 2193, n=20) |

What the restored instances report, per runtime (distinct values across answers):

| runtime | answers | boot_id | hostname | pid | first_random | random at request | mem_total_mb | cpus | rss_mb (median) | minflt delta (median) | mono_since_start_s | wall_since_start_s (snapshot age) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hr_v2_out_sts | 75 | 2 | 1 | 1 | 2 | 6 | [8017.0] | [2] | 98 | 2 | 66.2 to 68.9 | 107.8 to 191.7 |
