# E2: image size

Hypothesis: image size does not move the restore, because the padding is never read and a snapshot restores pages on demand.

Run: hr_v2_image_500 (image py-pad500, runtime version 1) and hr_v2_image_1500 (py-pad1500), V2, HTTP, MODE=http, created in parallel at about 2026-10-05 00:53 UTC with the four E3 runtimes. Invoked 00:58 to 01:00 UTC, 25 new sessions and 2 follow-ups each (50 follow-ups), label after-ready. Collected 01:01 UTC, all 150 requests joined to runtime records.

## Result

| runtime | pad | build_s (create to READY) | new session receipt_to_handler_ms median (p10 to p90) | new client_ms | follow-up client_ms |
| --- | --- | --- | --- | --- | --- |
| hr_v2_proto_http_v2 (group A baseline) | 0 | 184.9 | 1810 (1672 to 1980, n=5, E1) | 1922 (n=5, E1) | 174 (n=5) |
| hr_v2_image_500 | 500 MB | 200.9 | 1868 (1531 to 2232, n=25) | 1953 (1624 to 2330) | 170 |
| hr_v2_image_1500 | 1500 MB | 216.4 | 1782 (1560 to 2040, n=25) | 1882 (1667 to 2141) | 169 |

Baseline from E1 results.md covers only 5 sessions; the E1 "later" label (n=20) gives 1753 ms for receipt to handler. Against either, the differences are 0.06 s or less.

## Conclusion

Image size has no effect on the restore: 0 MB, 500 MB and 1500 MB images restore within 0.1 s of each other, inside the spread of each sample (p10 to p90 is about 0.5 s wide). Snapshot build time grows slowly with image size, about 16 s per extra 1000 MB (184.9, 200.9, 216.4 s), so most of the 3 minute build is fixed cost. Follow-ups are unchanged (about 170 ms).

## Notes

- The 1.5 GB image was accepted and reached READY without failure.
- The first five sessions on each runtime were slower by 0.1 to 0.2 s than the remaining 20 (receipt to handler 1940 vs 1725 for 1500; 2029 vs 1827 for 500), the same first-restores effect seen elsewhere; it is below the 0.15 s threshold for 1500 and just above for 500 but within sample noise at n=5.
- Receipt to handler of about 1.8 s dominates, as in the baseline. Image size does not change it.

## Commands

    PY=<scratchpad>/venv/bin/python
    $PY scripts/v2study/create.py create hr_v2_image_500 --image py-pad500 --protocol HTTP --platform V2 --env MODE=http --experiment E2
    $PY scripts/v2study/create.py create hr_v2_image_1500 --image py-pad1500 --protocol HTTP --platform V2 --env MODE=http --experiment E2
    $PY scripts/v2study/invoke.py --name <name> --protocol http --new 25 --followups 2 --label after-ready --out docs/runtime-v2-evidence/E2/<name>.after-ready.jsonl
    $PY scripts/v2study/collect.py docs/runtime-v2-evidence/E2/*.jsonl --md docs/runtime-v2-evidence/E2/results.md
    $PY scripts/v2study/create.py delete <name> --wait
