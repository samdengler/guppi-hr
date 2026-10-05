# E8. Bursts of new sessions

Group A, run on 5 October 2026 between 00:55 and 01:20 UTC (4 October in Seattle). The text
was returned to the main session, which saved it here.

## Hypothesis

V2 restores in parallel with no pool to drain, so 10 or 20 sessions at once each take about the single-session time. V1's pool is finite, so a burst past it boots microVMs and the tail rises to the 7 to 10 s seen after deploys (A21).

## What was run

Runtimes from E1: `hr_v2_proto_http_v2` (V2, id tVcBJN3RW3, version 1, READY 00:52:14) and `hr_v2_proto_http_v1` (V1, id 0Y1WTR7hS5, version 1, READY 00:49:31). Both use the `py` image with MODE=http and idle 900 s. Bursts of 1, 5, 10 and 20 new sessions were sent at once from threads, three repeats each 60 s apart, with 60 s between burst sizes and no follow-ups. V2 ran from 00:55:54 to 01:07:27, then V1 from 01:08:28 to 01:20:02, one platform after the other. There were 216 requests, all joined to the runtime's records. During the V2 bursts the E1 runs on `hr_v2_proto_mcp_v2` and `hr_v2_proto_a2a_v2` and other groups' runs were active in the same account. On V1, sessions from earlier bursts were still inside their 900 s idle window and each kept its microVM: 48, 68 and 88 live V1 sessions before the three 20-session repeats.

## Results

Per burst size, all repeats together, ms:

| runtime | burst | n | receipt_to_handler med / max | record_ms med / max | client_ms med / max | errors or throttles |
| --- | --- | --- | --- | --- | --- | --- |
| http_v2 | 1 | 3 | 1803 / 2448 | 1828 / 2466 | 1913 / 2544 | 0 |
| http_v2 | 5 | 15 | 1790 / 2042 | 1807 / 2058 | 1908 / 2257 | 0 |
| http_v2 | 10 | 30 | 1736 / 2804 | 1762 / 2821 | 1898 / 2898 | 0 |
| http_v2 | 20 | 60 | 1774 / 3576 | 1790 / 3592 | 2088 / 3950 | 0 |
| http_v1 | 1 | 3 | 487 / 505 | 504 / 518 | 586 / 721 | 0 |
| http_v1 | 5 | 15 | 494 / 828 | 507 / 843 | 702 / 948 | 0 |
| http_v1 | 10 | 30 | 380 / 608 | 396 / 623 | 530 / 892 | 0 |
| http_v1 | 20 | 60 | 5278 / 7420 | 5294 / 7544 | 5570 / 7854 | 0 |

On V2, 1 of 30 sessions at 10 and 3 of 60 at 20 took over 2.5 s from receipt to handler; one at 20 took over 3 s. On V1, 37 of 60 sessions at 20 took over 3 s.

Bursts of 20 per repeat. A cold boot is a session whose process started after the client sent:

| runtime | repeat | start (UTC) | receipt_to_handler med / max | client_ms med / max | cold boots | live V1 sessions before |
| --- | --- | --- | --- | --- | --- | --- |
| http_v2 | 1 | 01:05:18 | 1845 / 3576 | 2227 / 3950 | 0 | - |
| http_v2 | 2 | 01:06:22 | 1722 / 2495 | 1876 / 2644 | 0 | - |
| http_v2 | 3 | 01:07:24 | 1690 / 2776 | 1858 / 2890 | 0 | - |
| http_v1 | 1 | 01:17:38 | 479 / 7354 | 924 / 7854 | 9 of 20 | 48 |
| http_v1 | 2 | 01:18:46 | 676 / 7420 | 804 / 7790 | 9 of 20 | 68 |
| http_v1 | 3 | 01:19:54 | 5312 / 7366 | 5590 / 7558 | 19 of 20 | 88 |

Bursts of 1, 5 and 10 caused no cold boot on V1. The V1 cold boots took 5.2 to 7.4 s from receipt to handler; warm V1 sessions in the same bursts took 0.34 to 0.42 s.

From results.md (median, p10 to p90):

