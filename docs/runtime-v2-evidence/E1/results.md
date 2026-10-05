Collected 2026-10-05 01:06 UTC from docs/runtime-v2-evidence/E1/hr_v2_proto_a2a_v1.after-ready.jsonl, docs/runtime-v2-evidence/E1/hr_v2_proto_a2a_v2.after-ready.jsonl, docs/runtime-v2-evidence/E1/hr_v2_proto_a2a_v2.later.jsonl, docs/runtime-v2-evidence/E1/hr_v2_proto_http_v1.later.jsonl, docs/runtime-v2-evidence/E1/hr_v2_proto_http_v2.after-ready.jsonl, docs/runtime-v2-evidence/E1/hr_v2_proto_http_v2.later.jsonl, docs/runtime-v2-evidence/E1/hr_v2_proto_mcp_v1.after-ready.jsonl, docs/runtime-v2-evidence/E1/hr_v2_proto_mcp_v2.after-ready.jsonl.

570 requests ok, 0 failed, 495 joined to runtime records.

| runtime | label | kind | step | burst | wait | client_ms | to_receipt_ms | receipt_to_handler_ms | work_ms | handler_to_done_ms | record_ms | done_to_client_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hr_v2_proto_a2a_v1 | after-ready | followup | message/send |  | 0 | 152 (142 to 171, n=50) | 63 (58 to 72, n=50) | 52 (45 to 64, n=50) | 0 (0 to 0, n=50) | 16 (14 to 24, n=50) | 70 (62 to 84, n=50) | 18 (17 to 22, n=50) |
| hr_v2_proto_a2a_v1 | after-ready | new | message/send |  |  | 479 (426 to 731, n=25) | 65 (59 to 79, n=25) | 378 (333 to 632, n=25) | 0 (0 to 0, n=25) | 17 (14 to 20, n=25) | 396 (348 to 650, n=25) | 19 (18 to 21, n=25) |
| hr_v2_proto_a2a_v2 | after-ready | followup | message/send |  | 0 | 176 (156 to 203, n=50) | - | - | 0 (0 to 0, n=50) | - | - | - |
| hr_v2_proto_a2a_v2 | after-ready | new | message/send |  |  | 1980 (1693 to 2314, n=25) | - | - | 0 (0 to 0, n=25) | - | - | - |
| hr_v2_proto_a2a_v2 | later | followup | message/send |  | 0 | 175 (160 to 211, n=50) | 60 (52 to 77, n=50) | 76 (68 to 87, n=50) | 0 (0 to 0, n=50) | 17 (15 to 24, n=50) | 94 (85 to 117, n=50) | 19 (17 to 21, n=50) |
| hr_v2_proto_a2a_v2 | later | new | message/send |  |  | 1873 (1643 to 2172, n=25) | 60 (54 to 70, n=25) | 1782 (1543 to 2023, n=25) | 0 (0 to 0, n=25) | 18 (14 to 22, n=25) | 1800 (1564 to 2038, n=25) | 19 (18 to 25, n=25) |
| hr_v2_proto_http_v1 | later | followup | invocations |  | 0 | 154 (138 to 183, n=50) | 64 (57 to 76, n=50) | 53 (44 to 63, n=50) | 0 (0 to 0, n=50) | 15 (14 to 21, n=50) | 69 (60 to 81, n=50) | 17 (15 to 23, n=50) |
| hr_v2_proto_http_v1 | later | new | invocations |  |  | 486 (419 to 856, n=25) | 62 (56 to 70, n=25) | 387 (324 to 741, n=25) | 0 (0 to 0, n=25) | 16 (13 to 21, n=25) | 403 (339 to 756, n=25) | 17 (16 to 24, n=25) |
| hr_v2_proto_http_v2 | after-ready | followup | invocations |  | 0 | 174 (168 to 181, n=5) | 67 (61 to 68, n=5) | 73 (67 to 75, n=5) | 0 (0 to 0, n=5) | 14 (13 to 17, n=5) | 86 (82 to 91, n=5) | 17 (16 to 34, n=5) |
| hr_v2_proto_http_v2 | after-ready | new | invocations |  |  | 1922 (1897 to 2086, n=5) | 66 (62 to 135, n=5) | 1810 (1672 to 1980, n=5) | 0 (0 to 0, n=5) | 18 (15 to 22, n=5) | 1828 (1690 to 1997, n=5) | 23 (16 to 93, n=5) |
| hr_v2_proto_http_v2 | later | followup | invocations |  | 0 | 178 (157 to 191, n=40) | 63 (54 to 76, n=40) | 75 (67 to 92, n=40) | 0 (0 to 0, n=40) | 17 (14 to 20, n=40) | 95 (84 to 106, n=40) | 17 (15 to 21, n=40) |
| hr_v2_proto_http_v2 | later | new | invocations |  |  | 1868 (1599 to 2121, n=20) | 65 (57 to 73, n=20) | 1753 (1496 to 1999, n=20) | 0 (0 to 0, n=20) | 17 (14 to 27, n=20) | 1778 (1513 to 2013, n=20) | 17 (16 to 20, n=20) |
| hr_v2_proto_mcp_v1 | after-ready | followup | tools/call |  | 0 | 158 (144 to 184, n=50) | 66 (59 to 75, n=50) | 53 (47 to 67, n=50) | 0 (0 to 0, n=50) | 17 (14 to 22, n=50) | 71 (62 to 90, n=50) | 20 (17 to 25, n=50) |
| hr_v2_proto_mcp_v1 | after-ready | new | initialize |  |  | 476 (427 to 552, n=25) | 67 (58 to 75, n=25) | - | - | - | 390 (348 to 468, n=25) | 17 (15 to 19, n=25) |
| hr_v2_proto_mcp_v1 | after-ready | same-session | tools/call |  |  | 163 (143 to 181, n=25) | 67 (57 to 78, n=25) | 55 (47 to 64, n=25) | 0 (0 to 0, n=25) | 17 (15 to 21, n=25) | 73 (64 to 81, n=25) | 19 (18 to 24, n=25) |
| hr_v2_proto_mcp_v2 | after-ready | followup | tools/call |  | 0 | 175 (161 to 195, n=50) | 64 (54 to 74, n=50) | 72 (67 to 86, n=50) | 0 (0 to 0, n=50) | 17 (15 to 22, n=50) | 91 (84 to 103, n=50) | 19 (17 to 24, n=50) |
| hr_v2_proto_mcp_v2 | after-ready | new | initialize |  |  | 1915 (1700 to 2263, n=25) | 63 (58 to 76, n=25) | - | - | - | 1841 (1584 to 2145, n=25) | 19 (16 to 24, n=25) |
| hr_v2_proto_mcp_v2 | after-ready | same-session | tools/call |  |  | 178 (166 to 211, n=25) | 65 (57 to 74, n=25) | 76 (68 to 88, n=25) | 0 (0 to 0, n=25) | 17 (15 to 21, n=25) | 93 (85 to 119, n=25) | 19 (18 to 23, n=25) |

