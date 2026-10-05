Collected 2026-10-05 01:15 UTC from docs/runtime-v2-evidence/E9/hr_v2_auth_jwt.after-ready.jsonl, docs/runtime-v2-evidence/E9/hr_v2_auth_jwt.fresh-token.jsonl, docs/runtime-v2-evidence/E9/hr_v2_auth_jwt.same-token.jsonl.

97 requests ok, 0 failed, 97 joined to runtime records.

| runtime | label | kind | step | burst | wait | client_ms | to_receipt_ms | receipt_to_handler_ms | work_ms | handler_to_done_ms | record_ms | done_to_client_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hr_v2_auth_jwt | after-ready | followup | invocations |  | 0 | 330 (301 to 383, n=50) | 94 (82 to 116, n=50) | 194 (180 to 221, n=50) | 0 (0 to 0, n=50) | 16 (13 to 21, n=50) | 212 (196 to 241, n=50) | 18 (16 to 28, n=50) |
| hr_v2_auth_jwt | after-ready | new | invocations |  |  | 1998 (1772 to 2403, n=25) | 96 (81 to 134, n=25) | 1873 (1653 to 2234, n=25) | 0 (0 to 0, n=25) | 17 (14 to 21, n=25) | 1894 (1672 to 2251, n=25) | 18 (16 to 47, n=25) |
| hr_v2_auth_jwt | fresh-token | followup | invocations |  | 0 | 326 (298 to 410, n=10) | 95 (82 to 108, n=10) | 195 (175 to 240, n=10) | 0 (0 to 0, n=10) | 15 (14 to 20, n=10) | 209 (193 to 264, n=10) | 19 (18 to 108, n=10) |
| hr_v2_auth_jwt | fresh-token | new | invocations |  |  | 2414 | 188 | 2110 | 0 | 19 | 2130 | 97 |
| hr_v2_auth_jwt | same-token | followup | invocations |  | 0 | 344 (317 to 384, n=10) | 95 (84 to 105, n=10) | 201 (185 to 233, n=10) | 0 (0 to 0, n=10) | 17 (15 to 19, n=10) | 219 (201 to 246, n=10) | 18 (17 to 62, n=10) |
| hr_v2_auth_jwt | same-token | new | invocations |  |  | 2232 | 194 | 1967 | 0 | 22 | 1990 | 48 |

First five new sessions of a runtime (after READY or a deploy) against the rest, receipt_to_handler_ms:

| runtime | label | first 5 | rest | first 5 client_ms | rest client_ms |
| --- | --- | --- | --- | --- | --- |
| hr_v2_auth_jwt | after-ready | 1873 (1728 to 2234, n=5) | 1876 (1635 to 2205, n=20) | 2186 (1859 to 2397, n=5) | 1997 (1769 to 2378, n=20) |
| hr_v2_auth_jwt | fresh-token | 2110 | - | 2414 | - |
| hr_v2_auth_jwt | same-token | 1967 | - | 2232 | - |

What the restored instances report, per runtime (distinct values across answers):

| runtime | answers | boot_id | hostname | pid | first_random | random at request | mem_total_mb | cpus | rss_mb (median) | minflt delta (median) | mono_since_start_s | wall_since_start_s (snapshot age) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hr_v2_auth_jwt | 97 | 2 | 1 | 1 | 2 | 22 | [8017.0] | [2] | 51 | 0 | 66.3 to 71.0 | 122.5 to 228.4 |

CloudTrail GetWorkloadAccessTokenForJWT in the window (CloudTrail lags up to 15 minutes):

| runtime | requests sent | sessions | Identity calls |
| --- | --- | --- | --- |
| hr_v2_auth_jwt | 97 | 27 | 97 |
