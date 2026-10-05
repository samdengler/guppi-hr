# E9. Inbound JWT against IAM SigV4: findings

## Hypothesis

From the plan: the runtime's `GetWorkloadAccessTokenForJWT` call adds 0.1 to 0.3 s on every
request to a JWT runtime (A24 saw one call per request on V1 and V2), so SigV4 inbound is
cheaper per request and per restore; the release note's 30-minute token cache does not show.

## What was run

- Runtime `hr_v2_auth_jwt` (`hr_v2_auth_jwt-XhGIQ0HHWE`, version 1): V2, HTTP, image `py`,
  `MODE=http`, idle 900 s, PUBLIC, `customJWTAuthorizer` with the discovery URL of the study's
  Cognito user pool `us-east-1_2R2UtyJbr` and `allowedClients` = the client credentials app
  client `47n9t043qksmffi7uo9lvah54q` (no audience). Created 00:55:33 UTC, READY 00:58:39 UTC,
  build 186.4 s (baseline 184.9 s).
- Tokens: Cognito client credentials access tokens with scope `hr-v2-study/probe`, one hour
  lifetime. Token A (jti `8f37ebfc`, issued 00:56:00 UTC) for the first two runs; token B
  (jti `570d0469`, issued 01:00:40 UTC) for the third.
- Runs, all on 5 October 2026 UTC, one request in flight, bearer token over HTTPS with httpx:
  - `after-ready`: 25 new sessions with 2 follow-ups each, token A, 00:58:57 to 01:00:31
    (75 requests).
  - `same-token`: 1 new session with 10 follow-ups, token A, 01:00:32 to 01:00:37 (11 requests).
  - `fresh-token`: 1 new session with 10 follow-ups, token B, 01:00:41 to 01:00:47 (11 requests).
- Collected at 01:04 UTC and again at 01:15 UTC (15 minutes after the last request, for the
  CloudTrail lag); the counts did not change. 97 requests ok, 97 joined to runtime records.
- Baseline: `hr_v2_proto_http_v2` (SigV4) from `docs/runtime-v2-evidence/E1/results.md`,
  measured by group A from 00:52 UTC, the same image and settings apart from the authorizer.

## Results

Medians with p10 to p90 and n, in ms.

| runtime | label | kind | client_ms | to_receipt_ms | receipt_to_handler_ms | record_ms |
| --- | --- | --- | --- | --- | --- | --- |
| hr_v2_auth_jwt | after-ready | new | 1998 (1772 to 2403, n=25) | 96 (81 to 134, n=25) | 1873 (1653 to 2234, n=25) | 1894 (1672 to 2251, n=25) |
| hr_v2_auth_jwt | after-ready | followup | 330 (301 to 383, n=50) | 94 (82 to 116, n=50) | 194 (180 to 221, n=50) | 212 (196 to 241, n=50) |
| hr_v2_auth_jwt | same-token | new | 2232 | 194 | 1967 | 1990 |
| hr_v2_auth_jwt | same-token | followup | 344 (317 to 384, n=10) | 95 (84 to 105, n=10) | 201 (185 to 233, n=10) | 219 (201 to 246, n=10) |
| hr_v2_auth_jwt | fresh-token | new | 2414 | 188 | 2110 | 2130 |
| hr_v2_auth_jwt | fresh-token | followup | 326 (298 to 410, n=10) | 95 (82 to 108, n=10) | 195 (175 to 240, n=10) | 209 (193 to 264, n=10) |
| hr_v2_proto_http_v2 (SigV4) | after-ready | new | 1922 (1897 to 2086, n=5) | 66 (62 to 135, n=5) | 1810 (1672 to 1980, n=5) | 1828 (1690 to 1997, n=5) |
| hr_v2_proto_http_v2 (SigV4) | later | new | 1868 (1599 to 2121, n=20) | 65 (57 to 73, n=20) | 1753 (1496 to 1999, n=20) | 1778 (1513 to 2013, n=20) |
| hr_v2_proto_http_v2 (SigV4) | after-ready | followup | 174 (168 to 181, n=5) | 67 (61 to 68, n=5) | 73 (67 to 75, n=5) | 86 (82 to 91, n=5) |
| hr_v2_proto_http_v2 (SigV4) | later | followup | 178 (157 to 191, n=40) | 63 (54 to 76, n=40) | 75 (67 to 92, n=40) | 95 (84 to 106, n=40) |

Handler work was 0 ms and handler end to completion 15 to 22 ms on both runtimes.

