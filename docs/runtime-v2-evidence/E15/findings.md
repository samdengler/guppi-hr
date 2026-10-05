# E15. Credentials captured in the snapshot, after they expire: findings

Added by the main session on 5 October 2026 after E14 showed that every restored instance
calls AWS with the snapshot build's credentials (role session `snapstart-build-DEFAULT`,
`AssumeRole` duration 3600 s).

## Question

When the build's credentials expire an hour after the snapshot, does a restored instance
whose boto3 client was built before the snapshot still call AWS, from which credentials, and
at what cost? agentcore-samples reported a 403 `ExpiredTokenException` hours after startup
for credentials captured at start.

## Runtime and runs

`hr_v2_cred_v2` (id `hr_v2_cred_v2-4lRWGjHFV9`, V2, HTTP, image `py`, `MODE=http`,
`IMPORTS=heavy`, `PRIME=clients`, `OUTBOUND=1`, SigV4, PUBLIC, idle 900 s). Created 01:21
UTC, READY 01:24 (build 185 s). The handler calls `sts:GetCallerIdentity` with the STS client
built before the snapshot and reports the caller's role session name (`arn_tail`).

| label | sent (UTC) | new sessions | follow-ups |
| --- | --- | --- | --- |
| after-ready | 01:27 | 2 | 2 |
| build-plus-65min | 02:32:00 to 02:32:10, after 65 idle minutes | 2 | 2 |
| build-plus-72min | 02:32:40 to 02:33:05 | 6 | 6 |

Lines: `hr_v2_cred_v2.*.jsonl`; tables: `results.md`.

## Results

| label | request | caller (role session) | outbound call_ms | client_ms |
| --- | --- | --- | --- | --- |
| after-ready | first of session | `snapstart-build-DEFAULT` | 760, 856 | 2836, 2579 |
| after-ready | follow-up | `snapstart-build-DEFAULT` | 5.5, 5.4 | 187, 178 |
| build-plus-65min | first of session | `AgentCore-MicroVM-ddec1029-DEFAULT`, `AgentCore-MicroVM-0f077c68-DEFAULT` | 2370, 995 | 5155, 3444 |
| build-plus-65min | follow-up | the same per session | 8.7, 5.1 | 180, 197 |
| build-plus-72min | first of session | `AgentCore-MicroVM-<id>-DEFAULT`, a different id per session (6 of 6) | 37 to 46 (median 40) | 1841 to 2183 (median 2069) |
| build-plus-72min | follow-up | the same per session | 4.1 to 9.0 | 173 to 257 |

No request failed. Every answer came from one of the version's two snapshots (`boot_id`
39de4891 or 6011a6b7).

## Conclusion

The expiry is handled: once the build's credentials are past their hour, botocore's
refreshable container credentials fetch new ones from the platform's credentials endpoint
inside the restored microVM, and those are per microVM (role session
`AgentCore-MicroVM-<id>-DEFAULT`, a different id per session), so CloudTrail attribution per
session returns and no 403 occurs. In steady state the refresh costs nothing measurable: the
first call of a new session is 37 to 46 ms, the same as E14's 37 ms with unexpired build
credentials. The agentcore-samples failure is therefore specific to credentials copied out of
the provider chain (a static key pair), not to boto3 clients built before the snapshot. The HR
agents' priming (`prime.py`, one shared boto3 session and clients built at start) is safe on
this point.

The two sessions sent after 65 idle minutes paid 1.0 and 2.4 s on the outbound call and 3.4
and 5.2 s at the client. The six sessions sent 30 s later paid 40 ms. That is the slow window
after an idle hour (the same shape as the 20 to 35 s after READY in E5 and E14, and E7's
first sessions after idle), not the credential refresh, since the refresh happened on all eight.

## For AWS

Nothing new beyond A30 and A31: the build's credentials live in the snapshot for an hour and
are then replaced per microVM; the documentation could say so. The first sessions after an idle
hour pay seconds on their first outbound call.

## Commands

```
PY=<scratch venv python>
$PY scripts/v2study/create.py create hr_v2_cred_v2 --image py --protocol HTTP --platform V2 --env MODE=http --env IMPORTS=heavy --env PRIME=clients --env OUTBOUND=1 --experiment E15
$PY scripts/v2study/invoke.py --name hr_v2_cred_v2 --protocol http --new 2 --followups 1 --label after-ready --out docs/runtime-v2-evidence/E15/hr_v2_cred_v2.after-ready.jsonl
sleep 3900
$PY scripts/v2study/invoke.py --name hr_v2_cred_v2 --protocol http --new 2 --followups 1 --label build-plus-65min --out docs/runtime-v2-evidence/E15/hr_v2_cred_v2.65min.jsonl
$PY scripts/v2study/invoke.py --name hr_v2_cred_v2 --protocol http --new 6 --followups 1 --label build-plus-72min --out docs/runtime-v2-evidence/E15/hr_v2_cred_v2.72min.jsonl
$PY scripts/v2study/collect.py docs/runtime-v2-evidence/E15/*.jsonl --md docs/runtime-v2-evidence/E15/results.md
```