First five new sessions of a runtime (after READY or a deploy) against the rest, receipt_to_handler_ms:

| runtime | label | first 5 | rest | first 5 client_ms | rest client_ms |
| --- | --- | --- | --- | --- | --- |
| hr_v2_proto_a2a_v1 | after-ready | 410 (332 to 3325, n=5) | 374 (334 to 477, n=20) | 522 (425 to 3468, n=5) | 478 (426 to 573, n=20) |
| hr_v2_proto_a2a_v2 | after-ready | - | - | 2061 (1923 to 2378, n=5) | 1930 (1685 to 2298, n=20) |
| hr_v2_proto_a2a_v2 | later | 1789 (1638 to 2023, n=5) | 1766 (1535 to 1986, n=20) | 1885 (1735 to 2172, n=5) | 1859 (1639 to 2077, n=20) |
| hr_v2_proto_http_v1 | later | 804 (616 to 819, n=5) | 370 (322 to 443, n=20) | 900 (772 to 920, n=5) | 474 (416 to 550, n=20) |
| hr_v2_proto_http_v2 | after-ready | 1810 (1672 to 1980, n=5) | - | 1922 (1897 to 2086, n=5) | - |
| hr_v2_proto_http_v2 | later | 1738 (1518 to 2077, n=5) | 1755 (1492 to 1991, n=15) | 1834 (1621 to 2233, n=5) | 1877 (1592 to 2086, n=15) |
| hr_v2_proto_mcp_v1 | after-ready | - | - | 477 (441 to 3496, n=5) | 475 (430 to 551, n=20) |
| hr_v2_proto_mcp_v2 | after-ready | - | - | 1843 (1723 to 2130, n=5) | 1938 (1702 to 2295, n=20) |

What the restored instances report, per runtime (distinct values across answers):

| runtime | answers | boot_id | hostname | pid | first_random | random at request | mem_total_mb | cpus | rss_mb (median) | minflt delta (median) | mono_since_start_s | wall_since_start_s (snapshot age) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hr_v2_proto_a2a_v1 | 75 | 2 | 1 | 1 | 25 | 75 | [8017.0] | [2] | 78 | 1 | 0.8 to 6.0 | 0.8 to 32.7 |
| hr_v2_proto_a2a_v2 | 150 | 2 | 1 | 1 | 2 | 6 | [8017.0] | [2] | 79 | 1 | 66.1 to 68.3 | 117.6 to 507.7 |
| hr_v2_proto_http_v1 | 75 | 2 | 1 | 1 | 25 | 75 | [8017.0] | [2] | 51 | 0 | 3.1 to 6.0 | 11.1 to 327.8 |
| hr_v2_proto_http_v2 | 70 | 2 | 1 | 1 | 2 | 6 | [8017.0] | [2] | 51 | 0 | 66.0 to 78.3 | 126.3 to 300.4 |
| hr_v2_proto_mcp_v1 | 75 | 2 | 1 | 1 | 25 | 75 | [8017.0] | [2] | 59 | 1 | 1.0 to 5.9 | 1.0 to 40.0 |
| hr_v2_proto_mcp_v2 | 75 | 2 | 1 | 1 | 2 | 6 | [8017.0] | [2] | 59 | 0 | 66.5 to 67.9 | 117.7 to 201.8 |
