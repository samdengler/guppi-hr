# Evidence for the AgentCore Runtime V2 (unprimed) latency run of 4 October 2026

The ids behind every number in `latency-timelines-2026-10-04.md`: Connect contacts, the designer's
correlation ids, API Gateway and Lambda request ids, X-Ray and Dynatrace trace and span ids,
AgentCore Gateway request ids, runtime session ids, the log stream of each microVM, and the
request ids of the AgentCore Identity calls. The same data, with every step of every turn, is
in `latency-timelines-2026-10-04-evidence.json`.

Account `009080466601`, region `us-east-1`. Window 2026-10-04T21:41:30Z to 2026-10-04T21:53:40Z: 23 chats,
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
- On V2 a runtime's log stream is `runtime-logs-<session id>`, one per session; each new session is
  an instance restored from the version's snapshot, so the stream names the session.
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

Every snapshot read by a sub-agent: 11 calls on 10 different tools runtime sessions. Delivery is
from the issuer's answer (the gateway's runtime token) to the tools server's first span;
handshake from that first span to the `tools/call` span; total is the sub-agent's MCP span.

| Time | Contact | Tool | Tools gateway request id | Trace id | Tools runtime microVM (log stream) | Policy ms | Delivery ms | Handshake ms | Tool ms | Total ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 21:42:19.130 | `d39c338a-8878-4041-b185-e869082f6f3e` | hr___get_profile | `941a6f27-d9dd-4bfa-991c-7c1f19b3aaae` | `6ac2c8300137d8be22032585540dfb16` | `runtime-logs-0e1392a6-d9ca-4e82-99c2-c03602934654` | 51 | 1597 |  |  | 3533 |
| 21:43:30.977 | `c86cb354-f355-46b0-99b5-8a87a4193008` | hr___get_profile | `065d8154-21b4-4486-ae07-65b16e055748` | `6ac2c87f7088be63566c77fb004822f5` | `runtime-logs-28428b28-c10b-4857-a51c-b375cd4d35d8` | 52 | -49 |  |  | 3669 |
| 21:44:01.082 | `df68ec68-12db-4345-9288-04a1f24aa81c` | hr___get_profile | `0370c1c9-6f4c-4ca1-9f1a-4b80c203adca` | `6ac2c8953afbf1350fad1c313e3c48f1` | `runtime-logs-fcf11548-bf12-4f05-af53-ef9f7c9c696a` | 50 | -121 |  |  | 3636 |
| 21:45:30.977 | `de563712-a523-44d6-826e-7226d49c3fef` | hr___get_profile | `dafad436-8765-4330-b06c-cdb087da0217` | `6ac2c8f802dfd4457f1f2ae34e322608` | `runtime-logs-725b22f0-251a-415b-9337-1c742145e38f` | 53 | 276 |  |  | 6060 |
| 21:45:54.967 | `2266020c-510b-46b4-851b-a77515bb01f6` | hr___get_profile | `2cf0601e-a4e6-4261-8bcf-12254ba534fb` | `6ac2c9105e2cabdd0aff8f44504e4068` | `runtime-logs-82862774-aec4-4045-b735-af361f8fa8f7` | 54 | -272 |  |  | 3219 |
| 21:47:56.596 | `65853153-1ba0-4078-afbb-5d6c1a4b81bb` | hr___get_profile | `c6003e52-568e-4882-acd6-692acde6b81e` | `6ac2c98863d5ea456ff36ad60d3ec133` | `runtime-logs-8977bab8-b6e4-40d7-941d-81b8d73941a3` | 50 | -254 |  |  | 3615 |
| 21:48:18.725 | `10fd08e0-aef3-4847-b9a1-8cf583ee121e` | hr___get_profile | `e72da84c-ff76-4922-b2bb-1b0326a06dfd` | `6ac2c99e71e100d222a40c0230be21b8` | `runtime-logs-893df8a3-ab86-40bc-b835-80a27aad3500` | 49 | -307 |  |  | 3452 |
| 21:49:38.195 | `1da4d530-bbd7-47c1-97a5-7f1678554b8b` | hr___get_profile | `ed6315e3-c95a-4376-9829-f80500702d99` | `6ac2c9ef058b30f777e312626506a00e` | `runtime-logs-a69e1bb5-bb6e-4fb2-8409-ca4459f0c5a5` | 51 | -313 |  |  | 3981 |
| 21:50:00.427 | `ee99f857-5e8d-4ae2-bcfa-e91b03b84046` | hr___get_profile | `f6aa701d-8e78-4ee5-b625-2815019685ac` | `6ac2ca040c770f171384bca24ab2788d` |  | 49 |  |  |  | 3244 |
| 21:52:00.222 | `f86313e3-5c41-4056-887d-5016fc7e9004` | hr___get_profile | `1c8e8aa2-0d94-445c-8206-649459d0a065` | `6ac2ca7c7665fc42025be3d30bab840d` | `runtime-logs-9607e346-15fe-40d1-830c-d0bff25ed66c` | 49 | -253 |  |  | 3520 |
| 21:52:21.559 | `e4636a0d-537c-44f6-8682-08f73cbf201a` | hr___get_profile | `d745fdf0-ebb6-480a-8cb3-c47fe639c0d4` | `6ac2ca923c65a716459bf1466174b574` | `runtime-logs-85087117-f163-48b8-a29b-fd1e7288c0e9` | 57 | -266 |  |  | 3322 |

The runtime token exchange for each call (Identity to the issuer):

| Time | Tools gateway request id | Issuer API Gateway request id | Issuer Lambda request id | X-Ray trace |
| --- | --- | --- | --- | --- |
| 21:42:19.130 | `941a6f27-d9dd-4bfa-991c-7c1f19b3aaae` | `22e1c585-ee11-4f6c-bc51-5f0de65b1fa5` | `00ceb865-8cdb-49ef-beec-6194c810a4e5` | `1-6ac2c83b-75f646ef680eabe245db1151` |
| 21:43:30.977 | `065d8154-21b4-4486-ae07-65b16e055748` | `dcf82e19-3d18-41fa-86ef-e0c3b541653b` | `7921d285-b705-439e-bc5a-d3a54cf41629` | `1-6ac2c883-187e5d506f49978e0a5fc753` |
| 21:44:01.082 | `0370c1c9-6f4c-4ca1-9f1a-4b80c203adca` | `53a4c88a-dd25-4460-917a-78e11417b59d` | `41c0c3c0-7680-4caa-9965-3a1c8900b4f7` | `1-6ac2c8a1-6bb6d0fc15a344b8356d2e52` |
| 21:45:30.977 | `dafad436-8765-4330-b06c-cdb087da0217` | `4bad9d42-02a3-4e17-b55b-9327ca2e51a0` | `d37c304d-9453-4476-984c-b03005abefda` | `1-6ac2c8fb-718665ac5521b73847cb1f9e` |
| 21:45:54.967 | `2cf0601e-a4e6-4261-8bcf-12254ba534fb` | `7c0fa13f-4262-46bf-b265-df051f6e343c` | `5e8b80a6-e67c-48a2-aeba-7168cad6a3a1` | `1-6ac2c913-52aa0aff58ae08197f673484` |
| 21:47:56.596 | `c6003e52-568e-4882-acd6-692acde6b81e` | `c5000b9e-2a13-415a-9a3f-92ac4e096159` | `f5e9bb71-4908-4377-8bf1-d39aa555038f` | `1-6ac2c98c-04b26b9073fdd0453f0cd3f0` |
| 21:48:18.725 | `e72da84c-ff76-4922-b2bb-1b0326a06dfd` | `80ce2ad0-8c9b-4b63-9756-8825d385a40a` | `bbbdc72e-b92d-46bf-b061-9904121478be` | `1-6ac2c9a3-1a4841de52e8232409c13781` |
| 21:49:38.195 | `ed6315e3-c95a-4376-9829-f80500702d99` |  | `e459f159-ea48-4298-accb-5100764ec13e` |  |
| 21:50:00.427 | `f6aa701d-8e78-4ee5-b625-2815019685ac` | `f8978198-3d98-4a12-beac-608cc10e61b4` | `a41279fd-57b7-4b53-be44-0d8e8cc5e155` | `1-6ac2ca08-2f086f590721297b498db919` |
| 21:52:00.222 | `1c8e8aa2-0d94-445c-8206-649459d0a065` | `49a95e7b-333f-47b0-b03a-f6e54f2f6d45` | `b9f1c0ba-a701-4a52-b20c-c258bdca8367` | `1-6ac2ca80-27a1d39b23f53c7e3ecbddb0` |
| 21:52:21.559 | `d745fdf0-ebb6-480a-8cb3-c47fe639c0d4` | `cd400e9f-23c8-4549-aa68-1f6fe0a781f1` | `282b980f-b34b-4286-bcae-e4858899b70a` | `1-6ac2ca95-208ef7f77450d4fb32baf81c` |

## Sub-agent runtime sessions and microVMs (A21, time sink 2)

Every sub-agent request: 27 requests on 16 sessions, each session on its own instance. Delivery
is from the agents gateway's "Executing Http request for target" to the sub-agent's `POST /` span.

| Request time | Call | Runtime session id | Agents gateway request id | Gateway trace id | Sub-agent trace id (Dynatrace) | Root span id | MicroVM (log stream) | Process started | Delivery ms | Request ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 21:42:10.863 | first | `d39c338a-8878-4041-b185-e869082f6f3e-profile` | `3571a4d9-9c12-4d43-971f-3d12fd248501` | `6ac2c8306373dfff67389fbb3f223e7c` | `6ac2c8300137d8be22032585540dfb16` | `034d860fabbbd6fe` | `runtime-logs-d39c338a-8878-4041-b185-e869082f6f3e-profile` |  | 1957 | 13071 |
| 21:42:28.717 | follow-up | `d39c338a-8878-4041-b185-e869082f6f3e-profile` | `536d8f92-8d7e-45df-b76b-10b496f7b48c` | `6ac2c8441a31b83e7a5026ce42f6a893` | `6ac2c8442d3dd9193a74195413d17e78` | `3060a6770997e496` | `runtime-logs-d39c338a-8878-4041-b185-e869082f6f3e-profile` |  | 300 | 911 |
| 21:43:29.703 | first | `c86cb354-f355-46b0-99b5-8a87a4193008-profile` | `f99b676c-30b1-47df-9489-408d85301d20` | `6ac2c87f5bdebc2d69fbd01407b41db8` | `6ac2c87f7088be63566c77fb004822f5` | `034d860fabbbd6fe` | `runtime-logs-c86cb354-f355-46b0-99b5-8a87a4193008-profile` |  | 1991 | 5788 |
| 21:43:51.590 | first | `df68ec68-12db-4345-9288-04a1f24aa81c-profile` | `99aae8a0-e7c8-4f01-a9f0-a55615e442e4` | `6ac2c8955d53fb9529d88bb34450a829` | `6ac2c8953afbf1350fad1c313e3c48f1` | `49b44b3c6038c76f` | `runtime-logs-df68ec68-12db-4345-9288-04a1f24aa81c-profile` |  | 2152 | 14801 |
| 21:44:11.195 | follow-up | `df68ec68-12db-4345-9288-04a1f24aa81c-profile` | `6db63974-12ce-4c4f-ac78-55393ac4ec15` | `6ac2c8aa44e40862305f14853c7086b5` | `6ac2c8aa378898d0647fb15819958f41` | `4af1579e892640c0` | `runtime-logs-df68ec68-12db-4345-9288-04a1f24aa81c-profile` |  | 308 | 916 |
| 21:44:50.458 | first | `2dd0024b-e94b-4762-bb2a-a80801b3328a-travel` | `a647c00d-2a09-415e-b198-0e9b0b89d54e` | `6ac2c8d04b3a264818ee50d57f73fff6` | `6ac2c8d05a8db9d9251602134ecff1e3` | `20c1b3587db59a9f` | `runtime-logs-2dd0024b-e94b-4762-bb2a-a80801b3328a-travel` |  | 1944 | 12158 |
| 21:45:07.347 | follow-up | `2dd0024b-e94b-4762-bb2a-a80801b3328a-travel` | `bdae61c6-cf4c-4dc5-9f33-f505b0b60454` | `6ac2c8e259fb36e80f5486b00aba4fa3` | `6ac2c8e315c6b742334ece9220c47d82` | `5335239a5e342e67` | `runtime-logs-2dd0024b-e94b-4762-bb2a-a80801b3328a-travel` |  | 292 | 2219 |
| 21:45:29.801 | first | `de563712-a523-44d6-826e-7226d49c3fef-profile` | `11088f72-1683-4225-94c1-b78abeae01d9` | `6ac2c8f73b0c10d959f0d77778c181c9` | `6ac2c8f802dfd4457f1f2ae34e322608` | `034d860fabbbd6fe` | `runtime-logs-de563712-a523-44d6-826e-7226d49c3fef-profile` |  | 1790 | 8027 |
| 21:45:53.777 | first | `2266020c-510b-46b4-851b-a77515bb01f6-profile` | `b6dad121-b658-46c3-9d51-9beca2a01200` | `6ac2c90f624fee1d503f4b150ff7e49a` | `6ac2c9105e2cabdd0aff8f44504e4068` | `034d860fabbbd6fe` | `runtime-logs-2266020c-510b-46b4-851b-a77515bb01f6-profile` |  | 1735 | 5259 |
| 21:46:03.618 | follow-up | `2266020c-510b-46b4-851b-a77515bb01f6-profile` | `9e057492-4e41-4c6a-b2e9-862d8fa49179` | `6ac2c91b1976c756752016302975a55b` | `6ac2c91b4cd2f65e4051179b0cd251a5` | `405c168d803aed22` | `runtime-logs-2266020c-510b-46b4-851b-a77515bb01f6-profile` |  | 285 | 945 |
| 21:46:42.134 | first | `f67be432-6212-4e1e-89eb-0f340eb51c64-travel` | `df1040ba-616a-4c57-a796-a77d6e6bd8ca` | `6ac2c9405a48384d340daa6738f47014` | `6ac2c9401cf52200488eb58a572f4d18` | `20c1b3587db59a9f` | `runtime-logs-f67be432-6212-4e1e-89eb-0f340eb51c64-travel` |  | 1866 | 3773 |
| 21:46:50.598 | follow-up | `f67be432-6212-4e1e-89eb-0f340eb51c64-travel` | `95558667-f0dd-401c-bc57-d7de766991f4` | `6ac2c94a32e24bc639892985049b30a0` | `6ac2c94a61bb4e070d67964a13c03043` | `2902f90dba9669f5` | `runtime-logs-f67be432-6212-4e1e-89eb-0f340eb51c64-travel` |  | 326 | 2187 |
| 21:47:55.182 | first | `65853153-1ba0-4078-afbb-5d6c1a4b81bb-profile` | `c107b470-82a7-464d-9349-812df24b803a` | `6ac2c98830180fec6263c8686992707b` | `6ac2c98863d5ea456ff36ad60d3ec133` | `49b44b3c6038c76f` | `runtime-logs-65853153-1ba0-4078-afbb-5d6c1a4b81bb-profile` |  | 2552 | 5863 |
| 21:48:17.387 | first | `10fd08e0-aef3-4847-b9a1-8cf583ee121e-profile` | `e32cbe6a-5395-482c-b531-36e68da0d839` | `6ac2c99e4edf431e429c27d40ee33a84` | `6ac2c99e71e100d222a40c0230be21b8` | `49b44b3c6038c76f` | `runtime-logs-10fd08e0-aef3-4847-b9a1-8cf583ee121e-profile` |  | 2423 | 5610 |
| 21:48:27.939 | follow-up | `10fd08e0-aef3-4847-b9a1-8cf583ee121e-profile` | `52fdaea1-ffe9-472a-a746-3c0c56218793` | `6ac2c9ab77d8fec46a5fc8486c332665` | `6ac2c9ab1d3abb6a78765b9026759bd7` | `bab65a0b05794514` | `runtime-logs-10fd08e0-aef3-4847-b9a1-8cf583ee121e-profile` |  | 267 | 1046 |
| 21:49:06.944 | first | `f2e4ea22-8e9f-4a1a-9af4-5bf9da598f51-travel` | `6f2ffe7b-045e-4009-9eed-aed68fbf8b79` | `6ac2c9d0553e9aeb410d12932a85be84` | `6ac2c9d0698c1b68702ed6e00e809c79` | `20c1b3587db59a9f` | `runtime-logs-f2e4ea22-8e9f-4a1a-9af4-5bf9da598f51-travel` |  | 1964 | 3731 |
| 21:49:15.100 | follow-up | `f2e4ea22-8e9f-4a1a-9af4-5bf9da598f51-travel` | `279474a4-436c-4c31-8b5f-6552260f045a` | `6ac2c9da018b11602cefb1357e805ead` | `6ac2c9da4052fd9a4907b4292570dca4` | `2902f90dba9669f5` | `runtime-logs-f2e4ea22-8e9f-4a1a-9af4-5bf9da598f51-travel` |  | 269 | 2009 |
| 21:49:37.018 | first | `1da4d530-bbd7-47c1-97a5-7f1678554b8b-profile` | `c6b509dc-569d-4cfb-96a5-1d4201207e17` | `6ac2c9ee4b80c46776e37a096280bf44` | `6ac2c9ef058b30f777e312626506a00e` | `034d860fabbbd6fe` | `runtime-logs-1da4d530-bbd7-47c1-97a5-7f1678554b8b-profile` |  | 1962 | 5935 |
| 21:49:59.222 | first | `ee99f857-5e8d-4ae2-bcfa-e91b03b84046-profile` | `9cc40b38-7708-4e92-9ad8-7cc6216d00da` | `6ac2ca0436814ce21ab1824c0f295c7c` | `6ac2ca040c770f171384bca24ab2788d` | `034d860fabbbd6fe` | `runtime-logs-ee99f857-5e8d-4ae2-bcfa-e91b03b84046-profile` |  | 2320 | 5253 |
| 21:50:09.145 | follow-up | `ee99f857-5e8d-4ae2-bcfa-e91b03b84046-profile` | `91bc5116-af0b-4c92-b227-4e8cd3fa1741` | `6ac2ca10608a44225978ec13152f0bdf` | `6ac2ca1041e6ac87779fab0a390d3411` | `405c168d803aed22` | `runtime-logs-ee99f857-5e8d-4ae2-bcfa-e91b03b84046-profile` |  | 291 | 922 |
| 21:50:48.979 | first | `809bc097-cc6f-4d4a-bc50-e59e72034ce4-travel` | `047f08e0-fcd6-4829-8262-01b69fa6e623` | `6ac2ca364035263602b2cc222f848dd4` | `6ac2ca3615dfa18074d3557e4fc34a23` | `0df2ee66f7e31b06` | `runtime-logs-809bc097-cc6f-4d4a-bc50-e59e72034ce4-travel` |  | 2204 | 12429 |
| 21:51:06.128 | follow-up | `809bc097-cc6f-4d4a-bc50-e59e72034ce4-travel` | `89cff0d5-ef98-4619-a4ff-5557877b4eb1` | `6ac2ca494dbaacc02a268f66496ba433` | `6ac2ca49364fbbfc6cf37cf860aee7c2` | `44e138f096009314` | `runtime-logs-809bc097-cc6f-4d4a-bc50-e59e72034ce4-travel` |  | 295 | 1948 |
| 21:51:58.991 | first | `f86313e3-5c41-4056-887d-5016fc7e9004-profile` | `62c4d1a9-d027-4af1-8349-75451619156d` | `6ac2ca7c3c451a0104ae862b791ce958` | `6ac2ca7c7665fc42025be3d30bab840d` | `034d860fabbbd6fe` | `runtime-logs-f86313e3-5c41-4056-887d-5016fc7e9004-profile` |  | 2008 | 5549 |
| 21:52:20.410 | first | `e4636a0d-537c-44f6-8682-08f73cbf201a-profile` | `7f3d11e2-cfa6-4b5d-93d4-134f216a26fb` | `6ac2ca9220a7f82e0ddb5af521b08aa4` | `6ac2ca923c65a716459bf1466174b574` | `034d860fabbbd6fe` | `runtime-logs-e4636a0d-537c-44f6-8682-08f73cbf201a-profile` |  | 1945 | 5282 |
| 21:52:30.287 | follow-up | `e4636a0d-537c-44f6-8682-08f73cbf201a-profile` | `b12706b1-7872-425f-a69d-e5ba72873d38` | `6ac2ca9d76a056441158f15d5ecb7308` | `6ac2ca9d71c61abe3a994adf5db392af` | `405c168d803aed22` | `runtime-logs-e4636a0d-537c-44f6-8682-08f73cbf201a-profile` |  | 300 | 969 |
| 21:53:09.033 | first | `f63c8a61-a523-4a43-9e3b-580ecc6e3e2b-travel` | `fe612637-88f6-4200-9d3c-62568b24ce27` | `6ac2cac203112c1a101ea0236a033ce2` | `6ac2cac22eea48691f2d6c9128d4f2f0` | `0df2ee66f7e31b06` | `runtime-logs-f63c8a61-a523-4a43-9e3b-580ecc6e3e2b-travel` |  | 2255 | 3845 |
| 21:53:17.365 | follow-up | `f63c8a61-a523-4a43-9e3b-580ecc6e3e2b-travel` | `2a819ce7-a8d1-4cea-bedf-a222221dff7c` | `6ac2cacc2346e97d3076d39d2a170b8b` | `6ac2cacd4646bb8f10d2e3fd0a713a2a` | `06bfdb4e8f3fb5be` | `runtime-logs-f63c8a61-a523-4a43-9e3b-580ecc6e3e2b-travel` |  | 288 | 2215 |

## AgentCore Identity calls in the sub-agents (time sink 4)

The first request on each session: the workload access token, then the on-behalf-of exchange
for the tools token. Request ids are AgentCore Identity's `aws.request_id` from the botocore spans.

