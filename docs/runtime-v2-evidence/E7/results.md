Collected 2026-10-05 03:06 UTC from docs/runtime-v2-evidence/E7/hr_v2_cache_v2.after-ready.jsonl, docs/runtime-v2-evidence/E7/hr_v2_cache_v2.after-redeploy-later.jsonl, docs/runtime-v2-evidence/E7/hr_v2_cache_v2.after-redeploy.jsonl, docs/runtime-v2-evidence/E7/hr_v2_cache_v2.idle-2h.jsonl, docs/runtime-v2-evidence/E7/hr_v2_cache_v2.idle-30min.jsonl.

80 requests ok, 0 failed, 76 joined to runtime records.

| runtime | label | kind | step | burst | wait | client_ms | to_receipt_ms | receipt_to_handler_ms | work_ms | handler_to_done_ms | record_ms | done_to_client_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hr_v2_cache_v2 | after-ready | followup | invocations |  | 0 | 167 (154 to 181, n=5) | 56 (55 to 58, n=3) | 74 (65 to 77, n=3) | 0 (0 to 0, n=5) | 15 (14 to 16, n=3) | 90 (79 to 94, n=3) | 18 (15 to 18, n=3) |
| hr_v2_cache_v2 | after-ready | new | invocations |  |  | 1782 (1729 to 2188, n=5) | 61 (58 to 62, n=3) | 1886 (1649 to 2165, n=3) | 0 (0 to 0, n=5) | 16 (16 to 17, n=3) | 1904 (1666 to 2181, n=3) | 18 (17 to 24, n=3) |
| hr_v2_cache_v2 | after-redeploy | followup | invocations |  | 0 | 185 (176 to 290, n=5) | 65 (62 to 71, n=5) | 78 (76 to 97, n=5) | 0 (0 to 0, n=5) | 15 (14 to 70, n=5) | 110 (91 to 156, n=5) | 16 (14 to 68, n=5) |
| hr_v2_cache_v2 | after-redeploy | new | invocations |  |  | 2093 (1864 to 2225, n=5) | 69 (62 to 134, n=5) | 1944 (1757 to 2026, n=5) | 0 (0 to 0, n=5) | 16 (15 to 19, n=5) | 1960 (1774 to 2044, n=5) | 20 (16 to 93, n=5) |
| hr_v2_cache_v2 | after-redeploy-later | followup | invocations |  | 0 | 182 (166 to 203, n=20) | 64 (60 to 73, n=20) | 75 (69 to 83, n=20) | 0 (0 to 0, n=20) | 16 (13 to 19, n=20) | 92 (85 to 102, n=20) | 19 (16 to 54, n=20) |
| hr_v2_cache_v2 | after-redeploy-later | new | invocations |  |  | 1972 (1740 to 2285, n=20) | 67 (61 to 75, n=20) | 1832 (1612 to 2071, n=20) | 0 (0 to 0, n=20) | 16 (14 to 23, n=20) | 1847 (1649 to 2093, n=20) | 56 (16 to 120, n=20) |
| hr_v2_cache_v2 | idle-2h | followup | invocations |  | 0 | 188 (171 to 236, n=5) | 63 (59 to 70, n=5) | 73 (71 to 82, n=5) | 0 (0 to 0, n=5) | 16 (13 to 20, n=5) | 89 (87 to 100, n=5) | 24 (15 to 84, n=5) |
| hr_v2_cache_v2 | idle-2h | new | invocations |  |  | 1734 (1645 to 2084, n=5) | 64 (63 to 135, n=5) | 1638 (1539 to 1897, n=5) | 0 (0 to 0, n=5) | 17 (15 to 21, n=5) | 1653 (1557 to 1917, n=5) | 17 (16 to 38, n=5) |
| hr_v2_cache_v2 | idle-30min | followup | invocations |  | 0 | 178 (169 to 192, n=5) | 64 (61 to 81, n=5) | 72 (72 to 75, n=5) | 0 (0 to 0, n=5) | 16 (15 to 20, n=5) | 90 (88 to 92, n=5) | 18 (17 to 27, n=5) |
| hr_v2_cache_v2 | idle-30min | new | invocations |  |  | 2150 (1750 to 2312, n=5) | 72 (55 to 112, n=5) | 2054 (1634 to 2190, n=5) | 0 (0 to 0, n=5) | 17 (15 to 23, n=5) | 2077 (1654 to 2205, n=5) | 21 (17 to 23, n=5) |

First five new sessions of a runtime (after READY or a deploy) against the rest, receipt_to_handler_ms:

| runtime | label | first 5 | rest | first 5 client_ms | rest client_ms |
| --- | --- | --- | --- | --- | --- |
| hr_v2_cache_v2 | after-ready | 1886 (1649 to 2165, n=3) | - | 1782 (1729 to 2188, n=5) | - |
| hr_v2_cache_v2 | after-redeploy | 1944 (1757 to 2026, n=5) | - | 2093 (1864 to 2225, n=5) | - |
| hr_v2_cache_v2 | after-redeploy-later | 1885 (1820 to 2340, n=5) | 1721 (1581 to 1998, n=15) | 2076 (1929 to 2606, n=5) | 1864 (1712 to 2138, n=15) |
| hr_v2_cache_v2 | idle-2h | 1638 (1539 to 1897, n=5) | - | 1734 (1645 to 2084, n=5) | - |
| hr_v2_cache_v2 | idle-30min | 2054 (1634 to 2190, n=5) | - | 2150 (1750 to 2312, n=5) | - |

What the restored instances report, per runtime (distinct values across answers):

| runtime | answers | boot_id | hostname | pid | first_random | random at request | mem_total_mb | cpus | rss_mb (median) | minflt delta (median) | mono_since_start_s | wall_since_start_s (snapshot age) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hr_v2_cache_v2 | 80 | 2 | 1 | 1 | 4 | 8 | [8017.0] | [2] | 51 | 0 | 65.9 to 77.0 | 104.2 to 7359.3 |
