# Evidence for the AgentCore Runtime V2 with priming latency run of 4 October 2026

The ids behind every number in `latency-timelines-2026-10-04.md`: Connect contacts, the designer's
correlation ids, API Gateway and Lambda request ids, X-Ray and Dynatrace trace and span ids,
AgentCore Gateway request ids, runtime session ids, the log stream of each microVM, and the
request ids of the AgentCore Identity calls. The same data, with every step of every turn, is
in `latency-timelines-2026-10-04-evidence.json`.

Account `009080466601`, region `us-east-1`. Window 2026-10-04T21:58:00Z to 2026-10-04T22:09:40Z: 23 chats,
46 turns, no deploys inside the window; designer build(s) `7a4c9ca7-9af5-4919-9785-56ff5823d4e8`.
All times are UTC on 4 October 2026.
Offsets in ms are from the click that sent the question, or from the page's navigation for a
chat start. Tokens, access key ids, IP addresses and reply text are left out.

## Joining the sources

- The Connect contact id ties the browser, the chat start function, the designer's log and the
  sub-agents: the designer calls a sub-agent with runtime session id `{contactId}-{domain}`.
- The agents gateway's `trace_id` is its own; the sub-agent's spans start a new trace (the
  Dynatrace trace id below). The tools gateway logs the sub-agent's trace id, and the tools
  runtime logs the same `trace_id` on its MCP lines, so a tool call is joined to its microVM by
  trace id and time. A follow-up's MCP spans carry the first request's trace id (the MCP
  client's thread keeps its first context), so time decides between them.
- A runtime's microVM is its `[runtime-logs]<id>` log stream: one stream per microVM, created
  when the microVM boots.
- Identity's on-behalf-of exchanges call the token issuer through API Gateway; X-Ray links each
  issuer Lambda request id to the API Gateway request id and extended request id.
- The chat start's API Gateway request is matched to its Lambda invocation by time (the access
  log carries no Lambda request id; starts were seconds apart).

## Resources

| Resource | ARN or id |
| --- | --- |
| Amazon Connect instance guppi-connect | `arn:aws:connect:us-east-1:009080466601:instance/5665011a-f5fa-40e3-92d0-85ff625d10f6` |
| Contact flow (chat, Agentic CX block) | `arn:aws:connect:us-east-1:009080466601:instance/5665011a-f5fa-40e3-92d0-85ff625d10f6/contact-flow/79627021-74ad-4417-83ab-fa84d8258c63` |
| Agentic CX designer build (all turns) | `buildId 7a4c9ca7-9af5-4919-9785-56ff5823d4e8` |
| Chat start Lambda hr-chat-start (Rust, arm64, 1024 MB) | `arn:aws:lambda:us-east-1:009080466601:function:hr-chat-start` |
| Chat start REST API hr-chat-start, stage prod | `arn:aws:apigateway:us-east-1::/restapis/ng11tjce58/stages/prod` |
| Token issuer Lambda guppi-gpt-obo-issuer (Rust) | `arn:aws:lambda:us-east-1:009080466601:function:guppi-gpt-obo-issuer` |
| Token issuer REST API guppi-obo-issuer, stage prod | `arn:aws:apigateway:us-east-1::/restapis/kdkmszmwge/stages/prod` |
| Agents gateway hr-super-agent-agents (HTTP targets profile WRADAXMX9A, travel AGS0JX5M1V, pay WRBXBB12RO) | `arn:aws:bedrock-agentcore:us-east-1:009080466601:gateway/hr-super-agent-agents-rfkdgz7314` |
| Tools gateway hr-super-agent-tools (MCP; targets hr VODAOVCYZX, docs KB8LJT6NRY) | `arn:aws:bedrock-agentcore:us-east-1:009080466601:gateway/hr-super-agent-tools-7bi54dgr6g` |
| Policy engine on the tools gateway (ENFORCE) | `arn:aws:bedrock-agentcore:us-east-1:009080466601:policy-engine/hr_super_agent_tools_policy-gfigp9no2v` |
| Runtime hr_super_agent_profile, endpoint DEFAULT (version 21) | `arn:aws:bedrock-agentcore:us-east-1:009080466601:runtime/hr_super_agent_profile-7IkHmEG40H/runtime-endpoint/DEFAULT` |
| Runtime hr_super_agent_travel, endpoint DEFAULT (version 21) | `arn:aws:bedrock-agentcore:us-east-1:009080466601:runtime/hr_super_agent_travel-7yhekY3cSf/runtime-endpoint/DEFAULT` |
| Runtime hr_super_agent_pay, endpoint DEFAULT (version 21) | `arn:aws:bedrock-agentcore:us-east-1:009080466601:runtime/hr_super_agent_pay-7zZl2rCGqo/runtime-endpoint/DEFAULT` |
| Runtime hr_super_agent_tools (MCP server), endpoint DEFAULT (version 26) | `arn:aws:bedrock-agentcore:us-east-1:009080466601:runtime/hr_super_agent_tools-Ykb6G5FTK1/runtime-endpoint/DEFAULT` |
| Workload identity of the chat start | `arn:aws:bedrock-agentcore:us-east-1:009080466601:workload-identity-directory/default/workload-identity/hr-chat-start` |
| Credential provider for the hop tokens (chat start) | `arn:aws:bedrock-agentcore:us-east-1:009080466601:token-vault/default/oauth2credentialprovider/guppi-obo-hr-bridge` |
| Credential providers for the sub-agents' tools tokens | `arn:aws:bedrock-agentcore:us-east-1:009080466601:token-vault/default/oauth2credentialprovider/guppi-obo-hr-agent-profile (also -travel, -pay)` |
| Credential provider for the tools gateway's runtime token | `arn:aws:bedrock-agentcore:us-east-1:009080466601:token-vault/default/oauth2credentialprovider/guppi-obo-hr-tools-gateway` |
| Sub-agent model (cross-region inference profile) | `us.anthropic.claude-haiku-4-5-20251001-v1:0` |

## Log sources

| Source | Where | Ids it carries |
| --- | --- | --- |
| Chat start function | `/aws/lambda/hr-chat-start` | chat_start and chat_report JSON lines; START/REPORT with RequestId and XRAY TraceId |
| Chat start API access log | `/aws/apigateway/hr-chat-start` | requestId per request |
| Token issuer function | `/aws/lambda/guppi-gpt-obo-issuer` | one line per exchange: client, audience, route |
| Token issuer API access log | `/aws/apigateway/guppi-obo-issuer` | requestId |
| Agents gateway | `/aws/vendedlogs/bedrock-agentcore/hr-super-agent-agents` | request_id, trace_id, target |
| Tools gateway | `/aws/vendedlogs/bedrock-agentcore/hr-super-agent-tools` | request_id, trace_id, MCP method, tool, policy latency |
| Sub-agent runtimes | `/aws/bedrock-agentcore/runtimes/hr_super_agent_{profile,travel,pay}-*-DEFAULT` | [runtime-logs]<id> stream per microVM on V1; runtime-logs-<session id> stream per session on V2; run lines with duration_ms and trace_id |
| Tools runtime | `/aws/bedrock-agentcore/runtimes/hr_super_agent_tools-Ykb6G5FTK1-DEFAULT` | runtime-logs-<session id> stream per session on V2; trace_id on each MCP line |
| X-Ray spans | `aws/spans` | chat start and issuer Lambda spans, issuer API Gateway spans |
| Dynatrace | `tenant zfr04910, fetch spans where service.name starts with hr_super_agent` | sub-agent and tools runtime spans: trace.id, span.id, session.id, aws.request_id of Identity calls, gen_ai.* model fields |
| Agentic CX designer | `connect/acxd/logs.js <contactId> --json` | per-turn correlationId, messageId, buildId, model and data request events |

## Tool calls through the tools gateway (A23, time sink 1)

Every snapshot read by a sub-agent: 11 calls on 9 different tools runtime sessions. Delivery is
from the issuer's answer (the gateway's runtime token) to the tools server's first span;
handshake from that first span to the `tools/call` span; total is the sub-agent's MCP span.

| Time | Contact | Tool | Tools gateway request id | Trace id | Tools runtime microVM (log stream) | Policy ms | Delivery ms | Handshake ms | Tool ms | Total ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 21:58:51.079 | `561a7117-9536-4cc8-a758-6bb275dc12b9` | hr___get_profile | `37f4d90c-c7b0-4625-b1c5-680817a1c7d8` | `6ac2cc182a6077655e5d9bbb5dacf480` |  | 53 |  |  |  | 3577 |
| 21:59:26.617 | `d11a9f22-8b02-42e4-a420-126cdea3c0da` | hr___get_profile | `aab206e6-ec80-4c20-beda-d53cd30e7ca8` | `6ac2cc3b0b1649483eba08f907ce6be2` |  | 48 | -261 |  |  | 3117 |
| 21:59:47.514 | `f5c8d21e-cb89-48c7-9811-2029cbdfaf09` | hr___get_profile | `ae93d5f4-522f-4dcd-8edb-e1d22c423fdd` | `6ac2cc505398aeee76a16e5f667b15ae` |  | 53 | -198 |  |  | 3390 |
| 22:01:35.058 | `4a266146-5526-49e8-8642-bd074f0bf6dc` | hr___get_profile | `69dd9e92-d2bb-4f1b-86a9-8eb97899ca5d` | `6ac2ccbc52ef211d3d0ece9c20d9e1d8` | `runtime-logs-c2111e45-1e98-45fb-9bc3-5f89a142ec2c` | 47 | -231 |  |  | 3268 |
| 22:01:56.798 | `22034a3d-59a0-4a92-b3bb-41697ed163a4` | hr___get_profile | `01be85b5-950d-4b41-9444-667def1e9856` | `6ac2ccd259ee5eea6713b090546949c7` | `runtime-logs-7aa92b34-3263-4e01-b42a-82972e58cfc7` | 48 | 208 |  |  | 2981 |
| 22:03:49.574 | `00e687c5-9e54-4631-b182-17f3aca529a8` | hr___get_profile | `59702b60-69c2-409d-b3d8-49df036e6ada` | `6ac2cd427008459d4d0359e15a44a050` | `runtime-logs-9bf1c80e-49c3-45b9-ae91-f9e9b649f756` | 53 | 2511 |  |  | 4018 |
| 22:04:11.620 | `fd7abdc9-d95d-41c7-adea-3703b8fa492b` | hr___get_profile | `4e8c471a-4b6c-4ca8-bee0-b6b2d6456d78` | `6ac2cd5819e8923a445d3d3e5bd8162a` | `runtime-logs-20c3993a-01ea-4854-b9c0-80a424ebe7a8` | 65 | 2904 | 90 | 2 | 3467 |
| 22:05:31.285 | `f6651260-360b-4871-8432-3046d7b51925` | hr___get_profile | `0310d1fb-4fc8-450c-8317-473364716061` | `6ac2cda86ebe004d22cd65a901cc9639` |  | 45 |  |  |  | 3809 |
| 22:05:52.208 | `81ffe68f-1e8b-458a-9163-3456dbd51f58` | hr___get_profile | `e712d0fe-9ef6-4062-b268-ec5854fafa86` | `6ac2cdbd29692b7c5144663255a4223c` | `runtime-logs-ba33a63d-15cb-4c7e-a6e2-9e2ddcd0efd4` | 50 | -278 |  |  | 2722 |
| 22:07:43.933 | `1113830f-0426-4524-824d-91650de94404` | hr___get_profile | `d28a2fca-940b-4229-88fb-ee37036c76bc` | `6ac2ce2d29e0337e6fcaa29c1854c67e` | `runtime-logs-695a6ba5-1aaf-4a18-9589-6850f2875ccb` | 47 | -216 |  |  | 3414 |
| 22:08:08.210 | `4bd55fd5-a4a4-44b5-bcf8-643024f7cda9` | hr___get_profile | `a1f998d8-563d-4c2e-a486-11e6ba35f87a` | `6ac2ce453440180122989ebb5b437c14` | `runtime-logs-faecf06b-3907-404a-8131-381468f3e744` | 34 | -205 |  |  | 3449 |

The runtime token exchange for each call (Identity to the issuer):

| Time | Tools gateway request id | Issuer API Gateway request id | Issuer Lambda request id | X-Ray trace |
| --- | --- | --- | --- | --- |
| 21:58:51.079 | `37f4d90c-c7b0-4625-b1c5-680817a1c7d8` | `74b9196b-c14d-411c-9477-e07ebad20d90` | `a2ea8aa1-8de4-4271-be9f-dcbf3350edb8` | `1-6ac2cc1b-5a4d6d2701ba5790063ba52e` |
| 21:59:26.617 | `aab206e6-ec80-4c20-beda-d53cd30e7ca8` | `854ca7a0-a905-45d7-860d-f97dc274dcd6` | `409a35f2-bd9d-4471-88fb-661ed7c15e1a` | `1-6ac2cc3e-1acc31d874484f311e529c5d` |
| 21:59:47.514 | `ae93d5f4-522f-4dcd-8edb-e1d22c423fdd` | `03499afb-8fd9-4d37-b262-434c6ff51e5f` | `61c2ee74-b50f-4c5e-b763-fb037edb5eaf` | `1-6ac2cc53-19416b044ac535901b4c90ed` |
| 22:01:35.058 | `69dd9e92-d2bb-4f1b-86a9-8eb97899ca5d` | `a42db576-52fd-44fe-bb49-ba8cb22a6b26` | `caacad58-55c0-4ae3-bfde-01b2e6900e16` | `1-6ac2ccbf-343d99900b9b9ef80238ae60` |
| 22:01:56.798 | `01be85b5-950d-4b41-9444-667def1e9856` | `cdf86a57-b7d1-4c3c-9164-f35ba7a01e51` | `50afa373-53ec-44d5-b346-3e03629bc1d5` | `1-6ac2ccd5-4957c7905f3830cd459b2e6a` |
| 22:03:49.574 | `59702b60-69c2-409d-b3d8-49df036e6ada` |  | `fbad984c-2f46-4c3e-988d-849fc71895da` |  |
| 22:04:11.620 | `4e8c471a-4b6c-4ca8-bee0-b6b2d6456d78` | `6763d78e-c7e5-4d0d-b0ba-4bfbfc896558` | `ae98bcb9-7964-4961-b1c5-7f274f31c888` | `1-6ac2cd5b-4cc193a51b8b205131419c98` |
| 22:05:31.285 | `0310d1fb-4fc8-450c-8317-473364716061` | `6e11ed72-efa1-4437-b181-95766852f078` | `7c61ad93-3b37-43b6-918b-c7b6b5d268ed` | `1-6ac2cdab-648aa720313aeb2e778df17c` |
| 22:05:52.208 | `e712d0fe-9ef6-4062-b268-ec5854fafa86` | `29f5cbc2-319a-49e0-a516-5215d8536ff5` | `12fe718b-4bb0-4b22-924e-f8dc53f53e80` | `1-6ac2cdc0-08b515c737440fdd3020c7f4` |
| 22:07:43.933 | `d28a2fca-940b-4229-88fb-ee37036c76bc` | `2f5e0a2f-66c2-477e-9580-c5f6eec3960b` | `821c50a5-f09f-4d1d-bc63-c291ab1f6aa3` | `1-6ac2ce30-1fd1f9bf7c0bcbd06aec502e` |
| 22:08:08.210 | `a1f998d8-563d-4c2e-a486-11e6ba35f87a` | `fc18172f-8e02-4997-9142-88ea36956faf` | `84db7b7f-7008-4fbe-920b-30e1fd88c983` | `1-6ac2ce48-04efeeca3b5b4a9f1779b01f` |

## Sub-agent runtime sessions and microVMs (A21, time sink 2)

Every sub-agent request: 26 requests on 16 sessions, each session on its own instance. Delivery
is from the agents gateway's "Executing Http request for target" to the sub-agent's `POST /` span.

| Request time | Call | Runtime session id | Agents gateway request id | Gateway trace id | Sub-agent trace id (Dynatrace) | Root span id | MicroVM (log stream) | Process started | Delivery ms | Request ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 21:58:50.496 | first | `561a7117-9536-4cc8-a758-6bb275dc12b9-profile` | `fe732bef-c4e7-41db-b6b0-f97184c5ed91` | `6ac2cc1820f2e56e76ab07a74e259c22` | `6ac2cc182a6077655e5d9bbb5dacf480` | `5120ebb0b7929f28` | `runtime-logs-561a7117-9536-4cc8-a758-6bb275dc12b9-profile` |  | 2030 | 4926 |
| 21:59:26.019 | first | `d11a9f22-8b02-42e4-a420-126cdea3c0da-profile` | `ba858795-d425-43da-9494-0207f3efeca4` | `6ac2cc3b2a2fa20a7b3da4df63bfbc85` | `6ac2cc3b0b1649483eba08f907ce6be2` | `1cf995888aad5d77` | `runtime-logs-d11a9f22-8b02-42e4-a420-126cdea3c0da-profile` |  | 2308 | 4511 |
| 21:59:46.921 | first | `f5c8d21e-cb89-48c7-9811-2029cbdfaf09-profile` | `280c0d92-165e-46cd-b591-c7b371f80c8c` | `6ac2cc5020f809e02d98ff5d75a5a5ae` | `6ac2cc505398aeee76a16e5f667b15ae` | `3229f0786c2ba78a` | `runtime-logs-f5c8d21e-cb89-48c7-9811-2029cbdfaf09-profile` |  | 2014 | 4769 |
| 21:59:56.253 | follow-up | `f5c8d21e-cb89-48c7-9811-2029cbdfaf09-profile` | `c2778387-8b5d-4bd5-bcd3-61cf05025b2c` | `6ac2cc5b42acb9293b913aba4115ddb3` | `6ac2cc5b5f26258c29d2288034475a86` | `faeb68af29b3af26` | `runtime-logs-f5c8d21e-cb89-48c7-9811-2029cbdfaf09-profile` |  | 288 | 859 |
| 22:01:00.347 | first | `61ab9cfd-f7dd-43d1-9261-10a32948a19c-travel` | `0279f9e3-06aa-46dc-b23b-f077b9e3b771` | `6ac2cc993c1c33a95c2070580e435ea6` | `6ac2cc994331df2410066b6c4d916801` | `8eff4c80bbd88be0` | `runtime-logs-61ab9cfd-f7dd-43d1-9261-10a32948a19c-travel` |  | 2507 | 5235 |
| 22:01:10.923 | follow-up | `61ab9cfd-f7dd-43d1-9261-10a32948a19c-travel` | `f06177a3-3e29-4c81-9ccd-3e73b9b4dd80` | `6ac2cca6414a13ae64d1665b78991502` | `6ac2cca621832e10259b64562ccab5d9` | `28f31c05e4d25aee` | `runtime-logs-61ab9cfd-f7dd-43d1-9261-10a32948a19c-travel` |  | 280 | 2155 |
| 22:01:34.330 | first | `4a266146-5526-49e8-8642-bd074f0bf6dc-profile` | `978fc7e8-6b4a-4205-a997-0a0f22524894` | `6ac2ccbc78ae56467cb339454eaa2eaa` | `6ac2ccbc52ef211d3d0ece9c20d9e1d8` | `5cccecb7d57841ac` | `runtime-logs-4a266146-5526-49e8-8642-bd074f0bf6dc-profile` |  | 2041 | 4777 |
| 22:01:56.213 | first | `22034a3d-59a0-4a92-b3bb-41697ed163a4-profile` | `7841520e-6e26-4e01-ae22-bdb600abca0b` | `6ac2ccd125d74c724b4fd4ac58520201` | `6ac2ccd259ee5eea6713b090546949c7` | `1fe165aa1a1cb3aa` | `runtime-logs-22034a3d-59a0-4a92-b3bb-41697ed163a4-profile` |  | 2160 | 4375 |
| 22:02:05.344 | follow-up | `22034a3d-59a0-4a92-b3bb-41697ed163a4-profile` | `089f98d2-c9e6-434f-9bfb-ac8c4ca59b41` | `6ac2ccdc283d6ff41f8488757c969f64` | `6ac2ccdd1ef909ca287d6feb3a5632f9` | `2f7306e99c143638` | `runtime-logs-22034a3d-59a0-4a92-b3bb-41697ed163a4-profile` |  | 287 | 878 |
| 22:02:44.928 | first | `5fadbba0-6b87-454e-857a-1a5ca91fc798-travel` | `ed0dae40-6ae7-4bc6-a8a3-e830b66e92f1` | `6ac2cd02685b9541427b88f9605a1ab4` | `6ac2cd0253f5f33b5f52c67f68faca96` | `b287056983d5c4bd` | `runtime-logs-5fadbba0-6b87-454e-857a-1a5ca91fc798-travel` |  | 2046 | 4611 |
| 22:02:54.171 | follow-up | `5fadbba0-6b87-454e-857a-1a5ca91fc798-travel` | `a68af525-49b7-424b-b993-0de50db2ecf0` | `6ac2cd0d19125b04248846a770795c9d` | `6ac2cd0d53679f0e73b8f22970b9fed2` | `e95d0fb74f3bcd4e` | `runtime-logs-5fadbba0-6b87-454e-857a-1a5ca91fc798-travel` |  | 289 | 1901 |
| 22:03:48.980 | first | `00e687c5-9e54-4631-b182-17f3aca529a8-profile` | `1cd2b95c-ba7e-4604-aae3-0ef596961584` | `6ac2cd42099108bc0b70da341e86ec3d` | `6ac2cd427008459d4d0359e15a44a050` | `71e2cd5406ccc55d` | `runtime-logs-00e687c5-9e54-4631-b182-17f3aca529a8-profile` |  | 2552 | 5461 |
| 22:04:10.961 | first | `fd7abdc9-d95d-41c7-adea-3703b8fa492b-profile` | `28722fcc-1aee-474b-9bce-43fbfaa13b1d` | `6ac2cd586e565aa814392df923c3c78b` | `6ac2cd5819e8923a445d3d3e5bd8162a` | `61f977d65d1f96d5` | `runtime-logs-fd7abdc9-d95d-41c7-adea-3703b8fa492b-profile` |  | 2383 | 4890 |
| 22:04:20.503 | follow-up | `fd7abdc9-d95d-41c7-adea-3703b8fa492b-profile` | `9f27a1a0-3535-40fb-bbec-f312659cce0a` | `6ac2cd647db60d587c9e8a54393bbf66` | `6ac2cd6447bbb64b4060b8b56fd276b5` | `06fe78c9882bc4a8` | `runtime-logs-fd7abdc9-d95d-41c7-adea-3703b8fa492b-profile` |  | 309 | 844 |
| 22:04:59.977 | first | `261c9e37-d142-467c-93cf-db672b3361e1-travel` | `fbbff3f0-f549-444b-91f1-29a3ef7b194f` | `6ac2cd894524eb1764c8694169821a4c` | `6ac2cd89219f3d521fe1e4a874c61e0b` | `02aa8a0f6f49e8f1` | `runtime-logs-261c9e37-d142-467c-93cf-db672b3361e1-travel` |  | 2344 | 3351 |
| 22:05:08.272 | follow-up | `261c9e37-d142-467c-93cf-db672b3361e1-travel` | `08c5c7b3-88fa-4a14-8308-25f151b41865` | `6ac2cd930f40381a7ebd89e25dcf48ac` | `6ac2cd934d832e75081e10692a54dad2` | `0ce5c36b91dd5aef` | `runtime-logs-261c9e37-d142-467c-93cf-db672b3361e1-travel` |  | 307 | 1974 |
| 22:05:30.689 | first | `f6651260-360b-4871-8432-3046d7b51925-profile` | `6e5b9d79-8a43-4e01-8ea8-2bb9c2a74413` | `6ac2cda82d59d0151614dacb5d139814` | `6ac2cda86ebe004d22cd65a901cc9639` | `fa40096213407c6b` | `runtime-logs-f6651260-360b-4871-8432-3046d7b51925-profile` |  | 2168 | 5162 |
| 22:05:51.618 | first | `81ffe68f-1e8b-458a-9163-3456dbd51f58-profile` | `17fca8db-61ce-4546-a808-02329ae28f2b` | `6ac2cdbd463d02926f5716fc5fe8649c` | `6ac2cdbd29692b7c5144663255a4223c` | `743ffc6bd6dca98a` | `runtime-logs-81ffe68f-1e8b-458a-9163-3456dbd51f58-profile` |  | 1722 | 4100 |
| 22:06:00.413 | follow-up | `81ffe68f-1e8b-458a-9163-3456dbd51f58-profile` | `9776b1a1-698c-4921-8280-3b5b55f6c44d` | `6ac2cdc86f319d9456fe160c23491a51` | `6ac2cdc8499066892a4993a8164a5358` | `e748fd99d2a5f5ce` | `runtime-logs-81ffe68f-1e8b-458a-9163-3456dbd51f58-profile` |  | 287 | 854 |
| 22:06:39.729 | first | `2a04ab0d-4657-4c5b-ac56-0e3938be4d76-travel` | `cc1fcc46-d056-42b5-accc-d497d8e45cd1` | `6ac2cded5f23e3902cac9f5f32cf2d78` | `6ac2cded20a461f77705d76f675d44cc` | `02c4bf3b5e24c409` | `runtime-logs-2a04ab0d-4657-4c5b-ac56-0e3938be4d76-travel` |  | 2156 | 3050 |
| 22:06:47.419 | follow-up | `2a04ab0d-4657-4c5b-ac56-0e3938be4d76-travel` | `ebe60fce-f6ff-43b6-a499-b581b06a0731` | `6ac2cdf704b7c9a1732444816f5db6e9` | `6ac2cdf73d4081aa2748282c7bfd6cfc` | `b586d029f53d7f3f` | `runtime-logs-2a04ab0d-4657-4c5b-ac56-0e3938be4d76-travel` |  | 302 | 2063 |
| 22:07:43.273 | first | `1113830f-0426-4524-824d-91650de94404-profile` | `e34b52cd-9299-4bb6-b23b-2b0193524043` | `6ac2ce2d156c4cda6115f648343b5a6c` | `6ac2ce2d29e0337e6fcaa29c1854c67e` | `26abf4ce6b2a16ad` | `runtime-logs-1113830f-0426-4524-824d-91650de94404-profile` |  | 1805 | 4820 |
| 22:08:07.535 | first | `4bd55fd5-a4a4-44b5-bcf8-643024f7cda9-profile` | `2e4179df-8042-4300-b7c2-2273c0ec9d6e` | `6ac2ce45152dd2061a69ecd96c3c4dd4` | `6ac2ce453440180122989ebb5b437c14` | `419ca98364eb0998` | `runtime-logs-4bd55fd5-a4a4-44b5-bcf8-643024f7cda9-profile` |  | 2149 | 5207 |
| 22:08:17.506 | follow-up | `4bd55fd5-a4a4-44b5-bcf8-643024f7cda9-profile` | `8b561e5e-e49d-431b-8dc5-79447ad0d090` | `6ac2ce5122140d5f62867d6b6ea7ad48` | `6ac2ce51240e9ca61b6e7a4017c5c216` | `4a0a2a34db28c942` | `runtime-logs-4bd55fd5-a4a4-44b5-bcf8-643024f7cda9-profile` |  | 316 | 868 |
| 22:08:56.360 | first | `64af93c8-045c-4a01-a0e3-ffafaa3f6a4d-travel` | `c50233bf-f14d-412e-a04c-daea86aec4eb` | `6ac2ce76220afa044df5238d097caacb` | `6ac2ce761177893004fc29b400dc851e` | `88ca0de9b539ac9a` | `runtime-logs-64af93c8-045c-4a01-a0e3-ffafaa3f6a4d-travel` |  | 1772 | 2958 |
| 22:09:03.647 | follow-up | `64af93c8-045c-4a01-a0e3-ffafaa3f6a4d-travel` | `acb70a57-9817-42dc-b337-53c1e94f6de6` | `6ac2ce7f2af4e0ca79a49b93223b8a40` | `6ac2ce7f764273181e5410eb60df96c7` | `a38cbc876b9bb6a3` | `runtime-logs-64af93c8-045c-4a01-a0e3-ffafaa3f6a4d-travel` |  | 279 | 2071 |