First five new sessions after READY against the rest (receipt_to_handler_ms): 1873 (1728 to
2234, n=5) against 1876 (1635 to 2205, n=20); client 2186 against 1997. No difference.

CloudTrail `GetWorkloadAccessTokenForJWT` events with `workloadName` =
`hr_v2_auth_jwt-XhGIQ0HHWE`, read at 01:15 UTC (raw events in `cloudtrail-events.ndjson`):

| label | token | requests | sessions | calls |
| --- | --- | --- | --- | --- |
| after-ready | A | 75 | 25 | 75 |
| same-token | A | 11 | 1 | 11 |
| fresh-token | B | 11 | 1 | 11 |
| all | 2 tokens | 97 | 27 | 97 |

Sorted by time, the k-th event falls inside the k-th request's send to end window (1 s slack,
CloudTrail stamps whole seconds) for all 97 pairs, so the calls are one per request, follow-ups
included. Every call came from `AWSServiceRoleForBedrockAgentCoreRuntimeIdentity` with the
session name `CustomerSlrValidation`; none failed.

## Conclusion

A JWT runtime calls `GetWorkloadAccessTokenForJWT` once per request: 3 calls per session of 3
requests, 11 calls for 11 requests on one session with one token, 86 calls for one token over
100 seconds, so no per-session or per-token cache shows. The cost is about 0.12 s inside
the runtime on every request (follow-up receipt to handler 194 ms against 73 to 75 ms on SigV4)
and about 0.15 s at the client (330 ms against 174 to 178 ms); on a new session the same cost
sits on top of the restore (receipt to handler 1873 ms against 1753 to 1810 ms, under the
0.15 s threshold on its own). The hypothesis holds at the low end of its 0.1 to 0.3 s range.

## Surprises and notes for AWS

- The release note's 30-minute token cache does not show: the same access token sent 86 times
  in 100 seconds produced 86 exchanges, on new sessions and on follow-ups alike.
- A follow-up on an existing JWT session costs almost twice a SigV4 follow-up (330 ms against
  175 ms at the client). On a warm session the authorizer is the largest part of the
  platform's time.
- `to_receipt_ms` is about 30 ms higher on the JWT runtime (94 to 96 ms against 63 to 67 ms).
  The bearer requests go through httpx to the `/runtimes/{arn}/invocations` URL and the SigV4
  ones through boto3, so this part may be client side and is not counted in the 0.12 s.
- Like the baseline, the JWT runtime's answers show two `boot_id` values and two
  `first_random` values (two snapshots per version); hostname `localhost` and PID 1 on all 97.

## Commands

```
PY=<scratchpad>/venv/bin/python
$PY scripts/v2study/create.py create hr_v2_auth_jwt --image py --protocol HTTP --platform V2 --env MODE=http \
  --jwt-discovery https://cognito-idp.us-east-1.amazonaws.com/us-east-1_2R2UtyJbr/.well-known/openid-configuration \
  --jwt-client 47n9t043qksmffi7uo9lvah54q --experiment E9
# token: client_credentials POST to https://hr-v2-study-009080466601.auth.us-east-1.amazoncognito.com/oauth2/token
#   (basic auth with the client id and the secret read inside a command substitution), access token written to <scratchpad>/jwt.txt
$PY scripts/v2study/invoke.py --name hr_v2_auth_jwt --protocol http --new 25 --followups 2 --jwt-file <scratchpad>/jwt.txt \
  --label after-ready --out docs/runtime-v2-evidence/E9/hr_v2_auth_jwt.after-ready.jsonl
$PY scripts/v2study/invoke.py --name hr_v2_auth_jwt --protocol http --new 1 --followups 10 --jwt-file <scratchpad>/jwt.txt \
  --label same-token --out docs/runtime-v2-evidence/E9/hr_v2_auth_jwt.same-token.jsonl
# fresh token fetched into the same file
$PY scripts/v2study/invoke.py --name hr_v2_auth_jwt --protocol http --new 1 --followups 10 --jwt-file <scratchpad>/jwt.txt \
  --label fresh-token --out docs/runtime-v2-evidence/E9/hr_v2_auth_jwt.fresh-token.jsonl
$PY scripts/v2study/collect.py docs/runtime-v2-evidence/E9/*.jsonl --md docs/runtime-v2-evidence/E9/results.md --cloudtrail
# cloudtrail-events.ndjson: lookup_events(EventName=GetWorkloadAccessTokenForJWT) filtered on workloadName, matched to requests by time
$PY scripts/v2study/create.py delete hr_v2_auth_jwt --wait
```