| Time | Runtime session id | GetWorkloadAccessTokenForJWT request id | ms | GetResourceOauth2Token request id | Credential provider | ms | Issuer API Gateway request id | Issuer Lambda request id |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 21:42:16.595 | `d39c338a-8878-4041-b185-e869082f6f3e-profile` | `bfb86f31-0165-445e-92fb-83b10011059b` | 61 | `be0de9e4-d374-4505-9bc8-aa0e594b3ebc` | guppi-obo-hr-agent-profile | 162 | `dc29a125-0770-4a11-a9bd-232dc8625233` | `ec7f6ba4-03df-4b3b-a3e9-f1beff4cd8bd` |
| 21:43:30.057 | `c86cb354-f355-46b0-99b5-8a87a4193008-profile` | `1c7a29c8-2309-468e-b633-3886268b1924` | 60 | `f8c7d581-ed89-400a-9e23-06ac99664638` | guppi-obo-hr-agent-profile | 160 | `a4accd52-0537-49c1-8c4e-5ac92e04e45d` | `c0814893-5d51-428a-be76-a04cc20966b8` |
| 21:43:58.133 | `df68ec68-12db-4345-9288-04a1f24aa81c-profile` | `c82c8db8-f005-4ef9-a960-6d80746bf365` | 72 | `450da7c1-06f4-4b61-8ed8-aa9d507ecfe6` | guppi-obo-hr-agent-profile | 203 | `76c2dc94-5c37-4d2e-97ef-c7aa012ee727` | `3e4ab2fe-5cc1-4b6d-b4c6-3263d0ba4936` |
| 21:44:57.169 | `2dd0024b-e94b-4762-bb2a-a80801b3328a-travel` | `3181c296-f5f5-4ed5-9f13-88c5495252b7` | 60 | `5bb5a1e2-2e57-482c-a6eb-9b4e33f1eb24` | guppi-obo-hr-agent-travel | 193 | `3db0db2b-0405-4097-a083-7a2641d328d0` | `712f9c4b-e230-451a-8ba4-9514072afbeb` |
| 21:45:30.080 | `de563712-a523-44d6-826e-7226d49c3fef-profile` | `284a19ed-9723-4563-b25c-143922c1bfb9` | 69 | `8418d2a3-d4b4-49bd-be5b-1fe4420aa93b` | guppi-obo-hr-agent-profile | 172 | `a0ef7b7f-8827-4438-9fa1-999677608d0b` | `a787d655-eeee-47e7-8427-d711b515f8a3` |
| 21:45:54.054 | `2266020c-510b-46b4-851b-a77515bb01f6-profile` | `f42e383f-3f87-4259-8c56-874ac1fbbbd0` | 86 | `c1a24c73-dd33-4c32-a9f7-2903b4011862` | guppi-obo-hr-agent-profile | 162 | `0f5f4bff-c686-4158-8ff1-69d74080daba` | `523e2fab-c61f-43b5-b0dc-47a27a063937` |
| 21:46:42.410 | `f67be432-6212-4e1e-89eb-0f340eb51c64-travel` | `3ac61419-ccba-4dbb-82d6-26066cd10a73` | 66 | `028a4d22-fff5-429b-adac-f4d7f24188fd` | guppi-obo-hr-agent-travel | 189 | `753276cf-9fee-48ca-81f3-d052d750129e` | `69373e87-a0ae-48b7-8f3b-f169a5503714` |
| 21:47:55.554 | `65853153-1ba0-4078-afbb-5d6c1a4b81bb-profile` | `422cdc6e-7fa0-4d47-92ec-0ae85c5522f1` | 63 | `c64033ae-9fe5-4560-8e7d-8110d187715b` | guppi-obo-hr-agent-profile | 155 | `65540109-06f5-4ae8-afc5-a9e09198e43c` | `59f664bb-a30d-4857-ac5d-da01b9bddbeb` |
| 21:48:17.731 | `10fd08e0-aef3-4847-b9a1-8cf583ee121e-profile` | `b0139ac2-8767-4a7b-94ff-4904d7019f59` | 83 | `e1313cc2-8c94-4961-aef2-1e01bd807f88` | guppi-obo-hr-agent-profile | 165 | `3f3f1530-bf03-4ff1-bc71-69cbd5dce5ec` | `e0b2ed0f-6416-445e-9fdc-0c2460b6615c` |
| 21:49:07.223 | `f2e4ea22-8e9f-4a1a-9af4-5bf9da598f51-travel` | `8c5852de-a052-41f9-82a8-6aa1e74d7eea` | 57 | `90c5edb2-4f2e-4efc-922f-11c3e11c9fc5` | guppi-obo-hr-agent-travel | 161 | `cc5a26e6-535f-4dd9-977e-3202d2b80d2c` | `c8a7de7f-5693-4b96-97cb-eb4f8276260f` |
| 21:49:37.302 | `1da4d530-bbd7-47c1-97a5-7f1678554b8b-profile` | `a2319205-6a2e-4112-8986-b02aaa1f9170` | 66 | `60ee5275-f391-483a-8832-4165e81251cf` | guppi-obo-hr-agent-profile | 171 | `b091e431-8b6b-426e-838e-6403fc90b027` | `f37c0f40-0252-4512-b254-9ab88b171f74` |
| 21:49:59.495 | `ee99f857-5e8d-4ae2-bcfa-e91b03b84046-profile` | `8be19915-fb59-408a-a335-0525467c5f91` | 59 | `e9cc7e7e-fd83-4ace-a255-d204d619635e` | guppi-obo-hr-agent-profile | 184 | `7ec5d258-0cb5-4648-932a-634d16c8073d` | `e25016eb-f831-4586-9cc6-6dc8090adaa8` |
| 21:50:55.573 | `809bc097-cc6f-4d4a-bc50-e59e72034ce4-travel` | `2a4743a0-66df-4142-99f9-f8ffe6b845db` | 122 | `ee94aca8-701c-4ec0-9806-03d6d865d75d` | guppi-obo-hr-agent-travel | 159 | `5e0d0e71-6b6d-4622-a00c-1cfbc6ec799e` | `7493223f-4a18-4325-a5db-db57ec516875` |
| 21:51:59.262 | `f86313e3-5c41-4056-887d-5016fc7e9004-profile` | `815ef007-2fe5-44d1-ba2d-1f607f505979` | 64 | `99a38c01-7eb6-4d3a-b568-df87c310c2d7` | guppi-obo-hr-agent-profile | 171 | `c3dcafad-fe63-4b14-86c2-3cfb4c2cd893` | `923474eb-0902-4a25-b980-8471165bc96d` |
| 21:52:20.690 | `e4636a0d-537c-44f6-8682-08f73cbf201a-profile` | `62fc7a6b-9cef-4a66-8e66-07196bc51cbc` | 50 | `6b04d30a-6bb9-485c-a05a-f924f51c5ba7` | guppi-obo-hr-agent-profile | 151 | `2df534cd-f733-4077-989c-66e97aea563d` | `aefb7d35-2fe1-4e25-b772-53576bc2669f` |
| 21:53:09.388 | `f63c8a61-a523-4a43-9e3b-580ecc6e3e2b-travel` | `63e63bcb-2cf6-4d34-9a66-3d9823e2df10` | 101 | `87c7b8bd-01a7-4ee5-83b4-30d12ffaca17` | guppi-obo-hr-agent-travel | 161 | `e142e154-7a10-41d6-83b9-85071b24513e` | `e89f2438-0d4a-4c96-b81c-49b159052fec` |

## MCP setup calls through the tools gateway (time sink 4)

The `initialize`, `notifications/initialized` and `tools/list` of each new session.

| Time | Runtime session id | Method | Tools gateway request id | Sub-agent span id | ms |
| --- | --- | --- | --- | --- | --- |
| 21:42:18.774 | `d39c338a-8878-4041-b185-e869082f6f3e-profile` | initialize | `e5a7934a-cd73-41af-9eab-32831b4df181` | `3b43e63a4d303c9c` | 79 |
| 21:42:18.857 | `d39c338a-8878-4041-b185-e869082f6f3e-profile` | notifications/initialized | `8b4dd5ae-969d-4c46-be4e-af90df2fc4a1` | `3f0baab549b2bc6f` | 76 |
| 21:42:18.934 | `d39c338a-8878-4041-b185-e869082f6f3e-profile` | tools/list | `7595f52a-e59d-4a64-b9b6-1be776918187` | `e8d0d6be65a25c6f` | 193 |
| 21:43:30.655 | `c86cb354-f355-46b0-99b5-8a87a4193008-profile` | initialize | `db4513a7-788b-4cea-b3e1-c38ad86304f4` | `b4d384ea3ea57870` | 41 |
| 21:43:30.699 | `c86cb354-f355-46b0-99b5-8a87a4193008-profile` | notifications/initialized | `f2ee7427-584c-4c51-9357-045a0d72e797` | `bdaaa8cbd5b5ca81` | 83 |
| 21:43:30.783 | `c86cb354-f355-46b0-99b5-8a87a4193008-profile` | tools/list | `051aa7bb-6a68-4c28-afe1-cfca095ef3e8` | `bb39c72267e62df9` | 191 |
| 21:44:00.688 | `df68ec68-12db-4345-9288-04a1f24aa81c-profile` | initialize | `008bb069-7a52-40c3-a3f3-f74f619f4fad` | `a219aa942ab07f64` | 84 |
| 21:44:00.776 | `df68ec68-12db-4345-9288-04a1f24aa81c-profile` | notifications/initialized | `c649089c-4aba-4950-85f4-7d1dda28b0cd` | `ac2e57e7be768521` | 99 |
| 21:44:00.876 | `df68ec68-12db-4345-9288-04a1f24aa81c-profile` | tools/list | `a71bf85f-1424-4474-82c4-f4685ca45fd1` | `a3d1a677bf3a75c9` | 202 |
| 21:44:59.186 | `2dd0024b-e94b-4762-bb2a-a80801b3328a-travel` | initialize | `4e6c267f-fc91-42ea-ac22-5cb91dc8cda2` | `cd766d6df9161859` | 71 |
| 21:44:59.261 | `2dd0024b-e94b-4762-bb2a-a80801b3328a-travel` | notifications/initialized | `d6da2479-096d-45e8-a1ee-f26d0b6ca91b` | `863005ff2694fe45` | 98 |
| 21:44:59.360 | `2dd0024b-e94b-4762-bb2a-a80801b3328a-travel` | tools/list | `be32c5b7-cb4d-4199-8395-cf364adf44ca` | `ede1a3f769871b47` | 213 |
| 21:45:30.627 | `de563712-a523-44d6-826e-7226d49c3fef-profile` | initialize | `67fdfd1a-68d9-4e7b-85a3-6f1eb706bffd` | `b4d384ea3ea57870` | 82 |
| 21:45:30.711 | `de563712-a523-44d6-826e-7226d49c3fef-profile` | notifications/initialized | `468fa8d8-9d68-49e4-a563-458b34c2fba7` | `bdaaa8cbd5b5ca81` | 64 |
| 21:45:30.777 | `de563712-a523-44d6-826e-7226d49c3fef-profile` | tools/list | `22f1123a-4274-4813-8132-3c2c64cc3e58` | `c0dd1ffdf0928216` | 197 |
| 21:45:54.606 | `2266020c-510b-46b4-851b-a77515bb01f6-profile` | initialize | `c2538bdf-752f-4a08-b7dd-d142fbfa60ec` | `b4d384ea3ea57870` | 87 |
| 21:45:54.696 | `2266020c-510b-46b4-851b-a77515bb01f6-profile` | notifications/initialized | `5b9ce52c-af8c-4593-bd47-1ee23f67a796` | `bdaaa8cbd5b5ca81` | 82 |
| 21:45:54.779 | `2266020c-510b-46b4-851b-a77515bb01f6-profile` | tools/list | `8579ec3f-59ac-47ce-a51f-4db7bed3883f` | `c0dd1ffdf0928216` | 185 |
| 21:46:42.963 | `f67be432-6212-4e1e-89eb-0f340eb51c64-travel` | initialize | `0580930d-0f29-4ce6-b15b-e7ae88d3733a` | `bf024ff22d0e0d76` | 73 |
| 21:46:43.039 | `f67be432-6212-4e1e-89eb-0f340eb51c64-travel` | notifications/initialized | `d9a23784-ee49-4cbd-bfc4-f95988418f06` | `28db4616e3c3ad87` | 73 |
| 21:46:43.113 | `f67be432-6212-4e1e-89eb-0f340eb51c64-travel` | tools/list | `0a45ba31-060e-4f60-bac0-0edcc6fb145a` | `e84a014b67ec079b` | 217 |
| 21:47:56.217 | `65853153-1ba0-4078-afbb-5d6c1a4b81bb-profile` | initialize | `177688d7-6cea-4baf-a00f-c25d7c2d5de7` | `14f549490b242df4` | 107 |
| 21:47:56.328 | `65853153-1ba0-4078-afbb-5d6c1a4b81bb-profile` | notifications/initialized | `0719a01f-2924-402d-903b-c03a8fc8cf7b` | `615808a6ac9ecace` | 80 |
| 21:47:56.410 | `65853153-1ba0-4078-afbb-5d6c1a4b81bb-profile` | tools/list | `0c9dc281-3549-4893-b652-38a357d2c664` | `b543e23077326c98` | 183 |
| 21:48:18.397 | `10fd08e0-aef3-4847-b9a1-8cf583ee121e-profile` | initialize | `aec6c521-3ad8-42eb-8448-d7bdea9c2879` | `615808a6ac9ecace` | 96 |
| 21:48:18.497 | `10fd08e0-aef3-4847-b9a1-8cf583ee121e-profile` | notifications/initialized | `50c8ad39-bed6-43c0-89ae-d7737520226a` | `0eb2d1ae59e3ef52` | 31 |
| 21:48:18.530 | `10fd08e0-aef3-4847-b9a1-8cf583ee121e-profile` | tools/list | `fb7768b3-6708-481c-a788-2b60ca07620c` | `b543e23077326c98` | 192 |
| 21:49:07.746 | `f2e4ea22-8e9f-4a1a-9af4-5bf9da598f51-travel` | initialize | `3dda35a8-2b01-4fd3-8210-5ad53a86cc74` | `bf024ff22d0e0d76` | 99 |
| 21:49:07.849 | `f2e4ea22-8e9f-4a1a-9af4-5bf9da598f51-travel` | notifications/initialized | `9897e99c-7d6a-4e22-8059-941c7fe5a821` | `28db4616e3c3ad87` | 51 |
| 21:49:07.901 | `f2e4ea22-8e9f-4a1a-9af4-5bf9da598f51-travel` | tools/list | `4b417ff3-8b66-4d7a-bb49-2fcc9e0e6996` | `e84a014b67ec079b` | 200 |
| 21:49:37.851 | `1da4d530-bbd7-47c1-97a5-7f1678554b8b-profile` | initialize | `73084ed6-dc3e-4da8-9d41-552c34584fa5` | `b4d384ea3ea57870` | 75 |
| 21:49:37.930 | `1da4d530-bbd7-47c1-97a5-7f1678554b8b-profile` | notifications/initialized | `34e03f80-88dd-4c05-a970-f25a18df4ae3` | `bdaaa8cbd5b5ca81` | 85 |
| 21:49:38.016 | `1da4d530-bbd7-47c1-97a5-7f1678554b8b-profile` | tools/list | `06604147-fbaa-4859-87a9-9038c7a49a2d` | `c0dd1ffdf0928216` | 176 |
| 21:50:00.040 | `ee99f857-5e8d-4ae2-bcfa-e91b03b84046-profile` | initialize | `67714c3d-b715-4e63-aad6-8bcf66f8ce34` | `b4d384ea3ea57870` | 89 |
| 21:50:00.132 | `ee99f857-5e8d-4ae2-bcfa-e91b03b84046-profile` | notifications/initialized | `f25dd501-c11c-41c4-8900-f0145090f2f5` | `bdaaa8cbd5b5ca81` | 100 |
| 21:50:00.234 | `ee99f857-5e8d-4ae2-bcfa-e91b03b84046-profile` | tools/list | `f5ad1df9-e3e8-4722-8f74-31ae65c553d4` | `bb39c72267e62df9` | 190 |
| 21:50:57.948 | `809bc097-cc6f-4d4a-bc50-e59e72034ce4-travel` | initialize | `ea198a36-1c27-4174-bfc4-c0220cc3bedc` | `7bd8c71494a82a0b` | 50 |
| 21:50:58.001 | `809bc097-cc6f-4d4a-bc50-e59e72034ce4-travel` | notifications/initialized | `efb81934-e20f-4392-8700-772464a92e11` | `27fb4caed43ac80e` | 83 |
| 21:50:58.087 | `809bc097-cc6f-4d4a-bc50-e59e72034ce4-travel` | tools/list | `2f8148bc-112c-4ca0-99e1-9f3bbccf7fa2` | `06e328fb1748a07f` | 211 |
| 21:51:59.799 | `f86313e3-5c41-4056-887d-5016fc7e9004-profile` | initialize | `afb000da-916d-400b-b97c-5fb875035ba4` | `b4d384ea3ea57870` | 93 |
| 21:51:59.894 | `f86313e3-5c41-4056-887d-5016fc7e9004-profile` | notifications/initialized | `176c0751-42c5-49bf-b742-20a99e200d34` | `bdaaa8cbd5b5ca81` | 83 |
| 21:51:59.978 | `f86313e3-5c41-4056-887d-5016fc7e9004-profile` | tools/list | `f5b3bba6-0bdb-497e-8999-baf9c26ef404` | `c0dd1ffdf0928216` | 241 |
| 21:52:21.192 | `e4636a0d-537c-44f6-8682-08f73cbf201a-profile` | initialize | `ded05375-996a-4691-b8ee-4a8650dc28a8` | `b4d384ea3ea57870` | 99 |
| 21:52:21.294 | `e4636a0d-537c-44f6-8682-08f73cbf201a-profile` | notifications/initialized | `2cd8e17b-c3a6-40a3-a1de-efe24ca7b41f` | `bdaaa8cbd5b5ca81` | 70 |
| 21:52:21.366 | `e4636a0d-537c-44f6-8682-08f73cbf201a-profile` | tools/list | `c7cd9811-2662-43c7-a897-5d89c21674a8` | `c0dd1ffdf0928216` | 190 |
| 21:53:10.066 | `f63c8a61-a523-4a43-9e3b-580ecc6e3e2b-travel` | initialize | `1326bd50-1059-4533-a934-77b5dab03ada` | `8c99045c74064a14` | 82 |
| 21:53:10.151 | `f63c8a61-a523-4a43-9e3b-580ecc6e3e2b-travel` | notifications/initialized | `dc04d80e-d261-4c80-a44a-6bee6561f641` | `3e40e64b68a50531` | 30 |
| 21:53:10.183 | `f63c8a61-a523-4a43-9e3b-580ecc6e3e2b-travel` | tools/list | `ec0e3115-2e09-41fe-9eae-9cf347ec864d` | `215361eb1ac932c7` | 162 |

## Sub-agent model calls (time sink 3)

One Bedrock `ConverseStream` per sub-agent request, from the Strands `chat` spans.

| Time | Runtime session id | Trace id | Span id | Model | Input tokens | Output tokens | Time to first token ms | Call ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 21:42:22.814 | `d39c338a-8878-4041-b185-e869082f6f3e-profile` | `6ac2c8300137d8be22032585540dfb16` | `fb0fe9b4e676e1c2` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2017 | 38 | 861 | 1117 |
| 21:42:28.787 | `d39c338a-8878-4041-b185-e869082f6f3e-profile` | `6ac2c8442d3dd9193a74195413d17e78` | `29f50291bd467263` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2065 | 37 | 533 | 839 |
| 21:43:34.713 | `c86cb354-f355-46b0-99b5-8a87a4193008-profile` | `6ac2c87f7088be63566c77fb004822f5` | `51a726c5c3eb336d` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2013 | 30 | 596 | 774 |
| 21:44:04.884 | `df68ec68-12db-4345-9288-04a1f24aa81c-profile` | `6ac2c8953afbf1350fad1c313e3c48f1` | `7f7889416b1b6303` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2017 | 38 | 1257 | 1501 |
| 21:44:11.286 | `df68ec68-12db-4345-9288-04a1f24aa81c-profile` | `6ac2c8aa378898d0647fb15819958f41` | `e1334af58ab0d143` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2065 | 37 | 544 | 822 |
| 21:45:00.479 | `2dd0024b-e94b-4762-bb2a-a80801b3328a-travel` | `6ac2c8d05a8db9d9251602134ecff1e3` | `33e1d0565407a719` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2407 | 154 | 947 | 2133 |
| 21:45:08.124 | `2dd0024b-e94b-4762-bb2a-a80801b3328a-travel` | `6ac2c8e315c6b742334ece9220c47d82` | `4b65d48ffe71293f` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 4346 | 52 | 642 | 1439 |
| 21:45:37.102 | `de563712-a523-44d6-826e-7226d49c3fef-profile` | `6ac2c8f802dfd4457f1f2ae34e322608` | `4b2a013428f28e37` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2013 | 30 | 506 | 723 |
| 21:45:58.248 | `2266020c-510b-46b4-851b-a77515bb01f6-profile` | `6ac2c9105e2cabdd0aff8f44504e4068` | `d17c30272ec6a62f` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2017 | 38 | 559 | 785 |
| 21:46:03.687 | `2266020c-510b-46b4-851b-a77515bb01f6-profile` | `6ac2c91b4cd2f65e4051179b0cd251a5` | `245a88b10d2b6ae6` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2065 | 37 | 601 | 873 |
| 21:46:44.147 | `f67be432-6212-4e1e-89eb-0f340eb51c64-travel` | `6ac2c9401cf52200488eb58a572f4d18` | `28da2b9ea6b7b056` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2407 | 154 | 550 | 1756 |
| 21:46:51.340 | `f67be432-6212-4e1e-89eb-0f340eb51c64-travel` | `6ac2c94a61bb4e070d67964a13c03043` | `7562eb2451a6f3f9` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 4346 | 52 | 572 | 1442 |
| 21:48:00.299 | `65853153-1ba0-4078-afbb-5d6c1a4b81bb-profile` | `6ac2c98863d5ea456ff36ad60d3ec133` | `6975f5144cad9e58` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2013 | 31 | 488 | 741 |
| 21:48:22.258 | `10fd08e0-aef3-4847-b9a1-8cf583ee121e-profile` | `6ac2c99e71e100d222a40c0230be21b8` | `6975f5144cad9e58` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2017 | 38 | 514 | 735 |
| 21:48:28.028 | `10fd08e0-aef3-4847-b9a1-8cf583ee121e-profile` | `6ac2c9ab1d3abb6a78765b9026759bd7` | `60b9eb67ce5a0b95` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2065 | 39 | 569 | 953 |
| 21:49:08.850 | `f2e4ea22-8e9f-4a1a-9af4-5bf9da598f51-travel` | `6ac2c9d0698c1b68702ed6e00e809c79` | `28da2b9ea6b7b056` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2407 | 151 | 599 | 1822 |
| 21:49:15.900 | `f2e4ea22-8e9f-4a1a-9af4-5bf9da598f51-travel` | `6ac2c9da4052fd9a4907b4292570dca4` | `7562eb2451a6f3f9` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 4343 | 43 | 573 | 1206 |
| 21:49:42.241 | `1da4d530-bbd7-47c1-97a5-7f1678554b8b-profile` | `6ac2c9ef058b30f777e312626506a00e` | `5a03205451a726c5` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2013 | 30 | 490 | 708 |
| 21:50:03.736 | `ee99f857-5e8d-4ae2-bcfa-e91b03b84046-profile` | `6ac2ca040c770f171384bca24ab2788d` | `d17c30272ec6a62f` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2017 | 38 | 533 | 735 |
| 21:50:09.220 | `ee99f857-5e8d-4ae2-bcfa-e91b03b84046-profile` | `6ac2ca1041e6ac87779fab0a390d3411` | `245a88b10d2b6ae6` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2065 | 39 | 516 | 844 |
| 21:50:59.122 | `809bc097-cc6f-4d4a-bc50-e59e72034ce4-travel` | `6ac2ca3615dfa18074d3557e4fc34a23` | `158944f8e5ef14f9` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2407 | 153 | 966 | 2281 |
| 21:51:06.898 | `809bc097-cc6f-4d4a-bc50-e59e72034ce4-travel` | `6ac2ca49364fbbfc6cf37cf860aee7c2` | `d9fbb56e1a38670a` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 4345 | 43 | 544 | 1174 |
| 21:52:03.806 | `f86313e3-5c41-4056-887d-5016fc7e9004-profile` | `6ac2ca7c7665fc42025be3d30bab840d` | `d17c30272ec6a62f` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2013 | 30 | 531 | 731 |
| 21:52:24.945 | `e4636a0d-537c-44f6-8682-08f73cbf201a-profile` | `6ac2ca923c65a716459bf1466174b574` | `d17c30272ec6a62f` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2017 | 38 | 487 | 744 |
| 21:52:30.354 | `e4636a0d-537c-44f6-8682-08f73cbf201a-profile` | `6ac2ca9d71c61abe3a994adf5db392af` | `245a88b10d2b6ae6` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2065 | 37 | 635 | 898 |
| 21:53:11.055 | `f63c8a61-a523-4a43-9e3b-580ecc6e3e2b-travel` | `6ac2cac22eea48691f2d6c9128d4f2f0` | `e978ed6f289c060d` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2407 | 151 | 591 | 1819 |
| 21:53:18.218 | `f63c8a61-a523-4a43-9e3b-580ecc6e3e2b-travel` | `6ac2cacd4646bb8f10d2e3fd0a713a2a` | `e5e5dbe5fb724055` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 4343 | 53 | 594 | 1358 |

