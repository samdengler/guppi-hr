Collected 2026-10-05 01:08 UTC from docs/runtime-v2-evidence/E5/hr_v2_imp_heavy_nopyc.after-ready.jsonl, docs/runtime-v2-evidence/E5/hr_v2_imp_heavy.after-ready.jsonl, docs/runtime-v2-evidence/E5/hr_v2_imp_heavy.rerun.jsonl, docs/runtime-v2-evidence/E5/hr_v2_imp_lazy.after-ready.jsonl, docs/runtime-v2-evidence/E5/hr_v2_imp_nopyc.after-ready.jsonl, docs/runtime-v2-evidence/E5/hr_v2_imp_nopyc.rerun.jsonl.

450 requests ok, 0 failed, 375 joined to runtime records.

| runtime | label | kind | step | burst | wait | client_ms | to_receipt_ms | receipt_to_handler_ms | work_ms | handler_to_done_ms | record_ms | done_to_client_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hr_v2_imp_heavy | after-ready | followup | invocations |  | 0 | 169 (152 to 194, n=50) | 59 (51 to 73, n=50) | 70 (63 to 83, n=50) | 0 (0 to 0, n=50) | 16 (14 to 22, n=50) | 86 (79 to 102, n=50) | 18 (16 to 21, n=50) |
| hr_v2_imp_heavy | after-ready | new | invocations |  |  | 1892 (1679 to 2104, n=25) | 61 (55 to 72, n=25) | 1772 (1569 to 2007, n=25) | 0 (0 to 0, n=25) | 16 (14 to 24, n=25) | 1786 (1587 to 2023, n=25) | 17 (15 to 19, n=25) |
| hr_v2_imp_heavy | rerun | followup | invocations |  | 0 | 170 (159 to 187, n=50) | 61 (55 to 72, n=50) | 73 (65 to 85, n=50) | 0 (0 to 0, n=50) | 16 (14 to 20, n=50) | 90 (81 to 101, n=50) | 18 (16 to 23, n=50) |
| hr_v2_imp_heavy | rerun | new | invocations |  |  | 1985 (1737 to 2193, n=25) | 57 (51 to 73, n=25) | 1879 (1637 to 2084, n=25) | 0 (0 to 0, n=25) | 16 (14 to 22, n=25) | 1895 (1655 to 2103, n=25) | 18 (17 to 61, n=25) |
| hr_v2_imp_heavy_nopyc | after-ready | followup | invocations |  | 0 | 166 (156 to 184, n=50) | 61 (55 to 71, n=50) | 71 (65 to 79, n=50) | 0 (0 to 0, n=50) | 16 (13 to 20, n=50) | 87 (81 to 100, n=50) | 17 (15 to 22, n=50) |
| hr_v2_imp_heavy_nopyc | after-ready | new | invocations |  |  | 1903 (1624 to 2190, n=25) | 61 (53 to 73, n=25) | 1804 (1522 to 2090, n=25) | 0 (0 to 0, n=25) | 16 (13 to 22, n=25) | 1819 (1541 to 2106, n=25) | 17 (16 to 19, n=25) |
| hr_v2_imp_lazy | after-ready | followup | invocations |  | 0 | 165 (155 to 197, n=50) | 59 (52 to 67, n=50) | 69 (64 to 85, n=50) | 0 (0 to 0, n=50) | 16 (14 to 23, n=50) | 87 (79 to 110, n=50) | 18 (16 to 23, n=50) |
| hr_v2_imp_lazy | after-ready | new | invocations |  |  | 2706 (2313 to 6745, n=25) | 60 (55 to 69, n=25) | 1786 (1551 to 2148, n=25) | 670 (607 to 4370, n=25) | 18 (15 to 24, n=25) | 2623 (2230 to 6616, n=25) | 18 (17 to 29, n=25) |
| hr_v2_imp_nopyc | after-ready | followup | invocations |  | 0 | 170 (153 to 200, n=50) | - | - | 0 (0 to 0, n=50) | - | - | - |
| hr_v2_imp_nopyc | after-ready | new | invocations |  |  | 1926 (1610 to 2428, n=25) | - | - | 0 (0 to 0, n=25) | - | - | - |
| hr_v2_imp_nopyc | rerun | followup | invocations |  | 0 | 174 (157 to 203, n=50) | 58 (54 to 68, n=50) | 74 (66 to 84, n=50) | 0 (0 to 0, n=50) | 17 (14 to 24, n=50) | 92 (82 to 103, n=50) | 18 (16 to 40, n=50) |
| hr_v2_imp_nopyc | rerun | new | invocations |  |  | 1904 (1609 to 2347, n=25) | 59 (54 to 75, n=25) | 1789 (1512 to 2232, n=25) | 0 (0 to 0, n=25) | 16 (14 to 21, n=25) | 1811 (1532 to 2249, n=25) | 18 (17 to 84, n=25) |

First five new sessions of a runtime (after READY or a deploy) against the rest, receipt_to_handler_ms:

| runtime | label | first 5 | rest | first 5 client_ms | rest client_ms |
| --- | --- | --- | --- | --- | --- |
| hr_v2_imp_heavy | after-ready | 1608 (567 to 2007, n=5) | 1782 (1578 to 1979, n=20) | 2012 (1700 to 2104, n=5) | 1883 (1671 to 2071, n=20) |
| hr_v2_imp_heavy | rerun | 1924 (1775 to 2048, n=5) | 1833 (1609 to 2115, n=20) | 2015 (1979 to 2169, n=5) | 1934 (1705 to 2209, n=20) |
| hr_v2_imp_heavy_nopyc | after-ready | 2025 (1845 to 2152, n=5) | 1798 (1498 to 1951, n=20) | 2128 (1937 to 2302, n=5) | 1897 (1599 to 2045, n=20) |
| hr_v2_imp_lazy | after-ready | 2044 (1667 to 2401, n=5) | 1747 (1541 to 1993, n=20) | 9187 (2621 to 9814, n=5) | 2491 (2308 to 2985, n=20) |
| hr_v2_imp_nopyc | after-ready | - | - | 2087 (1930 to 2381, n=5) | 1832 (1596 to 2403, n=20) |
| hr_v2_imp_nopyc | rerun | 1821 (1726 to 2072, n=5) | 1749 (1485 to 2308, n=20) | 1908 (1858 to 2204, n=5) | 1871 (1581 to 2436, n=20) |

What the restored instances report, per runtime (distinct values across answers):

| runtime | answers | boot_id | hostname | pid | first_random | random at request | mem_total_mb | cpus | rss_mb (median) | minflt delta (median) | mono_since_start_s | wall_since_start_s (snapshot age) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hr_v2_imp_heavy | 150 | 2 | 1 | 1 | 2 | 6 | [8017.0] | [2] | 84 | 1 | 65.9 to 78.3 | 107.8 to 587.6 |
| hr_v2_imp_heavy_nopyc | 75 | 2 | 1 | 1 | 2 | 6 | [8017.0] | [2] | 88 | 0 | 66.5 to 68.5 | 107.0 to 186.2 |
| hr_v2_imp_lazy | 75 | 2 | 1 | 1 | 2 | 6 | [8017.0] | [2] | 84 | 0 | 67.4 to 84.9 | 107.2 to 224.0 |
| hr_v2_imp_nopyc | 150 | 2 | 1 | 1 | 2 | 6 | [8017.0] | [2] | 53 | 0 | 66.9 to 69.7 | 107.1 to 588.7 |
