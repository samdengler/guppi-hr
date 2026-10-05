Collected 2026-10-05 01:08 UTC from docs/runtime-v2-evidence/E6/hr_v2_prime_clients.after-ready.jsonl, docs/runtime-v2-evidence/E6/hr_v2_prime_clients.rerun.jsonl, docs/runtime-v2-evidence/E6/hr_v2_prime_routes.after-ready.jsonl, docs/runtime-v2-evidence/E6/hr_v2_prime_routes.rerun.jsonl.

300 requests ok, 0 failed, 150 joined to runtime records.

| runtime | label | kind | step | burst | wait | client_ms | to_receipt_ms | receipt_to_handler_ms | work_ms | handler_to_done_ms | record_ms | done_to_client_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hr_v2_prime_clients | after-ready | followup | invocations |  | 0 | 171 (154 to 190, n=50) | - | - | 0 (0 to 0, n=50) | - | - | - |
| hr_v2_prime_clients | after-ready | new | invocations |  |  | 1905 (1677 to 2176, n=25) | - | - | 0 (0 to 0, n=25) | - | - | - |
| hr_v2_prime_clients | rerun | followup | invocations |  | 0 | 172 (158 to 216, n=50) | 59 (54 to 66, n=50) | 74 (66 to 92, n=50) | 0 (0 to 0, n=50) | 16 (14 to 23, n=50) | 92 (83 to 114, n=50) | 18 (17 to 27, n=50) |
| hr_v2_prime_clients | rerun | new | invocations |  |  | 2045 (1837 to 2299, n=25) | 60 (54 to 67, n=25) | 1949 (1703 to 2212, n=25) | 0 (0 to 0, n=25) | 18 (15 to 28, n=25) | 1967 (1729 to 2230, n=25) | 20 (17 to 63, n=25) |
| hr_v2_prime_routes | after-ready | followup | invocations |  | 0 | 168 (150 to 198, n=50) | - | - | 0 (0 to 0, n=50) | - | - | - |
| hr_v2_prime_routes | after-ready | new | invocations |  |  | 1919 (1644 to 2531, n=25) | - | - | 0 (0 to 0, n=25) | - | - | - |
| hr_v2_prime_routes | rerun | followup | invocations |  | 0 | 175 (162 to 234, n=50) | 61 (55 to 70, n=50) | 73 (65 to 88, n=50) | 0 (0 to 0, n=50) | 16 (14 to 22, n=50) | 89 (83 to 107, n=50) | 19 (17 to 60, n=50) |
| hr_v2_prime_routes | rerun | new | invocations |  |  | 1853 (1618 to 2426, n=25) | 60 (55 to 68, n=25) | 1706 (1525 to 2273, n=25) | 0 (0 to 0, n=25) | 17 (15 to 24, n=25) | 1720 (1546 to 2348, n=25) | 19 (18 to 28, n=25) |

First five new sessions of a runtime (after READY or a deploy) against the rest, receipt_to_handler_ms:

| runtime | label | first 5 | rest | first 5 client_ms | rest client_ms |
| --- | --- | --- | --- | --- | --- |
| hr_v2_prime_clients | after-ready | - | - | 1949 (1856 to 2139, n=5) | 1895 (1661 to 2157, n=20) |
| hr_v2_prime_clients | rerun | 2026 (1909 to 2160, n=5) | 1912 (1693 to 2253, n=20) | 2219 (2049 to 2254, n=5) | 2028 (1827 to 2340, n=20) |
| hr_v2_prime_routes | after-ready | - | - | 2051 (1792 to 2135, n=5) | 1893 (1627 to 2675, n=20) |
| hr_v2_prime_routes | rerun | 1782 (1615 to 2048, n=5) | 1704 (1480 to 2354, n=20) | 1886 (1753 to 2151, n=5) | 1802 (1573 to 2532, n=20) |

What the restored instances report, per runtime (distinct values across answers):

| runtime | answers | boot_id | hostname | pid | first_random | random at request | mem_total_mb | cpus | rss_mb (median) | minflt delta (median) | mono_since_start_s | wall_since_start_s (snapshot age) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hr_v2_prime_clients | 150 | 2 | 1 | 1 | 2 | 6 | [8017.0] | [2] | 97 | 0 | 67.1 to 77.2 | 105.5 to 588.6 |
| hr_v2_prime_routes | 150 | 2 | 1 | 1 | 2 | 6 | [8017.0] | [2] | 98 | 1 | 66.1 to 68.9 | 106.0 to 586.2 |