## Turns in the designer (routing, time sinks 3, 5, 6)

Each question as Connect and the designer saw it. Routing is the designer's `ModelStart` to
`ModelEnd`; "Connect in" is the click to the designer's `NluRequestReceived`.

| Click | Contact | Question | Flow | Designer correlation id | Designer message id | Page run id | Connect in ms | Routing ms | First words ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 21:42:07.498 | `d39c338a-8878-4041-b185-e869082f6f3e` | Change my address | ProfileFlow | `f7c621c5-696b-4917-93ec-b611b28bd118` | `e37f4b53-ec89-4634-a954-c4ffe1bec637` | `d0c65063-6057-4ec6-84d2-eddc228a50bc` | 593 | 568 | 16896 |
| 21:42:27.422 | `d39c338a-8878-4041-b185-e869082f6f3e` | And what is my emergency contact? | ProfileFlow | `20f74a96-37a6-4839-a1a8-8a5ba06a2fdb` | `60887551-3406-4ad0-b692-0c56d5d41c3e` | `e9e6e94d-3f2f-44f9-bf65-9ddac8dbb928` | 387 | 493 | 2569 |
| 21:43:22.412 | `c86cb354-f355-46b0-99b5-8a87a4193008` | Update my information | ClarifyFlow | `17d28f6e-ef12-454e-b930-97b30c1b01b9` | `0fc3537d-0cad-4571-a0f5-06f10961921e` | `609b4f26-1099-4327-a4c2-7754db178fa2` | 458 | 418 | 1284 |
| 21:43:26.736 | `c86cb354-f355-46b0-99b5-8a87a4193008` | my home address | ProfileFlow | `287cc5e2-c97a-4560-b186-d1f96606a8bb` | `948fef11-7988-4f66-b531-7ed46c0c2a37` | `d0d99e11-a8a9-44c3-97f6-0e16eaf87244` | 443 | 401 | 9172 |
| 21:43:48.525 | `df68ec68-12db-4345-9288-04a1f24aa81c` | Change my address | ProfileFlow | `eccbf57f-e85e-45e4-9cdc-dc11d7a17a78` | `adacf920-1473-4532-a744-c554b332f0e4` | `bb77caf1-56f1-44fe-bb6a-387bafc6683a` | 407 | 367 | 18285 |
| 21:44:09.839 | `df68ec68-12db-4345-9288-04a1f24aa81c` | And what is my emergency contact? | ProfileFlow | `54a66765-4f88-406a-8c23-cd908735a5ab` | `190dc9a2-ddd5-499b-8f65-05bcf7fffa47` | `ecc95ee9-7fe8-4a03-8e0c-690ec5de71ad` | 439 | 438 | 2605 |
| 21:44:25.100 | `9be583e6-2bbf-411a-8e73-4764c542ad63` | PTO policy | PolicyFlow | `152a6721-233a-4b09-9bb1-858e1a8585cf` | `be27cfb6-02ae-4f82-9cb4-082289019ad4` | `4100842b-a3b6-42d6-bc27-5c4927346029` | 467 | 394 | 3564 |
| 21:44:32.492 | `9be583e6-2bbf-411a-8e73-4764c542ad63` | Does unused PTO carry over? | PolicyFlow | `90fbbbd0-4966-4d3d-ae4f-970ef9d07eb0` | `24935abd-9a92-45d6-9e47-9b466590a285` | `639c15fa-efb1-4ba5-b9f2-fb295d671d48` | 384 |  | 1471 |
| 21:44:47.416 | `2dd0024b-e94b-4762-bb2a-a80801b3328a` | Buddy passes | TravelFlow | `054562a6-6feb-49c5-864a-f1c223437a47` | `63cf11b1-20f6-4d26-85da-bc8fa75e7853` | `669869a2-d072-496d-9044-9ac7d6978ea3` | 407 | 408 | 15642 |
| 21:45:06.093 | `2dd0024b-e94b-4762-bb2a-a80801b3328a` | Can my parents use them? | TravelFlow | `5a1c17b7-fff5-4152-83e5-1060c68e5e98` | `e6b44210-947e-4ae3-8d91-126061c2fc64` | `2413f8f0-7d69-4e49-b7b1-c1ecc1bfe494` | 345 | 491 | 3874 |
| 21:45:22.618 | `de563712-a523-44d6-826e-7226d49c3fef` | Update my information | ClarifyFlow | `4b1babdb-6295-4914-be84-525ee0345937` | `ce603fe0-cd60-41d2-aa04-2abef9ffdec2` | `7dabed00-a4db-41a3-aa33-4ca1eca5a3de` | 362 | 733 | 1364 |
| 21:45:27.016 | `de563712-a523-44d6-826e-7226d49c3fef` | my home address | ProfileFlow | `8f5c555a-9ce0-413b-834e-b476c331717b` | `909816c5-d772-46f5-999a-b0d6e2fd812a` | `cec8290d-12b5-46dc-ae18-02a129ff0ec8` | 416 | 446 | 11242 |
| 21:45:50.904 | `2266020c-510b-46b4-851b-a77515bb01f6` | Change my address | ProfileFlow | `2f02175b-ea51-46a2-8aa2-c9c91227b669` | `75dc2cb6-a5e4-418b-a58f-56b5b43d98ef` | `3d5eb2a1-1bba-4af8-842a-f7536af7abeb` | 464 | 551 | 8530 |
| 21:46:02.470 | `2266020c-510b-46b4-851b-a77515bb01f6` | And what is my emergency contact? | ProfileFlow | `bf620019-36eb-4c97-bb33-a7bfcf7fef7d` | `065fd7b1-0214-4d8e-b716-cf4f83e7fd16` | `85ccf585-d5d8-4f9e-b559-924bb5195a2c` | 355 | 371 | 2391 |
| 21:46:17.524 | `805255a6-fa48-4f68-804b-22e0578dd15d` | PTO policy | PolicyFlow | `f307c054-6c19-4240-9bab-29dfed08ec8f` | `34d36c3e-4051-4286-928c-93da4ba1b9b3` | `a1f72d75-67f9-4778-9d8f-8ee36bc63273` | 444 | 399 | 2961 |
| 21:46:24.330 | `805255a6-fa48-4f68-804b-22e0578dd15d` | Does unused PTO carry over? | PolicyFlow | `62724f12-c7cf-4882-9f12-f498eaa35332` | `c2cf3b64-452c-4b67-956f-85cd120a8349` | `f9f5b04b-d211-4fe5-8b4f-ea078e8bd5cb` | 312 |  | 1454 |
| 21:46:39.250 | `f67be432-6212-4e1e-89eb-0f340eb51c64` | Buddy passes | TravelFlow | `a134d76a-0a6f-472b-85e1-0416341a92ee` | `d53fd684-46cf-4a14-9fdf-3e6549a3f6b0` | `fba1a7ec-13ca-4e24-a67e-fafce65245a3` | 495 | 382 | 6977 |
| 21:46:49.244 | `f67be432-6212-4e1e-89eb-0f340eb51c64` | Can my parents use them? | TravelFlow | `5dca7722-a4c6-478c-8a0d-b4e036fcad4f` | `19637029-0627-42b1-9708-e7e331af6a38` | `6dd624b0-9725-4a7a-bf56-ecbf75517f2a` | 494 | 391 | 3803 |
| 21:47:05.676 | `aba8d26a-04a5-4761-a92d-55b4ee092c2a` | When was my last paycheck and how much was it? | PayFlow | `66a98aaa-ec1f-4627-a056-2f2f43700c21` | `3b573e46-d7d3-4670-abfb-4608611acd3f` | `9f6fbf87-ec56-4bd3-9341-0333fc97f57d` | 511 | 564 | 20712 |
| 21:47:29.427 | `aba8d26a-04a5-4761-a92d-55b4ee092c2a` | And the one before that? | PayFlow | `cc9b060a-fdb1-4243-992d-df94900f0681` | `a0bced2a-22d0-403d-9a30-054b32675550` | `cb0d393c-7316-4fc3-8648-215e36f6eff3` | 376 | 463 | 2396 |
| 21:47:44.463 | `65853153-1ba0-4078-afbb-5d6c1a4b81bb` | Update my information | ClarifyFlow | `a25f09ee-61fd-41a6-b94f-6b82fe7b6040` | `df81a594-bd47-4cac-acd3-345131de1e50` | `68f5a0ce-0153-4da4-960f-56d4debd5935` | 438 | 429 | 1158 |
| 21:47:48.645 | `65853153-1ba0-4078-afbb-5d6c1a4b81bb` | my home address | ProfileFlow | `30bf69e2-a27b-45af-8645-0e146c670001` | `0b3de839-17e5-4f59-8f92-790ad652407e` | `4866d11b-7487-4d65-ade4-9afe155e5ec0` | 429 | 3332 | 12755 |
| 21:48:13.997 | `10fd08e0-aef3-4847-b9a1-8cf583ee121e` | Change my address | ProfileFlow | `7ff7079d-29e4-4a59-b6b9-eff0cb6ba445` | `8f529aa9-724c-492a-b176-ab196c112738` | `3ff704a3-b85d-470c-8a2b-5f53bcc670dc` | 343 | 498 | 9379 |
| 21:48:26.397 | `10fd08e0-aef3-4847-b9a1-8cf583ee121e` | And what is my emergency contact? | ProfileFlow | `796c509a-91cf-475e-b5a5-2237eeb44249` | `164d2350-d95d-4f47-be3d-c94d0effa148` | `056f2a4e-934d-4869-aeb1-2a5760bfda60` | 335 | 814 | 2878 |
| 21:48:41.857 | `5047517e-5a34-463d-9908-5a6ed2706167` | PTO policy | PolicyFlow | `06fbffa1-65d3-4256-af00-896576753474` | `95b723d2-f9f7-4895-a242-f32d579ca42d` | `1365c4b1-bcff-48b8-91f8-76916014a770` | 380 | 434 | 3510 |
| 21:48:49.196 | `5047517e-5a34-463d-9908-5a6ed2706167` | Does unused PTO carry over? | PolicyFlow | `797c496a-a1a2-48bd-a4c9-5699e5acd0c8` | `5f54a70d-46cf-4d91-a919-4b770d485694` | `8cd249e1-7b4c-4277-a98f-6d75fbea9228` | 275 |  | 1255 |
| 21:49:03.899 | `f2e4ea22-8e9f-4a1a-9af4-5bf9da598f51` | Buddy passes | TravelFlow | `145ea4d8-19d1-442b-a7b3-f0974204757f` | `58000766-024d-4d31-afd9-e9e04013db6f` | `6181602c-89a4-4b19-a0ad-b205c01d5933` | 337 | 636 | 7106 |
| 21:49:14.023 | `f2e4ea22-8e9f-4a1a-9af4-5bf9da598f51` | Can my parents use them? | TravelFlow | `b3970192-a390-430f-8a8c-6c500b7158ea` | `282e41e2-d01f-4821-a67b-646abe126ebc` | `9f83779b-6a30-4013-833e-0b33159a4ab8` | 365 | 335 | 3428 |
| 21:49:30.036 | `1da4d530-bbd7-47c1-97a5-7f1678554b8b` | Update my information | ClarifyFlow | `093fd600-fa5e-46c4-8c44-a95a5bbce153` | `ab06ec5f-320c-45ee-81e4-8ecafa5cf2f6` | `3e42a4bc-cc27-417a-a250-0a9e2b7ea89c` | 352 | 346 | 986 |
| 21:49:34.058 | `1da4d530-bbd7-47c1-97a5-7f1678554b8b` | my home address | ProfileFlow | `0b0661dd-3eec-466c-9764-b8b12f7e638e` | `2f39d1d0-0724-456a-9d58-15b50de16564` | `7c1f45c6-0a47-4fab-a0bf-ace873272d57` | 395 | 435 | 9253 |
| 21:49:55.969 | `ee99f857-5e8d-4ae2-bcfa-e91b03b84046` | Change my address | ProfileFlow | `eae81911-8111-4522-a394-e87b67ebf138` | `cc8eaf70-dbd4-4373-95af-bca5bae6a340` | `e1059ba2-e272-4224-9dfa-765229fc6246` | 376 | 424 | 8895 |
| 21:50:07.901 | `ee99f857-5e8d-4ae2-bcfa-e91b03b84046` | And what is my emergency contact? | ProfileFlow | `a006dbfa-96ff-48e3-b8e9-8ff85e1f06bf` | `5841d85e-b2d2-4c78-b5c1-f9a7d09fbef2` | `ba7960d7-6ad0-4020-9e9c-3b2fedcc3228` | 384 | 430 | 2464 |
| 21:50:22.992 | `053ec9d9-882a-45d2-9d95-539b5e8cf044` | PTO policy | PolicyFlow | `08cc677a-3182-4249-b602-8745ead57b61` | `55b24c4f-be45-4ad3-8665-6bc664baa445` | `5435e824-f1bb-4ba4-be82-7ee035fcfbc5` | 426 | 338 | 3245 |
| 21:50:30.061 | `053ec9d9-882a-45d2-9d95-539b5e8cf044` | Does unused PTO carry over? | PolicyFlow | `acb3cb48-939d-4717-890a-780cf5cbf354` | `29ec04da-3d71-4e6a-a251-5b636b413a4f` | `6a1249f6-d0d5-4d9c-a7b7-c8fb82e2618b` | 317 |  | 1610 |
| 21:50:45.119 | `809bc097-cc6f-4d4a-bc50-e59e72034ce4` | Buddy passes | TravelFlow | `daa83c01-c2e3-41a4-99ec-ee8c81d35461` | `ddb233d1-e5e3-4f06-b27b-f5ed910913bd` | `4f1dc820-230b-4029-8a56-61d0e7a55e1c` | 459 | 994 | 16636 |
| 21:51:04.791 | `809bc097-cc6f-4d4a-bc50-e59e72034ce4` | Can my parents use them? | TravelFlow | `41b5d074-14f0-45c9-9158-59cc287c4e6f` | `35172ed1-a91c-4168-9fd6-156aadb186d2` | `b03a95fd-3c35-4307-bb4a-022a31684b34` | 365 | 568 | 3730 |
| 21:51:21.150 | `96368ac5-71b0-4ff6-873f-b435823ab645` | When was my last paycheck and how much was it? | PayFlow | `115b67d6-f7a2-4c40-9b77-1cad0ddd7434` | `c9218783-91f8-4a2e-9e83-060915ef283d` | `54a5e90c-6c35-4773-9bdf-60f6c40200d5` | 523 | 337 | 12661 |
| 21:51:36.841 | `96368ac5-71b0-4ff6-873f-b435823ab645` | And the one before that? | PayFlow | `f34abe35-6bf7-4d0f-8a93-05419f7fc111` | `d6728659-6131-4828-bcea-2d3fab9700ba` | `55601391-4bd0-41e0-a11c-3cc93be19caf` | 436 | 394 | 2401 |
| 21:51:51.902 | `f86313e3-5c41-4056-887d-5016fc7e9004` | Update my information | ClarifyFlow | `8a3259d2-0106-4899-b3b7-29a7187c205c` | `b91adb27-2869-4b5b-b492-65eadd843c50` | `e6d03a24-7df6-4252-8698-11390ecf2a41` | 395 | 494 | 1176 |
| 21:51:56.114 | `f86313e3-5c41-4056-887d-5016fc7e9004` | my home address | ProfileFlow | `fc63271c-6f21-471c-86eb-651960990aa3` | `8b9e3d0e-5ded-4eb9-b254-a219a6b09435` | `84c7dfda-603b-410f-8b95-265cc6b4c540` | 269 | 472 | 8786 |
| 21:52:17.557 | `e4636a0d-537c-44f6-8682-08f73cbf201a` | Change my address | ProfileFlow | `eb8aad78-69df-4d0c-a201-43d4776c143a` | `c4c0bdc8-769f-4798-bdc4-e106dfe04276` | `e3cca36c-1131-4f8a-8e5a-d692c7bde2f2` | 342 | 403 | 8450 |
| 21:52:29.030 | `e4636a0d-537c-44f6-8682-08f73cbf201a` | And what is my emergency contact? | ProfileFlow | `36124db9-5c37-4110-b1a8-f9f2f1fa0f37` | `bdf95f5c-0243-49b4-8794-0d0223366ddd` | `58743024-6e66-477d-85f6-949faec3eac6` | 369 | 457 | 2520 |
| 21:52:44.168 | `7f166771-4d9d-4ad3-bfe4-3143b78467a5` | PTO policy | PolicyFlow | `f1d1fa1e-d819-4f35-9778-d26771571dd4` | `8f7bec5e-00d8-4107-a37e-360a6793c75a` | `0ef30a84-4919-4ad4-9f26-6b38c75026ec` | 341 | 388 | 2863 |
| 21:52:50.858 | `7f166771-4d9d-4ad3-bfe4-3143b78467a5` | Does unused PTO carry over? | PolicyFlow | `dbc98c5c-05f4-4719-bb74-d3b1adcb0dc3` | `5d9baafe-59e2-4adc-9361-73b057544f6a` | `7c02f7f9-9ad4-4dd8-8f3f-6f3b2673799d` | 353 |  | 1608 |
| 21:53:05.881 | `f63c8a61-a523-4a43-9e3b-580ecc6e3e2b` | Buddy passes | TravelFlow | `bfef78a5-93c5-42e9-b11c-4c961316ca1e` | `814cce11-8504-43a8-9a51-943d0303db98` | `f7638ebb-4717-4135-aae4-a19c06bc16c0` | 438 | 352 | 7318 |
| 21:53:16.232 | `f63c8a61-a523-4a43-9e3b-580ecc6e3e2b` | Can my parents use them? | TravelFlow | `956651a7-e5e1-4c00-929e-c6427461ef5e` | `48240f63-fbf2-4cd9-ab9c-fcef1eb59ec0` | `a3b79985-9275-43fd-9f71-b75e1eb0ea49` | 321 | 385 | 3748 |

### Data requests from the designer

Every data request with its gateway request. PolicySearch and Travel's search go to the knowledge base target through the tools gateway.