## AgentCore Identity calls in the sub-agents (time sink 4)

The first request on each session: the workload access token, then the on-behalf-of exchange
for the tools token. Request ids are AgentCore Identity's `aws.request_id` from the botocore spans.

| Time | Runtime session id | GetWorkloadAccessTokenForJWT request id | ms | GetResourceOauth2Token request id | Credential provider | ms | Issuer API Gateway request id | Issuer Lambda request id |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 21:58:50.498 | `561a7117-9536-4cc8-a758-6bb275dc12b9-profile` | `3a9a067d-9acd-43aa-b6ca-cbd513943a49` | 61 | `6fccc385-f63d-4495-b162-dace7efcb53d` | guppi-obo-hr-agent-profile | 161 | `6b75a5bc-3568-405e-9111-59645dc8ff40` | `5b9e412c-ca19-484c-98fb-885e020047d5` |
| 21:59:26.021 | `d11a9f22-8b02-42e4-a420-126cdea3c0da-profile` | `7245e45c-a736-427f-869e-560307628d43` | 75 | `86ce6a2f-b023-4b09-9c10-9f95650ebccb` | guppi-obo-hr-agent-profile | 185 | `30fa118b-2b89-49ee-a2ce-3877e7e08648` | `cf8d8b25-1418-4b8f-86f1-e24cf471be47` |
| 21:59:46.923 | `f5c8d21e-cb89-48c7-9811-2029cbdfaf09-profile` | `932db4d4-eaf5-48c7-8a9b-9eb07f2ae868` | 54 | `7ab05ebd-b00f-4fd7-8cb0-00940f01b19f` | guppi-obo-hr-agent-profile | 158 | `45cacc58-09ce-4098-a313-4f2f3cb803d6` | `e2f9570d-8e4e-4b36-9474-59c246cecc32` |
| 22:01:00.350 | `61ab9cfd-f7dd-43d1-9261-10a32948a19c-travel` | `ed36458e-20be-40b9-a1b3-d43e8447fe82` | 57 | `5065b894-2432-4e03-8f71-01910f42bc58` | guppi-obo-hr-agent-travel | 167 | `3a0a309f-18ab-4d7a-8624-387717782521` | `6210cb8c-cedc-44fe-8412-05615b0d37b9` |
| 22:01:34.332 | `4a266146-5526-49e8-8642-bd074f0bf6dc-profile` | `4a28a78a-cc86-4c7c-95a2-69324470f667` | 70 | `1eeb3482-1967-4a2c-92d7-871d59be1906` | guppi-obo-hr-agent-profile | 251 |  | `2c2e9eeb-fe29-4619-9c86-b1a9c702854c` |
| 22:01:56.216 | `22034a3d-59a0-4a92-b3bb-41697ed163a4-profile` | `e464f85b-134e-4a3c-b887-41be99023eff` | 65 | `7a4ac1d6-c554-406e-b7bc-70b586990369` | guppi-obo-hr-agent-profile | 143 | `bc50cda6-81cd-4354-8ed9-5397df7be0dc` | `67270cf9-adb7-43ad-a8c6-d8da3ef65e80` |
| 22:02:44.930 | `5fadbba0-6b87-454e-857a-1a5ca91fc798-travel` | `f5cb8554-b33c-4ac1-aacf-ccfe4623baab` | 51 | `a96fbf4c-2d80-46ea-a21d-8f00334e0936` | guppi-obo-hr-agent-travel | 180 | `725dbd5f-b55a-47f3-a003-e937ee647e4f` | `c4ec8b23-f278-4ded-a64d-f9f0be9bd092` |
| 22:03:48.982 | `00e687c5-9e54-4631-b182-17f3aca529a8-profile` | `2b1d5123-4e29-4815-8492-e01bf80bd740` | 68 | `ac7b910f-915b-43f4-9a46-f3226a48e61f` | guppi-obo-hr-agent-profile | 166 | `44c0e5bd-3061-45be-a702-e08d78aab550` | `70cef576-fd2a-43ab-bc19-21d6fa1ea1f2` |
| 22:04:10.963 | `fd7abdc9-d95d-41c7-adea-3703b8fa492b-profile` | `b0aa0038-c247-4dea-bfc9-97cec8e6f378` | 62 | `76658467-7efc-48ea-878e-cf2a75674bc0` | guppi-obo-hr-agent-profile | 161 | `5afc1ed4-1526-4f06-9fab-8f51f8955afe` | `4d616f31-b975-42d3-afcf-e0b46f2e2a0c` |
| 22:04:59.980 | `261c9e37-d142-467c-93cf-db672b3361e1-travel` | `ecf43250-9d5f-4849-aece-dfb9787101d7` | 81 | `7b0c3959-3187-4ced-a909-09068360e7df` | guppi-obo-hr-agent-travel | 167 | `ac106dcd-d9b7-4528-b2a5-51123c71ab18` | `af0bd861-3f5a-41ac-ae23-fb6f992d21a3` |
| 22:05:30.691 | `f6651260-360b-4871-8432-3046d7b51925-profile` | `ded59373-7e20-4ef4-a034-70b667490818` | 59 | `d09e25f9-6805-4a74-b956-962a2bc030cd` | guppi-obo-hr-agent-profile | 175 | `c32fbdec-50d9-4502-a0c6-ea02c23e6d24` | `4412876a-3198-4725-a81e-9c62894dc167` |
| 22:05:51.620 | `81ffe68f-1e8b-458a-9163-3456dbd51f58-profile` | `01a2e834-0750-4e1b-800e-9f077ff6431c` | 49 | `60974d47-1f81-4760-ab90-a8461a993532` | guppi-obo-hr-agent-profile | 161 | `303d3024-62cd-4fda-8c50-53aa2d14404e` | `6e4273e9-08f2-43d3-a49a-494b0ca55d57` |
| 22:06:39.732 | `2a04ab0d-4657-4c5b-ac56-0e3938be4d76-travel` | `65fba45e-30f8-4d9c-a673-1abc5074342c` | 68 | `ac2063e9-4ea0-4f57-a128-3eacdc1e5b10` | guppi-obo-hr-agent-travel | 165 | `5055e2f5-465e-487d-8dc2-003f51038504` | `80dc3e77-b76a-4fcf-8c61-9eb690856e4b` |
| 22:07:43.275 | `1113830f-0426-4524-824d-91650de94404-profile` | `6cde29b3-a9ef-42df-9b49-4dbab2e8989f` | 57 | `a13da847-af8f-46be-bcc7-7a8c8aa3d0b7` | guppi-obo-hr-agent-profile | 179 | `980567b6-babf-4304-858d-77e34e9512e0` | `f2116dbb-2d8c-4196-a94b-28fcfcc4e181` |
| 22:08:07.538 | `4bd55fd5-a4a4-44b5-bcf8-643024f7cda9-profile` | `cc093c7f-c4b2-429c-ad8d-dee4766921de` | 67 | `1dede803-b0b6-4aa2-92ca-2e718428d74b` | guppi-obo-hr-agent-profile | 175 | `3de9d9ad-dbe7-4875-899e-06c68db07d84` | `157b2978-8010-4053-978a-56e17dcdab54` |
| 22:08:56.362 | `64af93c8-045c-4a01-a0e3-ffafaa3f6a4d-travel` | `86a748fb-96a0-42f2-96ca-3865001edbed` | 65 | `3327f341-6251-4955-919d-57a67ae091f7` | guppi-obo-hr-agent-travel | 171 | `d5752f91-9c12-4f6e-9769-ec7633898027` | `166b9a12-0428-407e-b6a4-3cedfd01b717` |

## MCP setup calls through the tools gateway (time sink 4)

The `initialize`, `notifications/initialized` and `tools/list` of each new session.

| Time | Runtime session id | Method | Tools gateway request id | Sub-agent span id | ms |
| --- | --- | --- | --- | --- | --- |
| 21:58:50.754 | `561a7117-9536-4cc8-a758-6bb275dc12b9-profile` | initialize | `3b0218f6-32b3-48a4-83e9-7e459c67d23b` | `3a9c49b56070e74b` | 82 |
| 21:58:50.838 | `561a7117-9536-4cc8-a758-6bb275dc12b9-profile` | notifications/initialized | `321d35a7-241f-4dd5-936a-285173bb5e12` | `6370c1e61f41c400` | 88 |
| 21:58:50.927 | `561a7117-9536-4cc8-a758-6bb275dc12b9-profile` | tools/list | `0be551f5-c1d0-471e-ad57-d7c8c432dce6` | `28cd097ccd4b7ef0` | 149 |
| 21:59:26.325 | `d11a9f22-8b02-42e4-a420-126cdea3c0da-profile` | initialize | `603af3a7-525f-4b99-b984-edc88b5ec4c7` | `1acef77f0f938c43` | 43 |
| 21:59:26.371 | `d11a9f22-8b02-42e4-a420-126cdea3c0da-profile` | notifications/initialized | `b35ac101-0d05-4031-897c-cf7e5a9628f9` | `77cd1786c7a97464` | 56 |
| 21:59:26.429 | `d11a9f22-8b02-42e4-a420-126cdea3c0da-profile` | tools/list | `d94b908a-c49e-4ead-bfd1-8112572f125e` | `44e330af86f87cf5` | 185 |
| 21:59:47.169 | `f5c8d21e-cb89-48c7-9811-2029cbdfaf09-profile` | initialize | `0c6fa8ea-880b-4d4e-80b9-186c30cc3d8a` | `e341466e967c4aec` | 67 |
| 21:59:47.238 | `f5c8d21e-cb89-48c7-9811-2029cbdfaf09-profile` | notifications/initialized | `f35c121d-2ccb-4f7b-bda4-5d06e62342ab` | `d4fe8d83206a346d` | 91 |
| 21:59:47.330 | `f5c8d21e-cb89-48c7-9811-2029cbdfaf09-profile` | tools/list | `3ba8c698-e923-4067-afb4-53a37c3848e9` | `062203e2ce8ac375` | 181 |
| 22:01:02.014 | `61ab9cfd-f7dd-43d1-9261-10a32948a19c-travel` | initialize | `27ef874e-caf7-488a-93e7-ffa1a6a298ec` | `5603f8a93e76a405` | 129 |
| 22:01:02.147 | `61ab9cfd-f7dd-43d1-9261-10a32948a19c-travel` | notifications/initialized | `dca4d07a-56cc-4c5c-a3f0-20265dc83b50` | `8e794a363455d273` | 273 |
| 22:01:02.422 | `61ab9cfd-f7dd-43d1-9261-10a32948a19c-travel` | tools/list | `ba47bfba-658c-441d-9381-ccc746f2a3bb` | `267f71f441af5392` | 203 |
| 22:01:34.696 | `4a266146-5526-49e8-8642-bd074f0bf6dc-profile` | initialize | `c3ba2467-5251-46d1-ae66-25418372158b` | `d7b1d0299e7c1267` | 94 |
| 22:01:34.793 | `4a266146-5526-49e8-8642-bd074f0bf6dc-profile` | notifications/initialized | `4fd70752-3f89-4014-901b-0a283a86474b` | `f1191bf1215bee5a` | 75 |
| 22:01:34.870 | `4a266146-5526-49e8-8642-bd074f0bf6dc-profile` | tools/list | `6a84396e-83d7-4ba3-9c28-93070ab462a0` | `cf2728851896e62d` | 184 |
| 22:01:56.466 | `22034a3d-59a0-4a92-b3bb-41697ed163a4-profile` | initialize | `57ca86d9-119f-46e7-8bd3-a9f7404de0c4` | `7984aa1d44ea3ae6` | 72 |
| 22:01:56.542 | `22034a3d-59a0-4a92-b3bb-41697ed163a4-profile` | notifications/initialized | `91e0c853-e37f-48b0-9e4b-9f678ad09665` | `d5e87c9180e2b5c5` | 83 |
| 22:01:56.626 | `22034a3d-59a0-4a92-b3bb-41697ed163a4-profile` | tools/list | `00b21aa9-0403-44d9-bdb6-ca1271eb76f0` | `2be79dd0aff313a5` | 168 |
| 22:02:46.388 | `5fadbba0-6b87-454e-857a-1a5ca91fc798-travel` | initialize | `1344254e-52c8-49fe-b008-f894cf42a79f` | `72663a8484e6fb0f` | 81 |
| 22:02:46.472 | `5fadbba0-6b87-454e-857a-1a5ca91fc798-travel` | notifications/initialized | `daf7a963-c938-418a-b305-17b514e33c59` | `ab884fb920727d3d` | 73 |
| 22:02:46.546 | `5fadbba0-6b87-454e-857a-1a5ca91fc798-travel` | tools/list | `76cebee8-db73-4a80-98a8-85eae132d278` | `4abb09ac7301f15d` | 126 |
| 22:03:49.258 | `00e687c5-9e54-4631-b182-17f3aca529a8-profile` | initialize | `a4a81e2f-4d44-430f-99c0-ee0de6418644` | `451914dce4fb30ac` | 92 |
| 22:03:49.353 | `00e687c5-9e54-4631-b182-17f3aca529a8-profile` | notifications/initialized | `44aff948-2825-423b-8f28-05e4ba0b5e7f` | `501c3f52085e637b` | 47 |
| 22:03:49.402 | `00e687c5-9e54-4631-b182-17f3aca529a8-profile` | tools/list | `17f11a20-87cd-45d0-9c48-f7b3b8c81f3e` | `fe86f2bad363234d` | 169 |
| 22:04:11.229 | `fd7abdc9-d95d-41c7-adea-3703b8fa492b-profile` | initialize | `13356def-76c4-4d1e-9917-7e28ffc83021` | `d9bf2fd66c078a1c` | 92 |
| 22:04:11.325 | `fd7abdc9-d95d-41c7-adea-3703b8fa492b-profile` | notifications/initialized | `a9f4ca05-edcb-4621-8c52-08c5fde50b0d` | `96abba1975a399ba` | 83 |
| 22:04:11.410 | `fd7abdc9-d95d-41c7-adea-3703b8fa492b-profile` | tools/list | `9f8a246f-0711-4f70-8a17-a303667f88ad` | `70ea1991b78971bf` | 208 |
| 22:05:00.271 | `261c9e37-d142-467c-93cf-db672b3361e1-travel` | initialize | `710a7b63-1412-455d-86bb-a9d764b47926` | `024f6db3cb7b678f` | 94 |
| 22:05:00.368 | `261c9e37-d142-467c-93cf-db672b3361e1-travel` | notifications/initialized | `b4f8e592-8fc7-431c-8921-21e091125aaa` | `af1d4d0363b93486` | 99 |
| 22:05:00.469 | `261c9e37-d142-467c-93cf-db672b3361e1-travel` | tools/list | `6a26739a-631e-4c59-9025-1e4a93658c27` | `8cf0b679c17b5d9f` | 186 |
| 22:05:30.960 | `f6651260-360b-4871-8432-3046d7b51925-profile` | initialize | `376c61e5-0ff3-4e7d-9efa-85fc39060fe8` | `7fb3dcd0ff1ac7d6` | 39 |
| 22:05:31.001 | `f6651260-360b-4871-8432-3046d7b51925-profile` | notifications/initialized | `165772d5-99f1-4150-adeb-dc92fe033e15` | `f2734a39125a8314` | 89 |
| 22:05:31.092 | `f6651260-360b-4871-8432-3046d7b51925-profile` | tools/list | `a8406c08-8d3c-4503-9975-9cececfce119` | `c8c34145f7c10bc3` | 190 |
| 22:05:51.864 | `81ffe68f-1e8b-458a-9163-3456dbd51f58-profile` | initialize | `31bdd4e1-1810-4323-aa0d-bce4ea46b676` | `55a1d7b9caf3111e` | 78 |
| 22:05:51.944 | `81ffe68f-1e8b-458a-9163-3456dbd51f58-profile` | notifications/initialized | `c5f5776f-805e-4167-be34-f998b430ee73` | `ea25b25731a87fdb` | 84 |
| 22:05:52.029 | `81ffe68f-1e8b-458a-9163-3456dbd51f58-profile` | tools/list | `a55c48e3-4ae7-4960-820d-b52a65296cc8` | `73bbe22a868c8ec4` | 176 |
| 22:06:40.008 | `2a04ab0d-4657-4c5b-ac56-0e3938be4d76-travel` | initialize | `6d0dc886-ff0a-48c3-b043-56a3ac56a3dd` | `232fce368b603b16` | 92 |
| 22:06:40.103 | `2a04ab0d-4657-4c5b-ac56-0e3938be4d76-travel` | notifications/initialized | `d268e55f-1413-47a7-be7f-733e70de628e` | `5b08207f1d0949b0` | 32 |
| 22:06:40.136 | `2a04ab0d-4657-4c5b-ac56-0e3938be4d76-travel` | tools/list | `5dad34ef-0592-4782-b5c7-af060256f5af` | `4a3e227cc4107e87` | 176 |
| 22:07:43.545 | `1113830f-0426-4524-824d-91650de94404-profile` | initialize | `f8bcdede-c701-42a1-8d91-2a321b42ee0b` | `3d070ccc2b787e49` | 102 |
| 22:07:43.649 | `1113830f-0426-4524-824d-91650de94404-profile` | notifications/initialized | `bf2b0308-9a7c-488a-b279-3c735a5f3c9f` | `ea45748551758f08` | 95 |
| 22:07:43.746 | `1113830f-0426-4524-824d-91650de94404-profile` | tools/list | `c1d00dd5-db61-4a6a-8d84-0b0549e24e31` | `cc0c34ed1c9af24a` | 185 |
| 22:08:07.824 | `4bd55fd5-a4a4-44b5-bcf8-643024f7cda9-profile` | initialize | `e90d37fb-a462-468c-b286-70a72ddcf1ea` | `75de09c474fd3ef1` | 108 |
| 22:08:07.935 | `4bd55fd5-a4a4-44b5-bcf8-643024f7cda9-profile` | notifications/initialized | `9f1def58-b21f-4f3d-9982-c96ae58c1cd3` | `82a75858e86176b7` | 97 |
| 22:08:08.034 | `4bd55fd5-a4a4-44b5-bcf8-643024f7cda9-profile` | tools/list | `d9999de5-4d13-41ec-a984-fd597c4a8138` | `f6673546ef4b980b` | 173 |
| 22:08:56.631 | `64af93c8-045c-4a01-a0e3-ffafaa3f6a4d-travel` | initialize | `6ced7631-23bf-41a8-98e5-28c2965ee981` | `debe42c4df343ed0` | 79 |
| 22:08:56.712 | `64af93c8-045c-4a01-a0e3-ffafaa3f6a4d-travel` | notifications/initialized | `81a091c3-479d-4385-b246-d7dfe0f86781` | `9b1369d1be8f3ce1` | 57 |
| 22:08:56.771 | `64af93c8-045c-4a01-a0e3-ffafaa3f6a4d-travel` | tools/list | `8b02158b-c352-4767-861e-4c27a45f215c` | `95c09fc24a274cc5` | 157 |

## Sub-agent model calls (time sink 3)

One Bedrock `ConverseStream` per sub-agent request, from the Strands `chat` spans.

