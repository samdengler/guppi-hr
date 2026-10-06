Collected 2026-10-06 12:32 UTC from docs/runtime-v2-evidence/D60/hr_v2_obo_a2a.negative-grant.jsonl, docs/runtime-v2-evidence/D60/hr_v2_obo_a2a.runtime-grant-obo-provider.jsonl, docs/runtime-v2-evidence/D60/hr_v2_obo_a2a.runtime-grant.jsonl.

16 requests ok, 0 failed, 16 joined to runtime records.

| runtime | label | kind | step | burst | wait | client_ms | to_receipt_ms | receipt_to_handler_ms | work_ms | handler_to_done_ms | record_ms | done_to_client_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hr_v2_obo_a2a | negative-grant | followup | message/send |  | 0 | 415 (411 to 418, n=2) | 106 (103 to 108, n=2) | 214 (209 to 220, n=2) | 0 (0 to 0, n=2) | 72 (67 to 76, n=2) | 286 (276 to 297, n=2) | 23 (18 to 27, n=2) |
| hr_v2_obo_a2a | negative-grant | new | message/send |  |  | 7603 (7541 to 7665, n=2) | 218 (135 to 302, n=2) | 2147 (2119 to 2174, n=2) | 0 (0 to 0, n=2) | 5206 (5079 to 5333, n=2) | 7353 (7198 to 7508, n=2) | 32 (22 to 41, n=2) |
| hr_v2_obo_a2a | runtime-grant | followup | message/send |  | 0 | 408 (384 to 420, n=3) | 100 (100 to 100, n=3) | 204 (194 to 215, n=3) | 0 (0 to 0, n=3) | 77 (70 to 82, n=3) | 281 (264 to 298, n=3) | 21 (19 to 26, n=3) |
| hr_v2_obo_a2a | runtime-grant | new | message/send |  |  | 2503 (2389 to 2616, n=3) | 108 (106 to 186, n=3) | 2031 (2021 to 2247, n=3) | 0 (0 to 0, n=3) | 216 (206 to 237, n=3) | 2273 (2242 to 2459, n=3) | 24 (19 to 31, n=3) |
| hr_v2_obo_a2a | runtime-grant-obo-provider | followup | message/send |  | 0 | 511 (501 to 568, n=3) | 115 (99 to 124, n=3) | 203 (198 to 214, n=3) | 0 (0 to 0, n=3) | 159 (149 to 208, n=3) | 356 (351 to 421, n=3) | 28 (22 to 59, n=3) |
| hr_v2_obo_a2a | runtime-grant-obo-provider | new | message/send |  |  | 2452 (2190 to 2549, n=3) | 136 (116 to 194, n=3) | 1995 (1706 to 2002, n=3) | 0 (0 to 0, n=3) | 289 (279 to 317, n=3) | 2281 (2023 to 2283, n=3) | 57 (36 to 79, n=3) |

First five new sessions of a runtime (after READY or a deploy) against the rest, receipt_to_handler_ms:

| runtime | label | first 5 | rest | first 5 client_ms | rest client_ms |
| --- | --- | --- | --- | --- | --- |
| hr_v2_obo_a2a | negative-grant | 2147 (2119 to 2174, n=2) | - | 7603 (7541 to 7665, n=2) | - |
| hr_v2_obo_a2a | runtime-grant | 2031 (2021 to 2247, n=3) | - | 2503 (2389 to 2616, n=3) | - |
| hr_v2_obo_a2a | runtime-grant-obo-provider | 1995 (1706 to 2002, n=3) | - | 2452 (2190 to 2549, n=3) | - |

What the restored instances report, per runtime (distinct values across answers):

| runtime | answers | boot_id | hostname | pid | first_random | random at request | mem_total_mb | cpus | rss_mb (median) | minflt delta (median) | mono_since_start_s | wall_since_start_s (snapshot age) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hr_v2_obo_a2a | 16 | 2 | 1 | 1 | 2 | 4 | [8017.0] | [2] | 86 | 1 | 66.4 to 72.9 | 247.5 to 351.3 |