| Time | Contact | Request | Gateway | Target | Gateway request id | Trace id | ms |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 21:42:08.797 | `d39c338a-8878-4041-b185-e869082f6f3e` | DelegateProfile | agents | profile | `3571a4d9-9c12-4d43-971f-3d12fd248501` | `6ac2c8306373dfff67389fbb3f223e7c` | 15255 |
| 21:42:28.332 | `d39c338a-8878-4041-b185-e869082f6f3e` | DelegateProfile | agents | profile | `536d8f92-8d7e-45df-b76b-10b496f7b48c` | `6ac2c8441a31b83e7a5026ce42f6a893` | 1374 |
| 21:43:27.606 | `c86cb354-f355-46b0-99b5-8a87a4193008` | DelegateProfile | agents | profile | `f99b676c-30b1-47df-9489-408d85301d20` | `6ac2c87f5bdebc2d69fbd01407b41db8` | 7978 |
| 21:43:49.328 | `df68ec68-12db-4345-9288-04a1f24aa81c` | DelegateProfile | agents | profile | `99aae8a0-e7c8-4f01-a9f0-a55615e442e4` | `6ac2c8955d53fb9529d88bb34450a829` | 17140 |
| 21:44:10.749 | `df68ec68-12db-4345-9288-04a1f24aa81c` | DelegateProfile | agents | profile | `6db63974-12ce-4c4f-ac78-55393ac4ec15` | `6ac2c8aa44e40862305f14853c7086b5` | 1440 |
| 21:44:26.049 | `9be583e6-2bbf-411a-8e73-4764c542ad63` | PolicySearch | tools | docs | `a9eab2b1-86ad-4195-83c7-6787b15e3ba3` | `6ac2c8ba6c964709402fc59a5f9f25ae` | 822 |
| 21:44:48.325 | `2dd0024b-e94b-4762-bb2a-a80801b3328a` | DelegateTravel | agents | travel | `a647c00d-2a09-415e-b198-0e9b0b89d54e` | `6ac2c8d04b3a264818ee50d57f73fff6` | 14424 |
| 21:44:59.576 | `2dd0024b-e94b-4762-bb2a-a80801b3328a` | travel sub-agent search | tools | docs | `071d3c2c-96eb-4694-aa17-734b29e4383f` | `6ac2c8d05a8db9d9251602134ecff1e3` | 743 |
| 21:45:06.955 | `2dd0024b-e94b-4762-bb2a-a80801b3328a` | DelegateTravel | agents | travel | `bdae61c6-cf4c-4dc5-9f33-f505b0b60454` | `6ac2c8e259fb36e80f5486b00aba4fa3` | 2728 |
| 21:45:07.350 | `2dd0024b-e94b-4762-bb2a-a80801b3328a` | travel sub-agent search | tools | docs | `81b9c92f-6b86-4c90-a897-64e458e8fc55` | `6ac2c8e315c6b742334ece9220c47d82` | 704 |
| 21:45:27.903 | `de563712-a523-44d6-826e-7226d49c3fef` | DelegateProfile | agents | profile | `11088f72-1683-4225-94c1-b78abeae01d9` | `6ac2c8f73b0c10d959f0d77778c181c9` | 10007 |
| 21:45:51.949 | `2266020c-510b-46b4-851b-a77515bb01f6` | DelegateProfile | agents | profile | `b6dad121-b658-46c3-9d51-9beca2a01200` | `6ac2c90f624fee1d503f4b150ff7e49a` | 7183 |
| 21:46:03.223 | `2266020c-510b-46b4-851b-a77515bb01f6` | DelegateProfile | agents | profile | `9e057492-4e41-4c6a-b2e9-862d8fa49179` | `6ac2c91b1976c756752016302975a55b` | 1415 |
| 21:46:18.394 | `805255a6-fa48-4f68-804b-22e0578dd15d` | PolicySearch | tools | docs | `851c0c6f-16d5-4e38-b432-e5c1b604e3f6` | `6ac2c92a6e10f8451eb9e08e1f8e2f35` | 728 |
| 21:46:40.155 | `f67be432-6212-4e1e-89eb-0f340eb51c64` | DelegateTravel | agents | travel | `df1040ba-616a-4c57-a796-a77d6e6bd8ca` | `6ac2c9405a48384d340daa6738f47014` | 5859 |
| 21:46:43.333 | `f67be432-6212-4e1e-89eb-0f340eb51c64` | travel sub-agent search | tools | docs | `3fa31823-1477-403f-a675-d3d395479324` | `6ac2c9401cf52200488eb58a572f4d18` | 751 |
| 21:46:50.153 | `f67be432-6212-4e1e-89eb-0f340eb51c64` | DelegateTravel | agents | travel | `95558667-f0dd-401c-bc57-d7de766991f4` | `6ac2c94a32e24bc639892985049b30a0` | 2716 |
| 21:46:50.601 | `f67be432-6212-4e1e-89eb-0f340eb51c64` | travel sub-agent search | tools | docs | `5eebe008-55d6-4729-a1a6-f584ffdfc450` | `6ac2c94a61bb4e070d67964a13c03043` | 668 |
| 21:47:06.823 | `aba8d26a-04a5-4761-a92d-55b4ee092c2a` | DelegatePay | agents | pay | `ff389f0c-c01e-4966-bf42-83c14360cbb2` | `6ac2c95a777ae5200b38a2ec03978abd` | 19344 |
| 21:47:30.345 | `aba8d26a-04a5-4761-a92d-55b4ee092c2a` | DelegatePay | agents | pay | `42f75d45-8cba-44e4-bba3-a8ef5dcc1165` | `6ac2c9726dc8406957aab0942fcda1f5` | 1291 |
| 21:47:52.525 | `65853153-1ba0-4078-afbb-5d6c1a4b81bb` | DelegateProfile | agents | profile | `c107b470-82a7-464d-9349-812df24b803a` | `6ac2c98830180fec6263c8686992707b` | 8599 |
| 21:48:14.866 | `10fd08e0-aef3-4847-b9a1-8cf583ee121e` | DelegateProfile | agents | profile | `e32cbe6a-5395-482c-b531-36e68da0d839` | `6ac2c99e4edf431e429c27d40ee33a84` | 8268 |
| 21:48:27.569 | `10fd08e0-aef3-4847-b9a1-8cf583ee121e` | DelegateProfile | agents | profile | `52fdaea1-ffe9-472a-a746-3c0c56218793` | `6ac2c9ab77d8fec46a5fc8486c332665` | 1487 |
| 21:48:42.697 | `5047517e-5a34-463d-9908-5a6ed2706167` | PolicySearch | tools | docs | `a36a8f8b-3f1e-4a84-b51a-370d7dad5973` | `6ac2c9ba70b270201f5db9b873824b2d` | 861 |
| 21:49:04.902 | `f2e4ea22-8e9f-4a1a-9af4-5bf9da598f51` | DelegateTravel | agents | travel | `6f2ffe7b-045e-4009-9eed-aed68fbf8b79` | `6ac2c9d0553e9aeb410d12932a85be84` | 5880 |
| 21:49:08.103 | `f2e4ea22-8e9f-4a1a-9af4-5bf9da598f51` | travel sub-agent search | tools | docs | `8e5ba8f7-11c4-4d4f-a213-a4fe20a67224` | `6ac2c9d0698c1b68702ed6e00e809c79` | 679 |
| 21:49:14.742 | `f2e4ea22-8e9f-4a1a-9af4-5bf9da598f51` | DelegateTravel | agents | travel | `279474a4-436c-4c31-8b5f-6552260f045a` | `6ac2c9da018b11602cefb1357e805ead` | 2451 |
| 21:49:15.102 | `f2e4ea22-8e9f-4a1a-9af4-5bf9da598f51` | travel sub-agent search | tools | docs | `7040bddf-8ec8-4131-a5c0-849a5294f01d` | `6ac2c9da4052fd9a4907b4292570dca4` | 726 |
| 21:49:34.919 | `1da4d530-bbd7-47c1-97a5-7f1678554b8b` | DelegateProfile | agents | profile | `c6b509dc-569d-4cfb-96a5-1d4201207e17` | `6ac2c9ee4b80c46776e37a096280bf44` | 8186 |
| 21:49:56.798 | `ee99f857-5e8d-4ae2-bcfa-e91b03b84046` | DelegateProfile | agents | profile | `9cc40b38-7708-4e92-9ad8-7cc6216d00da` | `6ac2ca0436814ce21ab1824c0f295c7c` | 7799 |
| 21:50:08.743 | `ee99f857-5e8d-4ae2-bcfa-e91b03b84046` | DelegateProfile | agents | profile | `91bc5116-af0b-4c92-b227-4e8cd3fa1741` | `6ac2ca10608a44225978ec13152f0bdf` | 1402 |
| 21:50:23.894 | `053ec9d9-882a-45d2-9d95-539b5e8cf044` | PolicySearch | tools | docs | `5156b607-df92-42ed-8ae6-a3490133f494` | `6ac2ca1f71caabaf1643ea1e291d10fa` | 821 |
| 21:50:46.673 | `809bc097-cc6f-4d4a-bc50-e59e72034ce4` | DelegateTravel | agents | travel | `047f08e0-fcd6-4829-8262-01b69fa6e623` | `6ac2ca364035263602b2cc222f848dd4` | 14821 |
| 21:50:58.302 | `809bc097-cc6f-4d4a-bc50-e59e72034ce4` | travel sub-agent search | tools | docs | `4f898f4f-e780-464c-867c-a39402ecd4e6` | `6ac2ca3615dfa18074d3557e4fc34a23` | 656 |
| 21:51:05.743 | `809bc097-cc6f-4d4a-bc50-e59e72034ce4` | DelegateTravel | agents | travel | `89cff0d5-ef98-4619-a4ff-5557877b4eb1` | `6ac2ca494dbaacc02a268f66496ba433` | 2472 |
| 21:51:06.131 | `809bc097-cc6f-4d4a-bc50-e59e72034ce4` | travel sub-agent search | tools | docs | `4690585d-b990-4582-b6c2-1b67706a0927` | `6ac2ca49364fbbfc6cf37cf860aee7c2` | 674 |
| 21:51:22.036 | `96368ac5-71b0-4ff6-873f-b435823ab645` | DelegatePay | agents | pay | `bf0e4786-2373-4e0a-84cc-4b68710cee94` | `6ac2ca5a16949b4613f19a912d4f9414` | 11495 |
| 21:51:37.694 | `96368ac5-71b0-4ff6-873f-b435823ab645` | DelegatePay | agents | pay | `6a8cb3a9-d40f-4399-9150-07d7265a680f` | `6ac2ca691543408a06f8d52c4fdf6b69` | 1250 |
| 21:51:56.889 | `f86313e3-5c41-4056-887d-5016fc7e9004` | DelegateProfile | agents | profile | `62c4d1a9-d027-4af1-8349-75451619156d` | `6ac2ca7c3c451a0104ae862b791ce958` | 7749 |
| 21:52:18.332 | `e4636a0d-537c-44f6-8682-08f73cbf201a` | DelegateProfile | agents | profile | `7f3d11e2-cfa6-4b5d-93d4-134f216a26fb` | `6ac2ca9220a7f82e0ddb5af521b08aa4` | 7462 |
| 21:52:29.881 | `e4636a0d-537c-44f6-8682-08f73cbf201a` | DelegateProfile | agents | profile | `b12706b1-7872-425f-a69d-e5ba72873d38` | `6ac2ca9d76a056441158f15d5ecb7308` | 1483 |
| 21:52:45.002 | `7f166771-4d9d-4ad3-bfe4-3143b78467a5` | PolicySearch | tools | docs | `ae1e185c-7385-4371-85f2-8ca480bb5a23` | `6ac2caad6c849ca2533a4ebd07ac6c5f` | 761 |
| 21:53:06.694 | `f63c8a61-a523-4a43-9e3b-580ecc6e3e2b` | DelegateTravel | agents | travel | `fe612637-88f6-4200-9d3c-62568b24ce27` | `6ac2cac203112c1a101ea0236a033ce2` | 6286 |
| 21:53:10.350 | `f63c8a61-a523-4a43-9e3b-580ecc6e3e2b` | travel sub-agent search | tools | docs | `10c2f6ce-d2d7-4c87-a721-59e0c4503a07` | `6ac2cac22eea48691f2d6c9128d4f2f0` | 623 |
| 21:53:16.958 | `f63c8a61-a523-4a43-9e3b-580ecc6e3e2b` | DelegateTravel | agents | travel | `2a819ce7-a8d1-4cea-bedf-a222221dff7c` | `6ac2cacc2346e97d3076d39d2a170b8b` | 2779 |
| 21:53:17.368 | `f63c8a61-a523-4a43-9e3b-580ecc6e3e2b` | travel sub-agent search | tools | docs | `6f2b53cd-b332-4be3-827c-497163756a46` | `6ac2cacd4646bb8f10d2e3fd0a713a2a` | 753 |

## Chat starts (time sink 9, question 6)

One per page load. The greeting columns are the designer's WelcomeFlow; the function's own steps
and the four hop token exchanges of each start are in the JSON file.

| Navigation | Contact | API Gateway request id | Lambda request id | X-Ray trace | Lambda log stream | Instance | Function ms | Browser ms | Greeting correlation id | Designer greeted |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 21:41:56.174 | `d39c338a-8878-4041-b185-e869082f6f3e` | `cd9f630e-8706-44ee-b8cb-b1a32496c88b` | `3fa63e71-b120-4d5a-a96a-133d233badd7` | `1-6ac2c825-7c4665897c94ad933e4ba12f` | `6c07a65861c54f49b9f89b38d62e8adc` | cold | 2895 | 3340 | `26514e3a-6a5e-4b26-ac0b-a5b9c729794a` | 21:42:00.021 |
| 21:43:11.191 | `c86cb354-f355-46b0-99b5-8a87a4193008` | `bb3fdc91-4193-4047-b597-aebf032828ed` | `59a09a15-9920-4f26-a3dd-09dc019f753f` | `1-6ac2c870-6955e56c3db0fd8d5533c023` | `567f545627b4448eb16e38dcd14ce1e4` | cold | 2593 | 3093 | `f6bf69b0-549d-4c2d-9c52-23ac94820ccf` | 21:43:14.829 |
| 21:43:37.479 | `df68ec68-12db-4345-9288-04a1f24aa81c` | `dfe2f792-a351-4692-b6db-3fa0580f3cf4` | `97fc7fb2-cc1c-4883-b4e1-efc6b3710348` | `1-6ac2c88a-22c0a6564668848a7ecccc48` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2362 | 2492 | `8e8d4389-7c0f-431d-9275-be5aacc83a0f` | 21:43:40.076 |
| 21:44:14.041 | `9be583e6-2bbf-411a-8e73-4764c542ad63` | `b9bfe42d-fb46-47fa-87fd-530009f4d121` | `b74ab135-0a0c-41f9-aae8-1326a56544a9` | `1-6ac2c8ae-0335cb6607bedcb2540d809d` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2415 | 2517 | `fa1452cb-2011-4ba4-99e3-16e453d910c2` | 21:44:16.788 |
| 21:44:36.352 | `2dd0024b-e94b-4762-bb2a-a80801b3328a` | `de164e00-bf09-447e-9cd7-053e09e202b6` | `7c5c78cd-964e-4246-a655-ba28f4090ead` | `1-6ac2c8c5-613ae74421c929e40a7cb716` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2375 | 2462 | `f8216a79-db9a-4bdd-ace7-a8f2427abb92` | 21:44:39.008 |
| 21:45:11.560 | `de563712-a523-44d6-826e-7226d49c3fef` | `388d0150-6f54-41be-b70f-648f3d96ce46` | `6814aaf1-a8d4-4054-8a2c-be7a724e7007` | `1-6ac2c8e8-74cac449256a29392780eea7` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2410 | 2463 | `22d09f20-2422-47f8-b9cf-769a4bf13c07` | 21:45:14.325 |
| 21:45:39.836 | `2266020c-510b-46b4-851b-a77515bb01f6` | `b1fdb719-c1c6-4346-87fb-9ec97eedfc3a` | `45a7b749-ccf7-493a-b0f9-e1adfa339920` | `1-6ac2c904-4c6f3920563b4ef90f07d8c1` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2370 | 2420 | `e255a3de-0bff-4b78-bf08-e33d37814e33` | 21:45:42.518 |
| 21:46:06.447 | `805255a6-fa48-4f68-804b-22e0578dd15d` | `4d2b07e9-c558-437a-a34c-46369ea30f44` | `0729680b-21f6-4a6e-9a7c-4f5826e9bcd8` | `1-6ac2c91f-7df0a7152156862518a17335` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2225 | 2280 | `ba4f75ed-8919-4d39-825a-cca54d945bbd` | 21:46:08.940 |
| 21:46:28.178 | `f67be432-6212-4e1e-89eb-0f340eb51c64` | `16ca05c8-23ce-4b65-8299-32a46a3a9b6d` | `009524dd-ac1d-4720-9a14-0f0f21ed3feb` | `1-6ac2c935-290a060a6502e3bd679ed8a7` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2268 | 2326 | `4fd00ffd-3b4d-4f97-bb0c-0211b56b9793` | 21:46:30.722 |
| 21:46:54.626 | `aba8d26a-04a5-4761-a92d-55b4ee092c2a` | `5bd7a513-d906-4d37-aafb-d768f6d1118f` | `6954732e-fb39-4d0f-b037-a79ea2ca71b2` | `1-6ac2c94f-0d08cc6625c01e33040c589e` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2236 | 2321 | `b7d48939-d5ac-40e2-98a2-b2fa21e84fda` | 21:46:57.070 |
| 21:47:33.402 | `65853153-1ba0-4078-afbb-5d6c1a4b81bb` | `1f03e3fb-f1fe-4bab-a233-efb89826616d` | `8d35fd52-ffbc-439a-8fd6-661b1d5bf10b` | `1-6ac2c976-4030357d51b279146d703bfb` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2334 | 2429 | `9d5c696d-681f-4e74-8e7e-783431a5963c` | 21:47:35.849 |
| 21:48:02.967 | `10fd08e0-aef3-4847-b9a1-8cf583ee121e` | `7cf2a025-1da5-4098-9685-75f9b7e77a9d` | `8182d167-38d0-41a7-8096-3fa48ef2e7c0` | `1-6ac2c993-2bb39a103c2f06375410e619` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2352 | 2436 | `12fd28fc-c0a5-4bf6-9d8d-d7a70b09cb96` | 21:48:05.560 |
| 21:48:30.820 | `5047517e-5a34-463d-9908-5a6ed2706167` | `22144ae8-078e-4083-84ce-fc2539872bd2` | `c52971f9-fc66-4348-889f-197028dd3650` | `1-6ac2c9af-43e02357395b0c7e3bfde5b7` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2103 | 2170 | `b5444ddb-287d-4283-9f7c-e74979efd82b` | 21:48:33.255 |
| 21:48:52.840 | `f2e4ea22-8e9f-4a1a-9af4-5bf9da598f51` | `3425463f-5149-49c6-b0d6-8fc627bfb336` | `02981d4c-4ba5-45c1-be0f-7b0924121410` | `1-6ac2c9c5-034942f230f1aee845ea0a99` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2255 | 2341 | `f29513f1-ca12-4952-bed9-1ec14eb083a3` | 21:48:55.392 |
| 21:49:19.000 | `1da4d530-bbd7-47c1-97a5-7f1678554b8b` | `8fc5b04e-85f7-4378-8664-7e54853210f0` | `1cab1cf9-00dd-4aa8-a8f8-e9227c8b8ffb` | `1-6ac2c9df-5d1c6a4573771aca650e3800` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2064 | 2126 | `5b214184-db8d-467c-9536-c3e5f8ee0b9c` | 21:49:21.341 |
| 21:49:44.903 | `ee99f857-5e8d-4ae2-bcfa-e91b03b84046` | `3dcefef8-b5f1-490c-8d19-6c455bad4953` | `0fad4b52-50b8-4aea-8a74-4f6232433fe2` | `1-6ac2c9f9-72e3217f40bf3b5f6e65f7bf` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2002 | 2051 | `de4c5dd4-890a-42c3-9969-308187bcb526` | 21:49:47.180 |
| 21:50:11.951 | `053ec9d9-882a-45d2-9d95-539b5e8cf044` | `6d09235c-5f57-4518-9653-d457af107666` | `fc0233c2-e60d-4d23-9f97-c802a5c25b87` | `1-6ac2ca14-010278742bfb14755fa5ccb2` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 1979 | 2026 | `baa2b608-dae7-498b-99ea-71a4dd76489f` | 21:50:14.210 |
| 21:50:34.047 | `809bc097-cc6f-4d4a-bc50-e59e72034ce4` | `91b05c3e-1c3f-45c0-9ebf-7c5d27c54032` | `f1c11a16-9f90-4446-8b93-c17fdd0bc2ee` | `1-6ac2ca2a-3b4fdf9a6334dd086679abc7` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2056 | 2161 | `5625e819-f170-46e2-bbde-07a6e613956a` | 21:50:36.249 |
| 21:51:10.111 | `96368ac5-71b0-4ff6-873f-b435823ab645` | `e87eea0d-62be-4306-a721-a5a4daba8f7f` | `4910568e-535c-4fa2-9725-ef1f98aa27c7` | `1-6ac2ca4e-13099e4a2b7437be0efb45a4` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2048 | 2139 | `66ca9256-9022-4f6a-89cf-8739eb2fdb45` | 21:51:12.515 |
| 21:51:40.814 | `f86313e3-5c41-4056-887d-5016fc7e9004` | `317cd7d9-0bf0-4bc6-80d8-402b00a1e19f` | `ee2ebe2a-bdf1-4570-aa6a-da00986b3f58` | `1-6ac2ca6d-281a82ac3a8614bc434ca2c2` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2028 | 2090 | `dc5c9e52-20b9-4c13-b0ed-bebbe9971c54` | 21:51:42.994 |
| 21:52:06.496 | `e4636a0d-537c-44f6-8682-08f73cbf201a` | `60674916-b5b7-41d8-8b0b-2a0b93ebd6a6` | `0305271b-5c96-44ea-b975-4d2cdae5db30` | `1-6ac2ca87-67f8dd6858ccce2e4309ce08` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2433 | 2514 | `4449b6c2-7acb-4b8d-92fd-6f0c796466cf` | 21:52:09.246 |
| 21:52:33.118 | `7f166771-4d9d-4ad3-bfe4-3143b78467a5` | `ce6ea2fc-5a83-4e87-8f8d-65896067245c` | `cc0c0339-3946-41ca-85e9-51662e9c6c61` | `1-6ac2caa1-4dc536763a98fc0f3665927c` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2174 | 2271 | `3605c0c0-cee0-49fa-8baf-56db224fb20c` | 21:52:35.622 |
| 21:52:54.825 | `f63c8a61-a523-4a43-9e3b-580ecc6e3e2b` | `ebbff32c-963a-4518-a862-dda2f2c466c5` | `4b54d713-9e9c-4dda-abd1-d297230db856` | `1-6ac2cab7-57338a066ffd188533ec6dea` | `567f545627b4448eb16e38dcd14ce1e4` | warm | 2247 | 2390 | `1647c037-1b69-4ed1-968d-c5defa081281` | 21:52:57.427 |

### Hop token exchanges at chat start

The four on-behalf-of exchanges of each start, at the issuer (credential provider `guppi-obo-hr-bridge`).