| Time | Runtime session id | Trace id | Span id | Model | Input tokens | Output tokens | Time to first token ms | Call ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 21:58:54.664 | `561a7117-9536-4cc8-a758-6bb275dc12b9-profile` | `6ac2cc182a6077655e5d9bbb5dacf480` | `3890fa2050c1d556` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2017 | 38 | 562 | 755 |
| 21:59:29.743 | `d11a9f22-8b02-42e4-a420-126cdea3c0da-profile` | `6ac2cc3b0b1649483eba08f907ce6be2` | `bb2e747be62bccf8` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2013 | 30 | 538 | 783 |
| 21:59:50.910 | `f5c8d21e-cb89-48c7-9811-2029cbdfaf09-profile` | `6ac2cc505398aeee76a16e5f667b15ae` | `fd0b983f9cb7af2f` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2017 | 38 | 549 | 776 |
| 21:59:56.260 | `f5c8d21e-cb89-48c7-9811-2029cbdfaf09-profile` | `6ac2cc5b5f26258c29d2288034475a86` | `50eca92a327cfee1` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2065 | 37 | 554 | 850 |
| 22:01:03.332 | `61ab9cfd-f7dd-43d1-9261-10a32948a19c-travel` | `6ac2cc994331df2410066b6c4d916801` | `57e9a30ff609c5f6` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2407 | 154 | 958 | 2245 |
| 22:01:11.604 | `61ab9cfd-f7dd-43d1-9261-10a32948a19c-travel` | `6ac2cca621832e10259b64562ccab5d9` | `bb5aca60dded25b2` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 4346 | 59 | 603 | 1470 |
| 22:01:38.335 | `4a266146-5526-49e8-8642-bd074f0bf6dc-profile` | `6ac2ccbc52ef211d3d0ece9c20d9e1d8` | `b23abf56a986ba22` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2013 | 31 | 506 | 768 |
| 22:01:59.788 | `22034a3d-59a0-4a92-b3bb-41697ed163a4-profile` | `6ac2ccd259ee5eea6713b090546949c7` | `7928560d5ce9ddb5` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2017 | 38 | 540 | 796 |
| 22:02:05.352 | `22034a3d-59a0-4a92-b3bb-41697ed163a4-profile` | `6ac2ccdd1ef909ca287d6feb3a5632f9` | `5d2acdfdd07dd79e` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2065 | 37 | 504 | 867 |
| 22:02:47.334 | `5fadbba0-6b87-454e-857a-1a5ca91fc798-travel` | `6ac2cd0253f5f33b5f52c67f68faca96` | `42df2226a149a926` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2407 | 151 | 940 | 2202 |
| 22:02:54.889 | `5fadbba0-6b87-454e-857a-1a5ca91fc798-travel` | `6ac2cd0d53679f0e73b8f22970b9fed2` | `96aa2d55ef3e92b1` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 4343 | 48 | 558 | 1179 |
| 22:03:53.601 | `00e687c5-9e54-4631-b182-17f3aca529a8-profile` | `6ac2cd427008459d4d0359e15a44a050` | `321da1ff0c8cff4e` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2013 | 31 | 633 | 836 |
| 22:04:15.096 | `fd7abdc9-d95d-41c7-adea-3703b8fa492b-profile` | `6ac2cd5819e8923a445d3d3e5bd8162a` | `ae8275bd8219e130` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2017 | 38 | 538 | 751 |
| 22:04:20.510 | `fd7abdc9-d95d-41c7-adea-3703b8fa492b-profile` | `6ac2cd6447bbb64b4060b8b56fd276b5` | `f0a4bc8259728861` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2065 | 37 | 532 | 833 |
| 22:05:01.543 | `261c9e37-d142-467c-93cf-db672b3361e1-travel` | `6ac2cd89219f3d521fe1e4a874c61e0b` | `e03f35632f937988` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2407 | 154 | 667 | 1781 |
| 22:05:08.902 | `261c9e37-d142-467c-93cf-db672b3361e1-travel` | `6ac2cd934d832e75081e10692a54dad2` | `8eae8c95a13f4c34` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 4346 | 45 | 635 | 1341 |
| 22:05:35.101 | `f6651260-360b-4871-8432-3046d7b51925-profile` | `6ac2cda86ebe004d22cd65a901cc9639` | `dfd2f90fde05a6fb` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2013 | 30 | 549 | 747 |
| 22:05:54.937 | `81ffe68f-1e8b-458a-9163-3456dbd51f58-profile` | `6ac2cdbd29692b7c5144663255a4223c` | `d8efbcb75ae2dfb9` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2017 | 38 | 545 | 777 |
| 22:06:00.420 | `81ffe68f-1e8b-458a-9163-3456dbd51f58-profile` | `6ac2cdc8499066892a4993a8164a5358` | `8cecaf41c50c8d2c` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2065 | 37 | 542 | 844 |
| 22:06:40.967 | `2a04ab0d-4657-4c5b-ac56-0e3938be4d76-travel` | `6ac2cded20a461f77705d76f675d44cc` | `fff6194fbf0c266e` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2407 | 154 | 599 | 1808 |
| 22:06:48.103 | `2a04ab0d-4657-4c5b-ac56-0e3938be4d76-travel` | `6ac2cdf73d4081aa2748282c7bfd6cfc` | `e447caeecdf792b7` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 4346 | 49 | 594 | 1376 |
| 22:07:47.354 | `1113830f-0426-4524-824d-91650de94404-profile` | `6ac2ce2d29e0337e6fcaa29c1854c67e` | `bc356c939dfaf2a3` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2013 | 30 | 536 | 735 |
| 22:08:11.668 | `4bd55fd5-a4a4-44b5-bcf8-643024f7cda9-profile` | `6ac2ce453440180122989ebb5b437c14` | `eabd7b54bd40fcb7` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2017 | 38 | 841 | 1070 |
| 22:08:17.514 | `4bd55fd5-a4a4-44b5-bcf8-643024f7cda9-profile` | `6ac2ce51240e9ca61b6e7a4017c5c216` | `ec69f82a4be6292a` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2065 | 37 | 529 | 856 |
| 22:08:57.643 | `64af93c8-045c-4a01-a0e3-ffafaa3f6a4d-travel` | `6ac2ce761177893004fc29b400dc851e` | `71ef578fac9fcb4d` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2407 | 151 | 503 | 1672 |
| 22:09:04.392 | `64af93c8-045c-4a01-a0e3-ffafaa3f6a4d-travel` | `6ac2ce7f764273181e5410eb60df96c7` | `919f6fdba1583196` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 4343 | 53 | 551 | 1323 |

## Turns in the designer (routing, time sinks 3, 5, 6)

Each question as Connect and the designer saw it. Routing is the designer's `ModelStart` to
`ModelEnd`; "Connect in" is the click to the designer's `NluRequestReceived`.

| Click | Contact | Question | Flow | Designer correlation id | Designer message id | Page run id | Connect in ms | Routing ms | First words ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 21:58:47.211 | `561a7117-9536-4cc8-a758-6bb275dc12b9` | Change my address | ProfileFlow | `502e2114-3bd3-4e89-9729-6ec412ee4f35` | `2a61c046-f44b-46d8-bfd1-5a145758749a` | `ab6ce780-95c8-420d-8346-c206ad5e8363` | 462 | 664 | 8626 |
| 21:58:58.869 | `561a7117-9536-4cc8-a758-6bb275dc12b9` | And what is my emergency contact? | ProfileFlow | `87a50eb5-633a-42dd-9f9f-9622543cc0e6` | `49ce497b-a23c-43ef-92ac-3daa16c7c0f5` | `10d3123f-c634-45f7-ba6c-8c5e1366ea69` | 372 | 480 | 2519 |
| 21:59:18.465 | `d11a9f22-8b02-42e4-a420-126cdea3c0da` | Update my information | ClarifyFlow | `572cc373-ef1b-4799-b346-f3bad5bb7692` | `2397295b-51d3-4ecd-9cb8-ab836e18a3d9` | `083d25f5-4623-451e-a9e0-15a7d893f0e7` | 428 | 520 | 1252 |
| 21:59:22.742 | `d11a9f22-8b02-42e4-a420-126cdea3c0da` | my home address | ProfileFlow | `7c5d3897-587d-42b9-9ce9-334c49998f47` | `fd82ccfa-ea8f-4ee5-840b-e1015d7fda95` | `b3885376-c453-4709-9fe4-08e67152f054` | 314 | 513 | 8295 |
| 21:59:43.759 | `f5c8d21e-cb89-48c7-9811-2029cbdfaf09` | Change my address | ProfileFlow | `0a14e803-04e2-4053-96e6-20e4cb6d20fc` | `a47ed2e3-264c-4b2b-a173-4d0051eb5349` | `9ff61e60-f7a3-42fe-84d4-b7344b762db0` | 456 | 548 | 8278 |
| 21:59:55.058 | `f5c8d21e-cb89-48c7-9811-2029cbdfaf09` | And what is my emergency contact? | ProfileFlow | `0a6a9060-5213-4a31-a257-19b31267652a` | `7afae6ed-21a4-4d43-93ce-59921c720fef` | `d7770347-1112-4950-987f-a02735d33a31` | 303 | 486 | 2390 |
| 22:00:11.769 | `ff24e31d-2bc1-41d2-93e0-034fb844cd65` | PTO policy | PolicyFlow | `3716ad19-2a76-4b24-855b-9c29975d3bd6` | `f25f0d21-d367-40f3-bca5-cfa9a13674bf` | `fc3f1fad-d384-40c7-a62d-5d602a151757` | 487 | 407 | 4263 |
| 22:00:19.861 | `ff24e31d-2bc1-41d2-93e0-034fb844cd65` | Does unused PTO carry over? | PolicyFlow | `30f4c412-7ef0-41de-b2c9-1bc35638f84a` | `ba9c730a-0341-4f1c-bccf-fd76f1c966b5` | `8e960ed4-0d53-4fcf-ab2c-7eac8d7248b6` | 21197 |  | 22318 |
| 22:00:55.807 | `61ab9cfd-f7dd-43d1-9261-10a32948a19c` | Buddy passes | TravelFlow | `13e3d8af-fcfb-4de6-abcd-c4974e67d845` | `182d34cb-7f6e-460a-ac4a-0c1144b2c736` | `9ec2f627-74cc-4e34-a8cf-9d5c733e5a90` | 1355 | 442 | 10091 |
| 22:01:08.921 | `61ab9cfd-f7dd-43d1-9261-10a32948a19c` | Can my parents use them? | TravelFlow | `68ab4201-31a0-475b-8b29-2eaca10d259c` | `3d4150ad-a7cd-41ac-a599-28bd4c654a92` | `070ce16f-e9de-4d1d-a5c7-f46f349a5b0e` | 1173 | 438 | 4453 |
| 22:01:27.015 | `4a266146-5526-49e8-8642-bd074f0bf6dc` | Update my information | ClarifyFlow | `933d7edf-4822-4b83-bf98-b8863ff7ecae` | `6461f227-3d81-46f9-abed-56f566f6ee0e` | `04e3f142-0ff0-4958-b10c-15e46382edc8` | 466 | 311 | 1153 |
| 22:01:31.192 | `4a266146-5526-49e8-8642-bd074f0bf6dc` | my home address | ProfileFlow | `1cfa1b80-d853-4cff-a344-a788dd0d1648` | `4243ad75-ba49-4352-abfb-68a206cc3604` | `7a70ea58-988c-4829-a098-03df9a10abcb` | 526 | 436 | 8221 |
| 22:01:52.304 | `22034a3d-59a0-4a92-b3bb-41697ed163a4` | Change my address | ProfileFlow | `63aab7cc-153e-4e7a-9a67-7d215b6a19ae` | `372f92a8-3df8-4930-8f28-1fc5483d5a41` | `544dc45e-6d31-45c2-b646-a89f88966419` | 450 | 1188 | 8590 |
| 22:02:03.926 | `22034a3d-59a0-4a92-b3bb-41697ed163a4` | And what is my emergency contact? | ProfileFlow | `b7bc1fc9-ca03-4053-a7f9-13601912d68f` | `42d31638-963d-413a-ae8f-e6de09708d5d` | `39b8ed80-9584-4e40-a36e-9861aa2d93da` | 580 | 432 | 2596 |
| 22:02:19.314 | `cef8c001-8097-4665-89e5-c4464d5f39cc` | PTO policy | PolicyFlow | `88d9b8c0-fd69-47a2-ae21-929f15d4c166` | `b5920983-8663-4cb7-a6f1-fabd05b288c0` | `27fe2ecc-6495-406a-af77-b3cf30e88100` | 416 | 730 | 3646 |
| 22:02:26.783 | `cef8c001-8097-4665-89e5-c4464d5f39cc` | Does unused PTO carry over? | PolicyFlow | `4b258a56-f19c-4afb-affc-354bd746f91d` | `87a93820-a680-4648-8f51-24c1c866c166` | `48c6d834-679c-4349-b340-99415f8dae88` | 276 |  | 1344 |
| 22:02:41.672 | `5fadbba0-6b87-454e-857a-1a5ca91fc798` | Buddy passes | TravelFlow | `1670c2df-fa19-45e9-baa1-78b816651a77` | `c7039a61-fd54-476f-bf9d-f5d9b1bf9cf7` | `cc7ca0bb-a1c3-4326-ad60-754b85d157d8` | 422 | 661 | 8181 |
| 22:02:52.876 | `5fadbba0-6b87-454e-857a-1a5ca91fc798` | Can my parents use them? | TravelFlow | `536faed7-ff0e-49e8-b2ba-9866af495244` | `ec93c39e-606f-46f1-96e0-2f9d553809aa` | `90789b64-4632-45f5-9539-e580c20a6941` | 438 | 432 | 3498 |
| 22:03:09.080 | `715747d7-272c-4159-af1b-c1f5573e6846` | When was my last paycheck and how much was it? | PayFlow | `9898c67e-5f74-4d0a-a2bc-03983297e2ac` | `7559ba85-d5b9-4961-b2e2-62bb22c76f71` | `e369b306-f8f5-4031-893c-3c0229c58e10` | 592 | 386 | 14169 |
| 22:03:26.286 | `715747d7-272c-4159-af1b-c1f5573e6846` | And the one before that? | PayFlow | `396b4932-0bb5-44f6-b7db-36b0e65e10a5` | `92a71d79-16ae-4a7a-8d50-82bda50d57b6` | `e55d8837-0958-434f-a941-0f41b3b6abbb` | 437 | 434 | 2526 |
| 22:03:41.550 | `00e687c5-9e54-4631-b182-17f3aca529a8` | Update my information | ClarifyFlow | `8ee4de01-f9a9-41fe-a403-90d7a35045b1` | `ffc76c74-163a-44db-be14-bff94f3d7a25` | `efff35cd-1596-4c15-b87a-689aa9093012` | 345 | 373 | 969 |
| 22:03:45.539 | `00e687c5-9e54-4631-b182-17f3aca529a8` | my home address | ProfileFlow | `9528bc51-7de3-4c98-b3bb-8ec39e255b2b` | `1cba5843-7687-43ab-9837-a5fb90b53096` | `57da4328-0789-4cc3-aa2e-7d03cdbd6a79` | 322 | 444 | 9200 |
| 22:04:07.437 | `fd7abdc9-d95d-41c7-adea-3703b8fa492b` | Change my address | ProfileFlow | `1951daf7-ee3b-4ef3-8b80-d88beb3b9c4e` | `79750701-57cb-4940-9a77-86564403f503` | `17a0eed4-e9be-4b1f-95d5-caf92a17fc50` | 488 | 461 | 8776 |
| 22:04:19.250 | `fd7abdc9-d95d-41c7-adea-3703b8fa492b` | And what is my emergency contact? | ProfileFlow | `1154d422-7276-4a3b-b623-361eb3c03a70` | `ae27619e-0f6d-4d19-b105-a70bb29d6f5a` | `7a0a3512-aded-43cc-9529-383cda1f1989` | 301 | 499 | 2437 |
| 22:04:34.676 | `f90803a4-5546-4c49-a337-e72b06839709` | PTO policy | PolicyFlow | `2fee62d2-8a40-443b-beac-68e11072aeff` | `19a007f0-5688-48a8-87ba-d96dc5fe0ab3` | `bf94259f-ec98-4123-a466-2f9d9220ffbf` | 464 | 463 | 2910 |
| 22:04:41.424 | `f90803a4-5546-4c49-a337-e72b06839709` | Does unused PTO carry over? | PolicyFlow | `8d02cd07-dc4c-4082-9756-91ea9d63284e` | `29a0f27c-48bc-4ab0-8838-78201b16d898` | `bfb28884-8df5-4705-8182-7639eb82940d` | 407 |  | 1594 |
| 22:04:56.539 | `261c9e37-d142-467c-93cf-db672b3361e1` | Buddy passes | TravelFlow | `2299b7b6-33e1-461c-8e6f-c735222ed55c` | `b0b96394-c314-4d91-8daf-7001eb5d9995` | `e825b386-3120-40b9-aa32-c8b757527b07` | 603 | 369 | 7177 |
| 22:05:06.747 | `261c9e37-d142-467c-93cf-db672b3361e1` | Can my parents use them? | TravelFlow | `31871a50-a9ab-41cf-859d-96e307a0f901` | `2f02822c-8eae-407a-945f-80ffe75c8ddf` | `d35799b3-e335-4977-b3db-a4c2cc7fa3da` | 595 | 436 | 4026 |
| 22:05:23.476 | `f6651260-360b-4871-8432-3046d7b51925` | Update my information | ClarifyFlow | `661a9a6e-71c0-409c-b7fe-6695cd345425` | `f858861b-31bf-4c3d-8023-134c9395a833` | `9fad9abe-71cf-49ff-a664-8bf00cf8b922` | 379 | 462 | 1080 |
| 22:05:27.579 | `f6651260-360b-4871-8432-3046d7b51925` | my home address | ProfileFlow | `d72408fc-932e-4630-841e-8d5032f762e4` | `7c5db7fc-4c5f-45e9-ab72-a60a05e66f7a` | `088ff484-ca95-470b-bd37-84b2874fc1ed` | 311 | 509 | 8616 |
| 22:05:48.912 | `81ffe68f-1e8b-458a-9163-3456dbd51f58` | Change my address | ProfileFlow | `63c94749-99f7-460e-a0a6-98bc8d4f73a9` | `8446e78f-1d54-4786-91e1-f16272e31f40` | `1a7308ec-781c-4119-9691-f84817c7dca5` | 442 | 410 | 7118 |
| 22:05:59.046 | `81ffe68f-1e8b-458a-9163-3456dbd51f58` | And what is my emergency contact? | ProfileFlow | `361e6648-68cd-4fdb-9f12-ee0fd9413c11` | `9620b326-fcac-4ceb-a365-118df03744ca` | `0bad4e18-f86b-4414-89ef-f0ced7b4c528` | 357 | 542 | 2525 |
| 22:06:14.251 | `492310b2-bab1-4d3c-97bf-423f58740a6b` | PTO policy | PolicyFlow | `4788e306-b2a1-4a8d-a020-16bbed6a8471` | `3f78f842-76bb-493c-8e00-4912e867541d` | `3f3a3802-99c0-42a1-b92d-3ccbc942dcad` | 331 | 358 | 3246 |
| 22:06:21.328 | `492310b2-bab1-4d3c-97bf-423f58740a6b` | Does unused PTO carry over? | PolicyFlow | `05ca5ed1-6984-4319-8fdf-140d98a368f5` | `f10a7638-1cb9-4caa-8f8e-72d59a69d83f` | `d574c59c-4e8c-4131-890d-a229408333f0` | 404 |  | 1503 |
| 22:06:36.355 | `2a04ab0d-4657-4c5b-ac56-0e3938be4d76` | Buddy passes | TravelFlow | `9e76d66d-0eeb-45b5-936e-6a9925b2bcb3` | `f6cbff7a-3e1a-4945-81ac-22c702f81884` | `b07c3077-55e4-45fe-b2c9-3740dcf50182` | 740 | 329 | 6749 |
| 22:06:46.131 | `2a04ab0d-4657-4c5b-ac56-0e3938be4d76` | Can my parents use them? | TravelFlow | `bba8a1a7-f31d-4043-aac4-bcbe2a500e2d` | `610f470a-c578-4637-85e4-b76ff2ae6f26` | `5dbff2da-adfd-4550-846b-f3110d83869d` | 466 | 405 | 3716 |
| 22:07:03.080 | `8b513564-423c-4d76-ab91-40c12a69c777` | When was my last paycheck and how much was it? | PayFlow | `87b1674e-3857-48ea-aadb-ea79c1b4a1d3` | `43f07bb5-05af-45fc-8cc7-52ccb1630ce5` | `6d8b0f6e-2cb1-4a2a-9c2d-9669487adf4d` | 426 | 437 | 12747 |
| 22:07:18.864 | `8b513564-423c-4d76-ab91-40c12a69c777` | And the one before that? | PayFlow | `47ac025d-ebe1-4fac-8621-77a9728de578` | `fa9f9c9e-e64f-4476-9b85-1cc9537e7b06` | `8c314029-e5bc-4d04-b869-395fce30c486` | 732 | 419 | 2716 |
| 22:07:35.115 | `1113830f-0426-4524-824d-91650de94404` | Update my information | ClarifyFlow | `1bfe8a78-ec77-4837-8efd-9ed0e8a75789` | `7f80efdd-766a-41b3-9877-9bc21fb7c4c1` | `2612e226-4c31-43d9-b141-7ab6833b0da9` | 418 | 395 | 1045 |
| 22:07:39.191 | `1113830f-0426-4524-824d-91650de94404` | my home address | ProfileFlow | `6f36a3fc-dcfa-444a-af22-6268ced92556` | `ca01dfda-3906-406f-9e6a-f5b4d7fa4a9d` | `6b2b594a-3f13-4799-b99e-fbf9b61b896c` | 1621 | 536 | 9221 |
| 22:08:01.365 | `4bd55fd5-a4a4-44b5-bcf8-643024f7cda9` | Change my address | ProfileFlow | `1550bd32-098e-4808-9b67-7d283b21f3e9` | `125295f9-f064-4f2e-9b8c-3cff509db420` | `aeb7b346-8297-4bff-8651-1905dc8f39be` | 3488 | 438 | 11753 |
| 22:08:16.143 | `4bd55fd5-a4a4-44b5-bcf8-643024f7cda9` | And what is my emergency contact? | ProfileFlow | `2a64939c-96bf-4f09-aedc-354fcf69917a` | `2b55cfcd-7dc0-413e-bab8-be19ca0642ad` | `0afc3b81-a2f3-4605-808f-5029e566ade1` | 534 | 371 | 2585 |
| 22:08:31.395 | `d835fa7a-20b8-43cd-b1cd-203b062e9c72` | PTO policy | PolicyFlow | `fa85d978-fad1-41a9-b798-8f2b4bc3cec5` | `acca5b0b-9e14-4d60-836d-a7e4e697e68a` | `67d2a978-1337-4309-9486-230c7f83aec5` | 433 | 395 | 3445 |
| 22:08:38.672 | `d835fa7a-20b8-43cd-b1cd-203b062e9c72` | Does unused PTO carry over? | PolicyFlow | `fe9721aa-7665-41a5-8dbc-3f3682b0b0d5` | `5fa318db-7303-45ef-97cb-3465586c8867` | `0c82ec62-5a6c-4a65-ae2d-8fbd04384cad` | 382 |  | 1435 |
| 22:08:53.574 | `64af93c8-045c-4a01-a0e3-ffafaa3f6a4d` | Buddy passes | TravelFlow | `5fe3cd21-b012-4a2b-8e2a-02da940cf93e` | `51ae4860-8aff-4389-80c6-7a27ba967078` | `c1c8d732-14ef-440d-8353-1182f61734b1` | 446 | 468 | 6043 |
| 22:09:02.640 | `64af93c8-045c-4a01-a0e3-ffafaa3f6a4d` | Can my parents use them? | TravelFlow | `25855dfe-c9ee-423f-be19-57809d67ab01` | `424ec230-e556-47d9-a5a9-737278b96fed` | `f69ea71f-2138-44f4-ac50-db02a6b8dd78` | 290 | 325 | 3481 |

