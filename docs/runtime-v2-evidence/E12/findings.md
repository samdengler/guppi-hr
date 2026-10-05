# E12 findings: gateway MCP sessions on against off

Run on 5 October 2026 (UTC) by the group F sub-agent of the Runtime V2 cold start study
(the text was returned to the main session, which saved it here). Raw lines:
`hr-v2-gw-off.jsonl` and `hr-v2-gw-on.jsonl` (one line per client call), `runtime-records.jsonl` (the target's own records, each tagged with the client call whose window holds it), `fixtures.json` (the gateways, targets and role policy as created), and `r0-version-rejected.*.jsonl` (a first round the gateways rejected, described below). Tables: `results.md`.

## Hypothesis

From the plan: with MCP sessions off, every `tools/call` through the gateway lands on a new runtime session of the target (A23: 21 calls, 21 sessions), so every tool call pays a V2 restore. With sessions on, one gateway session maps to one target session, so a conversation pays one restore.

## What was run

- Target runtime `hr_v2_gw_mcp_v2` (id `hr_v2_gw_mcp_v2-fYK6Rd5nYz`, version 1, platform V2, protocol MCP, image `py`, `MODE=mcp`, idle timeout 900 s, SigV4 inbound). Created 00:55:59, READY 00:59:04 (185 s). A dedicated runtime replaced the plan's `hr_v2_proto_mcp_v2` so the target's records hold gateway traffic only.
- Gateway role `hr-v2-study-gateway`: trusts `bedrock-agentcore.amazonaws.com` with `aws:SourceAccount` 009080466601. It allows `bedrock-agentcore:InvokeAgentRuntime` on `runtime/hr_v2_gw_mcp_v2*` and `bedrock-agentcore:GetWorkloadAccessToken*` on the default workload identity directory.
- Gateways, created at 00:57:18 with the AWS CLI; both were READY within 10 s.
  - `hr-v2-gw-off` (`hr-v2-gw-off-oxdpgfnszd`): `AWS_IAM` inbound, protocol MCP, no protocol configuration.
  - `hr-v2-gw-on` (`hr-v2-gw-on-xiqjdqnf24`): the same, plus `mcp.sessionConfiguration.sessionTimeoutInSeconds=3600`.
  - Neither sets `supportedVersions`.
- One target per gateway, named `probe`, created at 00:59:29.
  - `mcp.mcpServer.endpoint` is the runtime's invocation URL with the percent-encoded ARN and `?qualifier=DEFAULT`.
  - Credentials: `GATEWAY_IAM_ROLE` with `iamCredentialProvider` service `bedrock-agentcore`, region us-east-1.
  - Listing mode DEFAULT; no inline tool schema.
  - Both were READY in about 10 s after an implicit sync (00:59:30 to 00:59:36). The gateway lists the tool as `probe___probe_tool`.
- Client: `scripts/v2study/gateway_mcp.py`, sending raw HTTPS POSTs signed with SigV4 (service `bedrock-agentcore`) from the Mac mini.
  - A client session sends `initialize`, `notifications/initialized`, `tools/list` and five `tools/call`, one call at a time, and sends back the `Mcp-Session-Id` the gateway returns.
  - Sessions alternate between the gateways, and the order flips on each session index.
- Round r1 ran 01:01:08 to 01:03:02 with five client sessions per gateway. Round r2 ran 01:13:05 to 01:14:59, ten minutes after r1 ended, with five more per gateway.
- Totals per gateway: 10 client sessions, 50 `tools/call`, 80 client calls. The target logged 330 records inside client calls and 14 from the two target syncs. No call failed.
- Teardown 01:18 to 01:22: targets, gateways, role, runtime (`create.py delete --wait`) and its log delivery.

## Results

Target runtime sessions come from the target's records. Each record is attributed to the client call whose send-to-end window holds the record's receipt. The client's and the runtime's clocks agree within the 25 to 130 ms between the target's completion and the client's end.

| Gateway | Client sessions | tools/call ok | Runtime records | Distinct runtime sessions | Runtime sessions per client session | Records per runtime session | Methods on the target |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hr-v2-gw-off | 10 | 50 | 150 | 50 | {5: 10} | {3: 50} | {'initialize': 50, 'notifications/initialized': 50, 'tools/call': 50} |
| hr-v2-gw-on | 10 | 50 | 180 | 20 | {2: 10} | {1: 10, 17: 10} | {'server/discover': 10, 'initialize': 60, 'notifications/initialized': 60, 'tools/call': 50} |

What the gateway sends to the target for the first `tools/call` of a client session (the same in both rounds, all ten sessions):

| Gateway | New runtime sessions per client session | Methods behind tools/call 1 |
| --- | --- | --- |
| hr-v2-gw-off | 5 | initialize > notifications/initialized > tools/call |
| hr-v2-gw-on | 2 | server/discover > initialize > notifications/initialized > initialize > notifications/initialized > tools/call |

Every later `tools/call` on the sessions-on gateway reaches the target as `initialize > notifications/initialized > tools/call` on the stored runtime session (40 of 40). The client's `initialize`, `notifications/initialized` and `tools/list` never reach the target in either mode; the gateway answers them itself.

Target records by method (receipt to completion, median with p10 and p90):

| Gateway | Client step | Method on the target | Position on the runtime session | Records | record_ms |
| --- | --- | --- | --- | --- | --- |
| hr-v2-gw-off | tools/call 1 to 5 | initialize | first (restore) | 50 | 1724 to 1760 (p10 1550, p90 1971) |
| hr-v2-gw-off | tools/call 1 to 5 | notifications/initialized | later | 50 | 92 |
| hr-v2-gw-off | tools/call 1 to 5 | tools/call | later | 50 | 93 |
| hr-v2-gw-on | tools/call 1 | server/discover | first (restore) | 10 | 1806 (p10 1581, p90 1983, max 2161) |
| hr-v2-gw-on | tools/call 1 | initialize | first (restore) | 10 | 1631 (p10 1557, p90 1865) |
| hr-v2-gw-on | tools/call 2 to 5 | initialize | later | 40 | 91 |
| hr-v2-gw-on | tools/call 2 to 5 | notifications/initialized | later | 40 | 90 |
| hr-v2-gw-on | tools/call 2 to 5 | tools/call | later | 40 | 94 |

Client latency of `tools/call` (ms, median with p10 and p90):

| Gateway | Round | tools/call 1 | tools/call 2 to 5 | all tools/call |
| --- | --- | --- | --- | --- |
| hr-v2-gw-off | r1 | 2117 (p10 2036, p90 2363, n=5) | 2217 (p10 1985, p90 2398, n=20) | 2214 (n=25) |
| hr-v2-gw-off | r2 | 2340 (p10 2150, p90 2599, n=5) | 2158 (p10 1987, p90 2398, n=20) | 2174 (n=25) |
| hr-v2-gw-off | all | 2257 (p10 2047, p90 2494, n=10) | 2183 (p10 1985, p90 2398, n=40) | 2184 (p10 1987, p90 2419, n=50) |
| hr-v2-gw-on | r1 | 4271 (p10 4163, p90 4413, n=5) | 584 (p10 533, p90 614, n=20) | 605 (n=25) |
| hr-v2-gw-on | r2 | 4287 (p10 4010, p90 4824, n=5) | 580 (p10 523, p90 702, n=20) | 598 (n=25) |
| hr-v2-gw-on | all | 4279 (p10 4163, p90 4518, n=10) | 580 (p10 530, p90 649, n=40) | 603 (p10 530, p90 4271, n=50) |

Where a `tools/call` spends its time. `target span` runs from the first target record's receipt to the last one's completion; `gateway_ms` is the client's time outside that span.

| Gateway | Calls | target span ms | gateway_ms | tools/call record_ms | receipt_to_handler_ms of tools/call |
| --- | --- | --- | --- | --- | --- |
| hr-v2-gw-off | all 50 | 2011 (p10 1831, p90 2232) | 184 (p10 155, p90 246) | 93 | 74 |
| hr-v2-gw-on | call 1 (10) | 4067 (p10 3980, p90 4355) | 182 (p10 163, p90 277) | 92 | 74 |
| hr-v2-gw-on | calls 2 to 5 (40) | 374 (p10 353, p90 422) | 190 (p10 163, p90 254) | 94 | 74 |

Probe telemetry agrees with the records:
- Sessions off: every `tools/call` reports request counter `n=1` and a different runtime session header (50 of 50).
- Sessions on: each client session reports `n` = 1, 2, 3, 4, 5 from one process, one runtime session header, and a monotonic clock that advances by about 0.55 s per call.
- PID is 1 everywhere.

Per conversation, from the medians: sessions off costs about 2.18 s per tool call. Sessions on costs about 4.28 s for the first call and 0.58 s for each later one.

| Tool calls in one gateway session | Off | On |
| --- | --- | --- |
| 1 | 2.2 s | 4.3 s |
| 2 | 4.4 s | 4.9 s |
| 3 | 6.6 s | 5.4 s |
| 5 | 10.9 s | 6.6 s |

## Conclusion

The hypothesis holds for sessions off. Every `tools/call` opened a new target runtime session and paid a V2 restore (50 calls, 50 sessions, `initialize` at about 1.7 s on the target), for 2.2 s per call at the client in both rounds.

Sessions on keeps one target runtime session per gateway session, so later calls cost 0.58 s instead of 2.2 s. A conversation still pays two restores rather than one: before it initializes the session it keeps, the gateway opens a throwaway runtime session for `server/discover`. The first call therefore costs 4.3 s, about twice a sessions-off call. Sessions on is faster from the third tool call in a gateway session; for a conversation with one or two tool calls it is slower.

## Surprises

- **Discovery on a throwaway session.** The sessions-on gateway sends `server/discover` (the 2026-07-28 discovery method) on a new runtime session before the first `initialize` of every gateway session (10 of 10).
  - The probe's FastMCP 1.29 server does not implement it, and the call still costs a full restore (1.8 s median, 2.2 s max).
  - The sessions-off gateway never sends it.
  - The target sync at target creation does the same: `server/discover` on one runtime session, then `initialize`, `tools/list`, `prompts/list`, `resources/list` and `resources/templates/list` on a second. Each sync therefore costs two restores.
- **Repeated initialization.** The sessions-on gateway sends `initialize` and `notifications/initialized` to the target before every `tools/call`. On the first call it sends them twice: once to open the target session, once more before the tool call.
  - The AWS sessions page says the stored session id avoids repeated initialization.
  - The two extra round trips are about 0.28 s of the 0.58 s a later call costs.
  - Without them, a later call would take about 0.3 s. This is an estimate: `gateway_ms` 190 plus one 94 ms target record.
- **Protocol version rejection.** A gateway created without `supportedVersions` answers `initialize` with protocol version 2025-03-26 only.
  - It rejects any later call whose `Mcp-Protocol-Version` header is 2025-06-18 with HTTP 400 and JSON-RPC error -32600 ("Unsupported protocol version", `supported: ["2025-03-26"]`).
  - The first round (r0, 01:00:08 to 01:00:36, kept in `r0-version-rejected.*.jsonl`) failed this way because the client kept sending 2025-06-18. None of those calls reached the target.
  - Toward the target, the same gateways send `initialize` with 2025-06-18, and the sync uses 2025-11-25.
- **Two snapshot variants (for E13).** On the first request, `mono_since_start_s` read about 66.5 s or about 77.3 s. Across 70 restores there were two distinct `boot_id` and two `first_random` values. PID 1 and hostname are the same in all.
- **First initialize of each round.** The first client `initialize` of each round went to the off gateway and was the first call from the Mac in that round. It took 0.9 s in r1 and 1.15 s in r2; every other `initialize` took 0.15 to 0.22 s. `tools/list` answers from the gateway's catalog in about 0.12 s in both modes.
- **Gateway overhead.** Time spent outside the target is the same in both modes: about 0.18 to 0.19 s per call over SigV4 from the Mac.

## For AWS

1. **Discovery restore.** With MCP sessions on and an AgentCore Runtime target, each gateway session sends `server/discover` to the target on a fresh runtime session before initializing the session it keeps. Against a V2 runtime this is a full restore (1.6 to 2.2 s), and its result is thrown away. It doubles the first tool call (4.3 s against 2.2 s with sessions off). The discovery result could be cached per target at sync time, or sent on the session the gateway keeps.
2. **Repeated initialization.** With sessions on, the gateway sends `initialize` and `notifications/initialized` again on the stored target session before every `tools/call`. The documentation says the stored session id avoids repeated initialization. The two extra target round trips per tool call cost about 0.28 s.
3. **One session per call with sessions off.** Every `tools/call` to a Runtime MCP target is a new runtime session (50 of 50 here, as in A23), so on V2 every tool call pays a restore.
4. **Default protocol versions.** A gateway created without `supportedVersions` offers only 2025-03-26 to clients while it speaks 2025-06-18 and 2025-11-25 to its targets.

## Commands

```
PY=<scratch venv python>
$PY scripts/v2study/create.py create hr_v2_gw_mcp_v2 --image py --protocol MCP --platform V2 --env MODE=mcp --experiment E12

aws iam create-role --role-name hr-v2-study-gateway --assume-role-policy-document file://gw_trust.json \
  --tags Key=hr-v2-study,Value=2026-10-04
aws iam put-role-policy --role-name hr-v2-study-gateway --policy-name hr-v2-study-gateway --policy-document file://gw_policy.json
  # policy as in fixtures.json

aws bedrock-agentcore-control create-gateway --name hr-v2-gw-off --role-arn arn:aws:iam::009080466601:role/hr-v2-study-gateway \
  --protocol-type MCP --authorizer-type AWS_IAM --tags hr-v2-study=2026-10-04,experiment=E12
aws bedrock-agentcore-control create-gateway --name hr-v2-gw-on --role-arn arn:aws:iam::009080466601:role/hr-v2-study-gateway \
  --protocol-type MCP --authorizer-type AWS_IAM \
  --protocol-configuration '{"mcp":{"sessionConfiguration":{"sessionTimeoutInSeconds":3600}}}' \
  --tags hr-v2-study=2026-10-04,experiment=E12

# target_cfg.json: {"mcp":{"mcpServer":{"endpoint":"https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/arn%3Aaws%3Abedrock-agentcore%3Aus-east-1%3A009080466601%3Aruntime%2Fhr_v2_gw_mcp_v2-fYK6Rd5nYz/invocations?qualifier=DEFAULT"}}}
# target_cred.json: [{"credentialProviderType":"GATEWAY_IAM_ROLE","credentialProvider":{"iamCredentialProvider":{"service":"bedrock-agentcore","region":"us-east-1"}}}]
aws bedrock-agentcore-control create-gateway-target --gateway-identifier hr-v2-gw-off-oxdpgfnszd --name probe \
  --target-configuration file://target_cfg.json --credential-provider-configurations file://target_cred.json
aws bedrock-agentcore-control create-gateway-target --gateway-identifier hr-v2-gw-on-xiqjdqnf24 --name probe \
  --target-configuration file://target_cfg.json --credential-provider-configurations file://target_cred.json

$PY scripts/v2study/gateway_mcp.py run \
  --gw hr-v2-gw-off=https://hr-v2-gw-off-oxdpgfnszd.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp \
  --gw hr-v2-gw-on=https://hr-v2-gw-on-xiqjdqnf24.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp \
  --target probe --sessions 5 --calls 5 --round r1 --outdir docs/runtime-v2-evidence/E12
# ten minutes later, the same with --round r2

$PY scripts/v2study/gateway_mcp.py analyze \
  --runtime-arn arn:aws:bedrock-agentcore:us-east-1:009080466601:runtime/hr_v2_gw_mcp_v2-fYK6Rd5nYz --before 120 \
  --md docs/runtime-v2-evidence/E12/results.md --dump docs/runtime-v2-evidence/E12/runtime-records.jsonl \
  docs/runtime-v2-evidence/E12/hr-v2-gw-off.jsonl docs/runtime-v2-evidence/E12/hr-v2-gw-on.jsonl

aws bedrock-agentcore-control delete-gateway-target --gateway-identifier hr-v2-gw-off-oxdpgfnszd --target-id 0QLXQYQ1QR
aws bedrock-agentcore-control delete-gateway-target --gateway-identifier hr-v2-gw-on-xiqjdqnf24 --target-id EZ07TU790Z
aws bedrock-agentcore-control delete-gateway --gateway-identifier hr-v2-gw-off-oxdpgfnszd
aws bedrock-agentcore-control delete-gateway --gateway-identifier hr-v2-gw-on-xiqjdqnf24
aws iam delete-role-policy --role-name hr-v2-study-gateway --policy-name hr-v2-study-gateway
aws iam delete-role --role-name hr-v2-study-gateway
$PY scripts/v2study/create.py delete hr_v2_gw_mcp_v2 --wait
  # printed "log delivery source still in use after retries"; removed by hand:
aws logs delete-delivery --id cLE0RwHRP9yyTiHu
aws logs delete-delivery-source --name hr-v2-study-hr_v2_gw_mcp_v2
```