| Time | Contact | Audience | Issuer API Gateway request id | Issuer Lambda request id | X-Ray trace | Handler ms | Instance |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 21:41:58.088 | `d39c338a` | api://hr-agents/profile | `737dc4cc-2c78-40ab-9e28-c2cbca007af6` | `85f50566-142f-46e9-9da9-30446b3d4ab9` | `1-6ac2c826-6fe74d85771ebc8b31f4b946` | 20.64 |  |
| 21:41:58.092 | `d39c338a` | api://hr-agents/travel | `65eb6c2e-1027-44b4-a0b7-d062212a9df5` | `c5f91013-aeac-43a8-91fe-467ef7347cde` | `1-6ac2c826-1ca00a9b613cb29b4c947eb5` | 21.6 | cold |
| 21:41:58.113 | `d39c338a` | api://hr-agents/pay | `445b8f51-4540-4d6c-9f8e-e6d695717ddf` | `0acf2c3a-81fc-4984-83ee-d46443dfdff0` | `1-6ac2c826-2ffc4c6f0a2a453f4cb32d48` | 8.27 |  |
| 21:41:58.118 | `d39c338a` | api://hr-tools | `d076f0cd-8826-4783-9f47-3411ea4e8463` | `691f4b11-a982-484a-a7e6-fafce2bd5cb9` | `1-6ac2c826-78b261760a3991d011e2671b` | 7.56 |  |
| 21:43:13.069 | `c86cb354` | api://hr-agents/travel | `20656bd2-9a0e-4260-b406-520016d8ac2e` | `34a261a0-f71c-43cf-9883-e424f0143028` | `1-6ac2c871-69323efd6efcdb8466a33082` | 29.37 |  |
| 21:43:13.070 | `c86cb354` | api://hr-tools | `d92cdb44-670a-4e10-992c-3492bd9536e1` | `fd060dea-4b6d-437e-9d8f-5c14761b9998` | `1-6ac2c871-1c3298043b92d7ea12412dc1` | 22.84 |  |
| 21:43:13.086 | `c86cb354` | api://hr-agents/profile | `fd11857a-1460-4117-8c97-6dd144f1a9f9` | `37de49c1-0bf5-45fa-a2a5-f70d54ff5c23` | `1-6ac2c871-350e38db3e2bf81444c072d3` | 22.98 | cold |
| 21:43:13.095 | `c86cb354` | api://hr-agents/pay | `dc4b7f99-d9f5-40e2-a185-db3966ce66f8` | `7307d802-22d2-40d9-b6f4-9885271ccbc9` | `1-6ac2c871-4b7b28ee24f3520f15c7863d` | 27.02 | cold |
| 21:43:38.461 | `df68ec68` | api://hr-agents/travel | `ce180513-7b34-43e4-9ff7-5be7ffcbb415` | `09f95759-faf0-44b9-b8f0-c0e4dbf1c8aa` | `1-6ac2c88a-381b95df04d6803c36d6175b` | 22.12 |  |
| 21:43:38.467 | `df68ec68` | api://hr-agents/profile | `f6e0ded4-9695-49c4-a092-1ceedd46de3a` | `fe05dc59-a60c-4440-b9c2-7daa5b979fc3` | `1-6ac2c88a-42dc5f1d4837361e78844208` | 21.83 |  |
| 21:43:38.470 | `df68ec68` | api://hr-agents/pay | `6f4587dd-2945-40c6-b07c-1f114df90d56` | `115fb72a-c966-4a16-803c-da0967f1e547` | `1-6ac2c88a-1a9f53161c607e5866acc8c7` | 22.39 |  |
| 21:43:38.479 | `df68ec68` | api://hr-tools | `05db7561-5f1b-4959-91d5-2558932369d0` | `48820b7f-9b1f-4c0d-8c84-4c38cf3d14ac` | `1-6ac2c88a-6cf2b73d05716b9231a3ad2b` | 25.58 |  |
| 21:44:15.068 | `9be583e6` | api://hr-agents/travel | `b5e41ab6-2673-4135-a7f6-511d77bb2709` | `ddce9257-1183-4d18-b346-84e7ecdade24` | `1-6ac2c8af-34f6ae4f18d0891c1cd9ce93` | 21.27 |  |
| 21:44:15.077 | `9be583e6` | api://hr-tools | `a33bdaaf-79c6-4246-b4fc-b4652fc1d555` | `0feaaed9-0b1c-4abb-b733-233fcb97e25e` | `1-6ac2c8af-7505064e0ff6a89d57374c91` | 23.29 |  |
| 21:44:15.091 | `9be583e6` | api://hr-agents/profile | `c103880b-0bb1-4410-a293-4a2f983cf4a1` | `ba625d02-8a00-4f09-8ed5-37d17b34db60` | `1-6ac2c8af-7ccc39b61d6f4d5a1839422d` | 20.73 |  |
| 21:44:15.104 | `9be583e6` | api://hr-agents/pay | `8ae60529-dd69-4a09-a645-fe851c06cd91` | `3d0bd878-f498-4bb0-8109-baaf15a02cba` | `1-6ac2c8af-6c722bf30ae6a49c2bd88fcc` | 8.38 |  |
| 21:44:37.309 | `2dd0024b` | api://hr-agents/travel | `cfb0094f-5be3-410a-8534-0d26f8cb18d5` | `4c000afe-43a8-4017-8c4c-886076c7c977` | `1-6ac2c8c5-4f440ea851589bd91c1e09be` | 20.34 |  |
| 21:44:37.312 | `2dd0024b` | api://hr-agents/profile | `ba66b43a-a527-4f45-a3cc-240c45711d7f` | `67452b92-a62e-4ca7-97a1-edf36bafb34a` | `1-6ac2c8c5-3c3f150b5fa3654b5c462c64` | 20.16 |  |
| 21:44:37.334 | `2dd0024b` | api://hr-agents/pay | `ac084e35-3bc6-46b3-adf1-8fa967883999` | `413ba5b8-f8ab-495e-9a17-3cf38e716107` | `1-6ac2c8c5-5523e61a0687ed70071b7d46` | 18.78 |  |
| 21:44:37.335 | `2dd0024b` | api://hr-tools | `2c61b06c-f257-4c00-9e45-ed965a9a2639` | `65707960-1e79-4137-800e-79eb4ac86b3f` | `1-6ac2c8c5-1b7388b61fd04b1e5c9b8646` | 8.49 |  |
| 21:45:12.648 | `de563712` | api://hr-agents/travel | `077a1cb5-effe-49ed-a12e-f25d863654d1` | `89a72210-dd80-46f7-85d5-7a757c9ebf32` | `1-6ac2c8e8-09b45b48328c8ed9439858b5` | 22.23 |  |
| 21:45:12.651 | `de563712` | api://hr-agents/pay | `dcfe71e7-7cb1-4b4e-a029-39cc37d79ca6` | `0be80d5a-1973-4270-82a4-1480243f9c92` | `1-6ac2c8e8-2a2b99d7106952864accc8b1` | 22.79 |  |
| 21:45:12.658 | `de563712` | api://hr-agents/profile | `fc12b80d-f93f-48b0-9535-5535f0912ee2` | `58c002d3-24a8-4a73-8978-0209c0a7f57d` | `1-6ac2c8e8-7e5a6cf23840a22071d59594` | 24.17 |  |
| 21:45:12.695 | `de563712` | api://hr-tools | `a0dd4b7b-7f0c-47f7-98d0-b7cf02d1c9ce` | `a622ab69-80ce-4252-a977-5b8dd91fada7` | `1-6ac2c8e8-6a967cf912e3fc2b35e88b62` | 8.09 |  |
| 21:45:40.822 | `2266020c` | api://hr-agents/travel | `3ea8b7d3-c874-447c-8f61-cf25f44107ea` | `80210817-ec4a-4d0f-825e-b0ace3af04a7` | `1-6ac2c904-062d49f13ad1734d7a9ec78b` | 21.1 |  |
| 21:45:40.823 | `2266020c` | api://hr-tools | `30482bb8-cdd4-468d-b1d4-16a73f9cdc82` | `5a0fe43a-659f-4b88-8f4a-7560bd4499aa` | `1-6ac2c904-1f3506292ca9b5bc002a769c` | 19.96 |  |
| 21:45:40.829 | `2266020c` | api://hr-agents/pay | `b57c5ac1-9454-4011-ad3f-03569de81673` | `6da9de49-755d-41b1-bafb-e5bfd24d5871` | `1-6ac2c904-2cdcc8281de3559b53f496e8` | 23.86 |  |
| 21:45:40.839 | `2266020c` | api://hr-agents/profile | `74c26a58-84a5-4abe-b3ea-edb5d727a4d0` | `ddb4b4a2-e807-4773-b9ca-038b6a9ff610` | `1-6ac2c904-1225ae2246265e7b00d1c5e2` | 21.96 |  |
| 21:46:07.410 | `805255a6` | api://hr-tools | `b1b56cc5-7c4d-4a03-8977-4a308c0234a7` | `8d9ee601-a669-4b9d-b34d-0c17f822d92a` | `1-6ac2c91f-66b3b2665fd4756f30690efd` | 24.1 |  |
| 21:46:07.416 | `805255a6` | api://hr-agents/pay | `49eff8e3-7bc1-4c1c-95fb-1e2360868584` | `9b0ac10d-b991-4403-800d-862af9ff934f` | `1-6ac2c91f-26f4a3880b61ffc8262b9395` | 25.03 |  |
| 21:46:07.425 | `805255a6` | api://hr-agents/travel | `892d1e6a-c504-495e-a905-cf5dc75ea105` | `122328f3-0217-4f38-ab55-987f07ca7f39` | `1-6ac2c91f-184ab5ae1155140f67750ca1` | 22.78 |  |
| 21:46:07.435 | `805255a6` | api://hr-agents/profile | `daa99473-8089-485c-a6ea-ce5a5ce14402` | `1ff48f9c-c509-43f5-b9d5-8fa12dda2fed` | `1-6ac2c91f-2e3894d83c970f750b27618d` | 21.85 |  |
| 21:46:29.157 | `f67be432` | api://hr-tools | `1cf6e3cd-eadf-417d-a0e5-f0973da94044` | `4d663469-b001-4f5c-a347-4917049f11a4` | `1-6ac2c935-33e9efdd4457546638f38e60` | 21.21 |  |
| 21:46:29.178 | `f67be432` | api://hr-agents/travel | `531727b3-6c6b-4201-8160-aa7a24ae2bc6` | `796b37ed-a954-4d40-a7a3-0981629a1da9` | `1-6ac2c935-6cda21e1493e45f833a0e0cc` | 20.18 |  |
| 21:46:29.182 | `f67be432` | api://hr-agents/profile | `e91a1398-e9f7-40c2-accf-df57aa1e378b` | `2bca9fdd-0f3b-4f40-bfe3-4678617442b5` | `1-6ac2c935-0dcf97741488cffd4b7f6c63` | 20.81 |  |
| 21:46:29.184 | `f67be432` | api://hr-agents/pay | `090ef9a5-6c65-430d-9ccf-5a953256f2b5` | `b7a5834d-a3d9-408b-9810-16b9b47f1bdb` | `1-6ac2c935-1bc8d1290cb1fd44402e76e8` | 19.83 |  |
| 21:46:55.580 | `aba8d26a` | api://hr-agents/travel | `b609ab5e-484b-4423-807b-45c4abfc0d2f` | `67ca663e-d201-458a-990b-ac71bacfa310` | `1-6ac2c94f-3a49728a64036a927c17a546` | 19.67 |  |
| 21:46:55.584 | `aba8d26a` | api://hr-agents/pay | `be12df5d-7812-4776-b841-acd7d3cf90ee` | `eba697e5-862f-4ebd-b0f9-e288e57752f2` | `1-6ac2c94f-1ad11bf31d6c52c340121460` | 20.4 |  |
| 21:46:55.596 | `aba8d26a` | api://hr-agents/profile | `b59b728b-c362-4792-bb06-3c5e21f39032` | `4e033ef5-e929-48e3-a5bb-7ffc4094c41d` | `1-6ac2c94f-6dfeb6633f5ce56e1ef2b2b7` | 24.56 |  |
| 21:46:55.599 | `aba8d26a` | api://hr-tools | `b65c4e67-9bbc-4e13-b1a7-cc984b5b716d` | `0523ae8a-1c04-463d-a419-456569af18cc` | `1-6ac2c94f-7371bea94de308271968c32a` | 23.42 |  |
| 21:47:34.358 | `65853153` | api://hr-agents/profile | `3ddba053-0c3d-46fb-ab6d-93d7343426aa` | `2de1fd84-56b9-400b-9b40-22a892675e8c` | `1-6ac2c976-71307ddc714092e95f33f99e` | 23.09 |  |
| 21:47:34.371 | `65853153` | api://hr-tools | `af10dd25-6c0c-4195-8602-537fe3896622` | `afe854e0-e893-4a7d-8604-6b6378e3c239` | `1-6ac2c976-1348fb7a7eb1cf4d0bffe215` | 23.52 |  |
| 21:47:34.372 | `65853153` | api://hr-agents/pay | `10ff3c2b-1215-4bc5-a9c6-353cc42ac2fe` | `2e7d505f-2bab-4721-89d2-2e8f34073e9a` | `1-6ac2c976-56bd969b27854b786970b586` | 20.2 |  |
| 21:47:34.383 | `65853153` | api://hr-agents/travel | `0b7d7e0b-8bb5-4554-93da-905ff12dc309` | `da29ca15-b64a-40a4-b0ed-3769d9761ab4` | `1-6ac2c976-5bd810842b1ba8e73705b643` | 22.23 |  |
| 21:48:03.943 | `10fd08e0` | api://hr-agents/profile | `4ee88c99-06a4-4f30-b992-eb08b8f933c4` | `ee2da64e-c063-46c3-96b2-65f3cdb7609c` | `1-6ac2c993-13f1dec44b29ddfb482d122c` | 19.49 |  |
| 21:48:03.952 | `10fd08e0` | api://hr-agents/travel | `174ae221-b99b-4382-b891-d82f52eea3f2` | `176c1faa-e755-403e-88d5-47eddcce309d` | `1-6ac2c993-00f8461557b3cd483e797c07` | 22.01 |  |
| 21:48:03.959 | `10fd08e0` | api://hr-agents/pay | `03fad363-5d80-4125-b7bc-90943de4ee84` | `af23d2db-21df-4973-beeb-1fa297ddcc55` | `1-6ac2c993-6771c4b85ccd15c37b6fd861` | 23.35 |  |
| 21:48:03.969 | `10fd08e0` | api://hr-tools | `dc043f34-4af0-443f-ad52-d1123fe47286` | `52129f90-c078-42fe-a71f-4103aadb9299` | `1-6ac2c993-301ad0b120e9c58e091e32f3` | 7.9 |  |
| 21:48:31.781 | `5047517e` | api://hr-agents/profile | `0ed401af-b1dd-48c2-aa79-ef9cf59c189a` | `50684378-5f4c-4d3c-9ab6-ad64df27c5f5` | `1-6ac2c9af-437362fa1267445765cc8474` | 18.98 |  |
| 21:48:31.783 | `5047517e` | api://hr-agents/pay | `f694b25f-f0e2-4d67-b39d-5b897c3e005a` | `e1106d45-d935-4ed1-8bd9-0d5aa6525858` | `1-6ac2c9af-2f555b76128486f50a89f5a8` | 19.21 |  |
| 21:48:31.790 | `5047517e` | api://hr-tools | `93b32555-6ac2-4343-ad47-ac3273d10659` | `51992e59-323c-4154-8512-05f9fbbcd534` | `1-6ac2c9af-01b2637540cec2d8171580a9` | 20.57 |  |
| 21:48:31.795 | `5047517e` | api://hr-agents/travel | `c177a7b6-5965-45bb-a43b-20591703af6a` | `3f2b3313-e9ab-45ce-8454-d5f38d5762c5` | `1-6ac2c9af-1857f374118feb89285f51a6` | 26.0 |  |
| 21:48:53.910 | `f2e4ea22` | api://hr-tools | `eefc5128-4f16-494e-9a25-38c17215b43f` | `50f9d183-0491-4fdc-915f-427ce142997a` | `1-6ac2c9c5-6bc5914a745bf1d56107ef1f` | 23.58 |  |
| 21:48:53.926 | `f2e4ea22` | api://hr-agents/profile | `4b4126be-6115-4d90-b5bf-0666e96e2e2d` | `e6506bfd-9fd9-42c3-aebf-7d5a696d0458` | `1-6ac2c9c5-29ccc43935cdfe6f2f5f220e` | 21.12 |  |
| 21:48:53.936 | `f2e4ea22` | api://hr-agents/travel | `cc1832cd-f058-4836-894c-034ef6bf0c96` | `4bb09326-9255-4685-80be-1d039f77f14a` | `1-6ac2c9c5-46f670fa3167e6644b5a758f` | 21.96 |  |
| 21:48:53.939 | `f2e4ea22` | api://hr-agents/pay | `eccd64f0-865d-4109-83ec-426eae2b02d4` | `f2a6dc5a-0740-4f05-a197-652ad808b740` | `1-6ac2c9c5-37b164386c10118939823045` | 8.88 |  |
| 21:49:19.897 | `1da4d530` | api://hr-agents/pay | `c55c7022-24a4-44d3-8909-c6cc182efd2a` | `51f6b879-6ead-4a5d-b01a-dec69794638a` | `1-6ac2c9df-632d33696e4f27a67ff8b384` | 23.61 |  |
| 21:49:19.920 | `1da4d530` | api://hr-agents/travel | `ac4b464a-6220-4ec5-b000-16dbaddac425` | `3f8676ef-92d1-4b8a-b6b4-7139702217a7` | `1-6ac2c9df-1e90e66c75247f385a1144c0` | 26.24 |  |
| 21:49:19.930 | `1da4d530` | api://hr-agents/profile | `a0b50632-b19c-4ad4-aa1c-236490b9430f` | `d512f86f-095b-4f28-b23c-1a9ed48aa400` | `1-6ac2c9df-0ffd7cc849111f9740ff0488` | 8.52 |  |
| 21:49:19.942 | `1da4d530` | api://hr-tools | `17b011cd-0c03-434a-9646-6e8368777bb0` | `8dade0a3-fa56-466d-9fed-8d8df301e553` | `1-6ac2c9df-508c38231f8dd2492ff3ded2` | 19.51 |  |
| 21:49:45.839 | `ee99f857` | api://hr-agents/profile | `926501c5-07b8-47ff-847d-29a4c216e732` | `0d069b72-a979-48c9-90c8-a7594012fdcd` | `1-6ac2c9f9-5af8a80a2f6a137e084bbc05` | 22.28 |  |
| 21:49:45.841 | `ee99f857` | api://hr-agents/pay | `0b09290e-7b06-4eb9-8d9b-220d40f179fb` | `546cd39a-c552-4c60-a905-82dd76cae239` | `1-6ac2c9f9-416710465e3908fe01b7a92d` | 23.87 |  |
| 21:49:45.849 | `ee99f857` | api://hr-agents/travel | `887f80dc-e7b0-49b0-8c7d-e981b615c8c0` | `15c8ff3a-cfa4-4feb-9a96-9de0e535a25c` | `1-6ac2c9f9-5459eff87391c3941f63cf9c` | 22.43 |  |
| 21:49:45.857 | `ee99f857` | api://hr-tools | `7a5e4248-0ff1-4f3f-ad96-557a165b28ae` | `e682ad8c-3076-48d3-ac44-953cb074e2b3` | `1-6ac2c9f9-38220c224261f814009b5715` | 25.57 |  |
| 21:50:12.869 | `053ec9d9` | api://hr-agents/travel | `61ee6aee-d614-4192-998f-3a88be929a68` | `e578a207-adbc-4588-af12-b30981c1bd8c` | `1-6ac2ca14-6bc082d764a460b27a3b7989` | 23.38 |  |
| 21:50:12.873 | `053ec9d9` | api://hr-agents/profile | `caf8afe8-e8d5-48cf-8ba0-2ad25a8d3ab2` | `a4c59789-378b-43b2-937b-dc1f717411d4` | `1-6ac2ca14-1ee15e8a65a2abd27adc4174` | 23.65 |  |
| 21:50:12.886 | `053ec9d9` | api://hr-agents/pay | `dc1019e4-fa8b-4ceb-89df-1b25eb874c98` | `bce1e589-de53-4548-84bc-59c274239976` | `1-6ac2ca14-61b77109779a255d265e16dd` | 18.85 |  |
| 21:50:12.889 | `053ec9d9` | api://hr-tools | `0f467fbb-0e3f-4d51-89ef-341de5816b5f` | `753d3462-e40e-48a5-8fbe-f61bcb504c02` | `1-6ac2ca14-5219e84a7159fb9d19b47d63` | 23.8 |  |
| 21:50:34.819 | `809bc097` | api://hr-agents/travel | `bc23e21f-c9b7-4243-8255-331584ba6c1c` | `983b1f5f-ccba-4c43-bc60-7bad0cdca568` | `1-6ac2ca2a-66f1fefa775cca6a281da0d5` | 23.3 |  |
| 21:50:34.846 | `809bc097` | api://hr-tools | `077b7a3d-ed80-4765-9c66-18ceaa97acac` | `1e5049d1-b900-4189-9880-ad8b29a35cd1` | `1-6ac2ca2a-6598cf4e4361d34c0874263c` | 22.43 |  |
| 21:50:34.852 | `809bc097` | api://hr-agents/pay | `1070e8d1-42d9-408c-a4ce-7a5d0525484b` | `2badad2d-1bc1-4c2c-8b69-c533a69bf30c` | `1-6ac2ca2a-43944dce3fddc9cf6dd2ff57` | 7.96 |  |
| 21:50:34.860 | `809bc097` | api://hr-agents/profile | `2ea01c28-b1be-4a40-a5b1-c93b1ac3900f` | `ec28e9b4-db40-4da9-be33-798e0a02ca67` | `1-6ac2ca2a-4e23801d2c721cf64c0a8187` | 24.25 |  |
| 21:51:11.138 | `96368ac5` | api://hr-agents/travel | `f9a13f7a-7365-4568-a7ce-2325842992fa` | `c7fa8bfa-66b3-4dee-9413-5a98cb1d47b8` | `1-6ac2ca4f-71c78f24507557e2708afb94` | 25.39 |  |
| 21:51:11.141 | `96368ac5` | api://hr-agents/profile | `43161a1d-e3f2-433e-8f40-7e8091ef499a` | `1dcf89b8-9076-4ca9-a6c6-3fb56ad5c921` | `1-6ac2ca4f-6786741d4ebe4df837a20831` | 21.83 |  |
| 21:51:11.147 | `96368ac5` | api://hr-agents/pay | `0742632c-d7af-4e54-8d2e-8c696bad2ff1` | `12e77bec-2308-48a5-8b91-6a53f7c268ac` | `1-6ac2ca4f-6951ddfe2b7889873dcfbb90` | 19.78 |  |
| 21:51:11.157 | `96368ac5` | api://hr-tools | `9a7424f8-b349-4153-a660-3e2ab80100b1` | `ffca404e-e0b4-4a70-b7cc-3b9b791daefb` | `1-6ac2ca4f-4220d5a26c3db31b5a53f5bd` | 20.8 |  |
| 21:51:41.598 | `f86313e3` | api://hr-agents/profile | `645bf27e-fae3-42aa-9997-795f20d62fc0` | `ccc275b0-8089-4570-b9a3-a6e4159f04e2` | `1-6ac2ca6d-08296d79669d0cdc6fafceee` | 21.31 |  |
| 21:51:41.599 | `f86313e3` | api://hr-agents/pay | `7104c802-ae56-426a-acff-9e6e79b94e05` | `18b8889d-35e1-4e56-833a-5c53f5817425` | `1-6ac2ca6d-530ca57d110d3571225814e6` | 19.55 |  |
| 21:51:41.606 | `f86313e3` | api://hr-tools | `ff34432a-e465-44ed-8dd6-cc0c50e621cb` | `bea493b9-d024-4018-991a-e2cc2cd51c70` | `1-6ac2ca6d-055254215b6959f21b0e157a` | 23.03 |  |
| 21:51:41.613 | `f86313e3` | api://hr-agents/travel | `1cb9b90f-17f2-43c4-8799-ac8b7c684eb9` | `81cbfd32-abf3-4475-ac96-81b81ad07bf1` | `1-6ac2ca6d-73c2ef0732e6fb2e66935256` | 19.95 |  |
| 21:52:07.570 | `e4636a0d` | api://hr-agents/pay | `3b99eae9-818e-440c-af91-b88fdad37b62` | `881a18fa-abd6-4d7c-a6be-2c1468edcc0e` | `1-6ac2ca87-6df944b854c704ff351a491e` | 21.19 |  |
| 21:52:07.589 | `e4636a0d` | api://hr-tools | `f7a7dd66-382d-41bf-a1e4-38c767f9ee32` | `52aee19f-6db0-4e23-adc5-b64bf93d01f4` | `1-6ac2ca87-043050f03d0f5b4f59a5dbb4` | 21.59 |  |
| 21:52:07.591 | `e4636a0d` | api://hr-agents/travel | `32b8361a-5470-4afb-8ed8-c809f09fb8a7` | `cffe7407-4214-4e9b-933f-49ad5e0fcc64` | `1-6ac2ca87-2af9ad146a6a3857385f40f8` | 21.39 |  |
| 21:52:07.601 | `e4636a0d` | api://hr-agents/profile | `c787da86-15b1-40d4-95e9-2659cafe841b` | `a7142a23-f58e-4649-a4cf-9ef234ac0168` | `1-6ac2ca87-0814a505214997544042987b` | 7.88 |  |
| 21:52:34.075 | `7f166771` | api://hr-agents/travel | `b08f6f08-d501-48f1-8526-15bbeb41cdb9` | `fe32025b-026e-4c7d-b882-528abc3958a7` | `1-6ac2caa2-0d98d40366e8d4f44a434ddc` | 21.28 |  |
| 21:52:34.089 | `7f166771` | api://hr-agents/pay | `e71e0161-130c-45b9-a9e1-16f726c90325` | `b8cfa89d-8260-408a-91f3-63162e045319` | `1-6ac2caa2-4eb3c7df0491da8169121d35` | 20.61 |  |
| 21:52:34.093 | `7f166771` | api://hr-agents/profile | `3fb7d0e5-d267-4d46-b68f-3bef21c6eb89` | `19f7cc49-1da1-4045-90f1-2c4b212dc236` | `1-6ac2caa2-5259e46f212cf5291173487e` | 21.97 |  |
| 21:52:34.096 | `7f166771` | api://hr-tools | `3c116060-0509-4414-9a41-a4b7855b2a85` | `bd52af5e-98d6-4f6d-bcb3-d0d4cbc5d14e` | `1-6ac2caa2-08e714240f652b23658d5e4b` | 18.05 |  |
| 21:52:55.810 | `f63c8a61` | api://hr-agents/profile | `6b717922-8d17-4a8e-99c0-93480a9f2189` | `aa00779a-5c19-41c1-9c41-7e40bf14f154` | `1-6ac2cab7-41ffe3da447359ee0e15b7f1` | 20.81 |  |
| 21:52:55.818 | `f63c8a61` | api://hr-agents/pay | `bfec8b45-5b6c-49f4-bc07-15286eb34b64` | `94148125-23d2-4a3e-b3a4-b3f7b31d171c` | `1-6ac2cab7-3c2e1aff165525a75987a9d8` | 20.19 |  |
| 21:52:55.819 | `f63c8a61` | api://hr-agents/travel | `84949728-509c-4c9d-82c6-83bc2fde7cee` | `3908d402-109c-4ff4-97c8-398ea0c74afb` | `1-6ac2cab7-64cd855d0926c7933b5fad4f` | 22.54 |  |
| 21:52:55.835 | `f63c8a61` | api://hr-tools | `64dbfc80-5859-487d-9675-38358f303915` | `efdf4b09-8f42-45d7-8fec-5fd77e79d7f6` | `1-6ac2cab7-45dcfc9f79565d1b1b5eb93e` | 20.97 |  |

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
| 21:41:56.174 | `d39c338a-8878-4041-b185-e869082f6f3e` | `6769f472-9844-478b-8b42-1f8edb761444` | `36b32334-cdb4-49f9-bbd4-af40b5315b93` | `98d7804d-c152-4151-80da-5902f1c9e40a` | `6f842776-88af-4859-9d84-fb7a13d9f275` | `39076965-5ad7-4cf2-b9d6-e6d10c475c58` | `d482e529-1601-4837-ae01-c4aad28e4ad8` | `31b78d2a-ee30-47b0-8dcd-c59adecf5168` | `01a108dd-dde8-76f0-857a-f00e5f581dad` | 21:42:00.424 |
| 21:43:11.191 | `c86cb354-f355-46b0-99b5-8a87a4193008` | `6da99ce0-be4e-4577-8df0-7e6571e2b82e` | `d0f95270-4c78-4ad9-878f-8e46c557b802` | `9a0d1c84-b5cd-4197-a205-aa156e9bb8e6` | `d9525c78-be2c-483a-a946-b8258c8e8a11` | `33f5bd8e-cea9-4fe5-b877-5e25fa91c871` | `68622ecd-6c12-4fde-a669-2962fa093fde` | `548d0ad8-2614-440f-b998-beaa7bb874fd` | `01a108df-01da-7c17-85f6-113a1002d0b7` | 21:43:15.162 |
| 21:43:37.479 | `df68ec68-12db-4345-9288-04a1f24aa81c` | `fb992f1f-7557-41b4-a19e-7465226a418b` | `77e7feeb-3edb-47fe-ae6d-3da78a45662a` | `092d933a-4840-4dd3-b31b-4b945ac5fa53` | `7df257f5-7c28-44c9-bde1-d50fd23d9b9d` | `3aee9bc9-4b35-4eaf-8ea0-0687f3bbf900` | `8ef42078-56f3-4e92-9c23-00b8e1401b2b` | `8b63cb48-ba5e-428b-8c30-edba78e2cdad` | `01a108df-6487-752c-a7b6-6bffd4e36d2b` | 21:43:40.423 |
| 21:44:14.041 | `9be583e6-2bbf-411a-8e73-4764c542ad63` | `96786022-fe84-4a8c-ae1b-be1b30be6f59` | `78cbd0d0-7c4e-48aa-93a7-9a6b047e5ed1` | `a6b53174-12a7-42ea-86f6-c949119b227f` | `577f13a3-ecb5-4750-bd31-510a38092902` | `db265f63-2140-4f34-8b36-dc656931d4c8` | `6601b797-4045-4700-901e-a44ca3344b30` | `b9973221-c5ae-45bd-bcd6-ee380c5d6cc7` | `01a108df-f3c3-77d6-b9b6-3088ac3c1898` | 21:44:17.091 |
| 21:44:36.352 | `2dd0024b-e94b-4762-bb2a-a80801b3328a` | `b01eb473-4c89-49ab-a0e1-aae8d6568375` | `8a4a77ad-efbc-428d-baed-5eebd5f0b995` | `cccc6c93-a9f7-48ce-bcd3-39f841fa17f2` | `0bd72e77-6357-4137-8f7f-367c64fffdbe` | `eeaba1ea-6e28-4cb7-8686-6ee37727a36f` | `ef603997-d2a4-43c1-afb0-1994d42e0558` | `171f94a7-a4d1-4b97-9fe4-e89f3364b1c1` | `01a108e0-4aa0-78fc-981a-53f0742ca207` | 21:44:39.328 |
| 21:45:11.560 | `de563712-a523-44d6-826e-7226d49c3fef` | `19e03821-9b93-4d03-ba11-171b977cd3dd` | `369766b7-69cc-4c1d-b0b3-4541c64d0c0c` | `1d8c7177-e628-4ee1-bb5f-7f31c142cea4` | `9675c365-b39b-44b2-8a15-c5a9ffd1c311` | `e92f3b05-bf4c-4c3e-b805-9a60497c796d` | `3b02e272-c1bb-4cb6-b291-9bb59da823bb` | `2fcf9e59-7c13-4581-af23-6d0568cf5615` | `01a108e0-d48a-771f-887c-8b038b55724d` | 21:45:14.634 |
| 21:45:39.836 | `2266020c-510b-46b4-851b-a77515bb01f6` | `7874fe99-7984-4126-8365-8ddbc6711ad8` | `02749091-dd28-4d2a-a9db-7f90fea25e73` | `0f18958f-490f-465e-bb68-f613d98a0e65` | `363ff77e-9d04-410a-b2d0-cb7e2eaf5278` | `d961e348-dd15-48f7-8c86-3b40b939446a` | `69a129c8-c1bb-4e99-a5c6-746fd3d3e73e` | `160d26f9-e431-451b-9b69-4cadf17757a0` | `01a108e1-42a9-7ac2-822d-66552f9c07a4` | 21:45:42.825 |
| 21:46:06.447 | `805255a6-fa48-4f68-804b-22e0578dd15d` | `6ecd5d9b-0a80-40e6-a3ef-623d9d24f314` | `5291d132-2cc2-47c0-a663-05917fe864a3` | `9f7edb68-2cf1-49cc-8be0-d77fdf13d210` | `7a92d4f0-0d5b-4865-a7d4-51f9ddd8e72e` | `4b7f4f27-3c89-4cc5-8e9e-93d139e2bc20` | `82790d9b-0b26-4797-a7c4-c4852e835320` | `50f05f07-c35b-4d18-a102-733c1d0b1501` | `01a108e1-a9f1-708c-8460-4f42f73542e5` | 21:46:09.265 |
| 21:46:28.178 | `f67be432-6212-4e1e-89eb-0f340eb51c64` | `32a117d5-3f99-40fc-b327-a7ed7b727955` | `cd0dfcd8-26ac-4da7-aad6-4e9994596170` | `ca3682d2-a8cd-4329-806f-d4b1d970c68d` | `00dd7f9c-84db-4808-9588-a943e5eac717` | `90f83ca1-7818-40e8-83e1-b80c8e333a1c` | `e82cf126-0510-4777-9f2e-e37494435745` | `df07c56a-c6a7-4671-93a6-4e9220df2aeb` | `01a108e1-feff-78ec-8f44-22753685241a` | 21:46:31.039 |
| 21:46:54.626 | `aba8d26a-04a5-4761-a92d-55b4ee092c2a` | `378cf4e1-04ac-454f-bd6e-1242e066166a` | `e2394142-ceef-4020-8d66-a9189a539f61` | `49901ae3-665a-45a3-bd12-e433f0cdea36` | `f8cee8a9-edba-47ad-bc29-bfedc4d6be7f` | `de4d49be-9f97-4c0d-a9f2-8dd7da9ed9ae` | `e972bdbd-56a7-44b2-8501-2d965791d764` | `5c9a25f5-1c53-4294-9861-31f385fae581` | `01a108e2-660d-7ecd-825e-545624bfb40f` | 21:46:57.421 |
| 21:47:33.402 | `65853153-1ba0-4078-afbb-5d6c1a4b81bb` | `cd402b1b-32d9-4cb3-9072-da8811236c51` | `3b09c352-4a32-432b-94dc-bea131d41149` | `59ee8d36-c5b5-425f-b704-a79020f8217e` | `113ff457-edbd-487d-8489-eef767382c36` | `22c4770c-2399-4d6d-bbf2-c8398d09bb9f` | `6f07627f-6619-479f-afef-c1624a260e56` | `4174e877-a9d2-4b66-a635-5ebdbdd0b5a4` | `01a108e2-fd85-7c18-89a3-1227e4d5b89b` | 21:47:36.197 |
| 21:48:02.967 | `10fd08e0-aef3-4847-b9a1-8cf583ee121e` | `cbf9bd0e-07ce-4f81-8e87-284993c6fb33` | `8980be3e-383f-4530-8750-c394a1e84739` | `534ebd71-0703-48e7-8455-fe0406a7c3fe` | `f6e2cb4f-6350-409f-9c84-d566a454e0d5` | `e4848370-4996-4a5d-b5d7-8ab759adc36b` | `26823ad9-142b-41ae-ba78-19e6ab39db52` | `d0ca91fe-3845-4ba6-aa39-66fcb8bfd089` | `01a108e3-71b2-7e77-bdbe-955b9af91fad` | 21:48:05.938 |
| 21:48:30.820 | `5047517e-5a34-463d-9908-5a6ed2706167` | `1a0f8755-b298-4a79-930e-a28e4d69a6fc` | `23ffcc1c-8638-4ab2-a1d8-4d9149ad48e0` | `ef2a3789-a250-4297-ab7c-f278c1e61a5f` | `020ae718-50ca-487b-8d82-6cac25e6183b` | `b2f877df-abb3-43e4-a1b2-c028edfa4217` | `76b09b15-218f-4e13-99e9-7b1bbadc236a` | `d1004194-67b7-4942-9131-b92d991d8710` | `01a108e3-dd9e-765b-8bd8-13b7a14c94d8` | 21:48:33.566 |
| 21:48:52.840 | `f2e4ea22-8e9f-4a1a-9af4-5bf9da598f51` | `05e84ac4-e182-40bf-aa5b-54ba969785c3` | `e993013d-8130-426c-bebd-6ee0bf229603` | `1baae9e3-dc91-4bee-bc74-f31408327441` | `947b8b37-142c-4419-80d0-9daa83aa8738` | `85b820ac-57dc-4cab-a54e-8b1b38451015` | `5785e361-6610-4c61-a8c8-dbc4465d9fdf` | `d569c77b-496f-487b-8cec-0c1191dcd9e6` | `01a108e4-343e-7cf5-afc2-521eede43366` | 21:48:55.742 |
| 21:49:19.000 | `1da4d530-bbd7-47c1-97a5-7f1678554b8b` | `0e552cb3-11eb-4cd1-9d33-00bbafcac18a` | `52f6c7e8-8524-44b2-9683-1a991a787ee6` | `33f8c918-fd1c-428f-a69e-cc9036085c68` | `778d6b74-50c8-4b44-ae7c-2953f2c1002f` | `3e6f0843-e619-40e7-a250-3b86d6b618e0` | `04377cc2-e43a-462e-b879-3023da2a9e1d` | `699cd8ac-a345-4a6d-8c04-44dde5035872` | `01a108e4-9966-7e79-a64d-2b9fe3e0226c` | 21:49:21.638 |
| 21:49:44.903 | `ee99f857-5e8d-4ae2-bcfa-e91b03b84046` | `1f6c11d1-8121-4c2e-9426-e81cef2b5450` | `820ca2c2-c173-4f99-83e0-252c32f39aad` | `dede6d3b-0ce9-41c0-aea3-0ee40fa120b5` | `dfc1820e-dd25-467f-9aad-dad73449ebac` | `220a3131-4cfd-41b6-b52a-65ff00671da9` | `f6496781-512a-4aee-a091-6b377ff1a838` | `b171cd8d-5130-4103-b8a2-fc969c553bd8` | `01a108e4-fe75-7d00-97dd-ab0a026b7423` | 21:49:47.509 |
| 21:50:11.951 | `053ec9d9-882a-45d2-9d95-539b5e8cf044` | `6a25cf15-2671-4d3a-ac66-bad4d5563f6d` | `cc1b968a-534c-491c-a80b-90f75fb3659f` | `e4ab13db-1a6a-4ebf-b1bb-8cf26790baec` | `3d45ceb1-f213-4751-a224-dca27a420492` | `7b4a6e07-de3f-4884-a763-72549144e1c0` | `c749d993-7494-426f-bf45-c45dd13a3180` | `a96a73c4-2bd2-4a03-8307-880d37257b74` | `01a108e5-6804-7efb-8ee9-6317142f1beb` | 21:50:14.532 |
| 21:50:34.047 | `809bc097-cc6f-4d4a-bc50-e59e72034ce4` | `e231b9de-4992-4da3-a167-f30b7cc91b12` | `f262d5ab-59a2-4ef5-ac81-66590e6348a3` | `69afb2d1-5271-4bbc-a8a6-36ed0f3b795f` | `2379e8c8-5d91-4ae5-872a-0fde21a868c0` | `83075961-dca7-4b77-8a25-121727960e48` | `868dfd63-e002-40f5-b656-46accedfdb47` | `5645e25e-2476-4f04-aa59-f46674b18f60` | `01a108e5-be1c-7b1d-a1de-432a6a418269` | 21:50:36.572 |
| 21:51:10.111 | `96368ac5-71b0-4ff6-873f-b435823ab645` | `4c592eb2-d167-4a4e-938a-3dfdad442f0f` | `889ab1cb-1588-4fcf-8a16-27d4cc9e6ddc` | `ccef367b-72a4-421b-862d-b7e7fcbe2e0b` | `436d7997-f942-4542-a086-ce3948b89768` | `e6d56f90-c1fd-472a-9a37-9e18009c270a` | `311c604f-af6a-40f2-bc31-9dffa12a6749` | `4ce2e238-11ea-436c-af61-09a4dddedb24` | `01a108e6-4bb3-75af-a43c-c9ec0b0be5e3` | 21:51:12.819 |
| 21:51:40.814 | `f86313e3-5c41-4056-887d-5016fc7e9004` | `b676b78d-3fd0-406f-9a5e-76a00e8a63a0` | `0a49dab8-32f5-4751-9d45-e607fad3ed06` | `6a0d7e43-4342-4788-9ad9-1923fe5794b9` | `0527d909-5e60-429a-a363-12a5ba77e94c` | `658200f9-b725-475f-a2d9-4b0af46ad01f` | `d0e380d3-82f0-49d2-922e-b63e477e5488` | `e91dd383-213c-4fa9-bad8-684802ff01c1` | `01a108e6-c2bb-7844-b441-7bea1475448f` | 21:51:43.291 |
| 21:52:06.496 | `e4636a0d-537c-44f6-8682-08f73cbf201a` | `328023fc-04d5-488d-a6a9-d83f0379ad3f` | `6131dbfe-6da6-4202-8ec6-7153870223a5` | `d90c43e8-b379-4343-ba58-f7a0da480ade` | `84b6d983-bd0f-4ee2-b738-eaf838de3033` | `c48f6025-5ac8-4718-b1d6-29237f4a627b` | `bbd6b2a2-6a86-4412-8906-573ae4f99349` | `319fbd33-0df0-4147-a87f-3f9044635591` | `01a108e7-2949-7b17-a8b0-6795ba28ffa8` | 21:52:09.545 |
| 21:52:33.118 | `7f166771-4d9d-4ad3-bfe4-3143b78467a5` | `85bebd37-59de-4e26-b7e2-0d18f6c95ab3` | `7fff4230-6fa6-4af3-b683-c7e8fd524bb8` | `d682a091-b884-4dcc-97e4-c9ae214ed1fe` | `5491d5cd-dbc1-425e-8b2f-8468c85f2372` | `cd3dcd90-b270-4093-b2d1-9231121c9569` | `b6643b09-f022-4fd5-95a5-beb847238494` | `a6eaee2c-3d8c-445b-aebf-5f308274583e` | `01a108e7-9064-72a6-b240-92548b75ad1e` | 21:52:35.940 |
| 21:52:54.825 | `f63c8a61-a523-4a43-9e3b-580ecc6e3e2b` | `7b5e0d66-2124-4f5b-b35c-9e3f5a7decf6` | `1de9bc16-2f5a-4fe1-a93c-6faabf48fbe7` | `64d8cbec-94a0-4019-8c68-44c01eab62cc` | `436a1958-f1ea-43ec-8ebc-90a07ab5e81a` | `6114c7f5-8717-4f9e-9cfb-b17a21850346` | `34cab70f-e340-4a5b-a93f-89e257410ba5` | `98648563-7c6f-4f84-9161-30457697ae88` | `01a108e7-e57c-73dc-8276-667d599fe5e0` | 21:52:57.724 |