### Data requests from the designer

Every data request with its gateway request. PolicySearch and Travel's search go to the knowledge base target through the tools gateway.

| Time | Contact | Request | Gateway | Target | Gateway request id | Trace id | ms |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 21:58:48.360 | `561a7117-9536-4cc8-a758-6bb275dc12b9` | DelegateProfile | agents | profile | `fe732bef-c4e7-41db-b6b0-f97184c5ed91` | `6ac2cc1820f2e56e76ab07a74e259c22` | 7167 |
| 21:58:59.795 | `561a7117-9536-4cc8-a758-6bb275dc12b9` | DelegateProfile | agents | profile | `8c825f15-8db1-4221-a5dc-0c735145cff0` | `6ac2cc2349790bbc2063abe97ac0f22c` | 1336 |
| 21:59:23.597 | `d11a9f22-8b02-42e4-a420-126cdea3c0da` | DelegateProfile | agents | profile | `ba858795-d425-43da-9494-0207f3efeca4` | `6ac2cc3b2a2fa20a7b3da4df63bfbc85` | 7140 |
| 21:59:44.797 | `f5c8d21e-cb89-48c7-9811-2029cbdfaf09` | DelegateProfile | agents | profile | `280c0d92-165e-46cd-b591-c7b371f80c8c` | `6ac2cc5020f809e02d98ff5d75a5a5ae` | 7014 |
| 21:59:55.877 | `f5c8d21e-cb89-48c7-9811-2029cbdfaf09` | DelegateProfile | agents | profile | `c2778387-8b5d-4bd5-bcd3-61cf05025b2c` | `6ac2cc5b42acb9293b913aba4115ddb3` | 1309 |
| 22:00:12.744 | `ff24e31d-2bc1-41d2-93e0-034fb844cd65` | PolicySearch | tools | docs | `c11b9436-be2a-456d-8e16-a2f66db7ce02` | `6ac2cc6c710f44d561a8b7913928d305` | 756 |
| 22:00:57.722 | `61ab9cfd-f7dd-43d1-9261-10a32948a19c` | DelegateTravel | agents | travel | `0279f9e3-06aa-46dc-b23b-f077b9e3b771` | `6ac2cc993c1c33a95c2070580e435ea6` | 7944 |
| 22:01:02.629 | `61ab9cfd-f7dd-43d1-9261-10a32948a19c` | travel sub-agent search | tools | docs | `3a68f6d7-2471-4168-a44e-42bea4eb23a3` | `6ac2cc994331df2410066b6c4d916801` | 695 |
| 22:01:10.552 | `61ab9cfd-f7dd-43d1-9261-10a32948a19c` | DelegateTravel | agents | travel | `f06177a3-3e29-4c81-9ccd-3e73b9b4dd80` | `6ac2cca6414a13ae64d1665b78991502` | 2610 |
| 22:01:10.926 | `61ab9cfd-f7dd-43d1-9261-10a32948a19c` | travel sub-agent search | tools | docs | `68e5014f-d236-4b1b-9557-3629cf8341b9` | `6ac2cca621832e10259b64562ccab5d9` | 669 |
| 22:01:32.185 | `4a266146-5526-49e8-8642-bd074f0bf6dc` | DelegateProfile | agents | profile | `978fc7e8-6b4a-4205-a997-0a0f22524894` | `6ac2ccbc78ae56467cb339454eaa2eaa` | 7020 |
| 22:01:53.966 | `22034a3d-59a0-4a92-b3bb-41697ed163a4` | DelegateProfile | agents | profile | `7841520e-6e26-4e01-ae22-bdb600abca0b` | `6ac2ccd125d74c724b4fd4ac58520201` | 6706 |
| 22:02:04.961 | `22034a3d-59a0-4a92-b3bb-41697ed163a4` | DelegateProfile | agents | profile | `089f98d2-c9e6-434f-9bfb-ac8c4ca59b41` | `6ac2ccdc283d6ff41f8488757c969f64` | 1334 |
| 22:02:20.493 | `cef8c001-8097-4665-89e5-c4464d5f39cc` | PolicySearch | tools | docs | `e2e8d8fa-8e4d-4289-aa56-09ab539229b9` | `6ac2ccec7415ed742c06798a51e21ead` | 709 |
| 22:02:42.782 | `5fadbba0-6b87-454e-857a-1a5ca91fc798` | DelegateTravel | agents | travel | `ed0dae40-6ae7-4bc6-a8a3-e830b66e92f1` | `6ac2cd02685b9541427b88f9605a1ab4` | 6834 |
| 22:02:46.675 | `5fadbba0-6b87-454e-857a-1a5ca91fc798` | travel sub-agent search | tools | docs | `64af39af-1a19-459f-984f-4198a0061124` | `6ac2cd0253f5f33b5f52c67f68faca96` | 652 |
| 22:02:53.776 | `5fadbba0-6b87-454e-857a-1a5ca91fc798` | DelegateTravel | agents | travel | `a68af525-49b7-424b-b993-0de50db2ecf0` | `6ac2cd0d19125b04248846a770795c9d` | 2390 |
| 22:02:54.173 | `5fadbba0-6b87-454e-857a-1a5ca91fc798` | travel sub-agent search | tools | docs | `03e09307-13aa-43de-a2d1-8033e32f037a` | `6ac2cd0d53679f0e73b8f22970b9fed2` | 710 |
| 22:03:10.134 | `715747d7-272c-4159-af1b-c1f5573e6846` | DelegatePay | agents | pay | `b56515cd-10fa-481a-a8a1-1644da7dfc2b` | `6ac2cd1e6ffa4f257946deaa3cfdfb6f` | 12915 |
| 22:03:27.228 | `715747d7-272c-4159-af1b-c1f5573e6846` | DelegatePay | agents | pay | `f1377e15-e047-4af0-beaa-0c0c0b3e4739` | `6ac2cd2f76b183001586ef9a25348869` | 1261 |
| 22:03:46.333 | `00e687c5-9e54-4631-b182-17f3aca529a8` | DelegateProfile | agents | profile | `1cd2b95c-ba7e-4604-aae3-0ef596961584` | `6ac2cd42099108bc0b70da341e86ec3d` | 8197 |
| 22:04:08.488 | `fd7abdc9-d95d-41c7-adea-3703b8fa492b` | DelegateProfile | agents | profile | `28722fcc-1aee-474b-9bce-43fbfaa13b1d` | `6ac2cd586e565aa814392df923c3c78b` | 7458 |
| 22:04:20.080 | `fd7abdc9-d95d-41c7-adea-3703b8fa492b` | DelegateProfile | agents | profile | `9f27a1a0-3535-40fb-bbec-f312659cce0a` | `6ac2cd647db60d587c9e8a54393bbf66` | 1368 |
| 22:04:35.634 | `f90803a4-5546-4c49-a337-e72b06839709` | PolicySearch | tools | docs | `53343719-3f33-4526-b17e-b8c1685a8152` | `6ac2cd735dcc72367d596bb563ed1add` | 581 |
| 22:04:57.546 | `261c9e37-d142-467c-93cf-db672b3361e1` | DelegateTravel | agents | travel | `fbbff3f0-f549-444b-91f1-29a3ef7b194f` | `6ac2cd894524eb1764c8694169821a4c` | 5903 |
| 22:05:00.658 | `261c9e37-d142-467c-93cf-db672b3361e1` | travel sub-agent search | tools | docs | `04ed198a-6497-4d15-8fcf-021b754fe5eb` | `6ac2cd89219f3d521fe1e4a874c61e0b` | 876 |
| 22:05:07.837 | `261c9e37-d142-467c-93cf-db672b3361e1` | DelegateTravel | agents | travel | `08c5c7b3-88fa-4a14-8308-25f151b41865` | `6ac2cd930f40381a7ebd89e25dcf48ac` | 2485 |
| 22:05:08.275 | `261c9e37-d142-467c-93cf-db672b3361e1` | travel sub-agent search | tools | docs | `00611420-89bc-4c35-93b4-161fb40d8782` | `6ac2cd934d832e75081e10692a54dad2` | 619 |
| 22:05:28.424 | `f6651260-360b-4871-8432-3046d7b51925` | DelegateProfile | agents | profile | `6e5b9d79-8a43-4e01-8ea8-2bb9c2a74413` | `6ac2cda82d59d0151614dacb5d139814` | 7546 |
| 22:05:49.792 | `81ffe68f-1e8b-458a-9163-3456dbd51f58` | DelegateProfile | agents | profile | `17fca8db-61ce-4546-a808-02329ae28f2b` | `6ac2cdbd463d02926f5716fc5fe8649c` | 6034 |
| 22:05:59.995 | `81ffe68f-1e8b-458a-9163-3456dbd51f58` | DelegateProfile | agents | profile | `9776b1a1-698c-4921-8280-3b5b55f6c44d` | `6ac2cdc86f319d9456fe160c23491a51` | 1376 |
| 22:06:14.996 | `492310b2-bab1-4d3c-97bf-423f58740a6b` | PolicySearch | tools | docs | `9658c1dd-8e66-4689-a0fe-16a5bb16d15d` | `6ac2cdd753f7625d33ebb3ca06639470` | 870 |
| 22:06:37.469 | `2a04ab0d-4657-4c5b-ac56-0e3938be4d76` | DelegateTravel | agents | travel | `cc1fcc46-d056-42b5-accc-d497d8e45cd1` | `6ac2cded5f23e3902cac9f5f32cf2d78` | 5414 |
| 22:06:40.316 | `2a04ab0d-4657-4c5b-ac56-0e3938be4d76` | travel sub-agent search | tools | docs | `9753bb71-96c8-4d8e-8cf8-8c97fc4ed551` | `6ac2cded20a461f77705d76f675d44cc` | 643 |
| 22:06:47.027 | `2a04ab0d-4657-4c5b-ac56-0e3938be4d76` | DelegateTravel | agents | travel | `ebe60fce-f6ff-43b6-a499-b581b06a0731` | `6ac2cdf704b7c9a1732444816f5db6e9` | 2549 |
| 22:06:47.422 | `2a04ab0d-4657-4c5b-ac56-0e3938be4d76` | travel sub-agent search | tools | docs | `7092649b-d465-4124-a4ff-1adbdd48f26c` | `6ac2cdf73d4081aa2748282c7bfd6cfc` | 673 |
| 22:07:03.972 | `8b513564-423c-4d76-ab91-40c12a69c777` | DelegatePay | agents | pay | `ef468694-6fba-4d57-82e5-6bfe10849d3e` | `6ac2ce0773a7ecea2a2318d63f08113d` | 11553 |
| 22:07:20.041 | `8b513564-423c-4d76-ab91-40c12a69c777` | DelegatePay | agents | pay | `a3021903-644d-482e-a3f3-f33dc513d444` | `6ac2ce187c71ab290976d4b879448ebd` | 1287 |
| 22:07:41.373 | `1113830f-0426-4524-824d-91650de94404` | DelegateProfile | agents | profile | `e34b52cd-9299-4bb6-b23b-2b0193524043` | `6ac2ce2d156c4cda6115f648343b5a6c` | 6850 |
| 22:08:05.311 | `4bd55fd5-a4a4-44b5-bcf8-643024f7cda9` | DelegateProfile | agents | profile | `2e4179df-8042-4300-b7c2-2273c0ec9d6e` | `6ac2ce45152dd2061a69ecd96c3c4dd4` | 7563 |
| 22:08:17.068 | `4bd55fd5-a4a4-44b5-bcf8-643024f7cda9` | DelegateProfile | agents | profile | `8b561e5e-e49d-431b-8dc5-79447ad0d090` | `6ac2ce5122140d5f62867d6b6ea7ad48` | 1434 |
| 22:08:32.313 | `d835fa7a-20b8-43cd-b1cd-203b062e9c72` | PolicySearch | tools | docs | `75a7c559-6412-4f41-b501-765d1ba7de5d` | `6ac2ce605d7c27fb22026082396302b5` | 753 |
| 22:08:54.514 | `64af93c8-045c-4a01-a0e3-ffafaa3f6a4d` | DelegateTravel | agents | travel | `c50233bf-f14d-412e-a04c-daea86aec4eb` | `6ac2ce76220afa044df5238d097caacb` | 4884 |
| 22:08:56.930 | `64af93c8-045c-4a01-a0e3-ffafaa3f6a4d` | travel sub-agent search | tools | docs | `58e78151-9618-4ec9-8f11-fd4ca122624e` | `6ac2ce761177893004fc29b400dc851e` | 706 |
| 22:09:03.275 | `64af93c8-045c-4a01-a0e3-ffafaa3f6a4d` | DelegateTravel | agents | travel | `acb70a57-9817-42dc-b337-53c1e94f6de6` | `6ac2ce7f2af4e0ca79a49b93223b8a40` | 2566 |
| 22:09:03.650 | `64af93c8-045c-4a01-a0e3-ffafaa3f6a4d` | travel sub-agent search | tools | docs | `9aa7d981-677d-4fab-841f-0be122974d7a` | `6ac2ce7f764273181e5410eb60df96c7` | 737 |

## Chat starts (time sink 9, question 6)

One per page load. The greeting columns are the designer's WelcomeFlow; the function's own steps
and the four hop token exchanges of each start are in the JSON file.

| Navigation | Contact | API Gateway request id | Lambda request id | X-Ray trace | Lambda log stream | Instance | Function ms | Browser ms | Greeting correlation id | Designer greeted |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 21:58:35.371 | `561a7117-9536-4cc8-a758-6bb275dc12b9` | `1c5d875b-ce8f-49dc-b52c-0a7c340ce0a9` | `33886761-5bb4-489d-bd18-ce890f165274` | `1-6ac2cc0c-62de0e796e91f9f055ad704e` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2083 | 2204 | `a503f709-3983-4c20-a9fd-102b1f0b37f2` | 21:58:38.356 |
| 21:59:05.954 | `d11a9f22-8b02-42e4-a420-126cdea3c0da` | `ab8953a5-75b7-4f66-abd3-a754ebc97e13` | `8bb91f0c-f261-4f09-ab32-da3b86b1c976` | `1-6ac2cc2c-15e999a95b0efcc973d182a2` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2208 | 2351 | `10f850db-db50-4be7-a70f-80b3efcd3e4c` | 21:59:09.801 |
| 21:59:32.616 | `f5c8d21e-cb89-48c7-9811-2029cbdfaf09` | `be5b407e-ec9d-4a46-8f88-263206049c69` | `508a6cbe-8f60-4e76-920b-d4b6e370b3c6` | `1-6ac2cc45-63e35cf91cde608325569000` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 1928 | 2010 | `860b125f-75c3-4f88-acee-7d8e59c96e83` | 21:59:34.972 |
| 21:59:59.016 | `ff24e31d-2bc1-41d2-93e0-034fb844cd65` | `0eb0fd14-8b4b-4763-b135-d0425405b738` | `d5f5e7cc-86e3-4a69-a4bc-a567fd7f9b8a` | `1-6ac2cc61-7760ec1f1679597c52f536fb` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2145 | 2524 | `e1c6f21c-1cea-4cbb-a782-e49fb1ebd3d3` | 22:00:03.222 |
| 22:00:44.564 | `61ab9cfd-f7dd-43d1-9261-10a32948a19c` | `97462fcb-e705-408b-8a40-8d71bfc18e20` | `62e6a30c-3c96-4a29-909a-156e769727d6` | `1-6ac2cc8d-6ac6ca43277fa08d14c4c2c9` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2154 | 2326 | `fcd4b291-348e-487b-8585-f6c3e2969729` | 22:00:47.349 |
| 22:01:14.965 | `4a266146-5526-49e8-8642-bd074f0bf6dc` | `4285f630-7cf7-4975-9214-f0fb53a96ae8` | `fb2d03ff-c596-4efc-bb0d-1a2f44009bb3` | `1-6ac2ccad-402dfa3f174284ab28f6b563` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2029 | 2426 | `71a99627-40f4-4eea-a8ea-2fa28e16de3a` | 22:01:18.808 |
| 22:01:40.986 | `22034a3d-59a0-4a92-b3bb-41697ed163a4` | `c27597a8-ff5c-4deb-981f-62f980a6f54f` | `c5799765-67d5-4add-8759-559ca7d3949c` | `1-6ac2ccc6-3d462221308d5a3d59c8f66a` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2019 | 2289 | `df8bb253-05be-40cd-8eb7-05185f9eae05` | 22:01:43.775 |
| 22:02:08.124 | `cef8c001-8097-4665-89e5-c4464d5f39cc` | `c517c106-03c7-444b-94cd-bb0e1f580b95` | `186fa7fc-d2c9-4142-bd1d-c8ff13fd39f1` | `1-6ac2cce1-2478293c70deceb650c4b1ce` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 1949 | 2090 | `c7dc0740-88a9-497a-a720-f3b5f788a497` | 22:02:10.831 |
| 22:02:30.519 | `5fadbba0-6b87-454e-857a-1a5ca91fc798` | `a3ccdd34-5c7a-48e4-88bc-ce3b7d5afe27` | `efd60338-4d64-43b9-8f3e-c158e219abf5` | `1-6ac2ccf7-11fed8526dbe68262b58fdd6` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2050 | 2232 | `40ff6cd0-3a71-4e7a-8c04-52d542666c1c` | 22:02:33.068 |
| 22:02:57.965 | `715747d7-272c-4159-af1b-c1f5573e6846` | `c39869e1-6168-4e17-b8f8-3daf9d23a60e` | `efe09a74-b779-4adc-b838-a7b67b041396` | `1-6ac2cd12-221730744123e0aa3c19d363` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2109 | 2220 | `b2e3e575-242c-4c1e-83f1-6a836e98fab0` | 22:03:00.559 |
| 22:03:30.394 | `00e687c5-9e54-4631-b182-17f3aca529a8` | `00895e07-434b-4424-8f2c-6e6c611c815c` | `a409481f-61d9-4282-9409-94709f1f9f8f` | `1-6ac2cd33-00f21ac0753333157da28286` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2043 | 2202 | `3962d1a2-8355-475e-a1cf-e16afdd3d1d8` | 22:03:32.938 |
| 22:03:56.323 | `fd7abdc9-d95d-41c7-adea-3703b8fa492b` | `e54b83eb-bdda-4f3c-8af9-a1e03e195ce1` | `6df1cb6d-bbf3-4813-92df-e8f9d12a8885` | `1-6ac2cd4d-5102dcb65353106e24b177cf` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2015 | 2143 | `328fbdde-96f4-4b73-ad18-4db95f88bcf2` | 22:03:58.787 |
| 22:04:23.278 | `f90803a4-5546-4c49-a337-e72b06839709` | `7b1f75fb-aa41-4a32-95cf-cb342c86d3ba` | `8afc333c-0983-4cb4-8411-828495054d50` | `1-6ac2cd68-3419252246374e25043cb777` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2402 | 2690 | `06f8c8df-c1a0-43cb-9650-2536ac5dafc9` | 22:04:26.429 |
| 22:04:45.421 | `261c9e37-d142-467c-93cf-db672b3361e1` | `169ebc9f-f96d-4e22-8c5b-ab86e9472b9a` | `c23abc32-3764-45f9-9f55-0c3889005c27` | `1-6ac2cd7e-3c031f664dd719f347f29776` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2066 | 2186 | `89e70d0e-c9de-49a2-ab5f-d15624670587` | 22:04:47.989 |
| 22:05:12.341 | `f6651260-360b-4871-8432-3046d7b51925` | `4f88e768-f1a9-4f27-9835-646d11710c88` | `81c3b1ca-fd7e-446f-a506-616233e0a2bc` | `1-6ac2cd99-39f5c28d28ade3a671b872b6` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2094 | 2275 | `010b505f-f338-477d-9b13-adab486ec2ea` | 22:05:14.974 |
| 22:05:37.784 | `81ffe68f-1e8b-458a-9163-3456dbd51f58` | `caa0ebe6-4fd0-4f7f-9ee9-e23053f7b35b` | `9067405c-2b4b-4554-bf71-a952a6b15ed7` | `1-6ac2cdb2-0c5ecdfe1da858ce3b6bb2ce` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 1930 | 2044 | `a1de58d8-32cf-4fb3-82b7-b46fd1087817` | 22:05:40.396 |
| 22:06:03.155 | `492310b2-bab1-4d3c-97bf-423f58740a6b` | `0e1a1e75-ff81-42f2-8a15-2797ae66102f` | `2a7ea7bf-4d2e-4902-a6fb-1dcde73be21f` | `1-6ac2cdcc-7a7e7d31601970983ebcb24e` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 1910 | 2020 | `db1f1042-1fdf-4f68-a036-bd2be4276bf2` | 22:06:05.537 |
| 22:06:25.202 | `2a04ab0d-4657-4c5b-ac56-0e3938be4d76` | `8718bc09-6158-4b24-9f5b-76d71eabf432` | `829cf152-dd64-491b-9504-7c4d6e3faec5` | `1-6ac2cde2-1f7eb7402895a64b1175b795` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 1998 | 2175 | `18664f3f-9423-4c76-992c-67e383702945` | 22:06:27.743 |
| 22:06:51.417 | `8b513564-423c-4d76-ab91-40c12a69c777` | `023e5291-8d31-42c0-a1a4-785d3a1ae879` | `aafe0bdb-0a6f-45e4-997e-97237a6e97fa` | `1-6ac2cdfc-6936b23953b7f76a3b8bcc58` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 1992 | 2171 | `5a5de6e6-8a6b-4a3d-9e90-4ca4830d9507` | 22:06:54.223 |
| 22:07:23.159 | `1113830f-0426-4524-824d-91650de94404` | `69b46180-e952-410a-ba5e-2b0f474ce9ba` | `af31892e-7c1e-497a-96ab-8e532c761154` | `1-6ac2ce1c-22d404b728244d5d70c01abf` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2150 | 2319 | `85de808a-624c-4747-abe7-f3eeaa50094f` | 22:07:26.533 |
| 22:07:49.992 | `4bd55fd5-a4a4-44b5-bcf8-643024f7cda9` | `2b977a21-dd1f-4f34-a0e5-9a21b1f36b13` | `a24c5043-9b71-49c2-8f37-dd4444612162` | `1-6ac2ce37-104c0a971dea14ec2aff76d4` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2008 | 2117 | `ea4d2ca1-c4b7-4c1e-b4ff-41f04da204af` | 22:07:52.836 |
| 22:08:20.301 | `d835fa7a-20b8-43cd-b1cd-203b062e9c72` | `6524ffac-65cd-4d73-ab0e-b1f00a2152d5` | `e71f58cf-dfa7-42be-8b31-35e17cc91914` | `1-6ac2ce55-2a80e89f1a8367ca0f9005bf` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 1978 | 2085 | `9049010a-d1f2-4ffb-8d2e-d91ce0d5ccc0` | 22:08:22.838 |
| 22:08:42.490 | `64af93c8-045c-4a01-a0e3-ffafaa3f6a4d` | `8387b623-ab5f-4de7-a81c-fbcc76c3cb61` | `ccaccfd6-7316-434f-b0d1-492f0488b12b` | `1-6ac2ce6b-04c6c9c7465e9cfa34f77514` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2126 | 2277 | `62cde63f-13ff-4f9e-93df-06b8b783bec9` | 22:08:45.036 |

### Hop token exchanges at chat start

