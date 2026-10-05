Collected 2026-10-05 02:05 UTC from docs/runtime-v2-evidence/E11/hr_v2_proto_http_v2.idle-16min.1.jsonl, docs/runtime-v2-evidence/E11/hr_v2_proto_http_v2.idle-16min.2.jsonl, docs/runtime-v2-evidence/E11/hr_v2_proto_http_v2.idle-16min.3.jsonl, docs/runtime-v2-evidence/E11/hr_v2_proto_http_v2.idle-920s.1.jsonl, docs/runtime-v2-evidence/E11/hr_v2_proto_http_v2.idle-920s.2.jsonl, docs/runtime-v2-evidence/E11/hr_v2_proto_http_v2.waits.1.jsonl, docs/runtime-v2-evidence/E11/hr_v2_proto_http_v2.waits.2.jsonl, docs/runtime-v2-evidence/E11/hr_v2_proto_http_v2.waits.3.jsonl, docs/runtime-v2-evidence/E11/hr_v2_proto_http_v2.waits.4.jsonl, docs/runtime-v2-evidence/E11/hr_v2_proto_http_v2.waits.5.jsonl.

30 requests ok, 0 failed, 30 joined to runtime records.

| runtime | label | kind | step | burst | wait | client_ms | to_receipt_ms | receipt_to_handler_ms | work_ms | handler_to_done_ms | record_ms | done_to_client_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hr_v2_proto_http_v2 | idle-16min | followup | invocations |  | 960 | 2408 (2387 to 2861, n=3) | 534 (382 to 839, n=3) | 1984 (1866 to 2018, n=3) | 0 (0 to 0, n=3) | 17 (17 to 21, n=3) | 2006 (1884 to 2036, n=3) | 19 (17 to 29, n=3) |
| hr_v2_proto_http_v2 | idle-16min | new | invocations |  |  | 1815 (1783 to 2221, n=3) | 208 (182 to 214, n=3) | 1567 (1558 to 1973, n=3) | 0 (0 to 0, n=3) | 21 (17 to 23, n=3) | 1583 (1581 to 1993, n=3) | 18 (17 to 19, n=3) |
| hr_v2_proto_http_v2 | idle-920s | followup | invocations |  | 920 | 5210 (3336 to 7084, n=2) | 813 (750 to 876, n=2) | 4339 (2420 to 6258, n=2) | 0 (0 to 0, n=2) | 15 (14 to 15, n=2) | 4355 (2436 to 6273, n=2) | 42 (24 to 60, n=2) |
| hr_v2_proto_http_v2 | idle-920s | new | invocations |  |  | 2070 (2026 to 2114, n=2) | 143 (139 to 147, n=2) | 1894 (1844 to 1944, n=2) | 0 (0 to 0, n=2) | 17 (15 to 19, n=2) | 1911 (1863 to 1959, n=2) | 16 (16 to 16, n=2) |
| hr_v2_proto_http_v2 | waits | followup | invocations |  | 130 | 174 (164 to 180, n=5) | 62 (61 to 72, n=5) | 70 (68 to 74, n=5) | 0 (0 to 0, n=5) | 18 (15 to 22, n=5) | 91 (85 to 94, n=5) | 16 (16 to 20, n=5) |
| hr_v2_proto_http_v2 | waits | followup | invocations |  | 30 | 181 (175 to 195, n=5) | 73 (63 to 73, n=5) | 74 (70 to 87, n=5) | 0 (0 to 0, n=5) | 16 (14 to 21, n=5) | 92 (85 to 107, n=5) | 20 (19 to 22, n=5) |
| hr_v2_proto_http_v2 | waits | followup | invocations |  | 75 | 177 (164 to 201, n=5) | 64 (54 to 76, n=5) | 83 (76 to 92, n=5) | 0 (0 to 0, n=5) | 14 (14 to 15, n=5) | 98 (91 to 106, n=5) | 18 (16 to 22, n=5) |
| hr_v2_proto_http_v2 | waits | new | invocations |  |  | 2014 (1847 to 2246, n=5) | 177 (175 to 206, n=5) | 1800 (1628 to 2021, n=5) | 0 (0 to 0, n=5) | 16 (15 to 18, n=5) | 1820 (1644 to 2037, n=5) | 18 (17 to 20, n=5) |

First five new sessions of a runtime (after READY or a deploy) against the rest, receipt_to_handler_ms:

| runtime | label | first 5 | rest | first 5 client_ms | rest client_ms |
| --- | --- | --- | --- | --- | --- |
| hr_v2_proto_http_v2 | idle-16min | 1567 (1558 to 1973, n=3) | - | 1815 (1783 to 2221, n=3) | - |
| hr_v2_proto_http_v2 | idle-920s | 1894 (1844 to 1944, n=2) | - | 2070 (2026 to 2114, n=2) | - |
| hr_v2_proto_http_v2 | waits | 1800 (1628 to 2021, n=5) | - | 2014 (1847 to 2246, n=5) | - |

What the restored instances report, per runtime (distinct values across answers):

| runtime | answers | boot_id | hostname | pid | first_random | random at request | mem_total_mb | cpus | rss_mb (median) | minflt delta (median) | mono_since_start_s | wall_since_start_s (snapshot age) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hr_v2_proto_http_v2 | 30 | 2 | 1 | 1 | 2 | 8 | [8017.0] | [2] | 51 | 0 | 66.1 to 313.2 | 3492.3 to 4492.7 |