Connect stamps the greeting 320 ms (median, 297 to 403 ms) after the designer's `NluResponded`,
against 120 ms (median, 81 to 199 ms) for a reply; the greeting's extra time (report question 6) is
spent before Connect posts the first message of a contact, not on the way to the function's socket.

### Per turn

| Click | Contact | Question | SendMessage request id | Question message id | Connect stamp | Reply message ids | Reply SendMessage request ids | Reply stamps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 21:42:07.498 | `d39c338a` | Change my address | `f6fa089b-1620-4f74-88b5-689768dee395` | `01a108dd-fa52-7bb9-88d3-ec6456968af4` | 21:42:07.698 | `01a108de-3b0a-7542-a3f0-5ac3d23a27b2` | `6d097b10-67f4-447e-be30-1209aa1e249b` | 21:42:24.266 |
| 21:42:27.422 | `d39c338a` | And what is my emergency contact? | `b38d70bd-6cac-47cb-90d6-764034a39eb9` | `01a108de-47bc-7f6a-81b4-e49d3d16f6f3` | 21:42:27.516 | `01a108de-50ef-7724-b159-5bc93e9c39aa` | `5bff8caf-5684-4222-b677-d214a03918da` | 21:42:29.871 |
| 21:43:22.412 | `c86cb354` | Update my information | `bb198552-bbd0-4b06-9cc4-5a6c83cbb5c4` | `01a108df-1ed2-7469-9197-4bffec0c2513` | 21:43:22.578 | `01a108df-228f-7755-8ccc-65d51a5d5ac6` | `bec396f6-b4f2-472b-866a-e3615205bc92` | 21:43:23.535 |
| 21:43:26.736 | `c86cb354` | my home address | `dbdd76d9-7813-45b0-80b2-d58fe481c368` | `01a108df-2f8f-7300-9d2c-5a4358b83c43` | 21:43:26.863 | `01a108df-525f-7b98-9783-77f1c3b9a197` | `3e40b6f0-74bd-4dea-9d9c-4f96ef9a0732` | 21:43:35.775 |
| 21:43:48.525 | `df68ec68` | Change my address | `50bd4907-38f6-4518-8e27-6df3fbb82d4d` | `01a108df-84d6-7d65-a765-ff2e34f8fc81` | 21:43:48.694 | `01a108df-cb13-7218-a129-6fdabd589b8e` | `36250f8a-a47f-45b8-aad1-a7610bd0310c` | 21:44:06.675 |
| 21:44:09.839 | `df68ec68` | And what is my emergency contact? | `89f45cfa-e3ec-4fb9-9dad-4f1aafa7c80c` | `01a108df-d807-7f01-b179-0722ea24fdc4` | 21:44:09.991 | `01a108df-e139-7405-815e-bc4bb54bf6f2` | `bdfe7224-327b-4c03-8d18-23357775ffa1` | 21:44:12.345 |
| 21:44:25.100 | `9be583e6` | PTO policy | `0983a8c6-ac16-490e-ae3f-fb8872c7f3b0` | `01a108e0-13da-7303-9b9f-5b2e624aaca6` | 21:44:25.306 | `01a108e0-2039-74bb-b127-a892fcc75cde` | `b1a5d53a-0885-4f32-9a25-5b21c5b3e2fa` | 21:44:28.473 |
| 21:44:32.492 | `9be583e6` | Does unused PTO carry over? | `a01a374a-0b33-4a57-80b8-f1cdf67bb6bf` | `01a108e0-3048-7a5c-8eb7-0e0b0f86e40c` | 21:44:32.584 | `01a108e0-3529-76ea-ad82-12ffa475df5f` | `49c51e28-72bb-41e9-9a46-8329c0f1d826` | 21:44:33.833 |
| 21:44:47.416 | `2dd0024b` | Buddy passes | `be796435-e5f4-4ee8-ad7f-5cd1a17e6ecc` | `01a108e0-6ad5-7a71-9ae3-43a4e04102ba` | 21:44:47.573 | `01a108e0-a6d0-79c0-89bb-dcac46d59a56` | `5152124c-4323-465f-85ec-22457fe7d124` | 21:45:02.928 |
| 21:45:06.093 | `2dd0024b` | Can my parents use them? | `cdaf485f-e4a4-4e60-a10a-6f3970063b58` | `01a108e0-b3a0-7eb1-b8aa-8ce94670ce4b` | 21:45:06.208 | `01a108e0-c1f5-7860-a526-64453463f8db` | `6049dc12-ce83-4e13-8e90-27fdccb493e6` | 21:45:09.877 |
| 21:45:22.618 | `de563712` | Update my information | `70923825-be01-444c-8bde-663e525eb7a8` | `01a108e0-f45e-77a1-bd97-dc9284ff424e` | 21:45:22.782 | `01a108e0-f8b8-7f49-a21d-34a8567c4d58` | `f310bd36-6345-4a48-a94e-657ac91da307` | 21:45:23.896 |
| 21:45:27.016 | `de563712` | my home address | `faae1b22-b00c-426e-b0a4-4adaba24bdcb` | `01a108e1-0564-712b-8cf0-f8bb17abde49` | 21:45:27.140 | `01a108e1-3066-7c2e-a5af-ae7d81cff871` | `9e63595c-cfda-4b29-8f16-f08802dc4171` | 21:45:38.150 |
| 21:45:50.904 | `2266020c` | Change my address | `19641d8f-25e0-4e5f-97a0-58dc07f84aa2` | `01a108e1-6332-74c8-85b4-259e49643623` | 21:45:51.154 | `01a108e1-82e4-7787-b66f-89afa484a879` | `106398c5-6c68-4163-a32d-98336380c8fa` | 21:45:59.268 |
| 21:46:02.470 | `2266020c` | And what is my emergency contact? | `f3122c58-f623-4ca7-9593-ce28087ee051` | `01a108e1-8fd0-7f2b-a75c-34b0941f5f15` | 21:46:02.576 | `01a108e1-9847-74a4-b35b-935618de53a7` | `a1415ff7-d245-4a5e-9a9b-29dfc0bba4ed` | 21:46:04.743 |
| 21:46:17.524 | `805255a6` | PTO policy | `43890ad8-b0b2-465c-8a12-ea5eff62cffc` | `01a108e1-cadb-7cab-a690-3313eb2b13ed` | 21:46:17.691 | `01a108e1-d56e-7b60-8682-99e7ae59eaa5` | `4aeb818f-a7b5-4996-8250-9979df0a9179` | 21:46:20.398 |
| 21:46:24.330 | `805255a6` | Does unused PTO carry over? | `f5adb120-7243-48a4-b0cb-a42998f8e800` | `01a108e1-e539-7e04-b3f5-e4d6958c421e` | 21:46:24.441 | `01a108e1-ea0d-7235-af1f-0c706feb9d80` | `eb47b816-fd4e-422d-ac7c-0a00fa61b118` | 21:46:25.677 |
| 21:46:39.250 | `f67be432` | Buddy passes | `20b4a392-c03c-4e9e-818f-a0f37b5ee137` | `01a108e2-1fb7-7ac2-a810-1c318ca8cc9b` | 21:46:39.415 | `01a108e2-39fd-7660-acc1-eb0b9496a3d2` | `c76245a8-2340-44db-be1c-ee58582aca1b` | 21:46:46.141 |
| 21:46:49.244 | `f67be432` | Can my parents use them? | `9c50e0d4-446d-4e4b-a5ce-b634f557aece` | `01a108e2-46b2-74f8-847a-f6fcdf57b6d6` | 21:46:49.394 | `01a108e2-54ab-7a20-91e2-4c0ecaa3ea72` | `1bfd16bd-c8ec-48ee-a6ce-9b039e30bec3` | 21:46:52.971 |
| 21:47:05.676 | `aba8d26a` | When was my last paycheck and how much was it? | `65ee5f99-c0c5-4128-8831-530020de1b94` | `01a108e2-86e5-7e33-8bc1-d977fe39f0b2` | 21:47:05.829 | `01a108e2-d6e9-7a6e-83bc-92ddfeab499e` | `fcaecdae-d681-433f-b0b8-cfa1fac68743` | 21:47:26.313 |
| 21:47:29.427 | `aba8d26a` | And the one before that? | `a1c9adf7-8c65-4414-8009-0a6980f0ed6d` | `01a108e2-e376-7860-a941-9ae0b36f01bd` | 21:47:29.526 | `01a108e2-ec1e-7c75-8e1a-74fb4c47e75d` | `fba387c7-c88c-4c4c-a86e-d37c098a1cef` | 21:47:31.742 |
| 21:47:44.463 | `65853153` | Update my information | `97ec1c64-38de-47ef-ae03-6787ad6b2d78` | `01a108e3-1e6f-7a56-a2d8-ba08b17cac49` | 21:47:44.623 | `01a108e3-21df-7047-8a34-40d5030efd74` | `0e06c5e6-5397-46ea-b62e-3cb8b2820750` | 21:47:45.503 |
| 21:47:48.645 | `65853153` | my home address | `7d1b49d2-f54a-4942-bad5-c6c3f2cfe660` | `01a108e3-2e85-783b-b1e3-f49f47055fbd` | 21:47:48.741 | `01a108e3-5f9a-78ce-aaca-e947e527404a` | `19677d24-d317-447c-a447-ec76b3daec74` | 21:48:01.306 |
| 21:48:13.997 | `10fd08e0` | Change my address | `58bf7f28-4bd6-4326-bd81-a5930f0c12ca` | `01a108e3-91d2-7027-9986-2355e3824479` | 21:48:14.162 | `01a108e3-b570-7513-82ec-bc67dc73c462` | `40aea2d1-b7cf-4f99-9357-bb49ccb889d1` | 21:48:23.280 |
| 21:48:26.397 | `10fd08e0` | And what is my emergency contact? | `ecba9235-7cd7-4243-86d4-23057bffb9de` | `01a108e3-c21e-751a-98cf-42bf02d351ad` | 21:48:26.526 | `01a108e3-cc83-7084-86d9-95bdeeeb34c1` | `f78b6733-3ef1-4ed7-8b65-5a869f622825` | 21:48:29.187 |
| 21:48:41.857 | `5047517e` | PTO policy | `0353be86-c2e3-42d4-8d64-a26951663e4a` | `01a108e3-fea9-7eee-afbb-83cf2affb6d5` | 21:48:42.025 | `01a108e4-0b5a-7d04-811b-b26071286262` | `72ede6bd-32c8-4cef-bca6-3d23e40c17cf` | 21:48:45.274 |
| 21:48:49.196 | `5047517e` | Does unused PTO carry over? | `7ed3a944-a059-485f-beb9-6e8808a13ac0` | `01a108e4-1b19-79bd-aa3a-f942acc37216` | 21:48:49.305 | `01a108e4-1f3b-7ada-9e48-4929fb166e60` | `05ea72c1-2bee-4ae0-bbdf-34649fbce663` | 21:48:50.363 |
| 21:49:03.899 | `f2e4ea22` | Buddy passes | `a7781ccc-ecd8-4a68-8ad8-ace0fc83765c` | `01a108e4-54bc-7352-93a3-a1d9b43a8147` | 21:49:04.060 | `01a108e4-6f7f-741a-acdd-464647608f91` | `374e97d4-df53-4cb4-8afd-487003c95fbf` | 21:49:10.911 |
| 21:49:14.023 | `f2e4ea22` | Can my parents use them? | `77db3c8f-4504-45eb-972a-dc598fc7f3c4` | `01a108e4-7c0b-75d2-9e76-b17df4f4c2b7` | 21:49:14.123 | `01a108e4-888d-7b3b-9499-d871a9535672` | `aebe2728-2e9f-40f9-bf2d-0336688c3eba` | 21:49:17.325 |
| 21:49:30.036 | `1da4d530` | Update my information | `4556276a-4f86-492e-b23a-2fd4fcb12bc8` | `01a108e4-badc-7632-9445-a519ff9b4151` | 21:49:30.204 | `01a108e4-bdae-7c2c-8c7b-3c962a818a30` | `37eef96d-3800-447d-b17f-12a90b0cb6f5` | 21:49:30.926 |
| 21:49:34.058 | `1da4d530` | my home address | `6c94bc9b-87be-4e42-9f76-880919d2a1f5` | `01a108e4-ca56-7301-8c7b-088b38e1f9dd` | 21:49:34.166 | `01a108e4-edc5-777b-85cc-95059998c264` | `d14fa3b6-64d6-4340-bfce-8d910882b710` | 21:49:43.237 |
| 21:49:55.969 | `ee99f857` | Change my address | `99bd89fb-4244-495b-af44-5a60ba600662` | `01a108e5-203b-72fa-84be-5052ebe74ed1` | 21:49:56.155 | `01a108e5-41d9-7974-9fbf-43996c961082` | `d2e85354-bf6d-47a9-bb77-25c95f646daf` | 21:50:04.761 |
| 21:50:07.901 | `ee99f857` | And what is my emergency contact? | `d25a1e94-ad58-46a9-9fe4-07ad601dd6dd` | `01a108e5-4eb0-7719-9e91-9a90e2134f0c` | 21:50:08.048 | `01a108e5-5761-7fbc-927a-74a1f68d7f92` | `2ff954fc-8d1b-46bb-b3f6-97db337e0c31` | 21:50:10.273 |
| 21:50:22.992 | `053ec9d9` | PTO policy | `70ed7b18-3156-499e-bae4-545895b1b02d` | `01a108e5-89b0-769f-a7c4-d4440447b64b` | 21:50:23.152 | `01a108e5-9522-701f-b327-a3b7925aab99` | `c47d86e0-91ba-45cc-9199-13b867f7fb17` | 21:50:26.082 |
| 21:50:30.061 | `053ec9d9` | Does unused PTO carry over? | `a6eb2a14-e6cb-41aa-92fe-8d188177258b` | `01a108e5-a525-7ea0-9bdf-f0269aeeef2a` | 21:50:30.181 | `01a108e5-aa36-7e1f-b6d6-dbfde14d0d1f` | `408156e7-6cae-4e22-94fa-7f71fc6b40a8` | 21:50:31.478 |
| 21:50:45.119 | `809bc097` | Buddy passes | `840dd375-cc73-4aa5-887e-af5b2ff735c0` | `01a108e5-e017-7508-97bf-715a6053a274` | 21:50:45.271 | `01a108e6-202e-77b5-a39e-cf35a9400b53` | `cc560716-8ec3-4427-8ae5-6f2a136f48c6` | 21:51:01.678 |
| 21:51:04.791 | `809bc097` | Can my parents use them? | `cbcaec19-44ab-483e-b343-9442c36abe75` | `01a108e6-2ce5-768a-af2e-69c08ff37b89` | 21:51:04.933 | `01a108e6-3a72-7d62-a242-8c86c6eedf25` | `470fa185-2892-4951-86c0-29778d4b9b16` | 21:51:08.402 |
| 21:51:21.150 | `96368ac5` | When was my last paycheck and how much was it? | `691e9bf2-a7ee-4651-a0bd-96cd7ba975ba` | `01a108e6-6cee-74a6-a137-0a98af2557fa` | 21:51:21.326 | `01a108e6-9d5f-7f11-b1cc-409426ceade1` | `0b53d2c9-efb1-4955-b3d3-421a8cb660f0` | 21:51:33.727 |
| 21:51:36.841 | `96368ac5` | And the one before that? | `991857ab-ac41-4f2f-9fed-ee8f897d61df` | `01a108e6-a9f9-7d33-b2ba-829179c1b8a9` | 21:51:36.953 | `01a108e6-b282-7ad0-b1ff-49e6031cea18` | `782ccc28-4e32-4f51-89ba-a9640100984d` | 21:51:39.138 |
| 21:51:51.902 | `f86313e3` | Update my information | `9042810f-2b1b-405a-a339-676c720e58d2` | `01a108e6-e528-78b6-bc4d-a2196ba5acb6` | 21:51:52.104 | `01a108e6-e893-728f-bfe8-e99200e40e99` | `9db0440f-3773-4493-b1e7-f0b9e77e5e5d` | 21:51:52.979 |
| 21:51:56.114 | `f86313e3` | my home address | `b8e5fccc-bfa3-4176-a47f-6a6fd344a61a` | `01a108e6-f52e-74ef-9852-8a9812b10d1f` | 21:51:56.206 | `01a108e7-16cc-72ce-9f2a-5337fc85881e` | `1dcc5dee-a9df-46e5-90e4-9c8b64f038d0` | 21:52:04.812 |
| 21:52:17.557 | `e4636a0d` | Change my address | `9856c687-f786-4640-a2fb-6d80d2df3cd8` | `01a108e7-4932-724c-9593-c74751b27716` | 21:52:17.714 | `01a108e7-6945-70df-b33b-575adb9cc60d` | `e0ef0871-848d-4a46-b32f-e4afa8f07a7d` | 21:52:25.925 |
| 21:52:29.030 | `e4636a0d` | And what is my emergency contact? | `3d442da7-4119-4765-bc31-b673c181f5dc` | `01a108e7-75c8-76be-8d6e-db66d82af64b` | 21:52:29.128 | `01a108e7-7ef2-7fde-84bc-6dff50a9ace2` | `5b577ba0-a495-4468-b8f6-ef3945d83f6a` | 21:52:31.474 |
| 21:52:44.168 | `7f166771` | PTO policy | `7b3b440e-2311-4638-bdb2-d07c9f102aec` | `01a108e7-b12e-7241-b148-7aa3872bb4a2` | 21:52:44.334 | `01a108e7-bb37-793f-a0f0-164fc016bf0d` | `800a305a-d762-41a8-a7d7-b88e2142b951` | 21:52:46.903 |
| 21:52:50.858 | `7f166771` | Does unused PTO carry over? | `00756183-c0e6-4b2d-b5d7-5e97c570cbfc` | `01a108e7-cb1d-747b-aaf9-f9d584d085cd` | 21:52:50.973 | `01a108e7-d08d-70af-934a-78e8be17cf48` | `2d0fec28-846d-438a-8dbe-55fcc16dec17` | 21:52:52.365 |
| 21:53:05.881 | `f63c8a61` | Buddy passes | `bb468e88-fcc0-4d19-ac0f-712ec86d87e0` | `01a108e8-060d-7a73-9e86-cc1d0b8135a5` | 21:53:06.061 | `01a108e8-2197-758d-94ac-be9c432d4b5b` | `521e54c2-df0e-4b86-9f5b-6ab94c1c1506` | 21:53:13.111 |
| 21:53:16.232 | `f63c8a61` | Can my parents use them? | `d97d2857-1d16-4059-8d79-648120efd505` | `01a108e8-2e51-7c10-ade7-d2a051f0efef` | 21:53:16.369 | `01a108e8-3c1d-76fd-8a52-00330eb1f0a0` | `c878c60b-d6fb-4dbd-bcb7-962e90dd09df` | 21:53:19.901 |