The four on-behalf-of exchanges of each start, at the issuer (credential provider `guppi-obo-hr-bridge`).

| Time | Contact | Audience | Issuer API Gateway request id | Issuer Lambda request id | X-Ray trace | Handler ms | Instance |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 21:58:36.928 | `561a7117` | api://hr-agents/pay | `0c2e2cc3-0f3e-422e-b76d-75bf780a11fe` | `4803e16d-de3c-4d6b-971e-18c42096a76d` | `1-6ac2cc0c-48ef92645cc5820110ad6731` | 22.29 |  |
| 21:58:36.931 | `561a7117` | api://hr-agents/travel | `ce63f7db-2f85-4a95-9980-3c6ab489af1f` | `9d3f9b6d-a0b7-403a-9695-a25f70e98b1b` | `1-6ac2cc0c-1cc8cf45568c3f160df313da` | 23.19 |  |
| 21:58:36.932 | `561a7117` | api://hr-tools | `fa1e0102-7f18-48fc-adcf-0ed6099ed1fa` | `57303c83-b701-4923-8e21-6016c4747c71` | `1-6ac2cc0c-254ac83f49d47ad862da3e79` | 20.01 |  |
| 21:58:36.973 | `561a7117` | api://hr-agents/profile | `0d7d0126-a0d6-484c-ab5c-cc98067baaab` | `197295e7-aeac-4b51-858d-e7cbb01fa299` | `1-6ac2cc0c-5d23d8506c5b256372e4d9a2` | 8.1 |  |
| 21:59:08.285 | `d11a9f22` | api://hr-tools | `6930c58d-e6fe-48b2-8a64-d988392b2c10` | `8933d42e-794d-4faf-9dcb-10859061bde7` | `1-6ac2cc2c-71d2abcc35b1f33b77981c28` | 25.26 |  |
| 21:59:08.300 | `d11a9f22` | api://hr-agents/travel | `f8994440-0610-448c-a67e-365fb873fa9a` | `8c95b87b-4dae-4c12-9e12-d22bdbbc33e6` | `1-6ac2cc2c-544e15f146d23cc5370e501b` | 23.02 |  |
| 21:59:08.302 | `d11a9f22` | api://hr-agents/profile | `b42add29-e691-4336-a7bf-d9c44144096c` | `6e44e74a-2cc9-4995-9a18-fa93a721b299` | `1-6ac2cc2c-65ac40ae752a7a812bbdbdbf` | 22.15 |  |
| 21:59:08.305 | `d11a9f22` | api://hr-agents/pay | `44d57ebf-f838-45f1-a291-529173d9ad92` | `7a2e819b-2491-4c3b-872b-ac71d2e19243` | `1-6ac2cc2c-23b5592950dd0514428c03cd` | 23.3 |  |
| 21:59:33.692 | `f5c8d21e` | api://hr-agents/travel | `1776712c-fb48-4177-b406-d164caeb30f4` | `48578084-22a5-4be0-a2a6-8cc0da9e9a88` | `1-6ac2cc45-494c50570c9de97f0c47534e` | 19.45 |  |
| 21:59:33.698 | `f5c8d21e` | api://hr-agents/profile | `5766e201-3e4f-4509-8d7f-4c32f7132046` | `efc05d80-6c29-4fbd-9ce0-2951f3cd0b13` | `1-6ac2cc45-7a695cb20b6673477d8087c1` | 21.73 |  |
| 21:59:33.699 | `f5c8d21e` | api://hr-agents/pay | `bfa039a9-b031-47c8-a1b2-2ec77a13eee5` | `9ff7da02-fc9a-4dc4-9f53-d1114fee4212` | `1-6ac2cc45-4bbb7d0b1b2da235641ee5cb` | 25.28 |  |
| 21:59:33.705 | `f5c8d21e` | api://hr-tools | `6132e87d-3ab8-4995-8dd0-abedaf7822a6` | `252e01c6-7230-40c4-9119-90c96c91ba4a` | `1-6ac2cc45-1403fe871feb92bb726be4dd` | 23.68 |  |
| 22:00:01.735 | `ff24e31d` | api://hr-agents/pay | `846b7cc8-d37d-4556-b40e-081c16f9141a` | `edfa324c-c8b7-4bf8-9b4c-68a24016dea2` | `1-6ac2cc61-2455c8dd377e1fe5256f1b02` | 29.18 |  |
| 22:00:01.745 | `ff24e31d` | api://hr-agents/profile | `e0c59305-2f89-48dd-8307-d0d68c0e5909` | `0e64f11b-4a59-4262-a9bb-c81dcc58aeba` | `1-6ac2cc61-5a80f56a5d5627165960593f` | 22.66 |  |
| 22:00:01.752 | `ff24e31d` | api://hr-agents/travel | `6eb015ba-0337-4f9c-b620-b5cc2b696eee` | `29548078-a3f6-438c-82bd-a6763764e899` | `1-6ac2cc61-034614070fb9a38f56f1d991` | 21.68 |  |
| 22:00:01.754 | `ff24e31d` | api://hr-tools | `679a5697-4253-48df-aed5-4c86a1efaee6` | `78d1bff8-e9c8-4d5d-b2b2-00f26f5ad577` | `1-6ac2cc61-74d2b62725f2c1db1bb686e8` | 23.59 |  |
| 22:00:45.885 | `61ab9cfd` | api://hr-agents/pay | `1ab79213-d4f9-44e7-9c64-515c6a4cfc79` | `a72ae486-fda3-469d-a4ea-be990b43934b` | `1-6ac2cc8d-769078e279bc89c55f36d67b` | 20.0 |  |
| 22:00:45.894 | `61ab9cfd` | api://hr-agents/profile | `e50edb4c-82c2-47ca-b9ec-3536ec5bc3b6` | `b7d480a4-a3bd-4d23-ba16-ffbeefa088f9` | `1-6ac2cc8d-0f8fe3ca4b6cfed959370d14` | 24.36 |  |
| 22:00:45.900 | `61ab9cfd` | api://hr-tools | `ff97ddfc-34f1-4b3c-986d-b6167954d672` | `56fc4609-801d-4b4b-bfee-fbd26fbcb19d` | `1-6ac2cc8d-4ac6a9c27e0644ab43595b0b` | 19.86 |  |
| 22:00:45.902 | `61ab9cfd` | api://hr-agents/travel | `1116be57-627f-4c6e-9027-4d67b88bcc59` | `9011d5a0-a6d2-40e0-b219-161393b20ca5` | `1-6ac2cc8d-65a89e0d20fab83d1bb5344e` | 22.79 |  |
| 22:01:17.461 | `4a266146` | api://hr-agents/pay | `8250e0b2-437b-4f27-9983-df676a09015b` | `d8a49cea-82f5-4297-869b-3f5a2cbcc0a4` | `1-6ac2ccad-051601284bb051dd43a0dfb2` | 22.15 |  |
| 22:01:17.481 | `4a266146` | api://hr-agents/travel | `75d7c2bb-2026-4a6c-9180-96b5e4e2b59f` | `b067f2af-2a13-4765-a633-17127e3750bd` | `1-6ac2ccad-1c0c1c7444dc20b365bc4cf4` | 22.29 |  |
| 22:01:17.482 | `4a266146` | api://hr-tools | `cd0df3cb-12c8-45cc-bec5-63adfed982a2` | `88b3728e-216e-4ee5-bc7b-3934d175301c` | `1-6ac2ccad-3f7484202bc4d1dc4c848703` | 25.08 |  |
| 22:01:17.487 | `4a266146` | api://hr-agents/profile | `2f97db20-2626-4ae2-b2c3-03018ddfd3c7` | `d1ebb259-7c4c-4f08-9f99-0f2f7c78c6ed` | `1-6ac2ccad-17ee34ed7fb17bd7404a7408` | 23.4 |  |
| 22:01:42.410 | `22034a3d` | api://hr-tools | `131f90bc-ff53-4bb8-bf0d-1842662f383d` | `5b18a6a5-59b9-4e8c-b0d0-9813cc0796db` | `1-6ac2ccc6-76585bfb536df8cb435e0d83` | 21.63 |  |
| 22:01:42.412 | `22034a3d` | api://hr-agents/travel | `c8b96690-a6fb-48c1-9920-91f8d3f21497` | `bb2fa2e7-8c26-433d-b594-26fb92d7ab84` | `1-6ac2ccc6-0fd28b9c31d1f33c3f58db18` | 26.73 |  |
| 22:01:42.425 | `22034a3d` | api://hr-agents/pay | `0ab5af97-85cd-48b6-a985-fbcb37d958bc` | `f11fe8ac-0f59-4632-92ec-449c7f63a5e5` | `1-6ac2ccc6-2f49a28f0f617f091af6f187` | 21.03 |  |
| 22:01:42.426 | `22034a3d` | api://hr-agents/profile | `dc995fc9-72c9-4386-afae-eed046a63bfa` | `39c4e408-54ea-48fc-8402-bae5ec7ea514` | `1-6ac2ccc6-6b9b78457a16e1ec72c447d9` | 22.93 |  |
| 22:02:09.480 | `cef8c001` | api://hr-tools | `e5ec881d-1ab4-4f03-bc64-d50bd1ad6a59` | `8194e74d-cc3e-4901-a745-6fdb3dca8d5b` | `1-6ac2cce1-3a23b8fb773ab30a24a15161` | 22.8 |  |
| 22:02:09.483 | `cef8c001` | api://hr-agents/travel |  | `f4ef0a6a-655a-4181-8107-c7c2109ee697` |  | 24.05 |  |
| 22:02:09.484 | `cef8c001` | api://hr-agents/pay | `da146464-0b1a-445b-8f98-d3e69dd7eae2` | `3c6f3810-ba38-4757-94b9-6978c75d12fd` | `1-6ac2cce1-0fb9934e193a9ea535a94456` | 21.52 |  |
| 22:02:09.495 | `cef8c001` | api://hr-agents/profile | `5780b54a-cca8-4118-8f9c-1e13f4dbdc82` | `13e8fd04-1ab5-4850-b6d2-cc0e673b0b4b` | `1-6ac2cce1-24f5ee3171139d187153948d` | 25.51 |  |
| 22:02:31.706 | `5fadbba0` | api://hr-tools | `cef9f187-fc6f-4d09-b36d-895129e79004` | `bc4f4d62-12aa-4e3d-a02f-45418624501b` | `1-6ac2ccf7-31e20a3f687beb15010bc9cf` | 23.38 |  |
| 22:02:31.713 | `5fadbba0` | api://hr-agents/pay | `65aa55ce-b140-4604-8154-108a65a41d39` | `45f64a4f-83fb-4c7a-9967-017445104e7c` | `1-6ac2ccf7-77da5610536d89485721515d` | 21.91 |  |
| 22:02:31.717 | `5fadbba0` | api://hr-agents/profile | `5791673e-bc3a-4de2-be12-03c78d85e35f` | `70d199e2-a94b-455f-b9c0-46276ae5a7c4` | `1-6ac2ccf7-24a93f256a5c71473d20469f` | 22.24 |  |
| 22:02:31.737 | `5fadbba0` | api://hr-agents/travel | `88712438-48ec-4067-93fc-042719057dff` | `45851eba-357d-43a7-a91f-c4230ec29017` | `1-6ac2ccf7-7dc25e7d0d6d333e303c0536` | 7.99 |  |
| 22:02:59.122 | `715747d7` | api://hr-tools | `8b99f6eb-0d03-4ab1-9012-0540f9ba9b59` | `0b556ea1-4116-4ee3-8562-cb0690d61483` | `1-6ac2cd13-1aa0045242fd4c0066a3186a` | 31.54 |  |
| 22:02:59.131 | `715747d7` | api://hr-agents/profile |  | `92f8c5c5-d4a0-43ce-9be2-9c3ec0f758a9` |  | 27.96 |  |
| 22:02:59.137 | `715747d7` | api://hr-agents/travel | `a5a8e1d1-dfd0-44a1-9ad9-7dce326d2d6e` | `a8044e74-7f46-487a-b2b8-d7778c35a559` | `1-6ac2cd13-237b47bd733dd7e24d065a22` | 24.95 |  |
| 22:02:59.169 | `715747d7` | api://hr-agents/pay | `bca84b6b-8f48-4430-b85f-16be05d55bc7` | `fa5044a6-46b0-47d9-9ef7-c3e3bd1aaa20` | `1-6ac2cd13-28bc078b7e26f4441af0c2d7` | 8.71 |  |
| 22:03:31.568 | `00e687c5` | api://hr-agents/pay | `c6f6ec73-f1c9-4f2a-a74a-9d6bd5ab917c` | `6f34b9dc-23ac-4e73-82ab-9749588e1c56` | `1-6ac2cd33-3b93fc0b443b3e4d55b2ca4d` | 22.64 |  |
| 22:03:31.568 | `00e687c5` | api://hr-agents/profile | `2f90e6c1-1c05-4f2b-9005-955602bc3278` | `61dd701e-45e9-443a-a52e-33d38684e704` | `1-6ac2cd33-154196dc592985072ab5ada9` | 26.05 |  |
| 22:03:31.568 | `00e687c5` | api://hr-agents/travel | `353de289-582c-4b87-b7dc-098bd3bfafdf` | `e42c2a12-6f19-433a-9c9e-46f63df29464` | `1-6ac2cd33-32ddebba6ec0b1fa02ac533b` | 23.11 |  |
| 22:03:31.584 | `00e687c5` | api://hr-tools | `771e39bd-6f76-4da0-990d-d0077374999b` | `dcb800b8-674a-40f5-803e-ad64ec277b15` | `1-6ac2cd33-234ba5052072c01d6da924fb` | 20.12 |  |
| 22:03:57.420 | `fd7abdc9` | api://hr-tools | `b79a735c-f90d-4b80-8dad-9f325385d679` | `816bff88-07c0-46f3-b5f1-f504a6359ea5` | `1-6ac2cd4d-7500749d5d157f5566880ef8` | 21.95 |  |
| 22:03:57.427 | `fd7abdc9` | api://hr-agents/travel | `6ffe4dd9-6fb9-49d0-a943-24653ed788f8` | `19bddd93-1d5a-4957-b28a-158694e6b570` | `1-6ac2cd4d-38f44b0c50ee2e89684d6ebc` | 21.18 |  |
| 22:03:57.432 | `fd7abdc9` | api://hr-agents/profile | `f38a99d7-d16f-4159-b8d5-b674433b33dd` | `25933622-5a2c-43ae-b799-646a896fd782` | `1-6ac2cd4d-5f2786734b6ed4c96928827f` | 24.39 |  |
| 22:03:57.439 | `fd7abdc9` | api://hr-agents/pay | `9b8556c6-d07e-41e6-af09-9a8b6cf99953` | `cfeddd61-6bf8-4e16-81fc-ba0547c2de87` | `1-6ac2cd4d-3c4afcb16a302e5565b82e91` | 29.26 |  |
| 22:04:24.992 | `f90803a4` | api://hr-agents/travel | `e7f9df09-a99a-4364-bbec-d0461819d7e6` | `ad0423f0-06b7-44be-895a-b5606689a2c9` | `1-6ac2cd68-7660d08a1f315cba4d74f9ca` | 22.75 |  |
| 22:04:24.999 | `f90803a4` | api://hr-agents/pay | `3be38d20-2bdf-4ccb-8caa-4077676fdfd3` | `6ddfdd81-a74e-4936-bf9e-e29d15bb8c14` | `1-6ac2cd68-5b775d786128f3e37f70b865` | 24.25 |  |
| 22:04:25.020 | `f90803a4` | api://hr-tools | `322392c4-103b-405e-88ed-85f6a424191a` | `67e9e6c0-f44f-4e9a-bd08-c4593b4e036f` | `1-6ac2cd69-2151428046193b4725668827` | 24.02 |  |
| 22:04:25.021 | `f90803a4` | api://hr-agents/profile | `41c49df9-936f-430b-9622-7ed21c9e4257` | `6ca1a2ee-caf7-4369-bcc1-8ff3237ea5ae` | `1-6ac2cd68-098f0dd673437e6d60d58390` | 26.88 |  |
| 22:04:46.551 | `261c9e37` | api://hr-agents/pay | `fbab5320-1c59-4cea-a7ed-9f885ea81e0a` | `7a26361b-37c6-4ed1-b7e4-4d012e5e9a2b` | `1-6ac2cd7e-739da7af3f14fa4d6dc7a515` | 21.5 |  |
| 22:04:46.563 | `261c9e37` | api://hr-agents/travel | `d5264b0e-c5c4-446a-95a7-8437b48e4c45` | `4319cdef-3d4c-4a71-908e-9e6d9e877afa` | `1-6ac2cd7e-525fb91862940577175d6702` | 20.76 |  |
| 22:04:46.568 | `261c9e37` | api://hr-agents/profile | `8c4cab07-c66d-4b05-a7ce-ec0ea2850095` | `6c7c1c75-387c-43e1-b86f-7ba3946d8fc5` | `1-6ac2cd7e-09453efc07c01fd60f03db35` | 20.84 |  |
| 22:04:46.569 | `261c9e37` | api://hr-tools | `4e7b1ade-3986-44f9-9140-ccb9f46508c2` | `60ce8b26-e00e-484e-a64d-20bcbefd208c` | `1-6ac2cd7e-6ca82c1909cc6bb619b0c950` | 23.53 |  |
| 22:05:13.636 | `f6651260` | api://hr-agents/travel | `f1466cb1-343c-431b-8930-e6a00311db57` | `8d476aff-7eef-4176-8267-a0e8afa5a969` | `1-6ac2cd99-7d87f6e97940a26101d1d14f` | 22.2 |  |
| 22:05:13.637 | `f6651260` | api://hr-agents/profile | `92f417ac-5377-4785-a7df-75d5f902ffd5` | `8f66a9eb-bd9f-4e57-bc7d-29b3e493d5cc` | `1-6ac2cd99-7c4e1e6353b1da8951e530d9` | 21.0 |  |
| 22:05:13.639 | `f6651260` | api://hr-agents/pay | `1c92ff7a-dfa0-4afd-a38c-696745508667` | `9f2e1ef4-a509-45e6-842d-ae394c5ced24` | `1-6ac2cd99-06a80295267ceade574897f2` | 19.85 |  |
| 22:05:13.655 | `f6651260` | api://hr-tools | `f6cbdce9-9f4f-40a5-94d4-6b743728e7ee` | `5dcbf2fb-169e-4a73-95d0-afc05a728443` | `1-6ac2cd99-6cefa72f5ab5f3ed3f002b79` | 20.8 |  |
| 22:05:39.074 | `81ffe68f` | api://hr-agents/travel | `ff37212e-935e-496d-a70d-4a59115a6bbc` | `f653d8a9-84a8-40c1-bc80-03eb28fbc216` | `1-6ac2cdb3-6d884a292349875b34ab36fa` | 18.85 |  |
| 22:05:39.076 | `81ffe68f` | api://hr-agents/profile | `345aa878-66c2-4f08-91c9-29fcfe101e1e` | `c1b1460c-e3df-4ac3-b991-09fc6a095399` | `1-6ac2cdb3-4ccfecf44e758bbf3aaa938c` | 20.68 |  |
| 22:05:39.100 | `81ffe68f` | api://hr-tools | `9fe871bc-32f1-479f-95fd-dec1b66e4615` | `c4ad3381-822f-4c41-9277-a33ea50b78cb` | `1-6ac2cdb3-1bef1876757ea2a4389b9709` | 25.02 |  |
| 22:05:39.106 | `81ffe68f` | api://hr-agents/pay | `be03e80b-1c7b-4f64-a09c-5b99f30c9e4d` | `23424426-12ba-4d13-a511-ac811f218f8d` | `1-6ac2cdb3-42af341840d84085620a62f4` | 7.47 |  |
| 22:06:04.266 | `492310b2` | api://hr-tools | `ba610b52-9e45-4fe3-aad4-3f715d9306cc` | `8db0b352-a14f-43cb-a920-2f95ed32f835` | `1-6ac2cdcc-1b7d9e874857251623c310fd` | 20.43 |  |
| 22:06:04.267 | `492310b2` | api://hr-agents/profile | `23da7932-8bbd-4326-a652-409bbc8185a8` | `61f2cced-9b4a-4d17-a0ef-aa54f93b30d6` | `1-6ac2cdcc-4e28d430231931311d74c6b5` | 24.94 |  |
| 22:06:04.274 | `492310b2` | api://hr-agents/travel | `21e57c07-eae5-4cbe-98ee-b4989870b2a5` | `b954b51a-d58a-447f-b81d-773c143fbb9f` | `1-6ac2cdcc-3b5a5872522e0c51178cfe6b` | 23.71 |  |
| 22:06:04.280 | `492310b2` | api://hr-agents/pay | `4a373626-4a8d-4707-aeed-1014f6fca62f` | `66e12f8c-886f-44a4-adf8-fd605d84022c` | `1-6ac2cdcc-35d6e66443f9b7ac4369540e` | 23.63 |  |
| 22:06:26.413 | `2a04ab0d` | api://hr-tools | `7385eac0-44d2-477c-9b3b-f00ea7a3a259` | `dc521157-a70e-4416-ab91-537eef9403f9` | `1-6ac2cde2-566ae121628fe3df2157367f` | 19.78 |  |
| 22:06:26.415 | `2a04ab0d` | api://hr-agents/profile | `56eadd94-1319-4ff5-a721-66706470e50a` | `d2accf53-121b-41a9-a78a-b2c9d1559a9a` | `1-6ac2cde2-34c723aa09afb53b0bb124b9` | 21.2 |  |
| 22:06:26.420 | `2a04ab0d` | api://hr-agents/travel | `c8c3cce4-c5aa-4956-9331-d417ffa309fc` | `2a4778f4-94f0-481a-9da1-9223e3a134a9` | `1-6ac2cde2-7cc5cca8722fb39a6de41520` | 24.41 |  |
| 22:06:26.437 | `2a04ab0d` | api://hr-agents/pay | `e5410223-00d9-447b-9d0c-296455dc538a` | `04cdadb2-f821-4be7-8d5f-05096982fa9b` | `1-6ac2cde2-67153adb6152cd503e38110e` | 21.52 |  |
| 22:06:52.863 | `8b513564` | api://hr-tools | `665c1cfe-a2b3-46c2-9540-5c18a01c82af` | `fc938864-85ea-46ca-964c-cef5fc86d487` | `1-6ac2cdfc-7c2ab2ac5a79e05970eb681d` | 20.6 |  |
| 22:06:52.872 | `8b513564` | api://hr-agents/profile | `c68437e6-1022-4011-8a98-767ba0e0229f` | `1e670161-3f6a-4160-8722-feb051e131ef` | `1-6ac2cdfc-6930b52d7a7ea459488de58c` | 23.72 |  |
| 22:06:52.876 | `8b513564` | api://hr-agents/pay | `1929a7cc-0822-40d3-8c63-2b9b9fef2ddb` | `b489036c-7c9e-48e0-8a4a-0e17e529c5e3` | `1-6ac2cdfc-5a714b45550c4f6f7ac5a212` | 22.86 |  |
| 22:06:52.878 | `8b513564` | api://hr-agents/travel | `7d160aa6-d875-4bfd-bd7a-3bde485e9e9c` | `2f4f8773-0a7f-4236-9f47-08345a51ce38` | `1-6ac2cdfc-2a296c434633eab85e6eac4e` | 23.51 |  |
| 22:07:25.051 | `1113830f` | api://hr-agents/profile | `237461b1-c42d-4cec-8d82-891914e5ab4a` | `6f1ebbea-c0e0-4568-bda3-b060f825fc7b` | `1-6ac2ce1d-541750014b672f3d109b4b81` | 23.4 |  |
| 22:07:25.055 | `1113830f` | api://hr-tools | `d507224d-6677-4e1a-92fa-38f063dee178` | `496c6707-2c29-492a-ad17-2508eb58c31f` | `1-6ac2ce1d-4a08752b1dce4d5501275dc8` | 24.8 |  |
| 22:07:25.069 | `1113830f` | api://hr-agents/travel | `38d6cc19-1268-4826-a7da-1c763f98db2f` | `1c020313-9e85-4e62-a23b-55601de0155d` | `1-6ac2ce1d-49198d9a503ccad7490005fa` | 23.9 |  |
| 22:07:25.085 | `1113830f` | api://hr-agents/pay | `432a07da-ef4e-4dae-9b7c-ad6d1513d8e2` | `37ca3bf0-7466-47b7-9a90-afb3147377a9` | `1-6ac2ce1d-4a9180205c0e045a51e11cb7` | 8.78 |  |
| 22:07:51.524 | `4bd55fd5` | api://hr-agents/pay | `8014fac5-6ba3-45f6-8a4d-42fd437c7eee` | `147eb5b8-15eb-45bf-a04f-31377ecf504f` | `1-6ac2ce37-3ce7ca8564c7d5313f892a3a` | 23.98 |  |
| 22:07:51.527 | `4bd55fd5` | api://hr-agents/profile | `2223df97-9f78-489f-bd6d-64bd7dcfd54b` | `8b6c9191-ea1c-489a-b1e0-ba1be3a1ad4d` | `1-6ac2ce37-23c94e331f0c97db2f50f488` | 20.52 |  |
| 22:07:51.531 | `4bd55fd5` | api://hr-agents/travel | `eecbb9d0-ba3f-4a6b-be76-4e5c5001f33d` | `2f83102c-cb43-4cde-aef8-799d3749cc7e` | `1-6ac2ce37-691e2d61582b83c26226352b` | 22.42 |  |
| 22:07:51.533 | `4bd55fd5` | api://hr-tools | `2d5a64da-f58f-4ff8-b63b-a1f290f1280a` | `c1e3bb93-a07f-419f-8297-ef12e9b2aa76` | `1-6ac2ce37-6b9f19a25b15768c3389838d` | 21.81 |  |
| 22:08:21.471 | `d835fa7a` | api://hr-agents/travel | `260825b3-5531-4fa4-9041-7e1e76aa6a32` | `2d2c6c4d-65d7-4207-8d0f-acae031c903c` | `1-6ac2ce55-6b795dd964cf60144e12e83f` | 21.21 |  |
| 22:08:21.482 | `d835fa7a` | api://hr-tools | `2540bc3c-6c34-4494-8da8-5fbffcec7cb8` | `38222281-8f07-435f-9764-efb85d41e988` | `1-6ac2ce55-31cfb2d3434ea46f6a14c7b1` | 23.13 |  |
| 22:08:21.484 | `d835fa7a` | api://hr-agents/profile | `f0491daf-22d6-44c9-9e76-2062b3f4b55f` | `54a69449-d092-49cb-a737-e61f24cb30f3` | `1-6ac2ce55-67c6482b4bd2474922b86735` | 20.75 |  |
| 22:08:21.512 | `d835fa7a` | api://hr-agents/pay | `73be52e4-429e-4a0e-8ced-44d15f3b5144` | `c39286b1-002c-4e1e-831c-0f0c737372fd` | `1-6ac2ce55-0c6343ed5941faf343eb4609` | 8.0 |  |
| 22:08:43.613 | `64af93c8` | api://hr-agents/travel | `6638518c-b453-4239-b27d-6769ad08cfd0` | `b1b28218-a640-4ed7-9fb6-66765ea48924` | `1-6ac2ce6b-68548ecf1d5d23280ff19c0a` | 20.25 |  |
| 22:08:43.615 | `64af93c8` | api://hr-agents/profile | `8c2443d9-3de6-4674-bd61-dcddac3b1c59` | `65eabec8-233a-4365-b2bd-cd85034b9e75` | `1-6ac2ce6b-457d10962319398a765b5daf` | 23.16 |  |
| 22:08:43.626 | `64af93c8` | api://hr-agents/pay | `917be944-86c9-4106-867f-6e94699c3385` | `11fe523a-c8b0-47eb-98a8-fb09960fae03` | `1-6ac2ce6b-3d8e0854444694b4184c2e86` | 22.23 |  |
| 22:08:43.626 | `64af93c8` | api://hr-tools | `74d1f4c5-7d35-48d1-9d0a-2612071ee7d8` | `fcd4e0cf-a24f-4d4c-8f83-4786e92b8302` | `1-6ac2ce6b-511765a14a06b0a77b4f6cb5` | 23.92 |  |

