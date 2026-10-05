# E6. Priming depth without network calls: findings

Run on 5 October 2026 between 00:55 and 01:09 UTC by the group D sub-agent (the text was
returned to the main session, which saved it here).

## Hypothesis

From the plan: building boto3 clients and running one request through the app before the snapshot moves their cost (service model parsing, route compilation, first JSON encode) out of the first request. Handler work falls and receipt to handler start does not change. This is the mechanism behind L33's 490 to 321 ms.

## Runtimes and runs

Both are platform V2, protocol HTTP, image `py`, `MODE=http`, `IMPORTS=heavy`, SigV4, PUBLIC network, idle timeout 900 s, version 1. Both were created at 00:55:18 UTC and READY at 00:58:24 UTC. The comparison runtime is `hr_v2_imp_heavy` from E5 (same image and imports, no priming, build_s 185.9).

| runtime | id | knobs | build_s |
| --- | --- | --- | --- |
| hr_v2_prime_clients | hr_v2_prime_clients-9g3HvH4c3g | `PRIME=clients` | 185.7 |
| hr_v2_prime_routes | hr_v2_prime_routes-qCzjQYADlM | `PRIME=routes` (clients plus one `TestClient` pass of `/ping` and `/invocations`) | 185.4 |

Each run is 25 new sessions sent one at a time (pace 1 s), with 2 follow-ups per session:

- `after-ready`, 00:58:27 to 00:59:51 UTC. Neither runtime had a log delivery until 01:03 UTC, so these lines have client and in-guest numbers but no runtime records.
- `rerun`, 01:05:07 to 01:06:33 UTC, with records. `hr_v2_imp_heavy` was rerun in the same window as the control.

Collected at 01:08 UTC: 300 requests, 0 failed, 150 joined (the `rerun` lines). Runtimes deleted at 01:19 UTC.

## Results

From `results.md` (E6) and the E5 `hr_v2_imp_heavy` rows, medians with p10 to p90:

| runtime | label | kind | client_ms | receipt_to_handler_ms | work_ms | record_ms |
| --- | --- | --- | --- | --- | --- | --- |
| hr_v2_imp_heavy | after-ready | new | 1892 (1679 to 2104, n=25) | 1772 (1569 to 2007, n=25) | 0 | 1786 (1587 to 2023, n=25) |
| hr_v2_prime_clients | after-ready | new | 1905 (1677 to 2176, n=25) | no records | 0 | no records |
| hr_v2_prime_routes | after-ready | new | 1919 (1644 to 2531, n=25) | no records | 0 | no records |
| hr_v2_imp_heavy | rerun | new | 1985 (1737 to 2193, n=25) | 1879 (1637 to 2084, n=25) | 0 | 1895 (1655 to 2103, n=25) |
| hr_v2_prime_clients | rerun | new | 2045 (1837 to 2299, n=25) | 1949 (1703 to 2212, n=25) | 0 | 1967 (1729 to 2230, n=25) |
| hr_v2_prime_routes | rerun | new | 1853 (1618 to 2426, n=25) | 1706 (1525 to 2273, n=25) | 0 | 1720 (1546 to 2348, n=25) |
| hr_v2_imp_heavy | rerun | followup | 170 (159 to 187, n=50) | 73 (65 to 85, n=50) | 0 | 90 (81 to 101, n=50) |
| hr_v2_prime_clients | rerun | followup | 172 (158 to 216, n=50) | 74 (66 to 92, n=50) | 0 | 92 (83 to 114, n=50) |
| hr_v2_prime_routes | rerun | followup | 175 (162 to 234, n=50) | 73 (65 to 88, n=50) | 0 | 89 (83 to 107, n=50) |

`work_ms` was 0.3 ms (p10 to p90 0.2 to 0.4) on every request of all three runtimes.

Start telemetry, done before the snapshot:

| runtime | start.import_ms (A / B) | start.prime_ms (A / B) | rss_mb | minflt delta in handler (new) |
| --- | --- | --- | --- | --- |
| hr_v2_imp_heavy | 645.6 / 878.1 | none | 84.1 | 2 |
| hr_v2_prime_clients | 644.6 / 832.6 | 80.7 / 112.3 | 96.7 | 0 |
| hr_v2_prime_routes | 638.7 / 831.3 | 94.8 / 125.7 | 97.8 | 3 |

Receipt to handler per snapshot, `rerun` (same window):

| runtime | snapshot A | snapshot B |
| --- | --- | --- |
| hr_v2_imp_heavy | 1745 (n=12) | 1924 (n=13) |
| hr_v2_prime_clients | 1861 (n=10) | 2005 (n=15) |
| hr_v2_prime_routes | 1671 (n=16) | 1890 (n=9) |

First five against the rest, client_ms, `after-ready`: prime_clients 1949 against 1895; prime_routes 2051 against 1893.

## Conclusion

Priming does not change the restore. On the same snapshot, receipt to handler for the primed runtimes is within 0.12 s of `hr_v2_imp_heavy` (clients +116 and +81 ms, routes -74 and -34 ms), and client_ms after READY is 1892, 1905 and 1919 ms. Handler work could not fall: it is 0.3 ms in all three because the probe's handler uses neither the clients nor any route state unless `OUTBOUND=1`. The cost moved out of the request is what the start measured: 81 to 112 ms to build three boto3 clients, and about 14 ms more for one `TestClient` pass through the app. E14 shows a primed client in use (`client_ms` 0.0 on the first request). L33's 490 to 321 ms is not reproduced, because that needs a handler that does the work.

## Surprising

- `PRIME=clients` is not free of calls before the snapshot. botocore's `Session.create_client` calls `get_credentials()`, so the start resolves credentials from the platform's credential source, and every restored instance then calls AWS with the snapshot build's credentials (see E14 findings).
- The `rerun` medians differ by up to 0.24 s between runtimes (1706 to 1949 ms). The cause is the snapshot mix, not the knob: 15 of 25 prime_clients sessions landed on the slower snapshot B against 9 of 25 for prime_routes.
- Two snapshots per runtime, as in E5. Snapshot B booted about 1.5 s slower to Python start, ran its imports and priming 25 to 40 percent slower, and restores 0.14 to 0.22 s slower.

## Failures and AWS behavior

- No request failed. Both runtimes lacked a log delivery until 01:03 UTC because `create.py` swallowed a `ConflictException` from `create_delivery`. The `after-ready` runtime records are lost, and the `rerun` supplies receipt to handler.

## Commands

```
PY=<scratch venv python>
B="--protocol HTTP --platform V2 --env MODE=http"
$PY scripts/v2study/create.py create hr_v2_prime_clients --image py $B --env IMPORTS=heavy --env PRIME=clients --experiment E6
$PY scripts/v2study/create.py create hr_v2_prime_routes --image py $B --env IMPORTS=heavy --env PRIME=routes --experiment E6
$PY scripts/v2study/invoke.py --name <name> --protocol http --new 25 --followups 2 --label after-ready --out docs/runtime-v2-evidence/E6/<name>.after-ready.jsonl
$PY scripts/v2study/invoke.py --name <name> --protocol http --new 25 --followups 2 --label rerun --out docs/runtime-v2-evidence/E6/<name>.rerun.jsonl
$PY scripts/v2study/collect.py docs/runtime-v2-evidence/E6/*.jsonl --md docs/runtime-v2-evidence/E6/results.md
$PY scripts/v2study/create.py delete <name> --wait
```
