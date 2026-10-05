Collected 2026-10-05 01:07 UTC from docs/runtime-v2-evidence/E3/hr_v2_fault_128.after-ready.jsonl, docs/runtime-v2-evidence/E3/hr_v2_fault_32.after-ready-rerun.jsonl, docs/runtime-v2-evidence/E3/hr_v2_fault_32.after-ready.jsonl, docs/runtime-v2-evidence/E3/hr_v2_touch_256.after-ready-rerun.jsonl, docs/runtime-v2-evidence/E3/hr_v2_touch_256.after-ready.jsonl, docs/runtime-v2-evidence/E3/hr_v2_touch_64.after-ready.jsonl.

450 requests ok, 0 failed, 296 joined to runtime records.

| runtime | label | kind | step | burst | wait | client_ms | to_receipt_ms | receipt_to_handler_ms | work_ms | handler_to_done_ms | record_ms | done_to_client_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hr_v2_fault_128 | after-ready | followup | invocations |  | 0 | 172 (154 to 205, n=50) | 62 (50 to 70, n=50) | 71 (64 to 89, n=50) | 2 (2 to 3, n=50) | 16 (14 to 23, n=50) | 92 (81 to 115, n=50) | 17 (16 to 21, n=50) |
| hr_v2_fault_128 | after-ready | new | invocations |  |  | 1905 (1675 to 2174, n=25) | 61 (52 to 69, n=25) | 1803 (1574 to 2064, n=25) | 2 (2 to 4, n=25) | 17 (14 to 21, n=25) | 1827 (1594 to 2084, n=25) | 17 (16 to 19, n=25) |
| hr_v2_fault_32 | after-ready | followup | invocations |  | 0 | 172 (160 to 190, n=50) | - | - | 1 (1 to 1, n=50) | - | - | - |
| hr_v2_fault_32 | after-ready | new | invocations |  |  | 1965 (1772 to 2364, n=25) | - | - | 1 (1 to 1, n=25) | - | - | - |
| hr_v2_fault_32 | after-ready-rerun | followup | invocations |  | 0 | 171 (158 to 198, n=50) | 60 (53 to 69, n=49) | 76 (65 to 88, n=49) | 1 (1 to 1, n=50) | 16 (14 to 22, n=49) | 93 (82 to 106, n=49) | 18 (16 to 21, n=49) |
| hr_v2_fault_32 | after-ready-rerun | new | invocations |  |  | 1913 (1654 to 2263, n=25) | 58 (53 to 86, n=25) | 1816 (1550 to 2154, n=25) | 1 (1 to 1, n=25) | 18 (14 to 26, n=25) | 1832 (1568 to 2176, n=25) | 18 (16 to 30, n=25) |
| hr_v2_touch_256 | after-ready | followup | invocations |  | 0 | 171 (156 to 186, n=50) | - | - | 0 (0 to 0, n=50) | - | - | - |
| hr_v2_touch_256 | after-ready | new | invocations |  |  | 2046 (1695 to 2540, n=25) | - | - | 0 (0 to 0, n=25) | - | - | - |
| hr_v2_touch_256 | after-ready-rerun | followup | invocations |  | 0 | 170 (155 to 211, n=50) | 58 (53 to 74, n=48) | 73 (67 to 88, n=48) | 0 (0 to 0, n=50) | 16 (14 to 22, n=48) | 90 (83 to 105, n=48) | 18 (16 to 33, n=48) |
| hr_v2_touch_256 | after-ready-rerun | new | invocations |  |  | 1960 (1688 to 2453, n=25) | 61 (51 to 72, n=24) | 1866 (1579 to 2285, n=24) | 0 (0 to 0, n=25) | 16 (13 to 22, n=24) | 1880 (1597 to 2302, n=24) | 18 (16 to 20, n=24) |
| hr_v2_touch_64 | after-ready | followup | invocations |  | 0 | 169 (156 to 186, n=50) | 61 (53 to 68, n=50) | 72 (65 to 81, n=50) | 0 (0 to 0, n=50) | 16 (14 to 21, n=50) | 88 (82 to 99, n=50) | 18 (16 to 23, n=50) |
| hr_v2_touch_64 | after-ready | new | invocations |  |  | 1914 (1755 to 2244, n=25) | 59 (54 to 73, n=25) | 1812 (1660 to 2105, n=25) | 0 (0 to 0, n=25) | 16 (14 to 23, n=25) | 1830 (1676 to 2123, n=25) | 17 (16 to 19, n=25) |

First five new sessions of a runtime (after READY or a deploy) against the rest, receipt_to_handler_ms:

| runtime | label | first 5 | rest | first 5 client_ms | rest client_ms |
| --- | --- | --- | --- | --- | --- |
| hr_v2_fault_128 | after-ready | 1943 (1826 to 2168, n=5) | 1789 (1545 to 1997, n=20) | 2140 (1928 to 2269, n=5) | 1890 (1640 to 2102, n=20) |
| hr_v2_fault_32 | after-ready | - | - | 1852 (1786 to 2164, n=5) | 1989 (1752 to 2405, n=20) |
| hr_v2_fault_32 | after-ready-rerun | 1721 (454 to 1958, n=5) | 1829 (1556 to 2175, n=20) | 1867 (1710 to 2055, n=5) | 1925 (1666 to 2289, n=20) |
| hr_v2_touch_256 | after-ready | - | - | 2140 (1980 to 2658, n=5) | 2022 (1679 to 2327, n=20) |
| hr_v2_touch_256 | after-ready-rerun | 2243 (1860 to 2403, n=4) | 1823 (1560 to 2196, n=20) | 2481 (1990 to 2564, n=5) | 1912 (1655 to 2294, n=20) |
| hr_v2_touch_64 | after-ready | 2022 (1724 to 2105, n=5) | 1808 (1640 to 2004, n=20) | 2128 (1820 to 2244, n=5) | 1913 (1737 to 2112, n=20) |

What the restored instances report, per runtime (distinct values across answers):

| runtime | answers | boot_id | hostname | pid | first_random | random at request | mem_total_mb | cpus | rss_mb (median) | minflt delta (median) | mono_since_start_s | wall_since_start_s (snapshot age) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hr_v2_fault_128 | 75 | 2 | 1 | 1 | 2 | 6 | [8017.0] | [2] | 185 | 0 | 66.5 to 68.3 | 155.1 to 234.2 |
| hr_v2_fault_32 | 150 | 2 | 1 | 1 | 2 | 6 | [8017.0] | [2] | 84 | 0 | 66.0 to 68.2 | 154.8 to 567.1 |
| hr_v2_touch_256 | 150 | 2 | 1 | 1 | 2 | 6 | [8017.0] | [2] | 319 | 0 | 66.4 to 68.5 | 154.7 to 569.6 |
| hr_v2_touch_64 | 75 | 2 | 1 | 1 | 2 | 6 | [8017.0] | [2] | 118 | 0 | 66.2 to 68.3 | 155.3 to 235.4 |