## AgentCore Identity calls from CloudTrail

Three callers that no span shows. The runtime itself calls `GetWorkloadAccessTokenForJWT`
(as `AWSServiceRoleForBedrockAgentCoreRuntimeIdentity`, session `CustomerSlrValidation`) once
for every request it delivers (50 matched here; on 4 Oct V1 it was 100 for 100 requests: 37 to the sub-agents, 63 to the
tools runtime, three per tool call). The tools gateway takes a new role session
(`gateway-session-<id>`) for every tool call and calls Identity twice in it. CloudTrail times
are to the second, so these rows are matched by caller and second.

### Runtime ingress

| Time | Calling session | Request delivered | GetWorkloadAccessTokenForJWT request id | CloudTrail second |
| --- | --- | --- | --- | --- |
| 21:42:10.863 | `d39c338a-8878-4041-b185-e869082f6f3e-profile` | sub-agent request | `d29c92ee-0673-488e-9dbe-54d02494b1e1` | 21:42:09 |
| 21:42:19.130 | `d39c338a-8878-4041-b185-e869082f6f3e-profile` | tools runtime request 1 of 3 (hr___get_profile) | `ae588782-504f-40c8-8295-e6747b050e5f` | 21:42:21 |
| 21:42:19.130 | `d39c338a-8878-4041-b185-e869082f6f3e-profile` | tools runtime request 2 of 3 (hr___get_profile) | `58f8eb79-448f-4586-8b5d-d42aa46689b1` | 21:42:21 |
| 21:42:19.130 | `d39c338a-8878-4041-b185-e869082f6f3e-profile` | tools runtime request 3 of 3 (hr___get_profile) | `17e2bc8e-470a-449e-8762-743ab0f97814` | 21:42:19 |
| 21:42:28.717 | `d39c338a-8878-4041-b185-e869082f6f3e-profile` | sub-agent request | `9d09fbae-e07d-4673-84ac-f4c37fe7db44` | 21:42:28 |
| 21:43:29.703 | `c86cb354-f355-46b0-99b5-8a87a4193008-profile` | sub-agent request |  |  |
| 21:43:30.977 | `c86cb354-f355-46b0-99b5-8a87a4193008-profile` | tools runtime request 1 of 3 (hr___get_profile) | `e8c101fc-c7b7-4933-85d9-ff12c656409c` | 21:43:34 |
| 21:43:30.977 | `c86cb354-f355-46b0-99b5-8a87a4193008-profile` | tools runtime request 2 of 3 (hr___get_profile) | `4bbecadb-c927-489f-acdc-91dd742c3bb1` | 21:43:33 |
| 21:43:30.977 | `c86cb354-f355-46b0-99b5-8a87a4193008-profile` | tools runtime request 3 of 3 (hr___get_profile) | `fa57b9fb-2e16-4035-a8a7-8f23cd6dc031` | 21:43:31 |
| 21:43:51.590 | `df68ec68-12db-4345-9288-04a1f24aa81c-profile` | sub-agent request |  |  |
| 21:44:01.082 | `df68ec68-12db-4345-9288-04a1f24aa81c-profile` | tools runtime request 1 of 3 (hr___get_profile) | `00396720-3710-4725-ae3a-27d8d6c25e9f` | 21:44:04 |
| 21:44:01.082 | `df68ec68-12db-4345-9288-04a1f24aa81c-profile` | tools runtime request 2 of 3 (hr___get_profile) | `303612c5-c24d-490c-b5e6-88c0ba11ed87` | 21:44:04 |
| 21:44:01.082 | `df68ec68-12db-4345-9288-04a1f24aa81c-profile` | tools runtime request 3 of 3 (hr___get_profile) | `ad321396-e5eb-4b3f-93b7-31aa667d4b01` | 21:44:01 |
| 21:44:11.195 | `df68ec68-12db-4345-9288-04a1f24aa81c-profile` | sub-agent request | `fe152d03-b75a-4acc-8c0c-40ae4a82ea9f` | 21:44:11 |
| 21:44:50.458 | `2dd0024b-e94b-4762-bb2a-a80801b3328a-travel` | sub-agent request |  |  |
| 21:45:07.347 | `2dd0024b-e94b-4762-bb2a-a80801b3328a-travel` | sub-agent request | `94b2e974-2d65-4f9d-a242-a45a45759d96` | 21:45:07 |
| 21:45:29.801 | `de563712-a523-44d6-826e-7226d49c3fef-profile` | sub-agent request | `dcf02f26-34d2-47ca-95b1-9b346582233e` | 21:45:28 |
| 21:45:30.977 | `de563712-a523-44d6-826e-7226d49c3fef-profile` | tools runtime request 1 of 3 (hr___get_profile) | `ab58f23d-7774-47db-b8c8-057e4daffbe9` | 21:45:33 |
| 21:45:30.977 | `de563712-a523-44d6-826e-7226d49c3fef-profile` | tools runtime request 2 of 3 (hr___get_profile) | `0385f8d2-10e9-43d6-9b4f-4d407b6fad84` | 21:45:33 |
| 21:45:30.977 | `de563712-a523-44d6-826e-7226d49c3fef-profile` | tools runtime request 3 of 3 (hr___get_profile) | `45f23638-2eb8-4ad8-a4dc-1af15f8745ec` | 21:45:31 |
| 21:45:53.777 | `2266020c-510b-46b4-851b-a77515bb01f6-profile` | sub-agent request | `6b665fc7-376f-4a6e-a3aa-f1816f30947f` | 21:45:52 |
| 21:45:54.967 | `2266020c-510b-46b4-851b-a77515bb01f6-profile` | tools runtime request 1 of 3 (hr___get_profile) | `1674b13f-82a4-4dea-a4bf-5ad92da5ed2a` | 21:45:57 |
| 21:45:54.967 | `2266020c-510b-46b4-851b-a77515bb01f6-profile` | tools runtime request 2 of 3 (hr___get_profile) | `2c6d4adb-0762-44f7-902e-91a2ad4ca65c` | 21:45:57 |
| 21:45:54.967 | `2266020c-510b-46b4-851b-a77515bb01f6-profile` | tools runtime request 3 of 3 (hr___get_profile) | `7485dae1-6889-4766-8332-d7f536e6e0f6` | 21:45:55 |
| 21:46:03.618 | `2266020c-510b-46b4-851b-a77515bb01f6-profile` | sub-agent request | `55fd0b5c-201d-4cd1-b2f7-a00ce8895299` | 21:46:03 |
| 21:46:42.134 | `f67be432-6212-4e1e-89eb-0f340eb51c64-travel` | sub-agent request |  |  |
| 21:46:50.598 | `f67be432-6212-4e1e-89eb-0f340eb51c64-travel` | sub-agent request | `a3b768c6-7829-4a90-bcee-9bfd79d9bc53` | 21:46:50 |
| 21:47:55.182 | `65853153-1ba0-4078-afbb-5d6c1a4b81bb-profile` | sub-agent request |  |  |
| 21:47:56.596 | `65853153-1ba0-4078-afbb-5d6c1a4b81bb-profile` | tools runtime request 1 of 3 (hr___get_profile) | `d7a514b2-5429-454c-9330-b832ea00a4b2` | 21:47:59 |
| 21:47:56.596 | `65853153-1ba0-4078-afbb-5d6c1a4b81bb-profile` | tools runtime request 2 of 3 (hr___get_profile) | `10dfbdc0-927b-4829-9059-763c266f238b` | 21:47:59 |
| 21:47:56.596 | `65853153-1ba0-4078-afbb-5d6c1a4b81bb-profile` | tools runtime request 3 of 3 (hr___get_profile) | `b6457aa3-ec08-4f06-a3d1-35a01bd35d29` | 21:47:57 |
| 21:48:17.387 | `10fd08e0-aef3-4847-b9a1-8cf583ee121e-profile` | sub-agent request |  |  |
| 21:48:18.725 | `10fd08e0-aef3-4847-b9a1-8cf583ee121e-profile` | tools runtime request 1 of 3 (hr___get_profile) | `01f11077-11e8-42c6-9503-f693c4822e89` | 21:48:21 |
| 21:48:18.725 | `10fd08e0-aef3-4847-b9a1-8cf583ee121e-profile` | tools runtime request 2 of 3 (hr___get_profile) | `b0ec411a-b2c0-4063-89eb-c37cbc8ea3a0` | 21:48:21 |
| 21:48:18.725 | `10fd08e0-aef3-4847-b9a1-8cf583ee121e-profile` | tools runtime request 3 of 3 (hr___get_profile) | `096ad692-aada-4288-8b88-7a3b79e4aa78` | 21:48:19 |
| 21:48:27.939 | `10fd08e0-aef3-4847-b9a1-8cf583ee121e-profile` | sub-agent request | `148d5119-be77-4eb1-bc7b-d718130e5751` | 21:48:27 |
| 21:49:06.944 | `f2e4ea22-8e9f-4a1a-9af4-5bf9da598f51-travel` | sub-agent request | `f67bfa62-666e-42b7-93ae-dd206acb7cc5` | 21:49:05 |
| 21:49:15.100 | `f2e4ea22-8e9f-4a1a-9af4-5bf9da598f51-travel` | sub-agent request | `0d493b74-c919-4339-83ad-057deb7fa049` | 21:49:15 |
| 21:49:37.018 | `1da4d530-bbd7-47c1-97a5-7f1678554b8b-profile` | sub-agent request |  |  |
| 21:49:38.195 | `1da4d530-bbd7-47c1-97a5-7f1678554b8b-profile` | tools runtime request 1 of 3 (hr___get_profile) | `96225130-0ead-4bda-b273-e4df46ccf40e` | 21:49:41 |
| 21:49:38.195 | `1da4d530-bbd7-47c1-97a5-7f1678554b8b-profile` | tools runtime request 2 of 3 (hr___get_profile) | `1b16e17e-429c-45c6-905e-755b621c9c59` | 21:49:41 |
| 21:49:38.195 | `1da4d530-bbd7-47c1-97a5-7f1678554b8b-profile` | tools runtime request 3 of 3 (hr___get_profile) | `71387356-3b11-486d-8ead-f1a354dce3e8` | 21:49:38 |
| 21:49:59.222 | `ee99f857-5e8d-4ae2-bcfa-e91b03b84046-profile` | sub-agent request |  |  |
| 21:50:00.427 | `ee99f857-5e8d-4ae2-bcfa-e91b03b84046-profile` | tools runtime request 1 of 3 (hr___get_profile) | `76c193bd-36dc-4388-acc7-2eac809644c8` | 21:50:03 |
| 21:50:00.427 | `ee99f857-5e8d-4ae2-bcfa-e91b03b84046-profile` | tools runtime request 2 of 3 (hr___get_profile) | `0fd94217-f8cd-4999-934f-7c97470cda64` | 21:50:03 |
| 21:50:00.427 | `ee99f857-5e8d-4ae2-bcfa-e91b03b84046-profile` | tools runtime request 3 of 3 (hr___get_profile) | `1d7522f1-070a-443c-aa18-aab89d2113a1` | 21:50:01 |
| 21:50:09.145 | `ee99f857-5e8d-4ae2-bcfa-e91b03b84046-profile` | sub-agent request | `ca3c1fbc-786d-4c81-9048-76fd1868531e` | 21:50:09 |
| 21:50:48.979 | `809bc097-cc6f-4d4a-bc50-e59e72034ce4-travel` | sub-agent request | `eecadf92-d14b-4564-9962-d5d8620e91a3` | 21:50:47 |
| 21:51:06.128 | `809bc097-cc6f-4d4a-bc50-e59e72034ce4-travel` | sub-agent request | `8f3e7267-bd09-43a3-8883-18af4f0c1a27` | 21:51:06 |
| 21:51:58.991 | `f86313e3-5c41-4056-887d-5016fc7e9004-profile` | sub-agent request | `b762a9e6-5321-4fc1-b0da-45185934b45a` | 21:51:57 |
| 21:52:00.222 | `f86313e3-5c41-4056-887d-5016fc7e9004-profile` | tools runtime request 1 of 3 (hr___get_profile) | `9d68bb85-cbe9-4b48-a39c-51113b634e31` | 21:52:03 |
| 21:52:00.222 | `f86313e3-5c41-4056-887d-5016fc7e9004-profile` | tools runtime request 2 of 3 (hr___get_profile) | `73ff8ba5-5476-41c9-93c2-3a0b27cb76d3` | 21:52:03 |
| 21:52:00.222 | `f86313e3-5c41-4056-887d-5016fc7e9004-profile` | tools runtime request 3 of 3 (hr___get_profile) | `3c418ae3-2182-4174-aab7-8576bd907cb2` | 21:52:00 |
| 21:52:20.410 | `e4636a0d-537c-44f6-8682-08f73cbf201a-profile` | sub-agent request |  |  |
| 21:52:21.559 | `e4636a0d-537c-44f6-8682-08f73cbf201a-profile` | tools runtime request 1 of 3 (hr___get_profile) | `e33b2497-95cc-46e6-a08b-7cecc05e18bb` | 21:52:24 |
| 21:52:21.559 | `e4636a0d-537c-44f6-8682-08f73cbf201a-profile` | tools runtime request 2 of 3 (hr___get_profile) | `54d5ecae-65fc-46f4-8f66-33c6710ebd81` | 21:52:24 |
| 21:52:21.559 | `e4636a0d-537c-44f6-8682-08f73cbf201a-profile` | tools runtime request 3 of 3 (hr___get_profile) | `9db0b403-0926-4482-ba46-784e6e063f7e` | 21:52:22 |
| 21:52:30.287 | `e4636a0d-537c-44f6-8682-08f73cbf201a-profile` | sub-agent request | `a1a1353c-c614-4bd5-a560-9d9861b61665` | 21:52:30 |
| 21:53:09.033 | `f63c8a61-a523-4a43-9e3b-580ecc6e3e2b-travel` | sub-agent request |  |  |
| 21:53:17.365 | `f63c8a61-a523-4a43-9e3b-580ecc6e3e2b-travel` | sub-agent request | `b8921925-370b-4776-943a-cfdf5cbaafae` | 21:53:17 |