## Connect calls from CloudTrail

CloudTrail records every Connect and participant call of a chat with its request id; the
participant calls carry the contact in `resources`, and `SendMessage` returns the message id
and Connect's own time to the millisecond. The browser's `SendMessage` time matched the page's
record for the 46 questions. The designer's messages go through the same
`SendMessage` from an internal AWS client: 23 greetings and 46 replies, which with the 46
questions are 115 billed messages.

### Per chat

| Navigation | Contact | StartChatContact | CreateParticipantConnection (function) | CreateParticipantConnection (designer) | Designer participant id | UpdateContactAttributes | CreateParticipantConnection (browser) | GetTranscript (browser) | Greeting message id | Greeting stamped |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 21:58:35.371 | `561a7117-9536-4cc8-a758-6bb275dc12b9` | `78057e51-e490-4686-bff7-71025f4bc04b` | `23aaf8c9-65fe-40d0-83cf-0f2bcd391375` | `b1343d4a-3a59-4ae0-8e44-e9972c0ceabb` | `411da731-64d0-434b-b0c5-49fc6dff5f61` | `9dadcdb3-a31f-44c3-bb4c-56aa088b298e` | `1ea2bb6b-8b33-48eb-94dc-b0799abb7c9d` | `475126b5-4aa8-4d34-abb8-6665ffb4c257` | `01a108ed-195e-7ba7-8a51-891d461b52fd` | 21:58:38.686 |
| 21:59:05.954 | `d11a9f22-8b02-42e4-a420-126cdea3c0da` | `901ea05f-bc82-419a-9797-18cbfff2e4d9` | `cca01e7b-c085-400b-9e12-7ba189f14695` | `d5e4511e-c934-4f46-9661-9a5b5a73d3fe` | `89df983b-fdda-4689-a36f-a761819adcc4` | `60958a8e-b98b-441b-878e-3caa041bb8e7` | `da579946-0023-40f7-9a6c-f66dac89b0af` | `6ec02bb2-d64d-423c-bbe7-e22ac28ddec1` | `01a108ed-944f-7b19-8470-8cca6d5a3da6` | 21:59:10.159 |
| 21:59:32.616 | `f5c8d21e-cb89-48c7-9811-2029cbdfaf09` | `6bff52af-5d92-4764-8690-86c77bda2784` | `452ee554-de9c-4008-836c-774f17292445` | `fbc44d6d-80eb-493a-8a11-6c68c3ed35a8` | `c3949f75-ed9b-4948-83b0-92e7ba55404f` | `493ed643-00af-4f95-a765-3f37425743f1` | `17243dc2-6c15-4eff-8493-0e3ec1a5675b` | `b7cf4292-30b5-445b-a737-608201f194bc` | `01a108ed-f688-7095-9128-e4d53ee1d00c` | 21:59:35.304 |
| 21:59:59.016 | `ff24e31d-2bc1-41d2-93e0-034fb844cd65` | `b4b2d2a1-022e-458f-9191-486e3f305429` | `4b2eecf3-9652-4bdf-97ff-d23d37a3708b` | `1b2e2207-322a-428c-8c72-b200451c27a3` | `410266c2-fd78-44f2-b2a6-5296ecfe800d` | `cf117d82-dccd-432a-aec9-92f3982c5083` | `d06daf03-00f5-4ed2-85bf-2df71b30c621` | `e18a848c-6740-4ace-bcaf-c75370bf0992` | `01a108ee-64d4-702f-a81d-a721e977ead9` | 22:00:03.540 |
| 22:00:44.564 | `61ab9cfd-f7dd-43d1-9261-10a32948a19c` | `2d983db1-46de-419b-a744-d9631548036e` | `9231a074-7a25-4cb4-8088-86251b04b278` | `b194dc5f-59f9-4904-90d1-1c7246e18294` | `d31ec4b7-cd00-4780-ba4b-023867ccb42f` | `e25df55a-b0bb-47e1-9df3-c329714e5f3e` | `4a2bf76d-3604-4b15-a54a-13e716aef134` | `ec7c321e-939c-4d0e-af8d-897eddc66347` | `01a108ef-1182-7ee2-8164-555c707df19d` | 22:00:47.746 |
| 22:01:14.965 | `4a266146-5526-49e8-8642-bd074f0bf6dc` | `9d9687c7-54d7-4e0f-854b-a9eb6d1a0140` | `9cda11cc-ed2a-40b6-b42a-280b1cb8b3b0` | `b5eb700d-6bd8-48bc-9084-17617f85cddd` | `276bce13-62f0-4390-8b1c-7fa31c0584dc` | `bfeb2351-a51d-4db7-8d34-b9659ae0b281` | `15cdb622-2d93-4bb9-9827-46cce2341f55` | `6ce334f8-b432-48a4-ba86-60be4265286d` | `01a108ef-8c37-7b97-a4af-e4f729babed5` | 22:01:19.159 |
| 22:01:40.986 | `22034a3d-59a0-4a92-b3bb-41697ed163a4` | `aa935b57-f477-41c6-ad5a-8ef45bbe2661` | `4835700f-2793-4cc8-97fd-445cffba4ca0` | `ef85b9e7-3371-499e-a30a-ea947b7bc613` | `20167e5e-cbe7-4d54-8aa2-2ff16a4a6e75` | `638c004a-4d4b-4253-8355-9f097a83a47c` | `857cfca0-548f-4d60-8c94-0af4dd40a5ae` | `c0823f0c-956a-4f43-b47c-faccfd4000e7` | `01a108ef-eda1-7d11-9946-93044ff42389` | 22:01:44.097 |
| 22:02:08.124 | `cef8c001-8097-4665-89e5-c4464d5f39cc` | `50946ede-c71c-4eb8-9ca6-ad7f4857be48` | `6f3173b7-8f28-4811-b90e-57145b6de4b4` | `aa48f251-6074-4492-ae79-24344c49455f` | `e1e61988-1e58-49b6-b9da-995b18693efe` | `ed29a880-0607-4243-b568-41b35a95b884` | `97e4895c-9f7a-4115-b6ee-2ad75f189b23` | `afb5fedb-4dbf-451e-8424-21af9227d105` | `01a108f0-574b-7c53-a6cd-2481a7f4839f` | 22:02:11.147 |
| 22:02:30.519 | `5fadbba0-6b87-454e-857a-1a5ca91fc798` | `60ada411-14ec-41ae-8e8b-2a8e8536214e` | `45ac88d6-c939-45a4-b3af-0a6de44b0558` | `18e98286-2d42-4ac1-b275-452d2b07adcd` | `fd04d514-a3a4-4966-b7bd-08f4dd414d5b` | `60a09a24-d447-4e49-a75e-f91789aafbd7` | `26d17f59-f6ad-4300-b128-646b5cbf081a` | `9d7bb7b3-009b-4869-ad99-75d23aa42e77` | `01a108f0-ae56-7a2e-9f79-62eb7bc160ee` | 22:02:33.430 |
| 22:02:57.965 | `715747d7-272c-4159-af1b-c1f5573e6846` | `a526d95a-3863-41cb-9d2a-79b480a189bd` | `4f1a54af-acea-406c-a513-6ed73bc51900` | `f6b39af4-3f84-42a4-94d2-1caa4a03c3c0` | `655c70c6-4f39-4500-8666-5a13f5a88241` | `a6eb53a6-7c56-464f-8733-fecbf477c06c` | `0a650d85-8390-490d-96a8-3fc559508936` | `a40645bc-edd8-4e04-9e2c-a0e22eb0b284` | `01a108f1-1990-71cc-b267-3fa23fd1d4ad` | 22:03:00.880 |
| 22:03:30.394 | `00e687c5-9e54-4631-b182-17f3aca529a8` | `30653dc4-7dc5-4baf-9958-d4f25d108ebb` | `e24851d1-a6c6-46a8-b29c-1df460dd5174` | `1e516a46-85f8-4fd1-b9cb-5f16df977c3c` | `e5970b64-8b52-4b7d-99e9-ec633d8b0e4a` | `19b97347-f995-494b-9807-0d987c2ce0ba` | `3b4ef74d-5aa8-4e4b-a024-b9954a3b7afc` | `836f3040-99cb-4c29-9dd9-9ae5599f953d` | `01a108f1-9815-76b1-bd8f-8145ea671ad9` | 22:03:33.269 |
| 22:03:56.323 | `fd7abdc9-d95d-41c7-adea-3703b8fa492b` | `07cf2d02-7d13-4751-8d54-d6e540ad8191` | `7abbccee-304b-4e28-b9a3-73b5881271e1` | `713ec5d9-7e36-43f7-bc7d-2473a8667cba` | `27161382-ebc6-4f8c-ad3b-35ce0a41d887` | `362afe6c-5c4f-4013-b05c-e2c17c1578cb` | `836c2be9-b1e3-48e1-8a3f-71c809b3b4d1` | `8414465c-3638-4e2b-8a6c-c60ac5058035` | `01a108f1-fd0e-74c4-8706-eef119633f52` | 22:03:59.118 |
| 22:04:23.278 | `f90803a4-5546-4c49-a337-e72b06839709` | `a229c662-ad04-478b-a150-7947d67ef4e5` | `4461f854-d334-490d-b676-cfdc6cf2414f` | `b7cda4ff-7034-4a5b-9b82-d6e02a416fa0` | `b673a7a5-13a2-4933-801c-d93895ff033f` | `751e8e11-dec7-468c-ae1b-2302dd62f6bc` | `b9e5b594-cf5a-480b-889d-691fb94b0716` | `d31ecb42-52b2-4210-a6ae-776915d28bca` | `01a108f2-6917-7408-9bf8-08c3aca87673` | 22:04:26.775 |
| 22:04:45.421 | `261c9e37-d142-467c-93cf-db672b3361e1` | `9d18acba-7dd9-49e2-a1f9-a1134e1e9db7` | `90f26e95-34b5-4724-a745-c8d23e1cde44` | `06255891-f953-4c1d-a11a-3bdc017b91fd` | `8ea84eac-4acb-41c0-8f3f-772d5bfe20be` | `f404ca13-49c5-4f74-a26a-0c9a9c1177a5` | `0b13bd03-25e5-49fd-87f4-0610605c988f` | `708c1c09-6469-4752-a62d-fc1fc0103c94` | `01a108f2-bd3e-735c-b45e-9e2b8fce313c` | 22:04:48.318 |
| 22:05:12.341 | `f6651260-360b-4871-8432-3046d7b51925` | `1cb08bba-5ac8-4b46-8f82-36e7e0720a24` | `2a2371f8-79c3-4c21-8181-16de210cea42` | `09ec4442-1e41-4953-b77d-a53be57ca7c3` | `f4db923a-c822-4389-9c4e-75e22a8ebee9` | `f0cd4cef-214a-44e9-94c7-148c10e1b6ca` | `a3d2c03e-e82e-4331-a222-39e7aa150e7b` | `0cf7ca02-599c-42bf-aa11-13b1f780a892` | `01a108f3-2721-7d90-81d7-d9d1cb65cbe6` | 22:05:15.425 |
| 22:05:37.784 | `81ffe68f-1e8b-458a-9163-3456dbd51f58` | `a174139b-8726-4353-bb5c-66aa3f77ce05` | `86bfed96-6605-48ef-844b-00c55fa220f0` | `ef7671bb-ac51-4f17-afd9-3e7a1a97d65e` | `8ad7be90-33c2-4de0-a22a-138825495767` | `24e50830-19c7-4656-8374-1848e228b109` | `ce6ec687-6647-40fa-8603-4df157a7b6b4` | `77e20258-67c0-465d-a2aa-1b756c2e77cd` | `01a108f3-89cf-7a1b-8187-48b5b82dee35` | 22:05:40.687 |
| 22:06:03.155 | `492310b2-bab1-4d3c-97bf-423f58740a6b` | `007b31f1-0294-4398-8a8b-f25b1556afeb` | `6d952772-b500-4fc8-a70a-699022c632b8` | `27c1b0b2-6bdd-4eb1-8625-34bb489f86e3` | `157b296b-696a-418f-9e0f-34ad1e31d808` | `a74a197a-7328-4b15-a389-083d81170e0e` | `01d54f22-b6f1-4ed0-aa14-fadb668769a5` | `4cac74c4-9199-445d-ba99-20934a32ff7f` | `01a108f3-ec25-7c18-b2cd-2603e6531723` | 22:06:05.861 |
| 22:06:25.202 | `2a04ab0d-4657-4c5b-ac56-0e3938be4d76` | `39f3a472-b687-4732-8bae-6ab89e7b3e24` | `5f0c3854-f083-46fe-afde-504a469887fa` | `7c38a098-e058-461b-8a6b-dabfefac8d60` | `730b07c3-e2ec-4d49-a0d6-7922c1981ca0` | `18680d5f-2a54-4455-bb9e-77c986079cc3` | `34450beb-28ac-41d0-9265-a2d65d265d77` | `002a0315-3ed1-4fe0-8ed4-725b5e583b1c` | `01a108f4-42f1-7080-9730-e1765ecf7f39` | 22:06:28.081 |
| 22:06:51.417 | `8b513564-423c-4d76-ab91-40c12a69c777` | `e73dfc9c-ea1e-4d94-88e7-5a1132a186b9` | `d963dfd0-93b3-45f9-a886-9692549fbed9` | `1694402e-c7b5-4790-a701-dbf7b8b3edc0` | `8e5d6090-5f1e-468d-8b72-677aa58a1bf5` | `f3ff7bfd-e893-441c-b161-ce543006d4c7` | `a5ba3c02-2e29-4d28-a48d-19329296fa21` | `271a197e-a2a4-46a3-ba5e-e48df23cfbc7` | `01a108f4-aa44-7e5a-9190-51af606294a1` | 22:06:54.532 |
| 22:07:23.159 | `1113830f-0426-4524-824d-91650de94404` | `3dcb1c7d-7f9d-4d50-a323-7b48a0c7f868` | `362903ba-045b-4807-984a-2022eac79ae2` | `29f82e0c-c7c1-487c-876b-fe614fb4cfab` | `e12139df-266e-4e34-a343-ea4f5758e764` | `758acd6d-6f86-48e2-9576-9cf2c82ffbe2` | `94d99ab3-50e4-4fa3-9e9f-90de50979f45` | `cdb9c424-b37a-433d-ae6c-bdc760391b5d` | `01a108f5-2886-7938-b9d2-f7137c957b53` | 22:07:26.854 |
| 22:07:49.992 | `4bd55fd5-a4a4-44b5-bcf8-643024f7cda9` | `087cc61a-60d7-4733-8994-c16a3bd1c2f9` | `e7e69d74-48fc-4e5d-8f10-c84f084a2fc3` | `63bd3f8b-9ecd-4869-ba26-69a921f0d1c0` | `a98881f8-b1c2-40dd-839b-d54fbca07a0a` | `c13a800b-9dc2-4c8a-98ac-de74416bb91a` | `3e9f89df-029f-4d08-a186-87c4ea253494` | `c59134c9-8e9e-4bbb-b133-a2b6ce25eb37` | `01a108f5-8f4a-7b08-954a-92735a3c3d22` | 22:07:53.162 |
| 22:08:20.301 | `d835fa7a-20b8-43cd-b1cd-203b062e9c72` | `908da57c-8810-4f38-a59b-5750005c9c96` | `12e81af5-e0d8-40d9-93d2-1025ec750130` | `a49cefed-0216-4d8a-ad2d-8f27b7e87191` | `7f07563c-d262-41f9-975c-c2368ff9489f` | `29d0d98e-7932-485d-b22b-ba3895a68b78` | `9dc3a059-edf9-4c8a-8526-302aa4958e6d` | `07a13db0-7e18-42ae-9980-2eccf9f3f29b` | `01a108f6-047d-7c0f-aecd-9b8de9f1e6c2` | 22:08:23.165 |
| 22:08:42.490 | `64af93c8-045c-4a01-a0e3-ffafaa3f6a4d` | `406cf124-e234-4b80-8447-35584580e4ec` | `57b1899d-2cf4-470b-9673-d34054f877c6` | `e56cae92-721e-4b0b-ac5d-9fd8caeeaddc` | `2c5a0b2c-1813-4a39-96c2-065398e38995` | `d01802d4-3baf-45d4-9819-317d7c2df38c` | `bbea89d5-862a-4227-b8f3-a9cc5350cedb` | `fdcbef9f-298f-4f6d-8407-250535ee05f2` | `01a108f6-5b39-79e8-af32-a6adf1ed4e9e` | 22:08:45.369 |

Connect stamps the greeting 330 ms (median, 291 to 451 ms) after the designer's `NluResponded`,
against 119 ms (median, 83 to 177 ms) for a reply; the greeting's extra time (report question 6) is
spent before Connect posts the first message of a contact, not on the way to the function's socket.

### Per turn

