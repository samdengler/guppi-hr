Collected 2026-10-05 01:01 UTC from docs/runtime-v2-evidence/E2/hr_v2_image_1500.after-ready.jsonl, docs/runtime-v2-evidence/E2/hr_v2_image_500.after-ready.jsonl.

150 requests ok, 0 failed, 150 joined to runtime records.

| runtime | label | kind | step | burst | wait | client_ms | to_receipt_ms | receipt_to_handler_ms | work_ms | handler_to_done_ms | record_ms | done_to_client_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hr_v2_image_1500 | after-ready | followup | invocations |  | 0 | 169 (152 to 193, n=50) | 62 (54 to 72, n=50) | 71 (64 to 82, n=50) | 0 (0 to 0, n=50) | 17 (14 to 23, n=50) | 89 (80 to 106, n=50) | 18 (15 to 23, n=50) |
| hr_v2_image_1500 | after-ready | new | invocations |  |  | 1882 (1667 to 2141, n=25) | 61 (53 to 74, n=25) | 1782 (1560 to 2040, n=25) | 0 (0 to 0, n=25) | 16 (14 to 24, n=25) | 1796 (1581 to 2055, n=25) | 18 (16 to 22, n=25) |
| hr_v2_image_500 | after-ready | followup | invocations |  | 0 | 170 (157 to 201, n=50) | 62 (54 to 70, n=50) | 73 (66 to 90, n=50) | 0 (0 to 0, n=50) | 17 (14 to 23, n=50) | 92 (82 to 108, n=50) | 18 (16 to 23, n=50) |
| hr_v2_image_500 | after-ready | new | invocations |  |  | 1953 (1624 to 2330, n=25) | 61 (51 to 71, n=25) | 1868 (1531 to 2232, n=25) | 0 (0 to 0, n=25) | 16 (13 to 21, n=25) | 1882 (1546 to 2248, n=25) | 17 (15 to 20, n=25) |

First five new sessions of a runtime (after READY or a deploy) against the rest, receipt_to_handler_ms:

| runtime | label | first 5 | rest | first 5 client_ms | rest client_ms |
| --- | --- | --- | --- | --- | --- |
| hr_v2_image_1500 | after-ready | 1940 (1775 to 2382, n=5) | 1725 (1523 to 2018, n=20) | 2081 (1890 to 2491, n=5) | 1814 (1635 to 2117, n=20) |
| hr_v2_image_500 | after-ready | 2029 (1658 to 2200, n=5) | 1827 (1528 to 2238, n=20) | 2215 (1746 to 2292, n=5) | 1914 (1617 to 2339, n=20) |

What the restored instances report, per runtime (distinct values across answers):

| runtime | answers | boot_id | hostname | pid | first_random | random at request | mem_total_mb | cpus | rss_mb (median) | minflt delta (median) | mono_since_start_s | wall_since_start_s (snapshot age) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hr_v2_image_1500 | 75 | 2 | 1 | 1 | 2 | 6 | [8017.0] | [2] | 51 | 1 | 69.1 to 70.6 | 135.0 to 213.7 |
| hr_v2_image_500 | 75 | 2 | 1 | 1 | 2 | 6 | [8017.0] | [2] | 51 | 0 | 73.3 to 84.6 | 151.4 to 230.5 |
