Collected 2026-10-05 02:35 UTC from docs/runtime-v2-evidence/E15/hr_v2_cred_v2.65min.jsonl, docs/runtime-v2-evidence/E15/hr_v2_cred_v2.72min.jsonl, docs/runtime-v2-evidence/E15/hr_v2_cred_v2.after-ready.jsonl.

20 requests ok, 0 failed, 16 joined to runtime records.

| runtime | label | kind | step | burst | wait | client_ms | to_receipt_ms | receipt_to_handler_ms | work_ms | handler_to_done_ms | record_ms | done_to_client_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hr_v2_cred_v2 | after-ready | followup | invocations |  | 0 | 183 (179 to 186, n=2) | - | - | 6 (6 to 6, n=2) | - | - | - |
| hr_v2_cred_v2 | after-ready | new | invocations |  |  | 2707 (2605 to 2810, n=2) | - | - | 808 (770 to 847, n=2) | - | - | - |
| hr_v2_cred_v2 | build-plus-65min | followup | invocations |  | 0 | 189 (182 to 196, n=2) | 71 (66 to 75, n=2) | 80 (75 to 84, n=2) | 7 (6 to 9, n=2) | 16 (15 to 17, n=2) | 103 (101 to 104, n=2) | 16 (15 to 16, n=2) |
| hr_v2_cred_v2 | build-plus-65min | new | invocations |  |  | 4299 (3615 to 4984, n=2) | 138 (82 to 194, n=2) | 2338 (2271 to 2404, n=2) | 1682 (1132 to 2233, n=2) | 76 (30 to 122, n=2) | 4097 (3434 to 4759, n=2) | 65 (31 to 99, n=2) |
| hr_v2_cred_v2 | build-plus-72min | followup | invocations |  | 0 | 192 (174 to 231, n=6) | 64 (62 to 71, n=6) | 78 (72 to 111, n=6) | 6 (5 to 8, n=6) | 17 (14 to 19, n=6) | 102 (92 to 136, n=6) | 23 (15 to 31, n=6) |
| hr_v2_cred_v2 | build-plus-72min | new | invocations |  |  | 2069 (1925 to 2156, n=6) | 69 (66 to 125, n=6) | 1907 (1721 to 1964, n=6) | 40 (39 to 45, n=6) | 17 (14 to 21, n=6) | 1965 (1781 to 2022, n=6) | 39 (17 to 66, n=6) |

First five new sessions of a runtime (after READY or a deploy) against the rest, receipt_to_handler_ms:

| runtime | label | first 5 | rest | first 5 client_ms | rest client_ms |
| --- | --- | --- | --- | --- | --- |
| hr_v2_cred_v2 | after-ready | - | - | 2707 (2605 to 2810, n=2) | - |
| hr_v2_cred_v2 | build-plus-65min | 2338 (2271 to 2404, n=2) | - | 4299 (3615 to 4984, n=2) | - |
| hr_v2_cred_v2 | build-plus-72min | 1865 (1708 to 1954, n=5) | 1970 | 2028 (1908 to 2122, n=5) | 2183 |

What the restored instances report, per runtime (distinct values across answers):

| runtime | answers | boot_id | hostname | pid | first_random | random at request | mem_total_mb | cpus | rss_mb (median) | minflt delta (median) | mono_since_start_s | wall_since_start_s (snapshot age) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hr_v2_cred_v2 | 20 | 2 | 1 | 1 | 2 | 6 | [8017.0] | [2] | 98 | 106 | 66.3 to 69.4 | 105.2 to 4070.0 |