### Tools gateway, per tool call

| Time | Tools gateway request id | Gateway role session | GetWorkloadAccessTokenForJWT request id | GetResourceOauth2Token request id |
| --- | --- | --- | --- | --- |
| 21:42:19.130 | `941a6f27-d9dd-4bfa-991c-7c1f19b3aaae` | `gateway-session-a2a9e920-e779-4a6c-9553-6e1e89e8d32d` | `cead2dbe-a555-40b8-9b8d-c2e258bc1303` | `80a7f691-c18e-4c72-98c8-420e37adef92` |
| 21:43:30.977 | `065d8154-21b4-4486-ae07-65b16e055748` | `gateway-session-1d6088fd-ba70-413e-9932-7ee13dba40d0` | `c2b04f37-60a4-437f-8c35-e907fd40fd39` | `ea5927bf-eaaf-452b-aa98-209ac4bbafec` |
| 21:44:01.082 | `0370c1c9-6f4c-4ca1-9f1a-4b80c203adca` | `gateway-session-aebecca1-ce99-427e-94c8-04a608c8f7f0` | `6ad5f983-03f8-4acb-91f7-9ee6e301693d` | `a5d5da78-e3ce-479f-bc35-bbb7e63e7bc9` |
| 21:45:30.977 | `dafad436-8765-4330-b06c-cdb087da0217` | `gateway-session-9cf2d2c4-4383-4034-88bf-6c7f1ed1fb0e` | `b4729c1d-ec70-4f88-93e6-7258cb91c0aa` | `764c72d3-b557-453d-8e1a-ae912aac6f0f` |
| 21:45:54.967 | `2cf0601e-a4e6-4261-8bcf-12254ba534fb` | `gateway-session-e6804770-4117-48e6-9d3b-07c61807f4a8` | `8f24b331-8cc4-493a-b538-7775075e31de` | `a4f15d93-5189-465b-bbfd-2b72107709b9` |
| 21:47:56.596 | `c6003e52-568e-4882-acd6-692acde6b81e` | `gateway-session-db5b89ae-e548-4df4-b001-872d544c5e48` | `5a00b7e4-f3a2-4d2b-a63f-b8c291cfeff3` | `647b2286-e055-4486-af6c-2622bc36fbde` |
| 21:48:18.725 | `e72da84c-ff76-4922-b2bb-1b0326a06dfd` | `gateway-session-db43dc4a-1300-4e95-a07f-07f924aff62a` | `22a09b55-1f7e-49ef-97b5-524b0d8997c4` | `84890d75-4d61-41ef-bc39-129ebf1abf3a` |
| 21:49:38.195 | `ed6315e3-c95a-4376-9829-f80500702d99` | `gateway-session-ff3e52db-207f-407e-9892-c316d8a709ec` | `2e3a686b-1983-4182-82c6-81ee4a9bfbb2` | `481351e1-5362-4a4b-acd5-16643a6e32be` |
| 21:50:00.427 | `f6aa701d-8e78-4ee5-b625-2815019685ac` | `gateway-session-bc590d4c-b5de-4b15-b2c4-1867ab3dd0aa` | `e2b55b1b-790a-4e82-b5d3-f7f18bd24dcd` | `755bf87e-f6fa-45d8-981a-6f9e95729807` |
| 21:52:00.222 | `1c8e8aa2-0d94-445c-8206-649459d0a065` | `gateway-session-d4e602a3-c0fa-45ff-96ae-b32316cc498c` | `85ecc346-6a90-4450-915f-87037452be51` | `df2ba179-b3fd-40e3-a501-f5161fbf71e1` |
| 21:52:21.559 | `d745fdf0-ebb6-480a-8cb3-c47fe639c0d4` | `gateway-session-19041e93-bde8-45d7-ad17-88920c4768c8` | `2b3aa379-b8da-4dee-bd9a-2e89140aaf38` | `98ee6179-ab22-47b7-b9f3-6271dfe93209` |

### Chat start

| Navigation | Contact | GetWorkloadAccessTokenForJWT request id | GetResourceOauth2Token request ids (four hop tokens) |
| --- | --- | --- | --- |
| 21:41:56.174 | `d39c338a-8878-4041-b185-e869082f6f3e` | `572bc0d8-f73c-49fb-9b54-b49cf47aea06` | `8d27d6ae-0cde-450c-8a27-847cc0e89c7b` `920eafcb-877d-4359-92aa-03d9d3623342` `76115815-dbae-422d-805b-34e70a956201` `35bb654c-7331-447d-b52f-74b96280b206` |
| 21:43:11.191 | `c86cb354-f355-46b0-99b5-8a87a4193008` | `2311666c-121b-4b89-963d-7d1f967aa952` | `f997c406-8826-47aa-9251-77a0e146f12a` `ac03b315-29d6-4ebe-b2e5-d038bc1d83ff` `7d643271-b55f-4b08-a2d8-155b257c2702` `fe15b365-bf4c-42c6-8196-a169dfa47794` |
| 21:43:37.479 | `df68ec68-12db-4345-9288-04a1f24aa81c` | `1ac9b513-037d-47f8-bcda-d92ee9fc8b42` | `a1d87822-d70f-42b7-8378-f73196499633` `29720b76-d191-4132-80af-c631a2e3db0a` `bc277508-ffbb-44a7-8ecf-08d201d76214` `190598ca-ffbc-4487-abd2-c60370d55d18` |
| 21:44:14.041 | `9be583e6-2bbf-411a-8e73-4764c542ad63` | `31a1844d-25ed-427d-b75d-cc98aef199b9` | `cc185f95-52b5-4039-931a-39184fbadde5` `6793bf75-d953-440b-befd-7213ae111b66` `ac9402d3-c415-4827-934d-8cd199dbe87d` `552a0cd2-830a-4ae0-82b7-0b633fb8f356` |
| 21:44:36.352 | `2dd0024b-e94b-4762-bb2a-a80801b3328a` | `5f6677a4-271e-4f96-9f67-854f6f2e40f8` | `9c50bb93-99e0-45a5-a48a-8d4476e35580` `dd745f2b-55da-495a-8afd-7c3d8070269d` `2ea6ec23-2f90-4b47-b0af-e0fd48333a2a` `1e54025d-ab4f-4af2-915b-56937d5ae3ab` |
| 21:45:11.560 | `de563712-a523-44d6-826e-7226d49c3fef` | `b3bd64ff-81b4-45fc-bf0e-ea426868452e` | `d721dc42-44d3-499c-807d-699a75c919f8` `5e6a51da-724d-44c0-bce6-bc1cd940c2d5` `59c3418e-120c-4323-bde4-7b675c4fd2eb` `766f9c03-6078-4267-b557-93d45ec3458c` |
| 21:45:39.836 | `2266020c-510b-46b4-851b-a77515bb01f6` | `fd36629e-da74-4eec-91b7-fe4d3ad6cfba` | `4c08def3-2210-4d0d-b4ff-fb29eeb125a8` `3d2ee5dc-751e-4b6e-8fb7-e0523809a8d5` `8e7b5d8e-0446-4b27-b451-f4acc5e1fb6e` `8a6c025d-c146-4142-ae97-5f0022f3d400` |
| 21:46:06.447 | `805255a6-fa48-4f68-804b-22e0578dd15d` | `70293e8c-2879-4ff2-8ff0-c7b7bbb26a63` | `6d212f4e-f7e9-46c9-beef-5f64aa9944a1` `5c116878-f1f7-4204-9498-62a25b950ed7` `2e1636f4-a91a-4917-a462-37373996180c` `6e6f355a-c89f-43e6-9727-deb7f94cb087` |
| 21:46:28.178 | `f67be432-6212-4e1e-89eb-0f340eb51c64` | `fb03c1cf-24bd-4d1f-bc0d-049811a7c43a` | `250cdaea-03a4-4086-b864-e866f9eafe4c` `fef0fb52-4b46-4d52-a244-735d05718c88` `f1476f5f-f739-4530-85c7-597ee3d8dc84` `382a32ca-8a97-43f6-b007-f8c716f7f1c2` |
| 21:46:54.626 | `aba8d26a-04a5-4761-a92d-55b4ee092c2a` | `43a6c110-4d0a-4d3b-9bad-3227234b9b3f` | `892327c2-685e-4472-87fb-2858c64c07a3` `7a816d68-bafe-4a43-9b63-c6bfdf1bda2f` `4e9219ef-afb7-4053-9a03-2b9893d558cf` `c24877c0-90a2-4c69-beda-032c495b289f` |
| 21:47:33.402 | `65853153-1ba0-4078-afbb-5d6c1a4b81bb` | `66b83fd4-59bc-437c-a595-e56f772f0613` | `1e7528d6-daf9-443b-9507-d3471a3eb9fe` `77ad25d2-8d09-4feb-840d-5a9c042ee199` `6cb0c3ee-e4ef-4e6f-816f-34d03779e242` `b14df2b6-1c21-41b5-a31d-d807d1296075` |
| 21:48:02.967 | `10fd08e0-aef3-4847-b9a1-8cf583ee121e` | `5e2f414d-1de3-4c6f-9984-9522f861ae50` | `e280e352-fb0c-43a1-9f5c-4bbe86db6771` `244b33ca-6865-444a-9eab-6f492c5c4865` `5c6b9614-f032-4cc2-a790-8d27e0c82434` `4f06f5d0-dd07-44cb-bc3a-2ea08f1f34f9` |
| 21:48:30.820 | `5047517e-5a34-463d-9908-5a6ed2706167` | `cf709998-61d4-491e-bc93-274c7d2a21a6` | `7e8f1555-8238-4500-82ea-56bae49618b2` `0406e547-fc01-4287-81fa-f86b3740b101` `c73283ae-f891-416f-8ddb-a9ae5ae883c1` `72e86344-852e-46cd-b8f9-8282568a90f5` |
| 21:48:52.840 | `f2e4ea22-8e9f-4a1a-9af4-5bf9da598f51` | `404a567a-e4c3-4fd9-b933-19c3401eaab8` | `1f346715-7346-4bd5-9ea8-d021901fe99e` `b6aa2130-03a2-4aab-b600-ac7ada95c424` `08ae06d0-d53a-46b9-be4f-790e9ab4aead` `16f4e516-8873-4317-9dbd-144555551d68` |
| 21:49:19.000 | `1da4d530-bbd7-47c1-97a5-7f1678554b8b` | `913b5174-4afe-4dbe-a5ea-84cfc27a1c86` | `2a3ab976-d87a-4231-8d36-f2fc0e2db98d` `e845502c-4c1e-409c-84f5-a8cdde297eea` `c8fa0554-5019-4a6b-a2c9-f4ed9549adf7` `9360f384-32c1-499f-8c63-3b977d37c555` |
| 21:49:44.903 | `ee99f857-5e8d-4ae2-bcfa-e91b03b84046` | `d1523f74-a83c-4c51-b8a6-c3f07846ffbc` | `06244933-cee9-47a8-8215-a69255a07291` `fc12a076-383d-45d4-927e-dced5adcbf9c` `0366d119-fc7f-4cdd-a19f-aef47f751e0f` `e6d619de-cde1-4253-a3c8-705158ee126a` |
| 21:50:11.951 | `053ec9d9-882a-45d2-9d95-539b5e8cf044` | `38e7f250-3518-40e4-b064-ba2179059420` | `d0c1a8fd-353f-450f-929b-1a37345a95fb` `7cdccb6d-5721-479e-8f1a-8719dbe1c897` `96889b48-6cad-45ae-b4f3-5fb0dc2cc4ed` `e14793df-da72-4bd7-b7d3-78e5bfc13157` |
| 21:50:34.047 | `809bc097-cc6f-4d4a-bc50-e59e72034ce4` | `0c45cc0e-d605-425e-8a83-d7162fc3c468` | `26da782e-8f45-4e9a-97a1-2d6793d3df98` `1f687248-ebb7-4016-806d-76e2cb92a3ae` `1b58e037-a35e-40ab-9152-20fdad8b919f` `4c7160c5-07cc-453c-a842-054127329038` |
| 21:51:10.111 | `96368ac5-71b0-4ff6-873f-b435823ab645` | `e5da81eb-dfa9-4725-a41f-0352c640e90c` | `30868edf-9b66-4de7-b1bb-95ce6eb8020e` `d8b77700-5ca6-404a-8b56-5e5ff56c8bab` `4e051c43-c5a1-4707-a38c-13e87b78e519` `08e876a6-80f3-44fd-9200-f69483dae564` |
| 21:51:40.814 | `f86313e3-5c41-4056-887d-5016fc7e9004` | `8ab23cdd-049d-411a-80f2-ac0ccda1bb50` | `9b611037-ba0b-4d49-87e1-4272fb15fe52` `84ee4ddd-e89c-4903-9503-71e5bda9be8d` `e08619d0-8843-46a7-934a-d1ec6b41c727` `a0570a7e-2052-4722-85ca-75edc3066af3` |
| 21:52:06.496 | `e4636a0d-537c-44f6-8682-08f73cbf201a` | `66aab9ab-05e6-4c80-9b87-04dd85381631` | `0452bb6c-7e7f-4f67-8986-c3039a50bd8c` `7e13b205-2648-4d5a-80b1-96ab8b619ba2` `a932d83e-2e8a-437b-9f42-6152cebe76b4` `45236ad2-29f4-40a6-afba-518a0beb0838` |
| 21:52:33.118 | `7f166771-4d9d-4ad3-bfe4-3143b78467a5` | `d84cb669-bf96-44e8-b632-30640f5b60a8` | `4b8a71b6-0dd9-4c20-a5fd-89c295e31d27` `f910ffc6-b80d-41ce-a2bb-06f1679c806c` `7bc3bec1-d704-4472-be0c-a7932ea835e3` `60838fb5-69a0-4423-80df-9a8b69fc607b` |
| 21:52:54.825 | `f63c8a61-a523-4a43-9e3b-580ecc6e3e2b` | `128749b7-689c-4b80-871d-200b654f1be7` | `1551c6f3-da64-4e28-a653-de5ccbbfd1d6` `d94c99ec-cf53-4730-9d82-3220ee1fc8e5` `80aeeda2-cadf-49dc-9cef-09f18a94c6fb` `75855f57-dfad-4e02-807d-faf27df03207` |

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
fetch spans, from: "2026-10-04T21:41:30Z", to: "2026-10-04T21:53:40Z"
| filter session.id == "48e7b0a1-5754-40ef-93a1-4998ae7f8fdd-profile"
| fields start_time, end_time, span.name, trace.id, span.id, service.instance.id, aws.request_id
| sort start_time asc
```

The designer's events for one contact: `node connect/acxd/logs.js <contactId> 3600000 --json`
in guppi-hr.