| runtime | label | kind | burst | client_ms | to_receipt_ms | receipt_to_handler_ms | record_ms |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hr_v2_proto_http_v1 | burst-1 | burst | 1 | 586 (453 to 694, n=3) | 63 (51 to 161, n=3) | 487 (369 to 501, n=3) | 504 (384 to 515, n=3) |
| hr_v2_proto_http_v1 | burst-5 | burst | 5 | 702 (463 to 923, n=15) | 69 (65 to 204, n=15) | 494 (352 to 764, n=15) | 507 (369 to 782, n=15) |
| hr_v2_proto_http_v1 | burst-10 | burst | 10 | 530 (432 to 730, n=30) | 70 (57 to 269, n=30) | 380 (320 to 461, n=30) | 396 (342 to 482, n=30) |
| hr_v2_proto_http_v1 | burst-20 | burst | 20 | 5570 (513 to 7583, n=60) | 248 (58 to 455, n=60) | 5278 (358 to 7304, n=60) | 5294 (373 to 7326, n=60) |
| hr_v2_proto_http_v2 | burst-1 | burst | 1 | 1913 (1909 to 2418, n=3) | 67 (61 to 132, n=3) | 1803 (1736 to 2319, n=3) | 1828 (1759 to 2339, n=3) |
| hr_v2_proto_http_v2 | burst-5 | burst | 5 | 1908 (1665 to 2133, n=15) | 71 (58 to 177, n=15) | 1790 (1546 to 1973, n=15) | 1807 (1563 to 1991, n=15) |
| hr_v2_proto_http_v2 | burst-10 | burst | 10 | 1898 (1716 to 2160, n=30) | 63 (57 to 269, n=30) | 1736 (1496 to 1978, n=30) | 1762 (1518 to 1995, n=30) |
| hr_v2_proto_http_v2 | burst-20 | burst | 20 | 2088 (1702 to 2470, n=60) | 241 (62 to 350, n=60) | 1774 (1493 to 2218, n=60) | 1790 (1511 to 2242, n=60) |

## Conclusion

Both halves of the hypothesis hold. On V2 the median receipt to handler stays at 1.74 to 1.80 s from 1 to 20 simultaneous sessions (no difference); only the maximum grows, to 3.6 s at 20. V1 serves bursts of up to 10 from its pool in 0.38 to 0.49 s, but a burst of 20 drains the pool of about 11 ready instances. The rest boot microVMs in 5.2 to 7.4 s (7.85 s at the client), which matches the 7 to 10 s seen after deploys. At 20 sessions at once V2 is faster than V1 (1.77 s against 5.28 s median).

## Surprises and AWS behavior

- The V1 pool held about 11 ready instances per burst and refilled within 60 s after the first 20-session repeat but not after the second: the third repeat found 1 ready instance and booted 19. The live V1 sessions from earlier bursts (48 to 88, each holding a microVM for 900 s idle) may limit the refill; this run cannot separate the two.
- The client's median at 20 on V2 (2.09 s) is higher than its receipt to handler suggests because the invoker opens new TLS connections for the burst (to_receipt 241 ms median; botocore keeps 10 pooled connections). Receipt to handler does not change, so this is client side.
- All 108 V2 burst sessions were restored from the same two snapshots, made at 00:50:33 and 00:50:35. Snapshot ages from 323 s to 1013 s made no difference to the restore time. Python's `random.random()` returned 2 distinct values across the 108 answers, one per snapshot.
- V1 instances paused 13 to 18 minutes in the pool (wall clock since start 803 to 1100 s) took 0.49 to 0.51 s from receipt to handler, against 0.34 s for one paused 50 s. This matches the E1 observation that long-paused V1 instances resume more slowly.
- No throttling or errors at 20 sessions per second on either platform.

## Commands

```
PY=<scratch venv python>
for RT in hr_v2_proto_http_v2 hr_v2_proto_http_v1; do for N in 1 5 10 20; do
  $PY scripts/v2study/invoke.py --name $RT --protocol http --burst $N --repeat 3 --gap 60 --label burst-$N --out docs/runtime-v2-evidence/E8/$RT.burst-$N.jsonl
  sleep 60
done; done
$PY scripts/v2study/collect.py docs/runtime-v2-evidence/E8/*.jsonl --md docs/runtime-v2-evidence/E8/results.md
```