| Click | Contact | Question | SendMessage request id | Question message id | Connect stamp | Reply message ids | Reply SendMessage request ids | Reply stamps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 21:58:47.211 | `561a7117` | Change my address | `266aa6af-2969-43f9-9d31-5a7bc061c428` | `01a108ed-3bad-70cc-beee-417657f91bf0` | 21:58:47.469 | `01a108ed-5bf9-76d8-8b36-e07f0791062c` | `98ded7f9-0a68-4497-bdb0-38daa24f0cb2` | 21:58:55.737 |
| 21:58:58.869 | `561a7117` | And what is my emergency contact? | `00c9ddbe-a34d-45a6-ad50-bd2d91212458` | `01a108ed-68cb-7740-880b-390196b570b6` | 21:58:59.019 | `01a108ed-71b7-768b-9a48-e55fb9cd7873` | `cf34661d-6502-4d31-8f9e-4557e68a3524` | 21:59:01.303 |
| 21:59:18.465 | `d11a9f22` | Update my information | `4e13b4b2-db38-43f4-89a2-ebab351fd471` | `01a108ed-b568-75bd-be6e-ae65e23c84bf` | 21:59:18.632 | `01a108ed-b956-7642-bdf1-c38121087675` | `97d7bde3-1df7-4eee-bd09-e11c058e62f4` | 21:59:19.638 |
| 21:59:22.742 | `d11a9f22` | my home address | `47c00174-1d01-457e-8aba-fefdadba02e3` | `01a108ed-c5f2-7970-ab6f-1017a89fb4e8` | 21:59:22.866 | `01a108ed-e595-789f-9df2-7ff94eb64d02` | `8495c2b2-94cc-4a90-82d9-ae4e083f9b74` | 21:59:30.965 |
| 21:59:43.759 | `f5c8d21e` | Change my address | `f63c0670-1df0-4f47-a8ab-db32942de3bd` | `01a108ee-184c-7baa-bd01-86c9e33ba721` | 21:59:43.948 | `01a108ee-3794-7282-b323-6306834db602` | `d7a6f3db-cfde-4069-9893-58b8aeecdfcd` | 21:59:51.956 |
| 21:59:55.058 | `f5c8d21e` | And what is my emergency contact? | `138e4c1c-1bbf-49b0-8b96-e197a81f3765` | `01a108ee-443d-7b5c-947a-dcafaa3b84f5` | 21:59:55.197 | `01a108ee-4c82-7919-acf6-29adb5e6a9e5` | `50b65e62-1b3c-4489-a582-e3b7d4ca0f11` | 21:59:57.314 |
| 22:00:11.769 | `ff24e31d` | PTO policy | `aa1fb88f-bd95-4279-b315-85fa3c86a1dd` | `01a108ee-85cf-730b-9c83-30625fd43d1c` | 22:00:11.983 | `01a108ee-90ec-7302-bd68-3d4f1e753f2f` | `6f9eac94-1873-41c0-9f13-3f8bc4c75b9e` | 22:00:14.828 |
| 22:00:19.861 | `ff24e31d` | Does unused PTO carry over? | `22567f80-8c17-4736-ae58-2dab5e1aefa9` | `01a108ee-f634-74f0-bbb0-c2b23749792f` | 22:00:40.756 | `01a108ee-fb66-7a55-a766-03da275f53a9` | `2d6abb56-033a-43fe-8691-caa9bad51981` | 22:00:42.086 |
| 22:00:55.807 | `61ab9cfd` | Buddy passes | `6af2adf3-114d-4186-b7e6-cad0120a7760` | `01a108ef-3574-7511-9bf9-c6371a6dc8b2` | 22:00:56.948 | `01a108ef-5816-7a44-88a7-0f6ee46375ce` | `ae40ed52-810c-4512-9f3b-ecfe05947222` | 22:01:05.814 |
| 22:01:08.921 | `61ab9cfd` | Can my parents use them? | `9b9d4d87-739d-4dc4-9250-63a05a0eae95` | `01a108ef-6805-7ff8-a126-dc676adbac29` | 22:01:09.893 | `01a108ef-7551-73c7-871f-07ec18ff0feb` | `d5b50d7b-76a7-40cc-9687-7a0a9dd82bb2` | 22:01:13.297 |
| 22:01:27.015 | `4a266146` | Update my information | `d88c6e57-7ad5-40e5-8c4c-e94ea0eb0e19` | `01a108ef-aba5-7875-8711-935cb68ba236` | 22:01:27.205 | `01a108ef-aee8-7ba9-b548-dc51a4aa2740` | `379b358c-9528-4238-919e-50bb5b56b970` | 22:01:28.040 |
| 22:01:31.192 | `4a266146` | my home address | `b735ecbc-cfa9-468e-b6b6-7ce2c9dc593b` | `01a108ef-bc38-75a8-b3cf-8b2dc49e9177` | 22:01:31.448 | `01a108ef-db04-7f3e-87ee-6e8e0a44121c` | `9751747a-f1bc-4f1d-816d-3f8e0e651f1d` | 22:01:39.332 |
| 22:01:52.304 | `22034a3d` | Change my address | `b8690242-ef60-49e7-9295-2cf5125c521b` | `01a108f0-0e50-7a57-b335-bd9259ee434a` | 22:01:52.464 | `01a108f0-2ee9-7623-8451-b0ecb70bdba0` | `c570fc17-17ae-4039-ac51-c3455faf9027` | 22:02:00.809 |
| 22:02:03.926 | `22034a3d` | And what is my emergency contact? | `12fba399-89d5-454c-874c-d5bd4ae21a43` | `01a108f0-3c58-7977-a103-a0343b65de86` | 22:02:04.248 | `01a108f0-44e9-7db3-9107-546bc1426535` | `139ea36f-2a40-4ea5-8cad-c9556308c4ee` | 22:02:06.441 |
| 22:02:19.314 | `cef8c001` | PTO policy | `3f564ccd-1301-4294-8ef4-c27ad255ff0e` | `01a108f0-77ec-7e16-9882-b06e6f0ce8a3` | 22:02:19.500 | `01a108f0-84f7-7208-aa87-7f47506b2fe5` | `2c5e7912-00e3-4c88-bf0e-d49b9433eab6` | 22:02:22.839 |
| 22:02:26.783 | `cef8c001` | Does unused PTO carry over? | `2bd3122c-f479-486f-8351-f4311a2a8608` | `01a108f0-94cf-73a9-90e4-62acee99e424` | 22:02:26.895 | `01a108f0-9954-7e99-bd0e-f87aee66bb69` | `6ceecc02-e822-42a2-b5a3-1f31b831fb08` | 22:02:28.052 |
| 22:02:41.672 | `5fadbba0` | Buddy passes | `ac90b677-781e-40c2-b62c-944898415052` | `01a108f0-cf36-7cea-9b70-cdfb403b147f` | 22:02:41.846 | `01a108f0-ee32-745d-af21-92c468cf831d` | `6b865778-166d-4d19-b400-7ec0d4f34522` | 22:02:49.778 |
| 22:02:52.876 | `5fadbba0` | Can my parents use them? | `09587d4b-e85d-4181-8d62-18dd656895dd` | `01a108f0-faea-72ea-b3e4-fdfd561e0c96` | 22:02:53.034 | `01a108f1-079d-7ec6-b2bc-62c76f89fb9f` | `f7ef0481-eeac-405e-b215-8729395fe8a2` | 22:02:56.285 |
| 22:03:09.080 | `715747d7` | When was my last paycheck and how much was it? | `fcef26d5-0d1b-4b99-b048-0bd51c4b0e1f` | `01a108f1-3a86-7360-9ad4-28fd896692cf` | 22:03:09.318 | `01a108f1-709f-7fef-8893-d7566e067816` | `b67cfa0b-be59-4b54-9cdd-1f574a7dae9f` | 22:03:23.167 |
| 22:03:26.286 | `715747d7` | And the one before that? | `87ba1b9f-5c66-406c-b8bc-80d2ea79fbcc` | `01a108f1-7d4c-7540-8d8c-a09628cbe5ea` | 22:03:26.412 | `01a108f1-8655-79db-a8ab-1e59388793c2` | `0a129be5-89f0-4cac-967b-96c65fe0ec6b` | 22:03:28.725 |
| 22:03:41.550 | `00e687c5` | Update my information | `7fb6a4ac-549b-40eb-a137-78da7d054754` | `01a108f1-b90e-7e9d-a608-6c356478f85c` | 22:03:41.710 | `01a108f1-bbe6-7541-8590-7832e66f0a9a` | `275fd97d-30f0-4fa6-a86d-5190eec2c0f6` | 22:03:42.438 |
| 22:03:45.539 | `00e687c5` | my home address | `bc3b4e0e-66bb-4d62-9c51-b4c2d2d3bb09` | `01a108f1-c87d-71af-9219-59f27da763ea` | 22:03:45.661 | `01a108f1-eba2-700b-b5f6-c0f3841b05da` | `dfa790b4-1ff8-49d3-a63e-c287665518c0` | 22:03:54.658 |
| 22:04:07.437 | `fd7abdc9` | Change my address | `ebed43f0-2a22-49a0-879a-d9198087cef8` | `01a108f2-1e58-7ade-a69f-28b2c90be16f` | 22:04:07.640 | `01a108f2-3f63-77ef-9303-1b1a9c50e3c7` | `cd6c9478-1e7d-4236-bad3-9e2621a488b2` | 22:04:16.099 |
| 22:04:19.250 | `fd7abdc9` | And what is my emergency contact? | `7b5c77fd-2c77-4e63-a7c7-be39a6038065` | `01a108f2-4c37-7e8e-8b9e-534fc331db41` | 22:04:19.383 | `01a108f2-54e7-7f59-a83c-9f4a04003a83` | `2bd16aaf-6ca1-4a6a-866a-1f8322c0561a` | 22:04:21.607 |
| 22:04:34.676 | `f90803a4` | PTO policy | `0cb2362c-3f00-4efc-9a86-5852fbceec0d` | `01a108f2-88bd-745d-95d9-95845a14521b` | 22:04:34.877 | `01a108f2-92f2-7cd7-b0fc-9954c8bf3ba7` | `5772bec4-f620-4097-bc62-4aec9178609b` | 22:04:37.490 |
| 22:04:41.424 | `f90803a4` | Does unused PTO carry over? | `ae29e2f7-a8f2-48d3-9348-6263b45fbaf8` | `01a108f2-a2d1-78e2-a604-4fd71a6c22a9` | 22:04:41.553 | `01a108f2-a82d-7517-9e46-ad01815f9bb2` | `fa9a8b28-a6c2-42eb-9eef-395dc068945c` | 22:04:42.925 |
| 22:04:56.539 | `261c9e37` | Buddy passes | `5db3bd6c-dcf5-4a26-b280-efc73e8db6e1` | `01a108f2-de61-78f3-90d9-01b25bc3915d` | 22:04:56.801 | `01a108f2-f90a-75e0-966b-4f2f872f16e5` | `e059d88e-738c-44cd-8bb0-974debf5216e` | 22:05:03.626 |
| 22:05:06.747 | `261c9e37` | Can my parents use them? | `971d723f-9ff4-4aa2-9215-813e79cc8b48` | `01a108f3-065f-7fb1-ab82-cbbc9ed901d0` | 22:05:07.039 | `01a108f3-13e0-722a-9c13-8650579c84a8` | `44aff436-ad26-4ea4-830e-4ef1783f92fe` | 22:05:10.496 |
| 22:05:23.476 | `f6651260` | Update my information | `5fb9ac31-8020-4055-8964-8962b0595669` | `01a108f3-4765-74ff-a4fd-4a0d26380ba7` | 22:05:23.685 | `01a108f3-4a73-79b9-903a-56dda1208f88` | `5da2cfb3-7f67-417a-a6fa-df5c981d5f98` | 22:05:24.467 |
| 22:05:27.579 | `f6651260` | my home address | `5a9a0493-ba74-4822-a8a3-bfeb82727cd5` | `01a108f3-5720-75ea-93b2-c226bfb1b13f` | 22:05:27.712 | `01a108f3-77f2-7e1c-b388-fe281f68a98b` | `d1a8947c-2937-430a-9fd9-adb59b5274b9` | 22:05:36.114 |
| 22:05:48.912 | `81ffe68f` | Change my address | `191502e6-69a1-4ddd-a6aa-19ee320ecad9` | `01a108f3-aaa8-7634-9866-86d6605aead1` | 22:05:49.096 | `01a108f3-c56d-7413-8ede-92bee5ec3321` | `253edafc-3ba8-4c91-8f72-cb5e982e3ed2` | 22:05:55.949 |
| 22:05:59.046 | `81ffe68f` | And what is my emergency contact? | `466a2f18-2996-4e58-8d4d-3c262a8ebc25` | `01a108f3-d1f9-7efb-81c6-9b1d7cfa19ec` | 22:05:59.161 | `01a108f3-db0a-7125-9847-26f12260c3f3` | `292b3098-d174-42aa-80b9-b7af2e611e59` | 22:06:01.482 |
| 22:06:14.251 | `492310b2` | PTO policy | `a1979830-cefd-420d-93ab-2b3fa1d3d135` | `01a108f4-0da6-7bdd-8324-9adc3535c9c6` | 22:06:14.438 | `01a108f4-18ce-77d7-b462-8e94e03e4e30` | `d5a86582-fd41-4357-a861-e0f5200b80fc` | 22:06:17.294 |
| 22:06:21.328 | `492310b2` | Does unused PTO carry over? | `8068c29d-6b8a-4bcf-9d8f-d5a725382b43` | `01a108f4-2918-740d-a7c4-038a8462a354` | 22:06:21.464 | `01a108f4-2e0b-78f0-9cc3-a44e6637c004` | `cfc84f0f-7f82-4452-be36-efe18676f22a` | 22:06:22.731 |
| 22:06:36.355 | `2a04ab0d` | Buddy passes | `9fd6d678-6f70-49dd-9429-b958795bc9ad` | `01a108f4-6573-7d79-b200-940ced1839a7` | 22:06:36.915 | `01a108f4-7d46-7790-9159-c7ee78521d6d` | `0111c6d6-49bc-4588-ad4b-2acdf601fdc7` | 22:06:43.014 |
| 22:06:46.131 | `2a04ab0d` | Can my parents use them? | `85f51b36-ce59-4b81-bf49-ad1d228aadaf` | `01a108f4-89f3-7941-9b5d-8c103e3eddda` | 22:06:46.259 | `01a108f4-97a8-7dfa-a324-d5c13e2b12fd` | `f3c3f190-0199-47aa-9c6f-da9b9bbd2195` | 22:06:49.768 |
| 22:07:03.080 | `8b513564` | When was my last paycheck and how much was it? | `12857735-9796-4564-8615-ae5e04a3735f` | `01a108f4-cc69-78cf-a604-745508b7748f` | 22:07:03.273 | `01a108f4-fcd8-7277-9d08-57f843a94030` | `c37a1254-7e3e-4ca0-90e4-4b54db803f61` | 22:07:15.672 |
| 22:07:18.864 | `8b513564` | And the one before that? | `4451db92-3ceb-46d1-b457-e44b77ce9848` | `01a108f5-0b4d-74a3-9bd2-e54f2ecd104c` | 22:07:19.373 | `01a108f5-1383-777c-b32a-de22ee7517a6` | `26066cbb-de6a-485d-8a99-4f6002dfd198` | 22:07:21.475 |
| 22:07:35.115 | `1113830f` | Update my information | `3d83b19e-198a-4369-bf06-71e1d2bd0bdb` | `01a108f5-498e-7f32-993f-a1efbabfca36` | 22:07:35.310 | `01a108f5-4c82-7ffb-8acf-0af284e4bbb9` | `6f8405ef-1ee7-4eda-ab6f-fcb6665e0ccb` | 22:07:36.066 |
| 22:07:39.191 | `1113830f` | my home address | `086f2d05-ded0-4c11-a4d0-6e6d4d58072e` | `01a108f5-5e49-76db-9f39-635bc8fda92a` | 22:07:40.617 | `01a108f5-7c65-757b-bfd4-53d62020d31c` | `c5725b62-f83d-4331-b533-12c19de126ba` | 22:07:48.325 |
| 22:08:01.365 | `4bd55fd5` | Change my address | `d4e2438a-1c59-4ce9-954b-54fefbe95ce5` | `01a108f5-bc45-7367-b77a-50b9a150efcf` | 22:08:04.677 | `01a108f5-dcc8-755d-84e6-a3f427d04b9e` | `b5c081ef-c20c-4930-bd77-c2842b550df2` | 22:08:13.000 |
| 22:08:16.143 | `4bd55fd5` | And what is my emergency contact? | `8c1d9843-3bb4-4835-8a8c-99713edba6d4` | `01a108f5-e9b5-7abd-8568-bc3e158d6e5a` | 22:08:16.309 | `01a108f5-f2c9-7478-b06e-5e21c62d784b` | `682275c1-2b5b-4bb4-9922-b4f9f94ecd07` | 22:08:18.633 |
| 22:08:31.395 | `d835fa7a` | PTO policy | `8c0b3909-1241-4352-be51-f16b13892707` | `01a108f6-256f-7f43-9e6d-a7ccd2f535e6` | 22:08:31.599 | `01a108f6-31c2-71cf-8812-e3605edf566f` | `e13e7c71-5bcc-410e-b09e-b1daaa7753e3` | 22:08:34.754 |
| 22:08:38.672 | `d835fa7a` | Does unused PTO carry over? | `3271efdb-0193-4c4b-bd33-e0bfde38edb8` | `01a108f6-4188-7497-ae0e-afcf6de4b8e7` | 22:08:38.792 | `01a108f6-462b-781e-a488-5dd6ad570d43` | `d609dafe-710c-49f1-beac-d31046f0b150` | 22:08:39.979 |
| 22:08:53.574 | `64af93c8` | Buddy passes | `a401a2c8-3239-4246-b0d8-86bfd1896855` | `01a108f6-7bf3-7a5d-9be3-57d32996f496` | 22:08:53.747 | `01a108f6-928b-7886-8b64-fd4173fc008b` | `390da3ef-53b7-43c2-826d-4bc3fefeb45b` | 22:08:59.531 |
| 22:09:02.640 | `64af93c8` | Can my parents use them? | `7fa30cd6-8c3b-44dc-8e1d-26fe23c668fb` | `01a108f6-9f2b-7fb7-9452-2f6255c3b9c1` | 22:09:02.763 | `01a108f6-abdd-7a99-85c0-330e76fe7d73` | `fd0338cf-e655-414a-b7c5-3110fb710c34` | 22:09:06.013 |

## AgentCore Identity calls from CloudTrail

Three callers that no span shows. The runtime itself calls `GetWorkloadAccessTokenForJWT`
(as `AWSServiceRoleForBedrockAgentCoreRuntimeIdentity`, session `CustomerSlrValidation`) once
for every request it delivers (46 matched here; on 4 Oct V1 it was 100 for 100 requests: 37 to the sub-agents, 63 to the
tools runtime, three per tool call). The tools gateway takes a new role session
(`gateway-session-<id>`) for every tool call and calls Identity twice in it. CloudTrail times
are to the second, so these rows are matched by caller and second.

### Runtime ingress

| Time | Calling session | Request delivered | GetWorkloadAccessTokenForJWT request id | CloudTrail second |
| --- | --- | --- | --- | --- |
| 21:58:50.496 | `561a7117-9536-4cc8-a758-6bb275dc12b9-profile` | sub-agent request |  |  |
| 21:58:51.079 | `561a7117-9536-4cc8-a758-6bb275dc12b9-profile` | tools runtime request 1 of 3 (hr___get_profile) | `0b5d4947-221d-410b-9a30-c44dc9b30fee` | 21:58:54 |
| 21:58:51.079 | `561a7117-9536-4cc8-a758-6bb275dc12b9-profile` | tools runtime request 2 of 3 (hr___get_profile) | `fadc4e79-a5c6-486b-bc35-1f3dffa69eda` | 21:58:54 |
| 21:58:51.079 | `561a7117-9536-4cc8-a758-6bb275dc12b9-profile` | tools runtime request 3 of 3 (hr___get_profile) | `e6950fec-5477-4ae1-9197-670797bbdb83` | 21:58:51 |
| 21:59:26.019 | `d11a9f22-8b02-42e4-a420-126cdea3c0da-profile` | sub-agent request |  |  |
| 21:59:26.617 | `d11a9f22-8b02-42e4-a420-126cdea3c0da-profile` | tools runtime request 1 of 3 (hr___get_profile) | `6dbfb05b-735a-4771-9fb5-cc13be9fb510` | 21:59:29 |
| 21:59:26.617 | `d11a9f22-8b02-42e4-a420-126cdea3c0da-profile` | tools runtime request 2 of 3 (hr___get_profile) | `83c524f0-2e86-426c-b459-fb3c69fb7261` | 21:59:29 |
| 21:59:26.617 | `d11a9f22-8b02-42e4-a420-126cdea3c0da-profile` | tools runtime request 3 of 3 (hr___get_profile) | `e5932344-9044-42d2-927f-8ac7ffde2df8` | 21:59:27 |
| 21:59:46.921 | `f5c8d21e-cb89-48c7-9811-2029cbdfaf09-profile` | sub-agent request | `1fb8569c-e3a3-493b-9788-e0d0a1a71dfe` | 21:59:45 |
| 21:59:47.514 | `f5c8d21e-cb89-48c7-9811-2029cbdfaf09-profile` | tools runtime request 1 of 3 (hr___get_profile) | `2fe8688c-27a1-495a-a7c0-eb011c7864ea` | 21:59:50 |
| 21:59:47.514 | `f5c8d21e-cb89-48c7-9811-2029cbdfaf09-profile` | tools runtime request 2 of 3 (hr___get_profile) | `7d472fcb-9955-4eb9-8cdd-7c3254be228b` | 21:59:50 |
| 21:59:47.514 | `f5c8d21e-cb89-48c7-9811-2029cbdfaf09-profile` | tools runtime request 3 of 3 (hr___get_profile) | `87561e09-3a16-4cf6-9fa8-d014498e77f4` | 21:59:48 |
| 21:59:56.253 | `f5c8d21e-cb89-48c7-9811-2029cbdfaf09-profile` | sub-agent request | `3dff3239-4bde-443c-8ecf-5d3628833586` | 21:59:56 |
| 22:01:00.347 | `61ab9cfd-f7dd-43d1-9261-10a32948a19c-travel` | sub-agent request |  |  |
| 22:01:10.923 | `61ab9cfd-f7dd-43d1-9261-10a32948a19c-travel` | sub-agent request | `4c4289af-323c-4ddf-9748-6542432341a5` | 22:01:10 |
| 22:01:34.330 | `4a266146-5526-49e8-8642-bd074f0bf6dc-profile` | sub-agent request |  |  |
| 22:01:35.058 | `4a266146-5526-49e8-8642-bd074f0bf6dc-profile` | tools runtime request 1 of 3 (hr___get_profile) | `c73712ee-2600-42cf-8a18-59620b8af7d8` | 22:01:38 |
| 22:01:35.058 | `4a266146-5526-49e8-8642-bd074f0bf6dc-profile` | tools runtime request 2 of 3 (hr___get_profile) | `3e4861fe-f04b-421b-b58b-a44fff07f035` | 22:01:37 |
| 22:01:35.058 | `4a266146-5526-49e8-8642-bd074f0bf6dc-profile` | tools runtime request 3 of 3 (hr___get_profile) | `8dc37b7d-cf5a-4e69-9a35-524d377ab14c` | 22:01:35 |
| 22:01:56.213 | `22034a3d-59a0-4a92-b3bb-41697ed163a4-profile` | sub-agent request |  |  |
| 22:01:56.798 | `22034a3d-59a0-4a92-b3bb-41697ed163a4-profile` | tools runtime request 1 of 3 (hr___get_profile) | `d5144672-9ae6-49ba-a053-7d317ef23774` | 22:01:59 |
| 22:01:56.798 | `22034a3d-59a0-4a92-b3bb-41697ed163a4-profile` | tools runtime request 2 of 3 (hr___get_profile) | `f24a0dfe-4d74-4600-aad9-ca2246635427` | 22:01:59 |
| 22:01:56.798 | `22034a3d-59a0-4a92-b3bb-41697ed163a4-profile` | tools runtime request 3 of 3 (hr___get_profile) | `e6fcc124-b3bb-4ef9-99f1-b6932dcc0938` | 22:01:57 |
| 22:02:05.344 | `22034a3d-59a0-4a92-b3bb-41697ed163a4-profile` | sub-agent request | `11e49580-72b5-4655-8a79-0a8383e9c4c3` | 22:02:05 |
| 22:02:44.928 | `5fadbba0-6b87-454e-857a-1a5ca91fc798-travel` | sub-agent request | `6d79a843-c557-44b0-b239-6c471b30d0c6` | 22:02:43 |
| 22:02:54.171 | `5fadbba0-6b87-454e-857a-1a5ca91fc798-travel` | sub-agent request | `3df93937-321c-4542-b193-5783060d4911` | 22:02:54 |
| 22:03:48.980 | `00e687c5-9e54-4631-b182-17f3aca529a8-profile` | sub-agent request |  |  |
| 22:03:49.574 | `00e687c5-9e54-4631-b182-17f3aca529a8-profile` | tools runtime request 1 of 3 (hr___get_profile) | `18f3f822-7665-4a8e-bef0-fca4f4dcef73` | 22:03:53 |
| 22:03:49.574 | `00e687c5-9e54-4631-b182-17f3aca529a8-profile` | tools runtime request 2 of 3 (hr___get_profile) | `243c2be3-d943-4106-bdd5-6d05cd2c957a` | 22:03:53 |
| 22:03:49.574 | `00e687c5-9e54-4631-b182-17f3aca529a8-profile` | tools runtime request 3 of 3 (hr___get_profile) | `a3cbc879-170b-4ce5-a03e-552c90bcd8db` | 22:03:50 |
| 22:04:10.961 | `fd7abdc9-d95d-41c7-adea-3703b8fa492b-profile` | sub-agent request |  |  |
| 22:04:11.620 | `fd7abdc9-d95d-41c7-adea-3703b8fa492b-profile` | tools runtime request 1 of 3 (hr___get_profile) | `186f16f9-64ae-4588-85b0-08e281e203b4` | 22:04:14 |
| 22:04:11.620 | `fd7abdc9-d95d-41c7-adea-3703b8fa492b-profile` | tools runtime request 2 of 3 (hr___get_profile) | `ea1f052b-6a90-4a39-8cc1-2924eda80660` | 22:04:14 |
| 22:04:11.620 | `fd7abdc9-d95d-41c7-adea-3703b8fa492b-profile` | tools runtime request 3 of 3 (hr___get_profile) | `4f379e85-7a47-42fd-8b8d-3e0fe54a0ba2` | 22:04:12 |
| 22:04:20.503 | `fd7abdc9-d95d-41c7-adea-3703b8fa492b-profile` | sub-agent request | `68d0ab3f-cb81-4f9d-b84b-a722d23ea8a1` | 22:04:20 |
| 22:04:59.977 | `261c9e37-d142-467c-93cf-db672b3361e1-travel` | sub-agent request |  |  |
| 22:05:08.272 | `261c9e37-d142-467c-93cf-db672b3361e1-travel` | sub-agent request | `5f3d406b-f0b0-45df-8512-431d79ef9a12` | 22:05:08 |
| 22:05:30.689 | `f6651260-360b-4871-8432-3046d7b51925-profile` | sub-agent request |  |  |
| 22:05:31.285 | `f6651260-360b-4871-8432-3046d7b51925-profile` | tools runtime request 1 of 3 (hr___get_profile) | `b793b3bf-e154-46e7-b9fe-481d89df961f` | 22:05:34 |
| 22:05:31.285 | `f6651260-360b-4871-8432-3046d7b51925-profile` | tools runtime request 2 of 3 (hr___get_profile) | `937f2023-2f7a-47e2-b9ed-3feac6a44434` | 22:05:34 |
| 22:05:31.285 | `f6651260-360b-4871-8432-3046d7b51925-profile` | tools runtime request 3 of 3 (hr___get_profile) | `d64d5d34-fba4-4d74-a4e3-4821f9e3c7df` | 22:05:31 |
| 22:05:51.618 | `81ffe68f-1e8b-458a-9163-3456dbd51f58-profile` | sub-agent request | `20572cba-17c3-4d70-b845-6228d5f4b48c` | 22:05:50 |
| 22:05:52.208 | `81ffe68f-1e8b-458a-9163-3456dbd51f58-profile` | tools runtime request 1 of 3 (hr___get_profile) | `16eda5c8-9e65-437e-98ac-0d44cbec6f6d` | 22:05:54 |
| 22:05:52.208 | `81ffe68f-1e8b-458a-9163-3456dbd51f58-profile` | tools runtime request 2 of 3 (hr___get_profile) | `4289e50d-9275-4eb4-8017-2a25ce11f089` | 22:05:54 |
| 22:05:52.208 | `81ffe68f-1e8b-458a-9163-3456dbd51f58-profile` | tools runtime request 3 of 3 (hr___get_profile) | `18855ae0-b14c-45de-8196-d12998b1c48a` | 22:05:52 |
| 22:06:00.413 | `81ffe68f-1e8b-458a-9163-3456dbd51f58-profile` | sub-agent request | `da2d99e1-22cd-4689-9238-12f9faac22b4` | 22:06:00 |
| 22:06:39.729 | `2a04ab0d-4657-4c5b-ac56-0e3938be4d76-travel` | sub-agent request |  |  |
| 22:06:47.419 | `2a04ab0d-4657-4c5b-ac56-0e3938be4d76-travel` | sub-agent request | `a242dad4-f110-4d75-9f83-c3d062ac92a2` | 22:06:47 |
| 22:07:43.273 | `1113830f-0426-4524-824d-91650de94404-profile` | sub-agent request |  |  |
| 22:07:43.933 | `1113830f-0426-4524-824d-91650de94404-profile` | tools runtime request 1 of 3 (hr___get_profile) | `95661208-f9d9-47dc-acb3-1b381d1d5ddf` | 22:07:47 |
| 22:07:43.933 | `1113830f-0426-4524-824d-91650de94404-profile` | tools runtime request 2 of 3 (hr___get_profile) | `e7ffd600-f6fa-4fc2-bb39-37e50982855b` | 22:07:46 |
| 22:07:43.933 | `1113830f-0426-4524-824d-91650de94404-profile` | tools runtime request 3 of 3 (hr___get_profile) | `874d0560-6e3a-4a97-8495-d8003ce7aa2b` | 22:07:44 |
| 22:08:07.535 | `4bd55fd5-a4a4-44b5-bcf8-643024f7cda9-profile` | sub-agent request |  |  |
| 22:08:08.210 | `4bd55fd5-a4a4-44b5-bcf8-643024f7cda9-profile` | tools runtime request 1 of 3 (hr___get_profile) | `3960ecbf-1fff-4716-b966-824030f52acb` | 22:08:11 |
| 22:08:08.210 | `4bd55fd5-a4a4-44b5-bcf8-643024f7cda9-profile` | tools runtime request 2 of 3 (hr___get_profile) | `fcdbdfcc-7664-4e23-b1cf-8b4b0d3f12ca` | 22:08:11 |
| 22:08:08.210 | `4bd55fd5-a4a4-44b5-bcf8-643024f7cda9-profile` | tools runtime request 3 of 3 (hr___get_profile) | `10946770-26fc-4593-8f88-336973299105` | 22:08:08 |
| 22:08:17.506 | `4bd55fd5-a4a4-44b5-bcf8-643024f7cda9-profile` | sub-agent request | `167a3dba-45e9-4826-9cda-14a6d5183f90` | 22:08:17 |
| 22:08:56.360 | `64af93c8-045c-4a01-a0e3-ffafaa3f6a4d-travel` | sub-agent request |  |  |
| 22:09:03.647 | `64af93c8-045c-4a01-a0e3-ffafaa3f6a4d-travel` | sub-agent request | `b712c055-9ecc-4ffd-b1f1-5a6b0bc08a48` | 22:09:03 |

