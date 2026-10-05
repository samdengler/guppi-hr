Collected 2026-10-05 01:22 UTC from docs/runtime-v2-evidence/E8/hr_v2_proto_http_v1.burst-1.jsonl, docs/runtime-v2-evidence/E8/hr_v2_proto_http_v1.burst-10.jsonl, docs/runtime-v2-evidence/E8/hr_v2_proto_http_v1.burst-20.jsonl, docs/runtime-v2-evidence/E8/hr_v2_proto_http_v1.burst-5.jsonl, docs/runtime-v2-evidence/E8/hr_v2_proto_http_v2.burst-1.jsonl, docs/runtime-v2-evidence/E8/hr_v2_proto_http_v2.burst-10.jsonl, docs/runtime-v2-evidence/E8/hr_v2_proto_http_v2.burst-20.jsonl, docs/runtime-v2-evidence/E8/hr_v2_proto_http_v2.burst-5.jsonl.

216 requests ok, 0 failed, 216 joined to runtime records.

| runtime | label | kind | step | burst | wait | client_ms | to_receipt_ms | receipt_to_handler_ms | work_ms | handler_to_done_ms | record_ms | done_to_client_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hr_v2_proto_http_v1 | burst-1 | burst | invocations | 1 |  | 586 (453 to 694, n=3) | 63 (51 to 161, n=3) | 487 (369 to 501, n=3) | 0 (0 to 0, n=3) | 14 (13 to 16, n=3) | 504 (384 to 515, n=3) | 17 (17 to 19, n=3) |
| hr_v2_proto_http_v1 | burst-10 | burst | invocations | 10 |  | 530 (432 to 730, n=30) | 70 (57 to 269, n=30) | 380 (320 to 461, n=30) | 0 (0 to 0, n=30) | 16 (15 to 24, n=30) | 396 (342 to 482, n=30) | 18 (17 to 40, n=30) |
| hr_v2_proto_http_v1 | burst-20 | burst | invocations | 20 |  | 5570 (513 to 7583, n=60) | 248 (58 to 455, n=60) | 5278 (358 to 7304, n=60) | 0 (0 to 0, n=60) | 16 (14 to 25, n=60) | 5294 (373 to 7326, n=60) | 20 (17 to 26, n=60) |
| hr_v2_proto_http_v1 | burst-5 | burst | invocations | 5 |  | 702 (463 to 923, n=15) | 69 (65 to 204, n=15) | 494 (352 to 764, n=15) | 0 (0 to 0, n=15) | 15 (13 to 20, n=15) | 507 (369 to 782, n=15) | 21 (17 to 60, n=15) |
| hr_v2_proto_http_v2 | burst-1 | burst | invocations | 1 |  | 1913 (1909 to 2418, n=3) | 67 (61 to 132, n=3) | 1803 (1736 to 2319, n=3) | 0 (0 to 0, n=3) | 21 (19 to 24, n=3) | 1828 (1759 to 2339, n=3) | 18 (18 to 19, n=3) |
| hr_v2_proto_http_v2 | burst-10 | burst | invocations | 10 |  | 1898 (1716 to 2160, n=30) | 63 (57 to 269, n=30) | 1736 (1496 to 1978, n=30) | 0 (0 to 0, n=30) | 17 (14 to 23, n=30) | 1762 (1518 to 1995, n=30) | 18 (16 to 21, n=30) |
| hr_v2_proto_http_v2 | burst-20 | burst | invocations | 20 |  | 2088 (1702 to 2470, n=60) | 241 (62 to 350, n=60) | 1774 (1493 to 2218, n=60) | 0 (0 to 0, n=60) | 16 (14 to 23, n=60) | 1790 (1511 to 2242, n=60) | 20 (17 to 37, n=60) |
| hr_v2_proto_http_v2 | burst-5 | burst | invocations | 5 |  | 1908 (1665 to 2133, n=15) | 71 (58 to 177, n=15) | 1790 (1546 to 1973, n=15) | 0 (0 to 0, n=15) | 16 (15 to 19, n=15) | 1807 (1563 to 1991, n=15) | 20 (17 to 35, n=15) |

First five new sessions of a runtime (after READY or a deploy) against the rest, receipt_to_handler_ms:

| runtime | label | first 5 | rest | first 5 client_ms | rest client_ms |
| --- | --- | --- | --- | --- | --- |

What the restored instances report, per runtime (distinct values across answers):

| runtime | answers | boot_id | hostname | pid | first_random | random at request | mem_total_mb | cpus | rss_mb (median) | minflt delta (median) | mono_since_start_s | wall_since_start_s (snapshot age) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hr_v2_proto_http_v1 | 108 | 2 | 1 | 1 | 108 | 108 | [8017.0] | [2] | 51 | 1 | 0.3 to 5.4 | 0.3 to 1099.6 |
| hr_v2_proto_http_v2 | 108 | 2 | 1 | 1 | 2 | 2 | [8017.0] | [2] | 51 | 0 | 65.7 to 78.7 | 322.7 to 1012.9 |
