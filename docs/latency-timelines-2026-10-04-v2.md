# HR assistant latency on AgentCore Runtime V2, 4 October 2026

The same harness, questions and pipeline as the V1 timelines of 4 October
(`latency-timelines-2026-10-04.md`), run twice on the new AgentCore Runtime (`PlatformVersion`
V2) for the four runtimes behind Connect: once as deployed (V2), and once with the servers primed
before the snapshot (V2 primed, `agent/src/hr_agent/prime.py`). Each run is 22 chats of the
four suggestions plus two typed Pay chats, and a smoke chat. Nothing else changed between the runs.

| Run | Window (UTC) | Runtime versions | Data |
| --- | --- | --- | --- |
| V1 | 20:19 to 20:34 | profile, travel, pay 21; tools 26 | `latency-timelines-2026-10-04-evidence.json` |
| V2 | 21:41:30 to 21:53:40 | 22 and 27 on V2, deployed 21:40:48 | `latency-timelines-2026-10-04-v2-evidence.json` |
| V2 primed | 21:58:00 to 22:09:40 | 23 and 28 on V2, ready 21:54:01 | `latency-timelines-2026-10-04-v2p-evidence.json` |

The deploy of the primed version started its runtime updates at 21:50:57, while the V2 run was
still going; its endpoints kept the V2 version until 21:54:01, and the chats in those minutes were
no slower than the earlier ones (Profile 8.79 s and 8.45 s against a median of 9.38 s before).

## Summary

- V2 made every first answer that reaches a sub-agent slower: Profile 6.19 s on V1, 9.25 s on V2
  and 8.62 s primed; Pay 8.62 s, 16.69 s and 13.46 s; Travel 6.88 s, 7.32 s and 7.18 s. ClarifyFlow,
  PolicyFlow and every follow-up stayed the same or got slightly faster.
- The cost is a fixed restore on every new session. The runtime takes 1.87 s (V2) and 2.06 s (V2
  primed) from receiving a session's first request to handing it to the container, against 0.84 s on
  V1, where a new session took an already running microVM from a pool. Later requests on a session
  take 0.19 to 0.20 s on all three.
- The tools gateway opens a new tools runtime session for every tool call (A23), so every snapshot
  read pays a restore: a tool call took 1.87 s through the gateway on V1 and 3.53 s (V2) and 3.41 s
  (V2 primed). Pay reads two records and pays it twice.