### Tools gateway, per tool call

| Time | Tools gateway request id | Gateway role session | GetWorkloadAccessTokenForJWT request id | GetResourceOauth2Token request id |
| --- | --- | --- | --- | --- |
| 21:58:51.079 | `37f4d90c-c7b0-4625-b1c5-680817a1c7d8` | `gateway-session-b60d1468-d82e-400d-b51e-ff3dcfc02cb9` | `866292ce-0ff4-4d36-b8d1-ce940bfa385b` | `0782843e-978d-4144-b5af-bb81f5c2a0ab` |
| 21:59:26.617 | `aab206e6-ec80-4c20-beda-d53cd30e7ca8` | `gateway-session-1b7b1109-3751-4eaf-a03f-d59fc41fdce3` | `ee193730-1f12-4b9f-8dd3-6933fc415871` | `78cecd2e-c40c-406a-a815-f6de8152f1b5` |
| 21:59:47.514 | `ae93d5f4-522f-4dcd-8edb-e1d22c423fdd` | `gateway-session-a2c97134-089a-4350-98ca-931fa47ad3ba` | `ce872603-4cfb-4979-af0e-1ae88a5f2ce4` | `f9defe8d-bcec-4305-9364-801577c12154` |
| 22:01:35.058 | `69dd9e92-d2bb-4f1b-86a9-8eb97899ca5d` | `gateway-session-d8e4eeb8-45d5-4a8c-8f21-2c3aab5251a9` | `0b0ce574-6980-4f9e-b635-a0e25d226247` | `b870076e-c902-4831-8e4d-a5aa24e0f6b6` |
| 22:01:56.798 | `01be85b5-950d-4b41-9444-667def1e9856` | `gateway-session-4be1d4e3-4d8a-4943-9da7-8645b57b6828` | `6552798d-7830-4883-802b-354e1129b43f` | `74af7273-e38b-4a9c-806a-f11a0ec2cfee` |
| 22:03:49.574 | `59702b60-69c2-409d-b3d8-49df036e6ada` | `gateway-session-b61d4650-436e-47e4-80c4-6729eef42840` | `985af2c9-2647-4056-ad33-5be616572628` | `3d1774f4-e585-4f64-a9c4-192c2cad3ea0` |
| 22:04:11.620 | `4e8c471a-4b6c-4ca8-bee0-b6b2d6456d78` | `gateway-session-652682bb-4ba7-4c0e-9ca3-5700f06b3be4` | `aebabe7e-15fb-4872-b5f8-1d7b76ce81f8` | `ef88eb5c-951e-4da0-8538-f97df0754f58` |
| 22:05:31.285 | `0310d1fb-4fc8-450c-8317-473364716061` | `gateway-session-976836b8-d4a1-4839-8380-aaa1a110920a` | `44f88da1-c45f-4427-969d-9ea4c1f3394b` | `6e71532e-7ae2-4f94-b0ef-8faacdc1a587` |
| 22:05:52.208 | `e712d0fe-9ef6-4062-b268-ec5854fafa86` | `gateway-session-e1bb42cf-a2ec-4d85-9813-a00aa0a1c2f5` | `3c1fe6a9-4bcd-4c6b-9b7b-a6e32e0884c4` | `e1a41ebf-7a68-43e2-a0c5-1e1f59373883` |
| 22:07:43.933 | `d28a2fca-940b-4229-88fb-ee37036c76bc` | `gateway-session-48f8ef0c-ec6d-4984-8745-f2a7d1780e6f` | `092eaa1e-366d-4aad-a796-3915129eb1b2` | `799a8426-8a86-4ea8-a71b-ed9a8c474600` |
| 22:08:08.210 | `a1f998d8-563d-4c2e-a486-11e6ba35f87a` | `gateway-session-7e8676b8-580c-4f3b-a83c-ba3ec86826b2` | `d478c656-3e2c-401e-a3b4-877a84b37d76` | `d027e256-cc14-4bfc-9a75-2ff2f9465f2c` |

### Chat start

| Navigation | Contact | GetWorkloadAccessTokenForJWT request id | GetResourceOauth2Token request ids (four hop tokens) |
| --- | --- | --- | --- |
| 21:58:35.371 | `561a7117-9536-4cc8-a758-6bb275dc12b9` | `bbcc5784-64fd-415e-bf03-18beb11a3b0c` | `fd2e47fc-aaf9-44e3-b1e4-79cc5b784ec3` `08fb7102-0f4b-46e9-971c-3f4df1eda4a0` `876522b7-26eb-4e02-bb6b-e8bbbc6bb2c4` `f43fc4b4-5e1b-4d0b-9108-ec9b4a917b08` |
| 21:59:05.954 | `d11a9f22-8b02-42e4-a420-126cdea3c0da` | `a1b82267-bfed-4465-80a3-f813f4f34fc0` | `8fd106fe-f21a-4ae8-bb04-562cd6b23344` `6f176288-e111-4a51-a7d8-d5a30a2ead62` `d4ebddc7-fcbd-417f-9d93-24f1d007a6f8` `897cf861-87e2-45d0-9cc1-da44f658445e` |
| 21:59:32.616 | `f5c8d21e-cb89-48c7-9811-2029cbdfaf09` | `cb0c6cf7-8aff-4b54-b238-37519d8f9c34` | `9ac97e33-1740-470f-8c84-e0361a581a92` `9273d25c-8de8-4f76-9abc-910fdfefc336` `c38bce50-d961-489e-8513-93f65e802028` `cc7daa3c-ce7b-471c-ac69-561cbe50cded` |
| 21:59:59.016 | `ff24e31d-2bc1-41d2-93e0-034fb844cd65` | `8cc19fb1-5a63-4578-9144-199f6244d730` | `624c7533-289e-4d17-a66f-e80e4f657973` `f6948a4a-6418-45be-b498-81c7d9efb5c6` `728ffb38-6519-4b3a-89b2-aa7736a06909` `fe5fd8c8-f711-4874-bd26-cf1c3b0a375a` |
| 22:00:44.564 | `61ab9cfd-f7dd-43d1-9261-10a32948a19c` | `618d54e8-843e-484b-ad95-429231ca5899` | `a1213093-f699-412f-b122-f23e4104700b` `53940b26-79fe-4967-80dd-31e0c7d1c2b0` `3e7bd81f-3922-49ad-9323-4ec6f4ac0737` `22026128-df1b-4839-86ea-17e264d75634` |
| 22:01:14.965 | `4a266146-5526-49e8-8642-bd074f0bf6dc` | `bacaf3ca-114c-4a41-b32a-6d06182f8636` | `e3971a79-136d-4616-ba72-d1277700ec70` `4982287e-346d-45df-b82d-f67dc2c434bb` `6054408f-9d11-43a7-b0c1-cdd97cd10276` `49c24042-b1a0-474c-8550-9376f21e09f0` |
| 22:01:40.986 | `22034a3d-59a0-4a92-b3bb-41697ed163a4` | `9c3610d8-7ca3-457f-b84e-c933426b24a7` | `3bee7391-0c6c-47e5-8eca-2e0e0e5ffadf` `9af2605d-2f9b-4de2-95a1-a146049af84f` `da6c9209-a971-4b33-ab86-9eafe0886562` `033cfe4c-f788-4a61-a145-0ff7da3a029f` |
| 22:02:08.124 | `cef8c001-8097-4665-89e5-c4464d5f39cc` | `89169aad-7495-4af3-a0ef-5af7093d0527` | `71ba620a-e242-43f6-bb75-eb623106ea70` `83d554db-cb39-4a21-88fd-a775d4436476` `6a3683cc-5fd1-4eb6-8f99-5deacfd19c8e` `9c34c37e-0c1a-4170-8b6d-44af4724d44a` |
| 22:02:30.519 | `5fadbba0-6b87-454e-857a-1a5ca91fc798` | `fb868e8d-273f-4e95-b7d0-bb0906706d77` | `651e47af-1975-4a28-924a-34976175e1a8` `11dc7c43-9f32-4a53-8e20-23150136178b` `6abdca65-cd7a-4063-b2ef-18dad3bfb215` `b34008b4-8a9f-47e2-9f99-feba7631b76e` |
| 22:02:57.965 | `715747d7-272c-4159-af1b-c1f5573e6846` | `f80362ac-263a-46f2-b97c-94247dc4d2fd` | `66a17854-42dc-43f6-8187-f6a9bc993327` `ac1082dd-c967-4c5e-b02d-fd17c0316f53` `580ba1dc-2feb-44c0-84da-d8468e4945ae` `c3ff30e4-d01c-463b-987b-8037c2ecbc9e` |
| 22:03:30.394 | `00e687c5-9e54-4631-b182-17f3aca529a8` | `b4964436-62a5-4c12-828c-3c19d6b14d00` | `95878062-7013-43d7-96c2-624e6f507e31` `99289b87-b9a3-4398-899e-b09b7e989989` `6637dbfc-fdd7-421c-acd1-9a32a01627fd` `6446d8de-9694-4c35-8230-111b9137351b` |
| 22:03:56.323 | `fd7abdc9-d95d-41c7-adea-3703b8fa492b` | `174b23db-e8bb-4a4d-a8b9-60399471d7f6` | `21da99cd-363b-4e09-b698-ef7d286f1751` `4a0e55cc-68c8-4678-8a65-cbed74156afa` `abe9883f-4f08-45ab-bd78-0f2298042ae9` `53efdd07-685a-429e-893a-b8b0c1392758` |
| 22:04:23.278 | `f90803a4-5546-4c49-a337-e72b06839709` | `aba1f701-0787-4aec-957b-59fbea4b5f7e` | `964894ba-6745-47af-89bd-4d8e400cb1a2` `13a2a795-a6da-494d-b5c4-3cb8969a8119` `924e11ec-99ba-4b45-b819-3d250fb3a32c` `4641e73b-563f-402c-967b-f97ca7d44089` |
| 22:04:45.421 | `261c9e37-d142-467c-93cf-db672b3361e1` | `2c469821-f5f2-4a86-b61e-efbf90c0d99f` | `61ca9b2f-2809-44a3-bd30-c9f415b0f287` `7a816ab5-a097-4a89-b637-b0d599de85cf` `e4c8bae5-40cd-4c24-b510-7598b45ba689` `bbf15509-7041-4fe3-9794-82f198817ac7` |
| 22:05:12.341 | `f6651260-360b-4871-8432-3046d7b51925` | `cf72b34c-7814-47bd-b9cd-8989f75cdb73` | `b349c653-5bc1-47d9-b643-f3835ed33339` `cef2d3ff-a599-4102-ba95-e9dde0f5851e` `7d3242c9-d9d9-4f94-9667-cab3977ce53c` `ceceb207-baa3-4265-badd-bf5e2a858bd8` |
| 22:05:37.784 | `81ffe68f-1e8b-458a-9163-3456dbd51f58` | `ba57c931-ff0b-4c5a-988e-79968b932ad2` | `2339fda6-910f-4756-8f09-bd85c32f59d1` `6d783f71-88a0-46b6-81bb-6f063fafa2e9` `0d6eed3d-54bb-4427-8c7c-f25fb1382d99` `6e8f1ba9-8568-49a8-acb5-424ccc3a36f6` |
| 22:06:03.155 | `492310b2-bab1-4d3c-97bf-423f58740a6b` | `c7ffbada-b901-4ce2-9a7c-c710a3b4744d` | `f5599fe8-ee80-4e71-b874-cb0d3276f4dd` `12232a9a-ac18-4644-a2bb-ba81a478fbdc` `283598f6-9ae8-4878-894d-3fed45345abe` `494fc2a2-9e50-40e8-959e-0c6119d1bfb4` |
| 22:06:25.202 | `2a04ab0d-4657-4c5b-ac56-0e3938be4d76` | `009cb5e4-577c-400a-9262-14a3ce5f7667` | `5eb841bb-7c74-4e09-9d8e-7f4c5e58ee44` `6783c41a-f404-45f4-96b6-087af0af5784` `4ce95566-c729-4766-b329-195f01ef1375` `172e51fd-92ec-4264-8c95-7933113ccce2` |
| 22:06:51.417 | `8b513564-423c-4d76-ab91-40c12a69c777` | `3e516d0c-893c-46d9-abcb-de4044d882e7` | `cb86bd11-34b2-464f-b38e-a89031e1339b` `1e743c39-a933-4f68-8047-c72931b62a13` `03715939-7da6-42aa-9b9d-31849ed1a849` `5a94a18d-4c1b-4a11-bac9-81008ec2b63f` |
| 22:07:23.159 | `1113830f-0426-4524-824d-91650de94404` | `49b9a19a-9594-4c99-b6a7-f0ebc3f9fad0` | `4c12ba2f-f0c7-4294-96b4-74971cb69800` `c28f8d1f-169c-449f-9022-c53d28a5af37` `0268d874-27d8-46d0-859c-2f0ccaa5decc` `c53f435d-4bbf-4336-b634-29e45456d81f` |
| 22:07:49.992 | `4bd55fd5-a4a4-44b5-bcf8-643024f7cda9` | `98623035-5966-4afe-886b-c13629dad7a1` | `af785876-fad4-4a93-8318-74ef94873b63` `d7f3d30a-ed21-453d-9710-e19fee93b563` `15877d6f-cc14-4856-8e82-d7e33e30fab7` `28d04425-d5a3-4fe2-a51f-87343ac6d63e` |
| 22:08:20.301 | `d835fa7a-20b8-43cd-b1cd-203b062e9c72` | `3ab7fa22-aad1-4cc1-894e-8878f29b829b` | `1b8c4eeb-0967-4229-b699-9e1b641c43d7` `8939c815-18a8-44d9-9822-f2621b113b47` `03bab195-6c78-4248-852b-fd70bf03719e` `c2a1d9a0-fdc7-4b60-bc7f-155eb42fd856` |
| 22:08:42.490 | `64af93c8-045c-4a01-a0e3-ffafaa3f6a4d` | `fff07d56-0d61-4fd8-a68b-5a4dabf0d471` | `baaca9e3-adf0-4e74-bddd-e938543f1bcf` `e35fff9e-be8c-468c-b4ca-d7d00d71a66c` `90c22910-5339-407c-9350-651b8a74a061` `f7037ec2-5810-4414-ab1a-847a61048fd3` |

## Ids still missing

| Gap | Why | Fix | Whose |
| --- | --- | --- | --- |
| Which runtime session id the tools gateway used for each call, and the runtime's request id | Neither the gateway's log nor the runtime's logs name them; the runtime's own `InvokeAgentRuntime` spans and application logs (request id, session id, `latency_ms`) are not turned on for our runtimes | Turn on the runtimes' observability; log the session and request headers in the tools server and the sub-agents | ours (config, code) |
| The parent of the sub-agent's root span, and the agents gateway's trace inside the runtime | The agents gateway's trace does not continue into the runtime (TC10); the parent span is in no backend we can read (TC9) | Ask AWS | AWS |
| Identity's own timing for the runtime's per-request token call | Only CloudTrail records it, to the second; no span or vended log | Ask AWS for spans or vended logs | AWS |
| The trace of each token exchange back to its caller | Identity starts a new trace at the token endpoint (TC10) | Ask AWS; meanwhile the issuer can log Identity's request headers | AWS (ours for a workaround) |
| 4 of 116 hop exchanges have no issuer API Gateway request id | X-Ray sampled them out | The issuer logs its API Gateway request id | ours (code) |
| The chat start's Lambda request id in the API's access log | The access log format leaves out `$context.integration.requestId` and `$context.xrayTraceId`; the stage has no X-Ray | Add both fields and turn on X-Ray for the stage | ours (config) |
| Request ids of the Connect calls in the chat start's own log | The function does not log them (CloudTrail has them, above) | Log the SDK's request id per call | ours (code) |
| Bedrock request id of each sub-agent model call | No botocore span for Bedrock Runtime; the Strands `chat` span has none | Log `ResponseMetadata.RequestId` from a botocore event hook | ours (code) |
| The designer's routing model call and its data requests | The designer emits no trace and no request ids for its model calls (A19); its log gives a correlation id per turn | Ask AWS | AWS |
| Connect's time from a stamped question to the designer, and from the designer's response to the stamp | No Connect span or log between `SendMessage` and the designer | Ask AWS (C15) | AWS |

## Queries to reproduce

CloudWatch Logs Insights, the tools gateway's requests for one trace:

```
fields @timestamp, request_id, body.log, body.requestBody
| filter trace_id = '6ac2b5126beb7ad13c8c647f2041850a'
| sort @timestamp asc
```

on `/aws/vendedlogs/bedrock-agentcore/hr-super-agent-tools`. The same trace id in
`/aws/bedrock-agentcore/runtimes/hr_super_agent_tools-Ykb6G5FTK1-DEFAULT` shows the tools runtime
microVM (log stream) that served the call:

```
fields @timestamp, @logStream, @message
| filter @message like '6ac2b5126beb7ad13c8c647f2041850a' and @logStream like 'runtime-logs'
| sort @timestamp asc
```

Dynatrace (tenant `zfr04910`), every span of one sub-agent session:

```
fetch spans, from: "2026-10-04T21:58:00Z", to: "2026-10-04T22:09:40Z"
| filter session.id == "48e7b0a1-5754-40ef-93a1-4998ae7f8fdd-profile"
| fields start_time, end_time, span.name, trace.id, span.id, service.instance.id, aws.request_id
| sort start_time asc
```

The designer's events for one contact: `node connect/acxd/logs.js <contactId> 3600000 --json`
in guppi-hr.
