Collected 2026-10-05 01:07 UTC from docs/runtime-v2-evidence/E4/hr_v2_lang_go_v1.after-ready.jsonl, docs/runtime-v2-evidence/E4/hr_v2_lang_go_v2.after-ready.jsonl, docs/runtime-v2-evidence/E4/hr_v2_lang_node_v2.after-ready.jsonl, docs/runtime-v2-evidence/E1/hr_v2_proto_http_v2.after-ready.jsonl, docs/runtime-v2-evidence/E1/hr_v2_proto_http_v1.later.jsonl.

310 requests ok, 0 failed, 307 joined to runtime records.

| runtime | label | kind | step | burst | wait | client_ms | to_receipt_ms | receipt_to_handler_ms | work_ms | handler_to_done_ms | record_ms | done_to_client_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hr_v2_lang_go_v1 | after-ready | followup | invocations |  | 0 | 149 (135 to 201, n=50) | 63 (57 to 81, n=50) | 51 (44 to 67, n=50) | 0 (0 to 0, n=50) | 15 (13 to 21, n=50) | 66 (58 to 85, n=50) | 17 (15 to 22, n=50) |
| hr_v2_lang_go_v1 | after-ready | new | invocations |  |  | 456 (399 to 526, n=25) | 64 (58 to 76, n=25) | 344 (309 to 378, n=25) | 0 (0 to 0, n=25) | 16 (14 to 23, n=25) | 366 (324 to 398, n=25) | 18 (15 to 30, n=25) |
| hr_v2_lang_go_v2 | after-ready | followup | invocations |  | 0 | 168 (157 to 202, n=50) | 60 (54 to 71, n=50) | 71 (64 to 89, n=50) | 0 (0 to 0, n=50) | 17 (13 to 25, n=50) | 89 (80 to 115, n=50) | 18 (16 to 23, n=50) |
| hr_v2_lang_go_v2 | after-ready | new | invocations |  |  | 1803 (1567 to 2042, n=25) | 61 (51 to 73, n=25) | 1690 (1470 to 1924, n=25) | 0 (0 to 0, n=25) | 17 (14 to 53, n=25) | 1733 (1493 to 1942, n=25) | 18 (16 to 19, n=25) |
| hr_v2_lang_node_v2 | after-ready | followup | invocations |  | 0 | 171 (153 to 189, n=50) | 59 (52 to 67, n=48) | 73 (67 to 80, n=48) | 0 (0 to 1, n=50) | 17 (15 to 26, n=48) | 92 (84 to 106, n=48) | 18 (16 to 22, n=48) |
| hr_v2_lang_node_v2 | after-ready | new | invocations |  |  | 1972 (1666 to 2334, n=25) | 64 (54 to 76, n=24) | 1796 (1545 to 2185, n=24) | 3 (2 to 3, n=25) | 18 (15 to 23, n=24) | 1819 (1565 to 2205, n=24) | 18 (16 to 23, n=24) |
| hr_v2_proto_http_v1 | later | followup | invocations |  | 0 | 154 (138 to 183, n=50) | 64 (57 to 76, n=50) | 53 (44 to 63, n=50) | 0 (0 to 0, n=50) | 15 (14 to 21, n=50) | 69 (60 to 81, n=50) | 17 (15 to 23, n=50) |
| hr_v2_proto_http_v1 | later | new | invocations |  |  | 486 (419 to 856, n=25) | 62 (56 to 70, n=25) | 387 (324 to 741, n=25) | 0 (0 to 0, n=25) | 16 (13 to 21, n=25) | 403 (339 to 756, n=25) | 17 (16 to 24, n=25) |
| hr_v2_proto_http_v2 | after-ready | followup | invocations |  | 0 | 174 (168 to 181, n=5) | 67 (61 to 68, n=5) | 73 (67 to 75, n=5) | 0 (0 to 0, n=5) | 14 (13 to 17, n=5) | 86 (82 to 91, n=5) | 17 (16 to 34, n=5) |
| hr_v2_proto_http_v2 | after-ready | new | invocations |  |  | 1922 (1897 to 2086, n=5) | 66 (62 to 135, n=5) | 1810 (1672 to 1980, n=5) | 0 (0 to 0, n=5) | 18 (15 to 22, n=5) | 1828 (1690 to 1997, n=5) | 23 (16 to 93, n=5) |

First five new sessions of a runtime (after READY or a deploy) against the rest, receipt_to_handler_ms:

| runtime | label | first 5 | rest | first 5 client_ms | rest client_ms |
| --- | --- | --- | --- | --- | --- |
| hr_v2_lang_go_v1 | after-ready | 364 (328 to 374, n=5) | 343 (305 to 378, n=20) | 456 (427 to 524, n=5) | 455 (397 to 494, n=20) |
| hr_v2_lang_go_v2 | after-ready | 1750 (1633 to 1977, n=5) | 1634 (1462 to 1884, n=20) | 1957 (1726 to 2138, n=5) | 1739 (1550 to 1983, n=20) |
| hr_v2_lang_node_v2 | after-ready | 1856 (471 to 2126, n=4) | 1796 (1556 to 2183, n=20) | 2041 (1788 to 2391, n=5) | 1944 (1655 to 2299, n=20) |
| hr_v2_proto_http_v1 | later | 804 (616 to 819, n=5) | 370 (322 to 443, n=20) | 900 (772 to 920, n=5) | 474 (416 to 550, n=20) |
| hr_v2_proto_http_v2 | after-ready | 1810 (1672 to 1980, n=5) | - | 1922 (1897 to 2086, n=5) | - |

What the restored instances report, per runtime (distinct values across answers):

| runtime | answers | boot_id | hostname | pid | first_random | random at request | mem_total_mb | cpus | rss_mb (median) | minflt delta (median) | mono_since_start_s | wall_since_start_s (snapshot age) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hr_v2_lang_go_v1 | 75 | 2 | 1 | 1 | 25 | 75 | [8017] | [2] | 5 | 10 | 3.0 to 3.7 | 11.2 to 115.8 |
| hr_v2_lang_go_v2 | 75 | 2 | 1 | 1 | 2 | 29 | [8016] | [2] | 5 | 10 | 70.8 to 71.9 | 197.2 to 272.8 |
| hr_v2_lang_node_v2 | 75 | 2 | 1 | 1 | 2 | 6 | [8017] | [2] | 51 | 10 | 68.7 to 79.1 | 459.2 to 539.5 |
| hr_v2_proto_http_v1 | 75 | 2 | 1 | 1 | 25 | 75 | [8017.0] | [2] | 51 | 0 | 3.1 to 6.0 | 11.1 to 327.8 |
| hr_v2_proto_http_v2 | 10 | 2 | 1 | 1 | 2 | 4 | [8017.0] | [2] | 51 | 0 | 66.2 to 78.0 | 126.3 to 137.6 |