- Priming worked as designed and took 342 ms (tools) and 812 ms (profile) at startup. It removed our
  own first-request work (the MCP client start fell from 310 ms to 42 ms; Pay's answer fell by 3.2 s)
  but cannot reach the restore itself.
- The new span deliveries (db53b19) put AgentCore's own spans into `aws/spans`: gateway, runtime,
  Identity and Policy. They show the restore inside `AgentCore.Runtime.Invoke`, confirm TC10 from
  AWS's side, and give the parent of the sub-agent's root span (TC9).

## First words

Median, with p10 to p90, from the click to the first reply text.

| Path | V1 | V2 | V2 primed | Turns (V1, V2, V2 primed) |
| --- | --- | --- | --- | --- |
| ClarifyFlow | 1.13 s (0.99 to 1.31) | 1.18 s (1.05 to 1.33) | 1.08 s (1.00 to 1.21) | 5, 5, 5 |
| PolicyFlow, first | 3.45 s (3.18 to 3.73) | 3.25 s (2.90 to 3.54) | 3.44 s (3.04 to 4.02) | 5, 5, 5 |
| PolicyFlow, follow-up | 1.72 s (1.57 to 2.10) | 1.47 s (1.33 to 1.61) | 1.50 s (1.38 to 14.03) | 5, 5, 5 |
| Profile, first | 6.19 s (5.62 to 7.14) | 9.25 s (8.53 to 16.90) | 8.62 s (8.22 to 9.22) | 17, 11, 11 |
| Profile, follow-up | 2.75 s (2.50 to 3.38) | 2.54 s (2.43 to 2.74) | 2.52 s (2.41 to 2.59) | 6, 6, 6 |
| Travel, first | 6.88 s (5.92 to 6.99) | 7.32 s (7.03 to 16.24) | 7.18 s (6.33 to 9.33) | 5, 5, 5 |
| Travel, follow-up | 4.13 s (3.71 to 4.40) | 3.75 s (3.55 to 3.85) | 3.72 s (3.49 to 4.28) | 5, 5, 5 |
| Pay, first | 8.62 s (8.06 to 9.17) | 16.69 s (13.47 to 19.91) | 13.46 s (12.89 to 14.03) | 2, 2, 2 |
| Pay, follow-up | 2.47 s (2.34 to 2.59) | 2.40 s | 2.62 s (2.54 to 2.70) | 2, 2, 2 |

The first chat to reach each runtime after the V2 deploy was the slowest of all (Profile 16.90 s in
the smoke chat and 18.28 s in the first main chat, Travel 15.64 s, Pay 20.71 s); one later Travel
chat (21:51) also took 16.64 s. The V1 run had 17 Profile first turns
because it included three reuse pairs; the V2 reuse pairs ran across the second deploy and are left
out.

## Profile, first call in a chat

Median durations of the steps (ms).

| Step | V1 | V2 | V2 primed |
| --- | --- | --- | --- |
| Connect hands the message to the designer | 285 | 239 | 205 |
| Routing model (designer) | 455 | 446 | 509 |
| Data request DelegateProfile (designer's view) | 5,047 | 8,186 | 7,140 |
| Runtime: session and delivery to the sub-agent | 933 | 1,991 | 2,149 |
| Sub-agent request (POST / on the runtime) | 3,834 | 5,787 | 4,820 |
| Sub-agent: MCP client start | 310 | 312 | 42 |
| MCP initialize, tools/list (tools gateway) | 98, 188 | 87, 191 | 82, 181 |
| Snapshot read `hr___get_profile` through the tools gateway | 1,865 | 3,533 | 3,414 |
| Model: time to first token, generation | 539, 224 | 531, 221 | 545, 227 |
| Connect posts the reply, pushes it to the page | 118, 94 | 149, 104 | 112, 82 |

## Pay and Travel, first call in a chat

| Step | V1 | V2 | V2 primed |
| --- | --- | --- | --- |
| Pay: data request DelegatePay (designer's view) | 7,423 | 15,420 | 12,234 |
| Travel: data request DelegateTravel (designer's view) | 5,767 | 6,286 | 5,903 |
| Travel: runtime session and delivery | 1,236 | 1,964 | 2,156 |
| Travel: sub-agent request | 4,346 | 3,845 | 3,351 |
| Travel: MCP client start | 379 | 416 | 44 |
| Travel: policy search `docs___Retrieve` | 689 | 679 | 695 |
| Travel: generation | 1,729 | 1,223 | 1,209 |

Travel reads the knowledge base, which is not a runtime, so it pays one restore per chat (the
sub-agent's session) and no more. Its shorter generation on V2 is the model's output length, not the
platform. The Pay sub-agent's own spans are missing from Dynatrace on V2 (see the observability
notes), so its inner steps come only from the runtime and gateway spans.

## Chat start

The chat start does not touch AgentCore Runtime and did not change: the browser's
`POST /api/hr/chat/start` took 2,305 ms (V1), 2,326 ms (V2) and 2,204 ms (V2 primed); the greeting
wait 1,090, 1,046 and 990 ms.

## Where the runtime's time goes

From the runtimes' own `InvokeAgentRuntime` records and `AgentCore.Runtime.Invoke` spans, joined to
the containers' spans. The runtime's clock and the containers' agree to about 20 ms at the end of a
request.

| Measure (median) | V1 | V2 | V2 primed |
| --- | --- | --- | --- |
| Agents gateway to the runtime's receipt, a session's first request | 92 ms | 101 ms | 96 ms |
| Runtime receipt to the sub-agent container, first request | 838 ms (464 to 1,404) | 1,870 ms (1,638 to 2,445) | 2,057 ms (1,642 to 2,464) |
| Runtime receipt to the sub-agent container, later requests | 183 ms | 202 ms | 194 ms |
| Tools runtime: receipt to the container, a session's first request | 613 ms | 2,052 ms | 2,087 ms |
| Tools runtime: receipt to the container, second and third requests | 180 to 192 ms | 206 to 208 ms | 202 to 211 ms |
| `AgentCore.Runtime.Invoke` on the tools runtime, first request of a session | not recorded | 2,051 ms | 2,233 ms |
| `AgentCore.Runtime.Invoke` on the tools runtime, later requests | not recorded | 338 ms | 307 ms |
| A whole tool call at the runtime (first receipt to third answer) | 1,435 ms | 2,992 ms | 3,001 ms |
| The `tools/call` itself at the runtime | 391 ms | 490 ms | 321 ms |

The restore is the same with and without priming because priming makes the snapshot hold more, not
less; what priming saves is the work after the restore. No AgentCore span breaks the restore down:
`AgentCore.Runtime.Invoke` is one span from receipt to answer, with `latency_ms` and `session.id`.

## AgentCore's own spans

Medians from `aws/spans` (V2 primed; V2 within a few ms):

| Span | Service | Median |
| --- | --- | --- |
| `AgentCore.Gateway.InboundAuth` | both gateways | 40 to 43 ms |
| `AgentCore.Identity.Authorize` | both gateways | 29 to 34 ms |
| `AgentCore.Gateway.EvaluateRoutingRules` | both gateways | 0 to 1 ms |
| `AgentCore.Policy.AuthorizeAction` (per tool call) | tools gateway | 50 ms |
| `AgentCore.Policy.PartiallyAuthorizeActions` (tools/list) | tools gateway | 70 ms |
| `AgentCore.Identity.GetWorkloadAccessToken` (runtime token, per call) | tools gateway | 39 ms |
| `AgentCore.Identity.GetResourceOauth2Token` (runtime token, per call) | tools gateway | 114 ms |
| `AgentCore.Gateway.Initialize`, `NotificationsInitialized`, `ListTools` | tools gateway | 68, 63, 162 ms |
| `AgentCore.Gateway.InvokeTool.hr___get_profile` | tools gateway | 3,242 ms |
| `AgentCore.Gateway.InvokeTool.docs___Retrieve` | tools gateway | 493 ms |
| `AgentCore.Gateway.Http.profile` | agents gateway | 6,725 ms |

Trace links in the same spans: the tools gateway's `InvokeTool` and the tools runtime's `Invoke`
share a trace on every call (48 of 48); the agents gateway's `Http` spans share a trace with the
runtime `Invoke` they cause on none of the calls (0 of 32), which confirms TC10 from AWS's own data;
and the sub-agent runtime's `Invoke` span is the parent of our sub-agent's root span in Dynatrace
(27 of 32), the parent that TC9 found missing.

## Observability notes from the V2 runs

- On V2 a runtime writes one log stream per session, `runtime-logs-<session id>`, and one
  `build-logs-<id>` stream per snapshot build. The process start lines are in the build stream: a
  restored session never starts a process.
- CloudTrail names V2 callers differently: the snapshot build calls Identity as
  `snapstart-build-DEFAULT` (38 calls in the primed run), and a sub-agent session as
  `AgentCore-MicroVM-<id>-DEFAULT`.
- The runtime still calls `GetWorkloadAccessTokenForJWT` once for every request it delivers on V2
  (76 for 76 requests; 80 for 78), as A24 found on V1.
- The containers on V2 make no calls to the instance metadata service (169.254.169.254); on V1 each
  sub-agent request read credentials there.
- Dynatrace lost most of the Pay sub-agent's spans on V2 (17 in the V2 run, none in the primed run,
  against 52 on V1), and fewer of the Profile sub-agent's (157 against 337 on V1 for a similar number
  of turns). The runtime and gateway spans of the same requests are complete, so the loss is in our
  exporter on restored, short-lived sessions, which end before a batch is sent.
- The tools runtime on V2 receives the platform's MCP pings on `http://127.0.0.1:8000/mcp`
  (about 2,000 spans per run), which the V1 filter for `localhost` does not exclude.

## The PTO follow-up that took 22.3 s

In the primed run, contact `ff24e31d-2bc1-41d2-93e0-034fb844cd65` (the third PolicyFlow chat), the
follow-up "Does unused PTO carry over?" showed its answer 22.32 s after the click. The browser sent
`SendMessage` at 22:00:19.869 UTC and its response arrived at 22:00:40.815; Connect stamped the
message at 22:00:40.756 (CloudTrail `SendMessage` request `22567f80-8c17-4736-ae58-2dab5e1aefa9`,
message `01a108ee-f634-74f0-bbb0-c2b23749792f`), and the designer received it 21.2 s after the click
and answered from the PolicyFlow journey in 883 ms. So 20.9 s passed between the browser sending the
request and Connect accepting it, with nothing of the HR stack involved; the other four follow-ups of
the run took 1.3 to 1.6 s. It does not depend on the runtime version.

## Data

- Report and step tables: `latency-timelines-2026-10-04-v2.md` (this file).
- Evidence with every id (contacts, request ids, trace and span ids, runtime sessions, CloudTrail):
  `latency-timelines-2026-10-04-v2-evidence.md` and `.json`, `latency-timelines-2026-10-04-v2p-evidence.md`
  and `.json`. The JSON files also carry AgentCore's own spans for each window under
  `agentcore_spans`.
- Decisions and findings that follow from it: latency log L32 and L33, aws-feedback A25.
