# E14. Outbound work from a restored instance: findings

Run on 5 October 2026 between 00:55 and 01:09 UTC by the group D sub-agent (the text was
returned to the main session, which saved it here).

## Hypothesis

From the plan: the first outbound call from a restored instance pays credentials (the container credentials endpoint), DNS and a TLS handshake, about 0.2 to 0.5 s, and the follow-up on the same session pays none of it.

## Runtime and run

`hr_v2_out_sts` (id `hr_v2_out_sts-0GLBG92pXW`, version 1): platform V2, HTTP, image `py`, `MODE=http`, `IMPORTS=heavy`, `PRIME=clients`, `OUTBOUND=1`, SigV4, PUBLIC network, idle timeout 900 s. Created at 00:55:18 UTC, READY at 00:58:24 UTC, build_s 185.5. The handler calls `sts:GetCallerIdentity` with the STS client built before the snapshot and times the client lookup (`work.outbound.client_ms`) and the call (`work.outbound.call_ms`).

`after-ready` ran 00:58:27 to 00:59:54 UTC: 25 new sessions one at a time (pace 1 s), with 2 follow-ups per session (50 follow-ups). Collected at 01:08 UTC: 75 requests, 0 failed, 75 joined. Deleted at 01:19 UTC.

## Results

From `results.md`:

| kind | client_ms | to_receipt_ms | receipt_to_handler_ms | work_ms | record_ms |
| --- | --- | --- | --- | --- | --- |
| new | 1940 (1690 to 2922, n=25) | 58 (53 to 77, n=25) | 1728 (1565 to 2207, n=25) | 38 (35 to 784, n=25) | 1843 (1616 to 2782, n=25) |
| followup | 173 (153 to 194, n=50) | 58 (50 to 68, n=50) | 70 (65 to 84, n=50) | 6 (5 to 6, n=50) | 94 (85 to 106, n=50) |

First five new sessions against the rest: receipt to handler 1872 against 1711 ms; client_ms 3088 against 1846 ms.

The timed call:

| request | sent (UTC) | out.call_ms | out.client_ms | minflt / majflt delta |
| --- | --- | --- | --- | --- |
| first request, new sessions 1 to 5 | 00:58:28 to 00:58:45 | 807 (741 to 954), min 736, max 1018 | 0.0 | 210 to 211 / 18 to 19 |
| first request, new sessions 6 to 25 | 00:58:50 to 00:59:52 | 37.0 (34.6 to 41.0, n=20), max 100.4 | 0.0 | 210 to 211 / 18 to 19 |
| follow-up 1 | | 5.4 (4.7 to 6.1, n=25) | 0.0 | 0 to 2 / 0 |
| follow-up 2 | | 5.1 (4.6 to 6.0, n=25) | 0.0 | 0 / 0 |

RSS went from 96.7 to 98.4 MB on the first request and stayed there. All 75 answers report the same caller: assumed-role session `snapstart-build-DEFAULT`.

CloudTrail (read-only lookups) recorded 75 `GetCallerIdentity` events from the study role between 00:58 and 01:01 UTC. Every one is from session `snapstart-build-DEFAULT` with one of two access keys (57 calls, the 19 sessions on snapshot A times 3; 18 calls, the 6 sessions on snapshot B times 3). Both keys come from `AssumeRole` calls by `bedrock-agentcore.amazonaws.com` at 00:56:25 UTC with `durationSeconds` 3600, so they expire at 01:56:25 UTC. That is about 17 s before the probe processes started (00:56:42 and 00:56:44). In the same window the study role also shows `AssumeRole` sessions named `AgentCore-MicroVM-<id>-DEFAULT` and `BedrockAgentCore-<uuid>`; these cannot be attributed to a runtime from the event.

## Conclusion

Once the runtime has been READY for about half a minute, the first outbound call from a restored instance costs 37 ms against 5 ms for a warm call. The follow-ups on the same session pay none of it again (5.1 to 5.4 ms). The first five new sessions after READY paid 0.74 to 1.02 s for the same call. Credentials cost nothing on the restored instance because `PRIME=clients` resolved them before the snapshot. The extra 32 ms is DNS, TCP and TLS to STS plus first-call code paths, which the probe does not separate. The hypothesis's 0.2 to 0.5 s is too high for the steady state and too low for the first restores after a deploy.

## Surprising

- The restored instances use the snapshot build's credentials. Every restore of a snapshot calls AWS with the same access key, attributed in CloudTrail to `snapstart-build-DEFAULT`, so per-session attribution is lost. The keys expire one hour after the build. Whether botocore refreshes them on a restored instance after that hour, and from which source, is not tested here. W1's risk (403 hours later in agentcore-samples) therefore applies to `PRIME=clients` and to any agent that builds boto3 clients before the snapshot, without any warm-up call. A test that would settle it: a `PRIME=clients`, `OUTBOUND=1` runtime invoked with one new session at 50, 65 and 120 minutes after its build, checking `arn_tail` and the CloudTrail access keys. (The main session runs this as E15.)
- The slow first calls follow time since READY, not order per snapshot. Snapshot A's sessions were slow until 00:58:45 and fast from 00:58:50. The same window shows in E5's lazy imports: slow until 00:58:50, fast from 00:59:01. The page fault counts are identical in the slow and fast cases.
- The cost of credentials plus client construction on a restored instance is not measured. That needs a variant with `OUTBOUND=1` and `PRIME=none`, which the plan does not include.

## Failures and AWS behavior

- No request failed, and the log delivery was in place (75 of 75 joined).
- For AWS: the role credentials minted for the snapshot build (`snapstart-build-DEFAULT`, 3600 s) end up in every restored instance of a process that resolved them at start. The questions for AWS are how refresh is meant to work on a restored microVM, and whether the credentials source serves per-microVM credentials after a restore (the `AgentCore-MicroVM-<id>-DEFAULT` sessions suggest it does). The first outbound call on the first restores after READY is 20 times slower than later ones.

## Commands

```
PY=<scratch venv python>
$PY scripts/v2study/create.py create hr_v2_out_sts --image py --protocol HTTP --platform V2 --env MODE=http --env IMPORTS=heavy --env PRIME=clients --env OUTBOUND=1 --experiment E14
$PY scripts/v2study/invoke.py --name hr_v2_out_sts --protocol http --new 25 --followups 2 --label after-ready --out docs/runtime-v2-evidence/E14/hr_v2_out_sts.after-ready.jsonl
$PY scripts/v2study/collect.py docs/runtime-v2-evidence/E14/*.jsonl --md docs/runtime-v2-evidence/E14/results.md
# CloudTrail, read-only: lookup_events EventName=AssumeRole (00:54 to 01:02 UTC) and EventName=GetCallerIdentity (00:58 to 01:01 UTC), filtered to role hr-v2-study-runtime
$PY scripts/v2study/create.py delete hr_v2_out_sts --wait
```
