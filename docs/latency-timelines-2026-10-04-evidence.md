# Evidence for the latency timelines of 4 October 2026

The ids behind every number in `latency-timelines-2026-10-04.md`: Connect contacts, the designer's
correlation ids, API Gateway and Lambda request ids, X-Ray and Dynatrace trace and span ids,
AgentCore Gateway request ids, runtime session ids, the log stream of each microVM, and the
request ids of the AgentCore Identity calls. The same data, with every step of every turn, is
in `latency-timelines-2026-10-04-evidence.json`.

Account `009080466601`, region `us-east-1`. Window 2026-10-04T20:16:00Z to 2026-10-04T20:34:00Z: 29 chats,
52 turns, no deploys (stack update times were the same before and after; every designer event
carried build `7a4c9ca7-9af5-4919-9785-56ff5823d4e8`). All times are UTC on 4 October 2026.
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
  log carries no Lambda request id; they were 13 to 25 ms apart, starts were seconds apart).

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
| Sub-agent runtimes | `/aws/bedrock-agentcore/runtimes/hr_super_agent_{profile,travel,pay}-*-DEFAULT` | [runtime-logs]<id> stream per microVM; run lines with duration_ms and trace_id |
| Tools runtime | `/aws/bedrock-agentcore/runtimes/hr_super_agent_tools-Ykb6G5FTK1-DEFAULT` | [runtime-logs]<id> stream per microVM; trace_id on each MCP line |
| X-Ray spans | `aws/spans` | chat start and issuer Lambda spans, issuer API Gateway spans |
| Dynatrace | `tenant zfr04910, fetch spans where service.name starts with hr_super_agent` | sub-agent and tools runtime spans: trace.id, span.id, session.id, aws.request_id of Identity calls, gen_ai.* model fields |
| Agentic CX designer | `connect/acxd/logs.js <contactId> --json` | per-turn correlationId, messageId, buildId, model and data request events |

## Tool calls through the tools gateway (A23, time sink 1)

Every snapshot read by a sub-agent: 21 calls, 21 different tools runtime microVMs. Delivery is
from the issuer's answer (the gateway's runtime token) to the tools server's first span;
handshake from that first span to the `tools/call` span; total is the sub-agent's MCP span.

| Time | Contact | Tool | Tools gateway request id | Trace id | Tools runtime microVM (log stream) | Policy ms | Delivery ms | Handshake ms | Tool ms | Total ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20:19:53.766 | `5f22aca7-7997-4941-b9f0-661ee9e5c1df` | hr___get_profile | `228c875a-1d39-435a-9e9a-05c70575073f` | `6ac2b4e75217d1766aef4d9b5f0055cc` | `b73b81cf-78b3-4fcf-bdd3-8d34a5a4b866` | 55 | 808 | 657 | 166 | 2000 |
| 20:20:37.092 | `48e7b0a1-5754-40ef-93a1-4998ae7f8fdd` | hr___get_profile | `d57b806a-7021-4bb1-af4b-5541e2d368f1` | `6ac2b5126beb7ad13c8c647f2041850a` | `b7e8f79e-1d03-4549-bcb8-74ada39ac255` | 53 | 1391 | 582 | 239 | 2589 |
| 20:20:56.764 | `6dfeece8-8827-40b9-9d0f-23d831147306` | hr___get_profile | `878dae5a-af5b-4157-b093-2cb75efeda60` | `6ac2b52653194bc26f962952431d1fe2` | `ebb8b468-1384-485a-8444-4996c72dc555` | 53 | 618 | 680 | 170 | 1889 |
| 20:22:15.663 | `f538cb39-a04d-433b-aed5-468d1aa2e6f5` | hr___get_profile | `0ebbd251-9b38-44ee-af10-2cbea0daf5ac` | `6ac2b5754a9b28dd5b754bc54cdeaa21` | `465d0976-c50b-47e1-ab46-35c11e2546c9` | 49 | 863 | 575 | 177 | 2141 |
| 20:22:34.561 | `cfacb8b9-0358-4598-8aa5-df0f85b0f2c9` | hr___get_profile | `d2826374-d66e-4980-9838-c46b3b50b131` | `6ac2b5887d869bfa42febe1043337710` | `e65c9dc9-e8a8-4ce7-a972-761672ddf780` | 64 | 611 | 611 | 160 | 1769 |
| 20:23:48.617 | `af2494cc-ecd3-4b55-800e-62c40dfb6120` | hr___get_direct_deposit | `9af2178c-1e07-4beb-b937-9b10f84f2fb4` | `6ac2b5d23c227893329f45417948d98e` | `22c29b7d-7d3f-4dd7-9b63-1b1aac7b8a54` | 41 | 787 | 633 | 160 | 1923 |
| 20:23:50.542 | `af2494cc-ecd3-4b55-800e-62c40dfb6120` | hr___list_pay_statements | `fc8be3a5-b365-44b7-899b-142cc941413b` | `6ac2b5d23c227893329f45417948d98e` | `4b65279f-006f-41e7-94de-7f90a9537b5a` | 47 | 557 | 557 | 173 | 1668 |
| 20:24:19.556 | `cda42b04-85ed-478d-b7ca-3a44ae86583f` | hr___get_profile | `2433533f-2460-4824-b80d-d26324be9e58` | `6ac2b5f00b53c16923c54eb20171c4e2` | `e888713a-f03d-4e65-927f-bd5dc28eec9f` | 45 | 747 | 615 | 167 | 1798 |
| 20:24:37.866 | `32f6a73b-e9e3-4a51-b994-616e9ffc5b31` | hr___get_profile | `9c48ca02-350c-44ff-91de-b60e64b75f41` | `6ac2b604201d020446df0e9d562b47ae` | `13662b8b-d525-4cdc-a0b1-c38cf6a239de` | 46 | 744 | 670 | 165 | 1919 |
| 20:25:54.835 | `ec9ce1dc-084b-4e70-9f80-e2e34c76ab32` | hr___get_profile | `351203d2-b6ce-41eb-a3a4-541b976c5226` | `6ac2b651684379356f4a5ca76ba13bb6` | `cd38b45a-2cd8-4ea9-8fdc-ff3bd50e8651` | 57 | 591 | 573 | 161 | 1686 |
| 20:26:12.962 | `73cc55da-9edd-49ed-afd1-24b84d5b57f1` | hr___get_profile | `dca73d83-1879-4d3e-a785-f9bf15f24a11` | `6ac2b663459535d6691379894b6bb9f9` | `5db7bbad-0345-4e7b-af57-08bdbbc560ca` | 48 | 594 | 546 | 158 | 1657 |
| 20:27:25.038 | `dfec37f3-344c-4a68-b2b6-f5a26c4e921c` | hr___get_direct_deposit | `bb932304-bda0-402b-bc22-27689933dcfd` | `6ac2b6aa36f0bb6a78c5befa6589b82e` | `2853aa89-f8a1-4549-b010-080e7fcf1343` | 52 | 764 | 571 | 199 | 1886 |
| 20:27:26.927 | `dfec37f3-344c-4a68-b2b6-f5a26c4e921c` | hr___list_pay_statements | `8675e1b3-48d4-4694-b299-065bfa8c3de4` | `6ac2b6aa36f0bb6a78c5befa6589b82e` | `74e5d067-38e5-46d0-81d6-0cec11ca1403` | 48 | 1267 | 560 | 193 | 2325 |
| 20:27:56.064 | `f776633d-b974-49f8-a83d-552cd0d4add2` | hr___get_profile | `c0271197-525e-4a4a-a0ae-eb2554a6b13d` | `6ac2b6ca3b3501ec5b769d7f4140a555` | `2c19f63f-1fee-4d01-afc2-9181ce6141e3` | 80 | 680 | 633 | 197 | 1929 |
| 20:28:15.386 | `ccdc8c33-8408-4b35-be10-4755bc79138d` | hr___get_profile | `b31cf143-78b0-4a0e-b53b-445edf518b82` | `6ac2b6dd221f8d51478e09b104ee097f` | `eca2c277-b438-438e-a3ee-159a98f5f6cb` | 47 | 708 | 615 | 205 | 1848 |
| 20:29:47.694 | `23afae83-0f81-4c9a-95e3-e30e47ae534b` | hr___get_profile | `1a6010b2-c48d-43c9-8867-6f95614d55ac` | `6ac2b73977149d6846d116f811ab1fac` | `b1367190-d702-4a30-8bee-5085186a3d65` | 41 | 1296 | 547 | 215 | 2396 |
| 20:30:54.739 | `e1e049bf-fb20-43d9-91e9-bd7064b73d07` | hr___get_profile | `f3a3e231-7251-42ee-b20b-50d11c462f6d` | `6ac2b77c2c22bc0101ba4e2e0f6d1012` | `e05fd682-e2a8-435e-bbe5-117d2f4af5e1` | 61 | 679 | 603 | 197 | 1865 |
| 20:31:14.117 | `d8aca622-381c-49ac-aca9-0396caaed7a1` | hr___get_profile | `464e4831-8370-40a0-9db3-8100f9d3585c` | `6ac2b78f35c8a9264419e5840b387696` | `cf14063a-8224-44c9-b38a-482f91881068` | 49 | 575 | 611 | 168 | 1694 |
| 20:32:20.542 | `12fcb31b-c340-40ad-a82a-da7b9057a88f` | hr___get_profile | `c0ad612b-8af4-4660-9a57-5d2d6584e655` | `6ac2b7d207b8d4aa3f7ae58c3490778f` | `7f2769e3-b958-4f45-acb6-bc8e02f76126` | 48 | 747 | 589 | 157 | 1864 |
| 20:32:38.920 | `c660689d-98a0-47fa-ab86-e66a91d9233e` | hr___get_profile | `1b915062-e205-4eec-a266-83f8fac04059` | `6ac2b7e546ced8a5487780e442392414` | `f9edd65a-6206-4377-a428-eb9dfd5cac82` | 54 | 784 | 590 | 157 | 1918 |
| 20:33:44.820 | `83e8cfb2-e30a-492a-8343-1d6df0b4b70f` | hr___get_profile | `cc2da0e9-fe7a-4bcb-8342-45652f54609c` | `6ac2b8274092e69b219e9fdf172d0a67` | `c6a512e8-5170-4b44-96dc-19e4fa63c6d0` | 56 | 658 | 636 | 195 | 1771 |

The runtime token exchange for each call (Identity to the issuer):

| Time | Tools gateway request id | Issuer API Gateway request id | Issuer Lambda request id | X-Ray trace |
| --- | --- | --- | --- | --- |
| 20:19:53.766 | `228c875a-1d39-435a-9e9a-05c70575073f` | `46d08100-c717-4cdd-9029-42a78bebfeb0` | `8e0781e8-bc1e-45bf-8835-645da4a0eb90` | `1-6ac2b4ea-32180c00052b84a22eaad85e` |
| 20:20:37.092 | `d57b806a-7021-4bb1-af4b-5541e2d368f1` | `ef3ff7ab-8663-4a3f-9093-f2fd3a86d6a2` | `cef7e393-ba5c-46e7-8106-8147d43fc4d4` | `1-6ac2b515-0207c2f42758f0eb5bde6df8` |
| 20:20:56.764 | `878dae5a-af5b-4157-b093-2cb75efeda60` | `c9a18cd4-8f06-458e-be2e-1c82f96a3f80` | `dbdee8f6-045b-402e-addd-44c509d3715b` | `1-6ac2b529-6d97622b14d1ab68111b857a` |
| 20:22:15.663 | `0ebbd251-9b38-44ee-af10-2cbea0daf5ac` | `20adb570-efe4-471e-9277-063a37000b97` | `587748fd-32b4-4365-93ab-123ac3701a2e` | `1-6ac2b578-1020bb5f74b3f7a32056e1bd` |
| 20:22:34.561 | `d2826374-d66e-4980-9838-c46b3b50b131` | `601686ca-aaa9-42be-913a-63d088bf393c` | `3bebb028-ae93-43fc-96a9-3d7a79a6132c` | `1-6ac2b58a-2a0df93d4196a598162417d1` |
| 20:23:48.617 | `9af2178c-1e07-4beb-b937-9b10f84f2fb4` | `440c4e28-9e6e-48e1-b301-3e7cb9e6da8e` | `e0c653ac-19f4-488e-81ec-3442c2ef23f8` | `1-6ac2b5d4-65571325387cdf3738e87485` |
| 20:23:50.542 | `fc8be3a5-b365-44b7-899b-142cc941413b` | `6a6dda71-76a6-4bee-9cbb-d000d7de944a` | `ef4dd3b0-63d0-4d3a-9f5a-84091863bbe6` | `1-6ac2b5d6-56bce15a6351aefd776b02eb` |
| 20:24:19.556 | `2433533f-2460-4824-b80d-d26324be9e58` | `2700e244-60d0-4e22-912e-152110e9e162` | `4205db29-9f47-47ea-9c7f-c2cc836895b1` | `1-6ac2b5f3-3b9bde292494c0822173b978` |
| 20:24:37.866 | `9c48ca02-350c-44ff-91de-b60e64b75f41` | `d19082ef-f979-424f-8dae-94e1eb920914` | `f011f493-5f8e-4e11-b851-bbf60f309dab` | `1-6ac2b606-5ed5752b4ad300e71ea1d8c8` |
| 20:25:54.835 | `351203d2-b6ce-41eb-a3a4-541b976c5226` | `dd92b907-e24d-41d2-9e53-ada6041593e1` | `2fb3af39-d2e4-46a4-84e2-62eba201895d` | `1-6ac2b653-020adff47768104641ba9e47` |
| 20:26:12.962 | `dca73d83-1879-4d3e-a785-f9bf15f24a11` | `ffe1ee00-e4dd-4c02-a63c-45448e755f9f` | `f6b8a2cb-98a0-4c42-8758-24fbc4162a1c` | `1-6ac2b665-1171e5bc3893c0577a6db538` |
| 20:27:25.038 | `bb932304-bda0-402b-bc22-27689933dcfd` | `fe21d2c4-15c9-4c77-9143-a6118ca43e1e` | `482f2eac-9a0f-4eb2-b724-4d100aef19cc` | `1-6ac2b6ad-232275df32f9eb156f015341` |
| 20:27:26.927 | `8675e1b3-48d4-4694-b299-065bfa8c3de4` | `ab03829b-e5aa-4d86-b1d7-d32c56e35308` | `e9820a52-c0db-4af6-9932-c654c93393a1` | `1-6ac2b6af-2ea5e7b201bbf3701beaf7d8` |
| 20:27:56.064 | `c0271197-525e-4a4a-a0ae-eb2554a6b13d` | `085229eb-7a82-4838-8764-bb703c2b5eb7` | `8bac9c08-cb0c-46f7-9c69-f4c529ce2fe3` | `1-6ac2b6cc-3ea954634e3a795c098b24bc` |
| 20:28:15.386 | `b31cf143-78b0-4a0e-b53b-445edf518b82` | `5242d93f-6e76-44ad-b312-fd10b3a183e2` | `3418baec-edcb-461d-a56c-1dadb7d0f94d` | `1-6ac2b6df-2499ed8f76d24be85d3709cc` |
| 20:29:47.694 | `1a6010b2-c48d-43c9-8867-6f95614d55ac` | `44851e1a-a990-4b16-969d-2cd9f8cc8813` | `0daf8b57-5a00-4b74-a8fe-2339855a5b10` | `1-6ac2b73b-3a4910142ce19d2204de0745` |
| 20:30:54.739 | `f3a3e231-7251-42ee-b20b-50d11c462f6d` | `d8be6039-2032-4ad1-a384-f279e60048f7` | `2477e1dc-2670-4484-b00d-cefc7c65071c` | `1-6ac2b77f-430a33ea130371955e48faec` |
| 20:31:14.117 | `464e4831-8370-40a0-9db3-8100f9d3585c` | `ea4c2cb2-4737-46f3-96ee-f8b48dab8eae` | `3fa45713-4f22-4886-a519-d8e4e22b3786` | `1-6ac2b792-3e2da20c3ac382d63525838f` |
| 20:32:20.542 | `c0ad612b-8af4-4660-9a57-5d2d6584e655` | `00201e8f-58cf-4c1a-8bbe-e1fdc233e275` | `ca3857b7-b5d2-48c9-91f9-8ebbefd4abcb` | `1-6ac2b7d4-2d57a9de3cd50d715108731e` |
| 20:32:38.920 | `1b915062-e205-4eec-a266-83f8fac04059` | `dc5c5571-44d5-4484-8fa5-c9cf8f7ba780` | `4dc023ed-28db-4bbc-ad85-6089639931b6` | `1-6ac2b7e7-5fd660361c26584100e29b26` |
| 20:33:44.820 | `cc2da0e9-fe7a-4bcb-8342-45652f54609c` | `d3399663-7080-4c52-a06c-36e552c6c426` | `5608c221-da09-452f-8c55-f128b22d0590` | `1-6ac2b829-24667b2a6622b7420a5a6f4c` |

## Sub-agent runtime sessions and microVMs (A21, time sink 2)

Every sub-agent request: 37 requests on 24 sessions, each session on its own microVM. Delivery
is from the agents gateway's "Executing Http request for target" to the sub-agent's `POST /` span.

| Request time | Call | Runtime session id | Agents gateway request id | Gateway trace id | Sub-agent trace id (Dynatrace) | Root span id | MicroVM (log stream) | Process started | Delivery ms | Request ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20:19:52.493 | first | `5f22aca7-7997-4941-b9f0-661ee9e5c1df-profile` | `ff4b203c-2868-47d0-b219-22c67f4f4c0b` | `6ac2b4e7325405e50437276c24a6a429` | `6ac2b4e75217d1766aef4d9b5f0055cc` | `df72a6bf480ebfc9` | `85209ea3-c6ff-4f5a-b3e8-85f8172bcfdb` | 20:08:42.881 | 1276 | 4222 |
| 20:20:01.559 | follow-up | `5f22aca7-7997-4941-b9f0-661ee9e5c1df-profile` | `0b86b9a3-dff5-4870-9d25-5914efd0da55` | `6ac2b4f117ec08ff3b0e772376c93191` | `6ac2b4f16852a71e166d06d8017bd246` | `1c71a10b8714282b` | `85209ea3-c6ff-4f5a-b3e8-85f8172bcfdb` | 20:08:42.881 | 296 | 942 |
| 20:20:35.988 | first | `48e7b0a1-5754-40ef-93a1-4998ae7f8fdd-profile` | `c581bd82-501e-4c29-8012-00da0495131c` | `6ac2b512171c964e606f76cc43035c4a` | `6ac2b5126beb7ad13c8c647f2041850a` | `d6235b9aea403efc` | `c933e99a-0704-4d01-8572-c214ea189c93` | 19:43:33.207 | 1092 | 4522 |
| 20:20:55.517 | first | `6dfeece8-8827-40b9-9d0f-23d831147306-profile` | `19673fe2-cf8a-48e8-bbe2-b5a895c45f0f` | `6ac2b526345ae900280aa4d70936232f` | `6ac2b52653194bc26f962952431d1fe2` | `ac8834fa2f5179ae` | `c7d19aab-6eea-4a4b-bcb3-0bbd98752414` | 19:48:58.828 | 934 | 3937 |
| 20:21:04.326 | follow-up | `6dfeece8-8827-40b9-9d0f-23d831147306-profile` | `65c5fbf9-37a0-4d60-9dc7-08f2aad8939b` | `6ac2b52f344bc8e84fcf589d46d13273` | `6ac2b530465944157f31bf434bb9542b` | `b81a59f3f0dbc95b` | `c7d19aab-6eea-4a4b-bcb3-0bbd98752414` | 19:48:58.828 | 285 | 1806 |
| 20:21:44.373 | first | `e2ceda77-100c-4ea2-bc32-d346935a6fef-travel` | `51291972-ad12-480d-942a-7694d43d95d4` | `6ac2b55751e6f4565cc503fa4dec1e15` | `6ac2b5575d9849fc35cd83a24c1c66dc` | `9a4fefabbbd11c70` | `28024341-8ceb-4000-9b45-002d23788873` | 19:44:04.119 | 1236 | 3816 |
| 20:21:52.708 | follow-up | `e2ceda77-100c-4ea2-bc32-d346935a6fef-travel` | `a4cf9c2f-b40e-4b87-a453-a01cd071be96` | `6ac2b56057587e471661ed5231457a59` | `6ac2b560699716366a05da9767c8ef0a` | `c554e0d531ee9477` | `28024341-8ceb-4000-9b45-002d23788873` | 19:44:04.119 | 274 | 2623 |
| 20:22:14.550 | first | `f538cb39-a04d-433b-aed5-468d1aa2e6f5-profile` | `6471b780-a48a-4247-a71a-6912c61c1c96` | `6ac2b575766c16cf4c02ff396aba190f` | `6ac2b5754a9b28dd5b754bc54cdeaa21` | `fde86e5eb083c8e2` | `02f533e0-ce73-4668-a222-93dea77d6f50` | 19:43:36.630 | 1156 | 4154 |
| 20:22:33.506 | first | `cfacb8b9-0358-4598-8aa5-df0f85b0f2c9-profile` | `f3799126-76e8-4eee-984c-ce42d85271fc` | `6ac2b58864b059601d6e04d93a4aa5bd` | `6ac2b5887d869bfa42febe1043337710` | `b6c7fb062fb4c7cd` | `f4ccc331-33ec-43da-a73d-4fc1af66b49a` | 19:43:36.445 | 780 | 3749 |
| 20:22:41.990 | follow-up | `cfacb8b9-0358-4598-8aa5-df0f85b0f2c9-profile` | `4f8480fc-df26-460e-943a-5dcc7f84b226` | `6ac2b5911dc8aed04f0e87766c523866` | `6ac2b5915767982d60daa5a146743765` | `d72e3deef10ec5d9` | `f4ccc331-33ec-43da-a73d-4fc1af66b49a` | 19:43:36.445 | 246 | 1052 |
| 20:23:20.717 | first | `ed74cbd8-aca6-4173-bcbb-2f4710304965-travel` | `17404d9b-0a5e-40e0-81d9-5d739942f251` | `6ac2b5b771732f9015872813325e6836` | `6ac2b5b7559f08cf1adae9525d2da1e4` | `809671e0ee5c391a` | `c435145e-6372-428a-8c5b-c7533b09eced` | 20:04:05.659 | 1245 | 4404 |
| 20:23:29.983 | follow-up | `ed74cbd8-aca6-4173-bcbb-2f4710304965-travel` | `19e821c2-3e73-426c-8613-5090b38d0a43` | `6ac2b5c12f26881f7b598ea06bde9aad` | `6ac2b5c173b458314161af823cc73b95` | `8447df63f8af7574` | `c435145e-6372-428a-8c5b-c7533b09eced` | 20:04:05.659 | 255 | 2665 |
| 20:23:47.518 | first | `af2494cc-ecd3-4b55-800e-62c40dfb6120-pay` | `64994363-0693-4869-b043-94186cdf7e54` | `6ac2b5d22da4d23120b41f02320fac4a` | `6ac2b5d23c227893329f45417948d98e` | `cec8c1d019e4b32a` | `ba268fe4-711b-4a21-a7d2-5c7173879f84` | 20:04:03.153 | 752 | 5777 |
| 20:23:57.965 | follow-up | `af2494cc-ecd3-4b55-800e-62c40dfb6120-pay` | `32968d25-1f82-434b-94b7-bc49ddf9f44e` | `6ac2b5dd7257ce7a436b17af1bf14e9b` | `6ac2b5dd708fdad64f3f9c5f46aae532` | `043e568dcfb0b0d5` | `ba268fe4-711b-4a21-a7d2-5c7173879f84` | 20:04:03.153 | 276 | 840 |
| 20:24:18.346 | first | `cda42b04-85ed-478d-b7ca-3a44ae86583f-profile` | `8d34f0fe-6692-422e-8f07-fa7eda9aeedf` | `6ac2b5f03ff68cd206beeb8f7181590a` | `6ac2b5f00b53c16923c54eb20171c4e2` | `8e544adbfb8e931c` | `cc2bad57-a601-49d6-9173-eea5e017f657` | 20:03:43.826 | 1494 | 3820 |
| 20:24:36.835 | first | `32f6a73b-e9e3-4a51-b994-616e9ffc5b31-profile` | `1b64aef2-593e-451f-87bf-243f730ed337` | `6ac2b604077fa2817211a12441352c19` | `6ac2b604201d020446df0e9d562b47ae` | `ee34200b7fa14654` | `3afd41e4-c188-4e29-a39c-a87ad7f6e5c1` | 20:23:08.221 | 637 | 3780 |
| 20:24:45.281 | follow-up | `32f6a73b-e9e3-4a51-b994-616e9ffc5b31-profile` | `ec36f90a-2b00-40f0-8794-1931ed5aa9a2` | `6ac2b60c4ba6c06016ba8bfa437e44a2` | `6ac2b60d20ca291e05899a9b20f69028` | `bb5309443325bb0a` | `3afd41e4-c188-4e29-a39c-a87ad7f6e5c1` | 20:23:08.221 | 287 | 916 |
| 20:25:23.713 | first | `ae9113a3-b377-4aad-8d7a-c1b2e9a20ed9-travel` | `e3cd814c-6cf4-4275-8a52-976dcbb906f9` | `6ac2b63274e921376d90a66b487e003f` | `6ac2b63212c1559928c39b1068d88018` | `270d45c44cf74b63` | `eb0c4ef7-c1c8-4d6b-9e95-35d89873af46` | 20:04:03.813 | 826 | 4836 |
| 20:25:33.059 | follow-up | `ae9113a3-b377-4aad-8d7a-c1b2e9a20ed9-travel` | `120b07fa-a0ad-47c0-8b33-a9c9a07f86f9` | `6ac2b63c3d3e5d610336eea30657d643` | `6ac2b63c5bf7da85647ec3cb57e63004` | `f3d3e1a04fa1ee88` | `eb0c4ef7-c1c8-4d6b-9e95-35d89873af46` | 20:04:03.813 | 271 | 1972 |
| 20:25:53.722 | first | `ec9ce1dc-084b-4e70-9f80-e2e34c76ab32-profile` | `21965ed9-65c4-4af5-98c6-504e9e5693b7` | `6ac2b65147560d320feaafde1ea6b0fc` | `6ac2b651684379356f4a5ca76ba13bb6` | `b2b5b6bbb576f969` | `843682b9-884a-4469-8c7a-5dd19cb8c62a` | 20:22:45.384 | 562 | 3600 |
| 20:26:11.865 | first | `73cc55da-9edd-49ed-afd1-24b84d5b57f1-profile` | `26b1e6b7-0e42-4a6d-a11a-dfa30cb45a11` | `6ac2b663559fa5597a43dbd5192c1704` | `6ac2b663459535d6691379894b6bb9f9` | `ec243d9771b66b58` | `c24821ff-4cb9-4c99-a4e7-7231eb22be77` | 20:24:31.526 | 608 | 3563 |
| 20:26:19.897 | follow-up | `73cc55da-9edd-49ed-afd1-24b84d5b57f1-profile` | `71a4d6ef-2e84-4833-9b6a-ac3f619fed04` | `6ac2b66b582d2b337f62bd3a39481ab9` | `6ac2b66b2da8da264f9c691677f4fc64` | `bc12fea3a5184719` | `c24821ff-4cb9-4c99-a4e7-7231eb22be77` | 20:24:31.526 | 303 | 936 |
| 20:26:58.141 | first | `5d7149af-22f4-4024-abd2-a78a6b9fe5be-travel` | `bfcc3bf4-a839-4988-94ad-4e1d072a766d` | `6ac2b69133596dd31fd6b8c359282a8f` | `6ac2b6913a68024a47fcab4e56d099a5` | `e8b89278be487ce8` | `a6151dd4-f77b-460d-b7b4-328ae850311b` | 20:14:44.287 | 844 | 3395 |
| 20:27:06.045 | follow-up | `5d7149af-22f4-4024-abd2-a78a6b9fe5be-travel` | `1f37de90-aaa9-4076-b257-fce5accad980` | `6ac2b699182a7c0c2e6050e77673abd5` | `6ac2b699366c62057190588b6fc3d875` | `42e07ebc1f8a71a9` | `a6151dd4-f77b-460d-b7b4-328ae850311b` | 20:14:44.287 | 270 | 2880 |
| 20:27:23.758 | first | `dfec37f3-344c-4a68-b2b6-f5a26c4e921c-pay` | `2c65d7c8-65c8-47fe-a689-93bf220085e8` | `6ac2b6aa310fcce23b0963da060927c0` | `6ac2b6aa36f0bb6a78c5befa6589b82e` | `dccfb72bbc27a6ee` | `dce66719-9868-4794-be1c-006eab8600b2` | 20:24:43.561 | 964 | 6922 |
| 20:27:35.295 | follow-up | `dfec37f3-344c-4a68-b2b6-f5a26c4e921c-pay` | `aa300fe8-6120-4010-96ea-a804da806aa2` | `6ac2b6b61858eb0258018bd9070cc97d` | `6ac2b6b75a4925ad72a288b55c4a24c4` | `79de7c5e3ee5e50f` | `dce66719-9868-4794-be1c-006eab8600b2` | 20:24:43.561 | 282 | 852 |
| 20:27:55.012 | first | `f776633d-b974-49f8-a83d-552cd0d4add2-profile` | `1499753a-9259-448c-99ff-a20a024af99c` | `6ac2b6ca51a27a8d3a7df5656d3ca352` | `6ac2b6ca3b3501ec5b769d7f4140a555` | `6f40cf8f0ddbbb50` | `8d77a819-d0d3-4549-a6b9-0a9ea9867c6e` | 20:26:20.283 | 577 | 4272 |
| 20:28:14.257 | first | `ccdc8c33-8408-4b35-be10-4755bc79138d-profile` | `4c9094d2-101d-4e8f-9a3f-674477cbbcfa` | `6ac2b6dd0ad7a76a13fc7e17063c3df4` | `6ac2b6dd221f8d51478e09b104ee097f` | `18c39ec686b7a04b` | `03c4586a-d09e-4fb4-9eb0-36e8be585c8a` | 19:48:56.226 | 807 | 3789 |
| 20:28:22.595 | follow-up | `ccdc8c33-8408-4b35-be10-4755bc79138d-profile` | `b8fd7310-2bff-44ca-9d4e-dbf0bc3d97cb` | `6ac2b6e6466e810730ebf7605d5dc65b` | `6ac2b6e65140b72409107c8245185619` | `0211787aa520234f` | `03c4586a-d09e-4fb4-9eb0-36e8be585c8a` | 19:48:56.226 | 291 | 1599 |
| 20:29:01.455 | first | `770f8eb9-0b88-4376-aae0-a322cac770e8-travel` | `59a71b95-631c-49e6-852b-8f7c8eb55e97` | `6ac2b70c2bedc6d61b99f5e31aebd6d4` | `6ac2b70c36b6f70a0d3818aa5e1bcd63` | `25963fe17b0d29c6` | `cad02b2a-604a-4b36-b7d9-87e7390b33b1` | 20:22:24.382 | 1250 | 4346 |
| 20:29:10.336 | follow-up | `770f8eb9-0b88-4376-aae0-a322cac770e8-travel` | `2280229f-b5c4-42c0-bc88-e4950a644a03` | `6ac2b715389e189126dc75c065679d6d` | `6ac2b71650ea7ebd7f25a3580b5337cb` | `45b18f8ce82b5d58` | `cad02b2a-604a-4b36-b7d9-87e7390b33b1` | 20:22:24.382 | 272 | 2658 |
| 20:29:46.498 | first | `23afae83-0f81-4c9a-95e3-e30e47ae534b-profile` | `b1189b6a-e9d8-48e8-a107-04f5e38aa284` | `6ac2b739051ac389485ea3492902005a` | `6ac2b73977149d6846d116f811ab1fac` | `b1f0498a19c316f0` | `09f3edeb-47c6-4164-9400-f0f477eb79c5` | 20:21:26.592 | 1243 | 4442 |
| 20:30:53.547 | first | `e1e049bf-fb20-43d9-91e9-bd7064b73d07-profile` | `5c791ee6-69ed-417a-88fd-5b1cb408d98e` | `6ac2b77c236067bf0fdf66236bda0a49` | `6ac2b77c2c22bc0101ba4e2e0f6d1012` | `19d77b9ed7884578` | `fac41c62-bf8b-464c-bc23-d52c4816cd2a` | 20:24:29.588 | 933 | 3860 |
| 20:31:12.958 | first | `d8aca622-381c-49ac-aca9-0396caaed7a1-profile` | `948b770d-8b0a-48db-9ff6-ac1e06cc57f3` | `6ac2b78f70a795db79826d8f2e09c00a` | `6ac2b78f35c8a9264419e5840b387696` | `74d2e72afcd4d57d` | `36eaa1c3-b873-49e9-8c64-a9620fc2af88` | 20:19:01.839 | 1361 | 3669 |
| 20:32:19.316 | first | `12fcb31b-c340-40ad-a82a-da7b9057a88f-profile` | `80f28222-a681-41cd-b850-49ffbc870420` | `6ac2b7d11bd921a141253228007fe669` | `6ac2b7d207b8d4aa3f7ae58c3490778f` | `f1376b723894640c` | `5a55c8fa-1778-4492-849f-8ec13d0bec94` | 20:08:43.832 | 1249 | 3988 |
| 20:32:37.826 | first | `c660689d-98a0-47fa-ab86-e66a91d9233e-profile` | `0e5d07d2-8853-4d22-9778-961586e6df2f` | `6ac2b7e51dbcd4d756acfb775cefdcc0` | `6ac2b7e546ced8a5487780e442392414` | `dc953d594ea9a03c` | `1f57c180-4477-490f-9707-a35b22a7cbdc` | 20:29:53.532 | 592 | 3834 |
| 20:33:43.762 | first | `83e8cfb2-e30a-492a-8343-1d6df0b4b70f-profile` | `2c6e8b40-0fcd-492a-a10b-6dce53abc0a7` | `6ac2b826174525cf353aea507725f9a8` | `6ac2b8274092e69b219e9fdf172d0a67` | `5d616ea38ecd1a9e` | `e118c96f-b923-4d2b-96d9-ebacfd51e0c8` | 20:26:21.234 | 706 | 3632 |

### The reuse pairs

Pairs of chats 66 s apart, same question, same employee. Each chat got its own session and microVM.

| Click | Contact | Chat | MicroVM (log stream) | Delivery ms | Sub-agent request ms |
| --- | --- | --- | --- | --- | --- |
| 20:29:44.167 | `23afae83-0f81-4c9a-95e3-e30e47ae534b` | reuse 0 A | `09f3edeb-47c6-4164-9400-f0f477eb79c5` | 1243 | 4442 |
| 20:30:51.477 | `e1e049bf-fb20-43d9-91e9-bd7064b73d07` | reuse 0 B | `fac41c62-bf8b-464c-bc23-d52c4816cd2a` | 933 | 3860 |
| 20:31:10.495 | `d8aca622-381c-49ac-aca9-0396caaed7a1` | reuse 1 A | `36eaa1c3-b873-49e9-8c64-a9620fc2af88` | 1361 | 3669 |
| 20:32:17.081 | `12fcb31b-c340-40ad-a82a-da7b9057a88f` | reuse 1 B | `5a55c8fa-1778-4492-849f-8ec13d0bec94` | 1249 | 3988 |
| 20:32:36.285 | `c660689d-98a0-47fa-ab86-e66a91d9233e` | reuse 2 A | `1f57c180-4477-490f-9707-a35b22a7cbdc` | 592 | 3834 |
| 20:33:42.084 | `83e8cfb2-e30a-492a-8343-1d6df0b4b70f` | reuse 2 B | `e118c96f-b923-4d2b-96d9-ebacfd51e0c8` | 706 | 3632 |

## AgentCore Identity calls in the sub-agents (time sink 4)

The first request on each session: the workload access token, then the on-behalf-of exchange
for the tools token. Request ids are AgentCore Identity's `aws.request_id` from the botocore spans.

| Time | Runtime session id | GetWorkloadAccessTokenForJWT request id | ms | GetResourceOauth2Token request id | Credential provider | ms | Issuer API Gateway request id | Issuer Lambda request id |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20:19:52.748 | `5f22aca7-7997-4941-b9f0-661ee9e5c1df-profile` | `d611247a-d186-43d3-95c1-a58a92910152` | 66 | `c9e0c9ab-5636-47ec-9b71-076526312d48` | guppi-obo-hr-agent-profile | 150 | `945724a4-05ca-47e4-b650-8f6956a6a0f7` | `1df81a72-7843-475e-a6c0-d4d6197b4234` |
| 20:20:36.207 | `48e7b0a1-5754-40ef-93a1-4998ae7f8fdd-profile` | `d1e166dc-0efb-4668-8d86-6bf7b632f15e` | 59 | `557f8201-a8c5-4a61-902c-e97a275a4040` | guppi-obo-hr-agent-profile | 170 | `0d28802e-9eb7-4261-bf2e-462a97e0faf6` | `20b6b6e8-feb5-43e6-92c8-252a48fe9669` |
| 20:20:55.768 | `6dfeece8-8827-40b9-9d0f-23d831147306-profile` | `de0f8fd7-4276-406f-81d7-781c5750de94` | 58 | `fe4a87c1-8ce0-46e9-b640-c62c1a30fa10` | guppi-obo-hr-agent-profile | 149 | `6e53b140-c4df-4589-b861-773fccd64ac9` | `ef9129d0-4562-4029-ac7c-3aa56506e2f1` |
| 20:21:44.632 | `e2ceda77-100c-4ea2-bc32-d346935a6fef-travel` | `446530ab-3761-4a1e-97a2-12d51358e9d9` | 67 | `638921b4-3632-46a0-bcf6-6b3e75c5d45e` | guppi-obo-hr-agent-travel | 141 | `ceb3371f-8adf-44c4-8af7-bbb7f9d468b6` | `bdf4ea68-1561-4f5e-aa5b-5cf06ae17bd8` |
| 20:22:14.750 | `f538cb39-a04d-433b-aed5-468d1aa2e6f5-profile` | `caf68362-84e5-4a7f-9232-5ff999fa6386` | 67 | `e1292248-1c24-4182-9b60-2a96cc9e21ab` | guppi-obo-hr-agent-profile | 176 | `fbca63da-9cdd-4a3b-a4b8-0ec3e132d785` | `0a664609-6317-4b11-ab84-09633a0ce107` |
| 20:22:33.721 | `cfacb8b9-0358-4598-8aa5-df0f85b0f2c9-profile` | `2509b134-b2a3-4a15-8a38-adb71208bcbe` | 66 | `5f457d99-9701-4ce0-acfc-9651a0800686` | guppi-obo-hr-agent-profile | 157 | `7776aafa-19c1-446c-bdfb-5d71aa872546` | `23b2f138-74ed-4fae-8ff8-72d1a237c5ed` |
| 20:23:20.966 | `ed74cbd8-aca6-4173-bcbb-2f4710304965-travel` | `54bcc009-ac9a-400e-9fab-7c85b72e262e` | 59 | `bc2237f8-5a66-4060-960d-1a7fe0951c76` | guppi-obo-hr-agent-travel | 184 | `1ec2001f-360a-44a3-b466-0435cab4faa1` | `960e5dd8-2431-495f-aa0a-14f14a17d551` |
| 20:23:47.721 | `af2494cc-ecd3-4b55-800e-62c40dfb6120-pay` | `36914058-72d7-43aa-b98b-73f429dba7ec` | 75 | `b94f93c3-8122-4763-bdf9-83fb48af46f0` | guppi-obo-hr-agent-pay | 148 | `37bdef54-4805-4f4b-ae61-3a801ef4cfb2` | `9d45a7d8-bf09-4179-8cec-d19a0413076c` |
| 20:24:18.594 | `cda42b04-85ed-478d-b7ca-3a44ae86583f-profile` | `24d6a4ff-21c7-404e-99dc-742bc65237d5` | 62 | `cb0922ed-d829-4b75-921d-d285df898702` | guppi-obo-hr-agent-profile | 141 | `665db270-6409-4525-91f5-84c7c7f17064` | `f9c0486d-2c94-48c2-aee1-2c2e54ddf234` |
| 20:24:37.034 | `32f6a73b-e9e3-4a51-b994-616e9ffc5b31-profile` | `b8b8f46e-856a-40a9-8b97-999e7c5f95fc` | 63 | `9e3098c4-07f8-4e6e-bc5b-2a3b99230172` | guppi-obo-hr-agent-profile | 132 |  | `8b97a4a5-e7db-40c5-8d8b-5d71e695f5c4` |
| 20:25:23.922 | `ae9113a3-b377-4aad-8d7a-c1b2e9a20ed9-travel` | `71a76ac8-40c0-462c-bf62-ae8c869509a4` | 65 | `c80a84ca-3d2f-4806-9a01-ba606f36041a` | guppi-obo-hr-agent-travel | 174 | `daeb09c9-0ca3-4413-a763-5dcbc75366f6` | `b6479fc9-31f9-4930-9f12-9225f3c6c8e2` |
| 20:25:53.921 | `ec9ce1dc-084b-4e70-9f80-e2e34c76ab32-profile` | `0c881d53-d182-4304-a5f5-3a7a3967efc9` | 59 | `13ea5ce0-9565-4f2d-9a7c-7ff6b8494ac3` | guppi-obo-hr-agent-profile | 156 | `e19d9b87-34a7-49da-8b4d-8880732fd71b` | `187a13fb-4538-4276-834e-1740870a5ea7` |
| 20:26:12.073 | `73cc55da-9edd-49ed-afd1-24b84d5b57f1-profile` | `1df5ce15-f26a-41e3-9a8d-97f23679b08a` | 55 | `11024454-a40d-4888-a456-130f658acb12` | guppi-obo-hr-agent-profile | 158 | `b3f4a126-3cd8-424e-b849-448aa5cff753` | `2fec23a3-365b-48e7-948b-41c80027aac9` |
| 20:26:58.356 | `5d7149af-22f4-4024-abd2-a78a6b9fe5be-travel` | `195cc31a-c549-4a97-ada8-69b9bf6002de` | 68 | `04637319-5f73-4ab6-af6c-e44c481fef7a` | guppi-obo-hr-agent-travel | 158 | `37899cbc-f763-4963-b511-b0e56d833296` | `c7ceec12-5454-4237-b667-5b2eac68acab` |
| 20:27:24.032 | `dfec37f3-344c-4a68-b2b6-f5a26c4e921c-pay` | `a9cc1d3f-3021-4949-9ba6-259b58bb03a6` | 55 | `6e15d2b9-8da1-44a4-9e16-9f25531e5d26` | guppi-obo-hr-agent-pay | 154 | `0f550d42-e55f-4d1b-af8c-40a452001d3b` | `af07743a-cc23-4982-9714-3cd4b2388074` |
| 20:27:55.214 | `f776633d-b974-49f8-a83d-552cd0d4add2-profile` | `9569a41b-97c8-4428-9bfd-69f5017fed8b` | 54 | `53de7499-4cdc-4d38-a837-925a6c62ee85` | guppi-obo-hr-agent-profile | 186 | `c217dabc-f3e3-409c-b191-ec76ed37aa9f` | `2fbca45c-2ca5-4b90-a9ee-7e4f390aa959` |
| 20:28:14.494 | `ccdc8c33-8408-4b35-be10-4755bc79138d-profile` | `3b005cf4-b527-4e4b-9f59-4ed36129c3cd` | 54 | `2a5a6c73-b025-4f63-acfa-9f7fe87383e2` | guppi-obo-hr-agent-profile | 154 | `7ee3b7e7-b2b1-44bf-a691-401b4447233f` | `221f342f-0821-4d17-b1bf-6b542cca2075` |
| 20:29:01.715 | `770f8eb9-0b88-4376-aae0-a322cac770e8-travel` | `1884d3d3-38bf-4520-a182-2fb58cc4dfb7` | 71 | `947ad7fb-ea03-428f-91a0-63a55eb673ca` | guppi-obo-hr-agent-travel | 171 | `ec735b64-6399-4abc-8070-28247ce3529c` | `1b730d10-0fa3-4021-b670-8308d15cb6cc` |
| 20:29:46.749 | `23afae83-0f81-4c9a-95e3-e30e47ae534b-profile` | `d71d4077-7747-415c-90b5-d6bbda9e331a` | 57 | `1b4c50d1-bd5c-4364-bfc9-15a147f4a7f0` | guppi-obo-hr-agent-profile | 137 | `0993a95b-b630-4208-9297-b35e5750a9bb` | `4dc7af96-15fc-489f-b58e-5e7b80122682` |
| 20:30:53.803 | `e1e049bf-fb20-43d9-91e9-bd7064b73d07-profile` | `d27e2d48-b9da-452a-89db-af1cb3c62879` | 71 | `2ffee2a9-ef97-4f5a-abe6-49892644916b` | guppi-obo-hr-agent-profile | 165 | `02de7392-0904-48b2-9cad-141fa443d31a` | `7fabf06b-e4e7-4159-a78b-b209bec23aba` |
| 20:31:13.214 | `d8aca622-381c-49ac-aca9-0396caaed7a1-profile` | `9c799cc9-c185-4e2a-b819-1910dd6137b7` | 61 | `fd4a9d33-20d8-44d3-b1cc-cce5eb23a07f` | guppi-obo-hr-agent-profile | 151 | `fcafc664-3db1-4df4-a5c6-e72aab2960d5` | `cdd1e722-00f2-4da1-8caa-b63e6aa74511` |
| 20:32:19.566 | `12fcb31b-c340-40ad-a82a-da7b9057a88f-profile` | `2e825562-bf51-488b-b196-e8fe2167c476` | 64 | `a6a847e7-02f6-4bf9-93f6-a9982120299d` | guppi-obo-hr-agent-profile | 158 | `ab24cf28-47fc-4801-96a5-02f1078d978d` | `927fd1b4-911d-4c6f-b714-13b9a5da7f5f` |
| 20:32:38.025 | `c660689d-98a0-47fa-ab86-e66a91d9233e-profile` | `ffe99d94-6cd7-4e98-802d-528d6e8430fc` | 59 | `0f6d4407-5f8d-4627-9033-0b6ff1c51639` | guppi-obo-hr-agent-profile | 158 | `9025b943-cf30-483b-b20c-7dad01654849` | `87c1799c-0bc5-4314-b1ac-5a0672df6ee0` |
| 20:33:43.965 | `83e8cfb2-e30a-492a-8343-1d6df0b4b70f-profile` | `0a59fccf-56ab-44f8-a19a-6be76c6280c7` | 59 | `6a508705-977b-44f5-9ee8-ce5cadfa6da3` | guppi-obo-hr-agent-profile | 166 | `3357efb9-280f-458b-a9df-8293f979f44a` | `6e1f2960-5e7b-42de-850d-ab90580f6209` |

## MCP setup calls through the tools gateway (time sink 4)

The `initialize`, `notifications/initialized` and `tools/list` of each new session.

| Time | Runtime session id | Method | Tools gateway request id | Sub-agent span id | ms |
| --- | --- | --- | --- | --- | --- |
| 20:19:53.344 | `5f22aca7-7997-4941-b9f0-661ee9e5c1df-profile` | initialize | `12344b5e-2574-48c7-b640-61f1db4ebb4d` | `805a569503e13a18` | 119 |
| 20:19:53.466 | `5f22aca7-7997-4941-b9f0-661ee9e5c1df-profile` | notifications/initialized | `5b32f36a-de12-4620-b8f8-89a9a4ce33b5` | `7276a5f06a595209` | 90 |
| 20:19:53.558 | `5f22aca7-7997-4941-b9f0-661ee9e5c1df-profile` | tools/list | `c68ffa70-c7e4-45ad-85b4-493bffb12810` | `07ed0521a6ac0cc6` | 205 |
| 20:20:36.717 | `48e7b0a1-5754-40ef-93a1-4998ae7f8fdd-profile` | initialize | `10c920bf-c5ee-44c9-aba8-90e7e99bc695` | `ee85ebc37a683836` | 100 |
| 20:20:36.820 | `48e7b0a1-5754-40ef-93a1-4998ae7f8fdd-profile` | notifications/initialized | `cfe15489-dd34-4941-ba75-d8fb311e6c20` | `9b03ae984c60b2ea` | 91 |
| 20:20:36.913 | `48e7b0a1-5754-40ef-93a1-4998ae7f8fdd-profile` | tools/list | `86d6590a-663e-4f59-9d8a-4a1d1bed16b0` | `8cc90ba805d7146e` | 177 |
| 20:20:56.363 | `6dfeece8-8827-40b9-9d0f-23d831147306-profile` | initialize | `98958cfa-2871-4055-9431-ba06530c8166` | `c2ba51f15b90478b` | 110 |
| 20:20:56.476 | `6dfeece8-8827-40b9-9d0f-23d831147306-profile` | notifications/initialized | `7bb70466-4b6a-4abd-9e28-60b5a49653e8` | `e5cc9a99f7db8a27` | 95 |
| 20:20:56.573 | `6dfeece8-8827-40b9-9d0f-23d831147306-profile` | tools/list | `4867e5d6-3319-4e86-b6f5-f1f2cb3a48f8` | `17581566365cdd7a` | 188 |
| 20:21:45.221 | `e2ceda77-100c-4ea2-bc32-d346935a6fef-travel` | initialize | `a32a7743-da83-4c32-bf56-e0a25a117bad` | `18252bf29fa7d35b` | 88 |
| 20:21:45.313 | `e2ceda77-100c-4ea2-bc32-d346935a6fef-travel` | notifications/initialized | `d00ab462-c2fb-4ce1-b23f-5c608e89b7ec` | `002967a80b936cc5` | 79 |
| 20:21:45.394 | `e2ceda77-100c-4ea2-bc32-d346935a6fef-travel` | tools/list | `0b7937ce-91ec-4633-96e2-347fd30038bd` | `fce1ef4b44a39c44` | 167 |
| 20:22:15.283 | `f538cb39-a04d-433b-aed5-468d1aa2e6f5-profile` | initialize | `8c86e2c4-ad21-4911-b49d-b76907711994` | `9df93a28f05e94fb` | 99 |
| 20:22:15.385 | `f538cb39-a04d-433b-aed5-468d1aa2e6f5-profile` | notifications/initialized | `9873bbd5-4f0d-46de-9c54-447cad69e2a1` | `9ba38b69ca3d8bd0` | 80 |
| 20:22:15.466 | `f538cb39-a04d-433b-aed5-468d1aa2e6f5-profile` | tools/list | `dd471af0-b9b7-46cf-9314-92228de3483b` | `1e470736375fae62` | 195 |
| 20:22:34.217 | `cfacb8b9-0358-4598-8aa5-df0f85b0f2c9-profile` | initialize | `e6bbb87f-002b-44c5-8007-3724c9e2dacc` | `d40b0c81ecb3a3d0` | 112 |
| 20:22:34.332 | `cfacb8b9-0358-4598-8aa5-df0f85b0f2c9-profile` | notifications/initialized | `c6eaf49b-c375-4f79-a8a5-25ca0cf3cfc4` | `c8fa35684be02cd9` | 29 |
| 20:22:34.363 | `cfacb8b9-0358-4598-8aa5-df0f85b0f2c9-profile` | tools/list | `d1b02577-379f-4a56-9b1c-ed0767a17c55` | `813056b5a84a050c` | 195 |
| 20:23:21.588 | `ed74cbd8-aca6-4173-bcbb-2f4710304965-travel` | initialize | `45ee4c70-e240-49c0-b68f-c8c3bde00525` | `80c039eb912b1b4e` | 101 |
| 20:23:21.692 | `ed74cbd8-aca6-4173-bcbb-2f4710304965-travel` | notifications/initialized | `41bf1afa-487d-4d5b-9208-85b8d5524c35` | `a5c6ab1bb354e27f` | 84 |
| 20:23:21.778 | `ed74cbd8-aca6-4173-bcbb-2f4710304965-travel` | tools/list | `f8763ebc-6f0e-4b60-b054-6b0be491733f` | `bb8c3aa38d749610` | 211 |
| 20:23:48.219 | `af2494cc-ecd3-4b55-800e-62c40dfb6120-pay` | initialize | `03a8a60d-e2e0-4229-bbb7-279ea160da9b` | `bbbeb5b157aea3ad` | 102 |
| 20:23:48.324 | `af2494cc-ecd3-4b55-800e-62c40dfb6120-pay` | notifications/initialized | `3da0dd60-1a25-4e79-b05b-0f109d28524e` | `e83d545401f078f0` | 76 |
| 20:23:48.402 | `af2494cc-ecd3-4b55-800e-62c40dfb6120-pay` | tools/list | `1a9101b4-d9c9-4324-9737-b49ae674cc51` | `8b552af9a13916d8` | 212 |
| 20:24:19.188 | `cda42b04-85ed-478d-b7ca-3a44ae86583f-profile` | initialize | `218546f6-c520-480d-b4b2-41db42511652` | `7079ae88b1f078c3` | 93 |
| 20:24:19.285 | `cda42b04-85ed-478d-b7ca-3a44ae86583f-profile` | notifications/initialized | `c407d8d0-e3ba-45a6-96a3-0897515f2e51` | `1702e3f608109c98` | 98 |
| 20:24:19.385 | `cda42b04-85ed-478d-b7ca-3a44ae86583f-profile` | tools/list | `022aab2e-1e08-4a6c-bf4e-fc473c0386ec` | `14b21ae43c769bef` | 167 |
| 20:24:37.511 | `32f6a73b-e9e3-4a51-b994-616e9ffc5b31-profile` | initialize | `c2742b3a-d506-454c-b3b8-291d85f3fcfc` | `4c163e97b0d6c057` | 98 |
| 20:24:37.613 | `32f6a73b-e9e3-4a51-b994-616e9ffc5b31-profile` | notifications/initialized | `35373c03-9f36-4fba-9d76-fac683dadd8e` | `ac908df1f84dd2dc` | 87 |
| 20:24:37.701 | `32f6a73b-e9e3-4a51-b994-616e9ffc5b31-profile` | tools/list | `af007370-d897-4fc2-a62b-99a8d461bb7e` | `d866673e58307b81` | 162 |
| 20:25:24.442 | `ae9113a3-b377-4aad-8d7a-c1b2e9a20ed9-travel` | initialize | `d6031d71-a184-44ac-bd5a-6ceeb4d0da2f` | `65ae9619d83f2f5c` | 100 |
| 20:25:24.545 | `ae9113a3-b377-4aad-8d7a-c1b2e9a20ed9-travel` | notifications/initialized | `3114897e-c1d3-49de-b672-05845ee2d24c` | `16cd3309fa41fc33` | 60 |
| 20:25:24.607 | `ae9113a3-b377-4aad-8d7a-c1b2e9a20ed9-travel` | tools/list | `05b8cc9e-cfec-4b03-82f6-8ac6efa6345f` | `d33a9aa2d14056fd` | 182 |
| 20:25:54.446 | `ec9ce1dc-084b-4e70-9f80-e2e34c76ab32-profile` | initialize | `1bac5004-34c4-4e99-afa0-cc528cdd6f7d` | `e6fcfe9abfc0ecba` | 135 |
| 20:25:54.584 | `ec9ce1dc-084b-4e70-9f80-e2e34c76ab32-profile` | notifications/initialized | `2689c288-e11a-4ace-830e-5c70efba82c7` | `a994d2e7162f535d` | 58 |
| 20:25:54.644 | `ec9ce1dc-084b-4e70-9f80-e2e34c76ab32-profile` | tools/list | `0aaeb78b-b7ca-42fd-b697-ef6585fab8cf` | `48ee1236075a256a` | 188 |
| 20:26:12.601 | `73cc55da-9edd-49ed-afd1-24b84d5b57f1-profile` | initialize | `3ac937ec-a518-4934-bf2b-5e71cebcde81` | `2671a73a4ae2c9f3` | 92 |
| 20:26:12.695 | `73cc55da-9edd-49ed-afd1-24b84d5b57f1-profile` | notifications/initialized | `421d943d-b814-424a-a7ee-72bc71546e2b` | `a32ef0980fb58335` | 69 |
| 20:26:12.767 | `73cc55da-9edd-49ed-afd1-24b84d5b57f1-profile` | tools/list | `ee9caca7-5106-4c12-bfc3-924f60039a6b` | `d7ce54bc96787f97` | 192 |
| 20:26:58.855 | `5d7149af-22f4-4024-abd2-a78a6b9fe5be-travel` | initialize | `1fe95cd5-c4b0-439c-8dd3-71dd7ef3f6da` | `2b80809567b34683` | 71 |
| 20:26:58.929 | `5d7149af-22f4-4024-abd2-a78a6b9fe5be-travel` | notifications/initialized | `e8fec591-a655-4ec5-a1c8-76846e761fa5` | `974c901413f2a992` | 25 |
| 20:26:58.955 | `5d7149af-22f4-4024-abd2-a78a6b9fe5be-travel` | tools/list | `f8ccb9c5-47d4-4f37-bf20-35c7a897c7ba` | `1e0256d44672e1c5` | 162 |
| 20:27:24.640 | `dfec37f3-344c-4a68-b2b6-f5a26c4e921c-pay` | initialize | `51635c1a-a249-41e1-bb83-fdab25e78d65` | `b8eceea9e66d6e48` | 95 |
| 20:27:24.740 | `dfec37f3-344c-4a68-b2b6-f5a26c4e921c-pay` | notifications/initialized | `f91a69d1-d825-4589-ac91-a35c101a70a9` | `bd9a0e2274979d0e` | 87 |
| 20:27:24.830 | `dfec37f3-344c-4a68-b2b6-f5a26c4e921c-pay` | tools/list | `3e273f90-a566-4d69-be17-64a834a68d5e` | `532b6ea6fc50f522` | 205 |
| 20:27:55.734 | `f776633d-b974-49f8-a83d-552cd0d4add2-profile` | initialize | `541fc793-8dad-4529-920c-b14bf1e3d104` | `fdc0f21cb8c11db9` | 78 |
| 20:27:55.816 | `f776633d-b974-49f8-a83d-552cd0d4add2-profile` | notifications/initialized | `8838fecf-ebbd-46e5-a5a7-96caa9137b12` | `30a1511ea33d7697` | 73 |
| 20:27:55.890 | `f776633d-b974-49f8-a83d-552cd0d4add2-profile` | tools/list | `00d19c1a-56ce-41c8-9353-497ce71f12dc` | `79f82bac5cd5804a` | 171 |
| 20:28:15.012 | `ccdc8c33-8408-4b35-be10-4755bc79138d-profile` | initialize | `862b1531-fc27-405c-b6a4-78bfc7e13b9d` | `fa334292cbd64d5f` | 73 |
| 20:28:15.089 | `ccdc8c33-8408-4b35-be10-4755bc79138d-profile` | notifications/initialized | `8018583f-4420-4ce8-9462-cdd06de29898` | `6e949fd92fe51300` | 54 |
| 20:28:15.144 | `ccdc8c33-8408-4b35-be10-4755bc79138d-profile` | tools/list | `95fdeda3-dfa4-43d0-b035-96920fac7bb1` | `5112ff197b9c55da` | 238 |
| 20:29:02.347 | `770f8eb9-0b88-4376-aae0-a322cac770e8-travel` | initialize | `92482466-2459-4131-9d27-0f6b20e5ea26` | `211b90ce18e348d8` | 102 |
| 20:29:02.453 | `770f8eb9-0b88-4376-aae0-a322cac770e8-travel` | notifications/initialized | `b0430d74-e2ae-4aa3-87e9-4990b5843593` | `b41ad296567d5502` | 90 |
| 20:29:02.544 | `770f8eb9-0b88-4376-aae0-a322cac770e8-travel` | tools/list | `f8717b43-faec-4a45-86dc-bcbfe0bd1757` | `59d611875eed10fe` | 189 |
| 20:29:47.320 | `23afae83-0f81-4c9a-95e3-e30e47ae534b-profile` | initialize | `27dcc711-1354-423d-824b-5a5687ac5ec0` | `89417e0ce738db2d` | 101 |
| 20:29:47.425 | `23afae83-0f81-4c9a-95e3-e30e47ae534b-profile` | notifications/initialized | `f3c8df29-75da-4e2c-9dee-ed40b315d5c2` | `91fc6d88fb1a04ae` | 84 |
| 20:29:47.511 | `23afae83-0f81-4c9a-95e3-e30e47ae534b-profile` | tools/list | `1cd408b0-17d4-4a2e-ab56-7da52a563e9b` | `174317c9c326848f` | 180 |
| 20:30:54.417 | `e1e049bf-fb20-43d9-91e9-bd7064b73d07-profile` | initialize | `29d0374c-e707-4837-a17b-ca68e65b8b05` | `918d78ed1df9debe` | 78 |
| 20:30:54.499 | `e1e049bf-fb20-43d9-91e9-bd7064b73d07-profile` | notifications/initialized | `c0f62304-7fc5-4741-83da-288b39ffb411` | `efe90653a46073d4` | 33 |
| 20:30:54.534 | `e1e049bf-fb20-43d9-91e9-bd7064b73d07-profile` | tools/list | `7d2ba43f-719d-455b-982b-71809690bb72` | `d5bbc8a9129c493f` | 202 |
| 20:31:13.816 | `d8aca622-381c-49ac-aca9-0396caaed7a1-profile` | initialize | `206da7b8-3183-47f8-b58a-ae81cef03aa8` | `37aa63e869582923` | 85 |
| 20:31:13.904 | `d8aca622-381c-49ac-aca9-0396caaed7a1-profile` | notifications/initialized | `47e17079-41ff-4faf-b8c7-635aba2feb64` | `20f680c1849b62a3` | 71 |
| 20:31:13.977 | `d8aca622-381c-49ac-aca9-0396caaed7a1-profile` | tools/list | `e3010223-61e4-4968-89ab-91baf243d4aa` | `77a7ceac249da423` | 136 |
| 20:32:20.161 | `12fcb31b-c340-40ad-a82a-da7b9057a88f-profile` | initialize | `3cfe85d2-a29d-4b10-92e5-57b9cc837cd6` | `ce81f1df4257ffdb` | 96 |
| 20:32:20.261 | `12fcb31b-c340-40ad-a82a-da7b9057a88f-profile` | notifications/initialized | `391aab67-fa12-4953-9eac-bfbb4adbac1f` | `85dca48bc206b0a0` | 82 |
| 20:32:20.345 | `12fcb31b-c340-40ad-a82a-da7b9057a88f-profile` | tools/list | `f81fdb64-6b51-4c9a-9652-d6c50ca23308` | `09379b2c95dcd935` | 194 |
| 20:32:38.528 | `c660689d-98a0-47fa-ab86-e66a91d9233e-profile` | initialize | `7563d731-a847-4445-977e-b6affb76ae3d` | `373154ec591235cb` | 110 |
| 20:32:38.641 | `c660689d-98a0-47fa-ab86-e66a91d9233e-profile` | notifications/initialized | `e2189c29-8d2f-47b4-9344-cbbb3247b73e` | `dddc65fc6bab87c4` | 86 |
| 20:32:38.728 | `c660689d-98a0-47fa-ab86-e66a91d9233e-profile` | tools/list | `f0336e02-1824-432a-88c2-86a85e35a68a` | `0880858612df1c23` | 189 |
| 20:33:44.467 | `83e8cfb2-e30a-492a-8343-1d6df0b4b70f-profile` | initialize | `4e079031-f681-4e84-b191-fc28e91b2f81` | `96b3e0acb9045a2a` | 91 |
| 20:33:44.562 | `83e8cfb2-e30a-492a-8343-1d6df0b4b70f-profile` | notifications/initialized | `6c858871-783f-489d-af5f-9b456e2bd877` | `6403508279efaecd` | 74 |
| 20:33:44.637 | `83e8cfb2-e30a-492a-8343-1d6df0b4b70f-profile` | tools/list | `8a113655-9827-41a6-8c05-c58e599c89c4` | `3765a3e4789bc1ec` | 180 |

## Sub-agent model calls (time sink 3)

One Bedrock `ConverseStream` per sub-agent request, from the Strands `chat` spans.

| Time | Runtime session id | Trace id | Span id | Model | Input tokens | Output tokens | Time to first token ms | Call ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20:19:55.849 | `5f22aca7-7997-4941-b9f0-661ee9e5c1df-profile` | `6ac2b4e75217d1766aef4d9b5f0055cc` | `efd287f0a30e65d8` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2017 | 38 | 544 | 862 |
| 20:20:01.639 | `5f22aca7-7997-4941-b9f0-661ee9e5c1df-profile` | `6ac2b4f16852a71e166d06d8017bd246` | `02ce8c4725546174` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2065 | 37 | 600 | 854 |
| 20:20:39.754 | `48e7b0a1-5754-40ef-93a1-4998ae7f8fdd-profile` | `6ac2b5126beb7ad13c8c647f2041850a` | `7f8b06f299223978` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2013 | 30 | 547 | 753 |
| 20:20:58.742 | `6dfeece8-8827-40b9-9d0f-23d831147306-profile` | `6ac2b52653194bc26f962952431d1fe2` | `895d26ca1b437838` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2017 | 38 | 539 | 707 |
| 20:21:04.402 | `6dfeece8-8827-40b9-9d0f-23d831147306-profile` | `6ac2b530465944157f31bf434bb9542b` | `53ee0f38e597ad59` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2065 | 39 | 577 | 1725 |
| 20:21:46.303 | `e2ceda77-100c-4ea2-bc32-d346935a6fef-travel` | `6ac2b5575d9849fc35cd83a24c1c66dc` | `dd33508e20c2869d` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2407 | 151 | 594 | 1882 |
| 20:21:53.499 | `e2ceda77-100c-4ea2-bc32-d346935a6fef-travel` | `6ac2b560699716366a05da9767c8ef0a` | `7b5041d7936c3ddf` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 4343 | 52 | 601 | 1828 |
| 20:22:17.868 | `f538cb39-a04d-433b-aed5-468d1aa2e6f5-profile` | `6ac2b5754a9b28dd5b754bc54cdeaa21` | `8f21a1606f3d4708` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2013 | 31 | 580 | 833 |
| 20:22:36.399 | `cfacb8b9-0358-4598-8aa5-df0f85b0f2c9-profile` | `6ac2b5887d869bfa42febe1043337710` | `7db92def29ef3462` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2017 | 38 | 564 | 852 |
| 20:22:42.049 | `cfacb8b9-0358-4598-8aa5-df0f85b0f2c9-profile` | `6ac2b5915767982d60daa5a146743765` | `04be62b2acb3eca2` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2065 | 37 | 661 | 990 |
| 20:23:22.823 | `ed74cbd8-aca6-4173-bcbb-2f4710304965-travel` | `6ac2b5b7559f08cf1adae9525d2da1e4` | `1053d01963995ea2` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2407 | 192 | 538 | 2293 |
| 20:23:30.768 | `ed74cbd8-aca6-4173-bcbb-2f4710304965-travel` | `6ac2b5c173b458314161af823cc73b95` | `8fed59887b0ed609` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 4384 | 48 | 594 | 1875 |
| 20:23:52.288 | `af2494cc-ecd3-4b55-800e-62c40dfb6120-pay` | `6ac2b5d23c227893329f45417948d98e` | `32f624a1f1fa25c5` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2158 | 38 | 567 | 1003 |
| 20:23:58.024 | `af2494cc-ecd3-4b55-800e-62c40dfb6120-pay` | `6ac2b5dd708fdad64f3f9c5f46aae532` | `0b0684348da52891` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2205 | 41 | 572 | 778 |
| 20:24:21.439 | `cda42b04-85ed-478d-b7ca-3a44ae86583f-profile` | `6ac2b5f00b53c16923c54eb20171c4e2` | `293bc024cf124a28` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2013 | 30 | 504 | 722 |
| 20:24:39.856 | `32f6a73b-e9e3-4a51-b994-616e9ffc5b31-profile` | `6ac2b604201d020446df0e9d562b47ae` | `db2962cda72615c1` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2017 | 38 | 500 | 756 |
| 20:24:45.342 | `32f6a73b-e9e3-4a51-b994-616e9ffc5b31-profile` | `6ac2b60d20ca291e05899a9b20f69028` | `c7bd91f045d3d100` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2065 | 37 | 575 | 853 |
| 20:25:25.549 | `ae9113a3-b377-4aad-8d7a-c1b2e9a20ed9-travel` | `6ac2b63212c1559928c39b1068d88018` | `a855ce2785a27966` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2407 | 151 | 515 | 2996 |
| 20:25:33.791 | `ae9113a3-b377-4aad-8d7a-c1b2e9a20ed9-travel` | `6ac2b63c5bf7da85647ec3cb57e63004` | `8921886bbda2f55c` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 4343 | 44 | 561 | 1238 |
| 20:25:56.585 | `ec9ce1dc-084b-4e70-9f80-e2e34c76ab32-profile` | `6ac2b651684379356f4a5ca76ba13bb6` | `54e319b0584790ba` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2013 | 30 | 544 | 734 |
| 20:26:14.689 | `73cc55da-9edd-49ed-afd1-24b84d5b57f1-profile` | `6ac2b663459535d6691379894b6bb9f9` | `d8cdae1d8b2d06b0` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2017 | 38 | 502 | 736 |
| 20:26:19.960 | `73cc55da-9edd-49ed-afd1-24b84d5b57f1-profile` | `6ac2b66b2da8da264f9c691677f4fc64` | `6bb918a2fbd8fed1` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2065 | 39 | 533 | 871 |
| 20:26:59.837 | `5d7149af-22f4-4024-abd2-a78a6b9fe5be-travel` | `6ac2b6913a68024a47fcab4e56d099a5` | `4f066045fed19ccb` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2407 | 154 | 512 | 1695 |
| 20:27:06.800 | `5d7149af-22f4-4024-abd2-a78a6b9fe5be-travel` | `6ac2b699366c62057190588b6fc3d875` | `5f96966815b1d42a` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 4346 | 53 | 570 | 2122 |
| 20:27:29.341 | `dfec37f3-344c-4a68-b2b6-f5a26c4e921c-pay` | `6ac2b6aa36f0bb6a78c5befa6589b82e` | `28dd71b23430c6e9` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2158 | 43 | 556 | 1335 |
| 20:27:35.374 | `dfec37f3-344c-4a68-b2b6-f5a26c4e921c-pay` | `6ac2b6b75a4925ad72a288b55c4a24c4` | `b40c8570f8a3b735` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2210 | 41 | 558 | 769 |
| 20:27:58.062 | `f776633d-b974-49f8-a83d-552cd0d4add2-profile` | `6ac2b6ca3b3501ec5b769d7f4140a555` | `36dfb494c3a041a1` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2013 | 30 | 642 | 1219 |
| 20:28:17.304 | `ccdc8c33-8408-4b35-be10-4755bc79138d-profile` | `6ac2b6dd221f8d51478e09b104ee097f` | `b0e1d8798a48824b` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2017 | 38 | 499 | 738 |
| 20:28:22.656 | `ccdc8c33-8408-4b35-be10-4755bc79138d-profile` | `6ac2b6e65140b72409107c8245185619` | `20cd823e6051154f` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2065 | 39 | 598 | 1534 |
| 20:29:03.513 | `770f8eb9-0b88-4376-aae0-a322cac770e8-travel` | `6ac2b70c36b6f70a0d3818aa5e1bcd63` | `42c456a6be02bdbe` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2407 | 154 | 555 | 2284 |
| 20:29:11.214 | `770f8eb9-0b88-4376-aae0-a322cac770e8-travel` | `6ac2b71650ea7ebd7f25a3580b5337cb` | `d0a5cebed7539d18` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 4346 | 49 | 645 | 1777 |
| 20:29:50.174 | `23afae83-0f81-4c9a-95e3-e30e47ae534b-profile` | `6ac2b73977149d6846d116f811ab1fac` | `7b922e6df5d4be24` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2017 | 38 | 553 | 761 |
| 20:30:56.691 | `e1e049bf-fb20-43d9-91e9-bd7064b73d07-profile` | `6ac2b77c2c22bc0101ba4e2e0f6d1012` | `3afae7cccd21e2b0` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2017 | 38 | 514 | 712 |
| 20:31:15.898 | `d8aca622-381c-49ac-aca9-0396caaed7a1-profile` | `6ac2b78f35c8a9264419e5840b387696` | `cc091ce00c2444aa` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2017 | 38 | 506 | 724 |
| 20:32:22.488 | `12fcb31b-c340-40ad-a82a-da7b9057a88f-profile` | `6ac2b7d207b8d4aa3f7ae58c3490778f` | `027cf6fbbd96c5cf` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2017 | 38 | 588 | 812 |
| 20:32:40.904 | `c660689d-98a0-47fa-ab86-e66a91d9233e-profile` | `6ac2b7e546ced8a5487780e442392414` | `29c7187ef8c9671e` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2017 | 38 | 489 | 752 |
| 20:33:46.660 | `83e8cfb2-e30a-492a-8343-1d6df0b4b70f-profile` | `6ac2b8274092e69b219e9fdf172d0a67` | `eb63875d48b6930c` | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2017 | 38 | 525 | 731 |

## Turns in the designer (routing, time sinks 3, 5, 6)

Each question as Connect and the designer saw it. Routing is the designer's `ModelStart` to
`ModelEnd`; "Connect in" is the click to the designer's `NluRequestReceived`.

| Click | Contact | Question | Flow | Designer correlation id | Designer message id | Page run id | Connect in ms | Routing ms | First words ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20:19:49.996 | `5f22aca7-7997-4941-b9f0-661ee9e5c1df` | Change my address | ProfileFlow | `f6c0d55e-b785-4d01-8332-c0ab2dd7d4d8` | `a0624039-3921-4538-9b2e-0566bf4c7d76` | `a21541db-e199-4a80-8385-1c4669a31ccd` | 560 | 455 | 7200 |
| 20:20:00.222 | `5f22aca7-7997-4941-b9f0-661ee9e5c1df` | And what is my emergency contact? | ProfileFlow | `77395e2a-11d6-4be9-a73b-38bf34ce6c13` | `3bff92b8-4a52-4293-9e65-dde9e0e6da24` | `c0bfaf05-6555-417a-b122-f35779aebaa8` | 470 | 409 | 2761 |
| 20:20:29.480 | `48e7b0a1-5754-40ef-93a1-4998ae7f8fdd` | Update my information | ClarifyFlow | `01a1cb00-7804-4944-af26-ce8bf809e666` | `43ad6df7-8bd9-46d2-9598-d43a455b26d9` | `7cf332ec-4ded-4765-b381-d66791b69805` | 443 | 544 | 1277 |
| 20:20:33.801 | `48e7b0a1-5754-40ef-93a1-4998ae7f8fdd` | my home address | ProfileFlow | `befd35cc-889d-4ea6-a203-1f1b8b3d60ed` | `8c622522-4803-4912-ba01-011091b7e8a4` | `d7e5e5e4-1a14-4da7-b5f3-da779c09d2a6` | 449 | 492 | 7159 |
| 20:20:53.614 | `6dfeece8-8827-40b9-9d0f-23d831147306` | Change my address | ProfileFlow | `4dd2f087-5cec-4457-b52e-97fe062a9058` | `bd8bb0a1-69d9-4678-b89d-e4d1b700cc7f` | `5a993812-179c-47c7-af58-d29938e95b7e` | 382 | 444 | 6193 |
| 20:21:02.826 | `6dfeece8-8827-40b9-9d0f-23d831147306` | And what is my emergency contact? | ProfileFlow | `f6ca78e5-9cc5-4f9a-8678-ab1a05e81f80` | `f49464fc-60b1-420e-ad0e-5842cf413670` | `24e32050-ee00-42da-b56a-70dc454f5d31` | 522 | 560 | 3653 |
| 20:21:19.132 | `8a8a1a63-33be-4f59-9294-aa0df1ae7f6e` | PTO policy | PolicyFlow | `7b319a92-ecff-4908-8886-ad36358822ed` | `08184757-c06e-4d07-ad69-c94efb6dd783` | `f08fdafd-e43e-4982-a81a-887a672339be` | 434 | 403 | 3797 |
| 20:21:26.758 | `8a8a1a63-33be-4f59-9294-aa0df1ae7f6e` | Does unused PTO carry over? | PolicyFlow | `b8252d71-c154-4ea1-8494-9539a922c36c` | `1b369758-b76c-46cb-9c26-251e04684889` | `ab075ef6-2824-457b-8218-844f2261a82a` | 328 |  | 1938 |
| 20:21:42.123 | `e2ceda77-100c-4ea2-bc32-d346935a6fef` | Buddy passes | TravelFlow | `e6dd1834-6393-448b-80cf-5f1ee52026af` | `3ff34060-733a-4d3d-aac6-44d50bef78c7` | `96ff3ed7-8e76-4173-b3e9-c80963fb50c5` | 400 | 389 | 6396 |
| 20:21:51.554 | `e2ceda77-100c-4ea2-bc32-d346935a6fef` | Can my parents use them? | TravelFlow | `79359aff-0efa-46ed-9858-b60e02173ea7` | `449771c5-4ac0-4265-88b6-c643a18088e8` | `66e54042-3568-4489-a4c0-258b763e9f1a` | 353 | 371 | 4130 |
| 20:22:08.312 | `f538cb39-a04d-433b-aed5-468d1aa2e6f5` | Update my information | ClarifyFlow | `1033032a-6c42-4240-82fc-99b46968e5ae` | `e29f4fc8-6dc7-4b22-a489-83d69e835fe6` | `1dd7b0d8-1391-4060-bf21-c61934dec673` | 401 | 338 | 975 |
| 20:22:12.307 | `f538cb39-a04d-433b-aed5-468d1aa2e6f5` | my home address | ProfileFlow | `ced6dd0f-1df3-41cf-be6c-38ebfb86ab5e` | `6352dc79-70f0-4a2c-8e81-a9d7dcd74ff0` | `75a23092-88c1-4090-93d1-ef941d4290b9` | 289 | 648 | 6718 |
| 20:22:31.668 | `cfacb8b9-0358-4598-8aa5-df0f85b0f2c9` | Change my address | ProfileFlow | `807b5eda-e1d0-49e4-8731-aa1e0b7def4a` | `1676cee9-5241-4419-a36a-648ef4a40d5f` | `9bae6258-2c77-42b1-a02a-cdded3a2ad07` | 499 | 423 | 5901 |
| 20:22:40.599 | `cfacb8b9-0358-4598-8aa5-df0f85b0f2c9` | And what is my emergency contact? | ProfileFlow | `8e359e69-fd8a-42f8-8f30-15dab947a2c0` | `261e2015-2247-4d2d-9c5d-26a8b1b3c238` | `9d1e54be-b133-49dd-ae11-9953c64957fc` | 397 | 614 | 2736 |
| 20:22:56.016 | `6da0565d-857c-46fd-9d4d-42852de004f9` | PTO policy | PolicyFlow | `ed223897-1b38-4bd9-ba98-ade45ecb76e3` | `791144ba-fc0b-4769-bf7e-3b7fdabef054` | `43789a7c-b2fc-42b8-85db-660790ff01bb` | 494 | 426 | 3631 |
| 20:23:03.464 | `6da0565d-857c-46fd-9d4d-42852de004f9` | Does unused PTO carry over? | PolicyFlow | `69e41b47-e62e-4040-911e-6e191a7031ea` | `52a63324-05c7-45ba-a6c6-57e680b53581` | `27edea9f-d975-423c-920e-467df29c91ca` | 374 |  | 1565 |
| 20:23:18.463 | `ed74cbd8-aca6-4173-bcbb-2f4710304965` | Buddy passes | TravelFlow | `0fb84915-cef7-4eb4-b394-081d7a4d1043` | `d4338ed5-42b5-4907-bf9a-4ddb1b4ef049` | `1bc564fe-854e-4da6-9088-49c2effc4bae` | 444 | 430 | 7032 |
| 20:23:28.516 | `ed74cbd8-aca6-4173-bcbb-2f4710304965` | Can my parents use them? | TravelFlow | `caf9f8af-80bf-4597-bb45-51534b8d2f73` | `49a8dfa0-d004-4d29-b722-9c8c7408d6b2` | `8f2e6710-5265-4198-b5b4-ac21a3c8b883` | 348 | 718 | 4515 |
| 20:23:45.662 | `af2494cc-ecd3-4b55-800e-62c40dfb6120` | When was my last paycheck and how much was it? | PayFlow | `faef9090-1463-4362-b8f1-eaede688730a` | `5a20ce6b-2d35-427c-8c2e-15688bc29342` | `6846eafa-4f04-43e2-a339-7d61ce252968` | 418 | 518 | 7924 |
| 20:23:56.625 | `af2494cc-ecd3-4b55-800e-62c40dfb6120` | And the one before that? | PayFlow | `655f378a-f953-420e-8ff9-f363c724ebfd` | `6672c4ce-d1cf-4292-9944-6d90f11aa735` | `6d98f567-302f-4d38-8446-d4b821d7dcda` | 363 | 567 | 2621 |
| 20:24:11.869 | `cda42b04-85ed-478d-b7ca-3a44ae86583f` | Update my information | ClarifyFlow | `3ee378df-ae92-475a-90c1-1f5de66bb129` | `2c5d3d6c-8be1-488a-b095-1f677fd04848` | `20f71b69-523e-4272-aff8-d37ca4edb65a` | 359 | 409 | 1006 |
| 20:24:15.894 | `cda42b04-85ed-478d-b7ca-3a44ae86583f` | my home address | ProfileFlow | `1b21809e-0367-4308-96bf-2030ee447c39` | `aa3fd4f4-fb61-4348-9eb6-78808eb525b6` | `f15b4ec0-50c3-4892-83c1-471a2c7a3530` | 364 | 460 | 6627 |
| 20:24:35.154 | `32f6a73b-e9e3-4a51-b994-616e9ffc5b31` | Change my address | ProfileFlow | `89a43ed4-ca8a-4d53-a898-34db3c230130` | `6e4a4d45-1501-4245-9402-8d41e0206914` | `737e040f-0a65-4ad3-805e-7243d4395864` | 368 | 553 | 5804 |
| 20:24:43.978 | `32f6a73b-e9e3-4a51-b994-616e9ffc5b31` | And what is my emergency contact? | ProfileFlow | `f2b96878-22da-473f-9b4d-b47bbd596249` | `117c697f-fec5-4f02-8e30-fbc956e836eb` | `1670320b-fd54-4d15-8506-4cf721394a97` | 422 | 453 | 2573 |
| 20:24:59.259 | `02a4898f-3278-4b23-8217-344fd3f568ef` | PTO policy | PolicyFlow | `b474daaa-2b91-43b5-b870-cba9e7b6ee05` | `5c8ce0b0-7d76-4079-8f20-290d2056cdea` | `5d3d9ca7-d313-4121-b8b6-ae1d54309028` | 419 | 424 | 3144 |
| 20:25:06.233 | `02a4898f-3278-4b23-8217-344fd3f568ef` | Does unused PTO carry over? | PolicyFlow | `d4a22ce6-45b2-4ab9-99ef-8a9f5a434546` | `ff1eb217-d175-407e-b8a1-aa42ce22c913` | `27310eac-e23b-4af1-9541-3074d37be3fc` | 282 |  | 2205 |
| 20:25:21.919 | `ae9113a3-b377-4aad-8d7a-c1b2e9a20ed9` | Buddy passes | TravelFlow | `c04f9adc-0052-4a25-8233-43cd6d6cc7c4` | `93b249e8-dda1-4f4f-adae-eb0108e7b768` | `8359ace8-ba85-452b-a848-b04daecd4acc` | 421 | 410 | 6918 |
| 20:25:31.871 | `ae9113a3-b377-4aad-8d7a-c1b2e9a20ed9` | Can my parents use them? | TravelFlow | `2d9fa51b-83ef-48ec-988c-cf4ee9c3931e` | `2dcdaa95-4cb9-470f-aa00-edca4a457166` | `6ab927a2-b8fc-4a00-82cd-db08c09c9de6` | 339 | 442 | 3468 |
| 20:25:47.987 | `ec9ce1dc-084b-4e70-9f80-e2e34c76ab32` | Update my information | ClarifyFlow | `29bcc49c-7b98-4fc0-98b3-38daf389051c` | `9efaf77f-84a9-4dde-9cf3-6615f56fafe3` | `eb446586-c09b-4ca4-b613-57f26fb81449` | 340 | 446 | 1134 |
| 20:25:52.140 | `ec9ce1dc-084b-4e70-9f80-e2e34c76ab32` | my home address | ProfileFlow | `9900993e-5fae-4eeb-9da6-664e2eaad35e` | `dde6b30d-ab95-4856-9dfc-9fd6d9ecd4fa` | `792b4af8-7245-47e1-b24e-c6c422cb61b5` | 446 | 377 | 5486 |
| 20:26:10.250 | `73cc55da-9edd-49ed-afd1-24b84d5b57f1` | Change my address | ProfileFlow | `47a77ad9-9701-4757-b055-5abd1989f277` | `0351dcb7-01cb-4561-ae85-f576b6f81b7e` | `6ccac3a0-b5b3-4df7-a27b-88560a81fb51` | 430 | 410 | 5537 |
| 20:26:18.799 | `73cc55da-9edd-49ed-afd1-24b84d5b57f1` | And what is my emergency contact? | ProfileFlow | `bb09a96b-9062-4bb4-9719-512c9ddec8eb` | `44a2919d-70cd-4fc5-ba79-a79dddf27d03` | `1025f014-6f33-42c5-af6a-f81984606fe7` | 291 | 383 | 2437 |
| 20:26:33.882 | `a95c6ecf-19af-4c76-b467-3801c61a2e4b` | PTO policy | PolicyFlow | `cfa2c455-42ef-4839-8c52-f0f25cb2e0f1` | `e9bd61f3-de11-4e0e-87a4-6431f02aeb79` | `c8192b14-1a35-4ade-948c-2f45a5dc2c62` | 415 | 592 | 3446 |
| 20:26:41.155 | `a95c6ecf-19af-4c76-b467-3801c61a2e4b` | Does unused PTO carry over? | PolicyFlow | `ea1e2550-299c-4d6f-afb8-658df15dacc2` | `2f43e04c-c6ac-4531-9c00-5c3dbdec5ff5` | `421a4190-5b80-4977-a1d0-07b44ead82ab` | 487 |  | 1724 |
| 20:26:56.325 | `5d7149af-22f4-4024-abd2-a78a6b9fe5be` | Buddy passes | TravelFlow | `73d9a051-a83c-4b26-a54f-382943c055e4` | `b2e713ab-d232-4f51-bb9e-d4b6bf9fa132` | `95788d2e-7272-477b-88cf-524e30fe9b88` | 342 | 364 | 5606 |
| 20:27:04.961 | `5d7149af-22f4-4024-abd2-a78a6b9fe5be` | Can my parents use them? | TravelFlow | `86588780-20c3-4374-9cfe-b713bbb8c4b2` | `0338a139-30cf-4368-b0f4-3fa4cbf0e825` | `0114016e-88be-4cf6-8d84-7bb06b392e17` | 314 | 360 | 4232 |
| 20:27:21.802 | `dfec37f3-344c-4a68-b2b6-f5a26c4e921c` | When was my last paycheck and how much was it? | PayFlow | `77d1eb6d-5789-46ae-ae1c-b6d10ec95bf3` | `091e25f1-aeea-4974-9192-039a311cd36e` | `f842f0a8-e0a5-4c83-847f-7e5754d64d01` | 351 | 490 | 9310 |
| 20:27:34.130 | `dfec37f3-344c-4a68-b2b6-f5a26c4e921c` | And the one before that? | PayFlow | `67e811af-5aac-498a-934e-8e0a40ca5aae` | `8102bb11-30f9-4095-806f-26008a0b4298` | `76c3f6a0-63d6-4f57-9fc9-366caaf8696c` | 377 | 380 | 2312 |
| 20:27:49.100 | `f776633d-b974-49f8-a83d-552cd0d4add2` | Update my information | ClarifyFlow | `7aad15dd-80c4-42f7-ae11-79a1486c7f02` | `f0fa466a-bcc3-4571-8a8f-5f4f455dc306` | `0fba9cae-2e89-4de5-bec1-2aca6e0c7248` | 351 | 722 | 1326 |
| 20:27:53.448 | `f776633d-b974-49f8-a83d-552cd0d4add2` | my home address | ProfileFlow | `bc23613f-8399-47a2-a3e9-45d30c2a8ecb` | `690c468f-3ed8-4603-bbe7-fad3cdc2fbca` | `2ba68617-856b-47c0-9718-5d21029235d5` | 397 | 468 | 6164 |
| 20:28:12.266 | `ccdc8c33-8408-4b35-be10-4755bc79138d` | Change my address | ProfileFlow | `5d459d96-7a8d-426a-8a12-84d76ee71192` | `dd6d78ed-5779-45f7-8a0a-9f69aff17450` | `63556a13-aa3c-4670-97f3-f7c2d7aad294` | 382 | 683 | 6158 |
| 20:28:21.458 | `ccdc8c33-8408-4b35-be10-4755bc79138d` | And what is my emergency contact? | ProfileFlow | `2163eaa5-4512-4b65-99a1-50a2b4988f4d` | `f25ebc9a-fa03-4202-81c6-2237e6fa57d1` | `37837d1f-e05b-41d7-82db-c3a0f7079c75` | 277 | 432 | 3101 |
| 20:28:37.204 | `12b6aebc-fcaa-444c-9367-f537d454c460` | PTO policy | PolicyFlow | `2c2d5659-b544-49de-a1ea-73c26a356ea7` | `e3d3fb87-e530-4caa-8e04-76420b8cb42f` | `74994641-81a8-480d-8f67-9fa851a71eb2` | 357 | 417 | 3245 |
| 20:28:44.265 | `12b6aebc-fcaa-444c-9367-f537d454c460` | Does unused PTO carry over? | PolicyFlow | `df117114-0cd0-414f-ab2d-7d237792eb62` | `7a9ca148-fa0e-483d-ac26-840b0f0f3629` | `ceae4ad1-cbd1-43f8-a4df-46261c7a9067` | 392 |  | 1582 |
| 20:28:59.292 | `770f8eb9-0b88-4376-aae0-a322cac770e8` | Buddy passes | TravelFlow | `6652bf61-b470-4c4e-94d0-6ae99bd32fc8` | `1fedd389-2f20-4763-b22e-098c8c2c266c` | `b3e7d3f5-ea71-417d-88bc-32f95c5df6db` | 418 | 387 | 6880 |
| 20:29:09.195 | `770f8eb9-0b88-4376-aae0-a322cac770e8` | Can my parents use them? | TravelFlow | `5dd2f147-ab45-4e0f-9b18-d5b569c14bd9` | `89f03c9f-374b-49a1-bf5d-28e96586249b` | `4eb1f69c-b460-46a4-b29b-8ee799033967` | 304 | 444 | 4084 |
| 20:29:44.167 | `23afae83-0f81-4c9a-95e3-e30e47ae534b` | Change my address | ProfileFlow | `60ec3f93-125d-4bc6-a335-f5adaa935cdc` | `530c339b-0e1d-4461-abae-2ea67b670882` | `62377d03-47d1-4064-a639-15ef392e0221` | 550 | 440 | 7127 |
| 20:30:51.477 | `e1e049bf-fb20-43d9-91e9-bd7064b73d07` | Change my address | ProfileFlow | `6ae0c6a4-91c0-4e75-a787-9fb43067aed0` | `4c764e5a-a479-4d6d-b0ab-f33db783b499` | `97973573-564e-41e9-972d-777f2ce28d38` | 476 | 474 | 6338 |
| 20:31:10.495 | `d8aca622-381c-49ac-aca9-0396caaed7a1` | Change my address | ProfileFlow | `01ac8146-3c42-48b7-8963-b42eb839ced9` | `4da48280-41dc-40c3-aba3-836455988454` | `850d7d09-d703-4df8-bc9f-0f1dbcc6be83` | 414 | 480 | 6466 |
| 20:32:17.081 | `12fcb31b-c340-40ad-a82a-da7b9057a88f` | Change my address | ProfileFlow | `f9afa575-d6a6-40f8-bc19-797bb5222f6e` | `546c53e6-5776-4859-bf46-2992e3f2da63` | `cd315423-178f-43a9-a0d0-de30b32a863e` | 467 | 402 | 6570 |
| 20:32:36.285 | `c660689d-98a0-47fa-ab86-e66a91d9233e` | Change my address | ProfileFlow | `62c18baf-ce78-4673-bf9b-b882749629a1` | `2539dae1-654d-47e5-b4c7-2b26311574ef` | `d6a01afa-da26-4891-9d53-fc258a16fc4e` | 364 | 454 | 5677 |
| 20:33:42.084 | `83e8cfb2-e30a-492a-8343-1d6df0b4b70f` | Change my address | ProfileFlow | `ff9eac84-0750-47a4-85b1-cb8cc7675a8a` | `581e9b44-d2c4-4228-9f88-f400689f8351` | `a43872c0-b2ed-43c0-b39d-0f903a298d16` | 398 | 404 | 5740 |

### Data requests from the designer

Every data request with its gateway request. PolicySearch and Travel's search go to the knowledge base target through the tools gateway.

| Time | Contact | Request | Gateway | Target | Gateway request id | Trace id | ms |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 20:19:51.118 | `5f22aca7-7997-4941-b9f0-661ee9e5c1df` | DelegateProfile | agents | profile | `ff4b203c-2868-47d0-b219-22c67f4f4c0b` | `6ac2b4e7325405e50437276c24a6a429` | 5703 |
| 20:20:01.127 | `5f22aca7-7997-4941-b9f0-661ee9e5c1df` | DelegateProfile | agents | profile | `0b86b9a3-dff5-4870-9d25-5914efd0da55` | `6ac2b4f117ec08ff3b0e772376c93191` | 1448 |
| 20:20:34.770 | `48e7b0a1-5754-40ef-93a1-4998ae7f8fdd` | DelegateProfile | agents | profile | `c581bd82-501e-4c29-8012-00da0495131c` | `6ac2b512171c964e606f76cc43035c4a` | 5848 |
| 20:20:54.471 | `6dfeece8-8827-40b9-9d0f-23d831147306` | DelegateProfile | agents | profile | `19673fe2-cf8a-48e8-bbe2-b5a895c45f0f` | `6ac2b526345ae900280aa4d70936232f` | 5102 |
| 20:21:03.936 | `6dfeece8-8827-40b9-9d0f-23d831147306` | DelegateProfile | agents | profile | `65c5fbf9-37a0-4d60-9dc7-08f2aad8939b` | `6ac2b52f344bc8e84fcf589d46d13273` | 2278 |
| 20:21:20.094 | `8a8a1a63-33be-4f59-9294-aa0df1ae7f6e` | PolicySearch | tools | docs | `04a08dc0-2eba-41fc-a264-943e3dbf57a6` | `6ac2b5401978288c78ca917439898edd` | 705 |
| 20:21:43.030 | `e2ceda77-100c-4ea2-bc32-d346935a6fef` | DelegateTravel | agents | travel | `51291972-ad12-480d-942a-7694d43d95d4` | `6ac2b55751e6f4565cc503fa4dec1e15` | 5265 |
| 20:21:45.565 | `e2ceda77-100c-4ea2-bc32-d346935a6fef` | travel sub-agent search | tools | docs | `48f8e4e6-3b1a-45d3-90d9-499150724bb5` | `6ac2b5575d9849fc35cd83a24c1c66dc` | 653 |
| 20:21:52.304 | `e2ceda77-100c-4ea2-bc32-d346935a6fef` | DelegateTravel | agents | travel | `a4cf9c2f-b40e-4b87-a453-a01cd071be96` | `6ac2b56057587e471661ed5231457a59` | 3144 |
| 20:21:52.711 | `e2ceda77-100c-4ea2-bc32-d346935a6fef` | travel sub-agent search | tools | docs | `27556cab-71dc-424c-98b4-9c0e4d68966b` | `6ac2b560699716366a05da9767c8ef0a` | 709 |
| 20:22:13.280 | `f538cb39-a04d-433b-aed5-468d1aa2e6f5` | DelegateProfile | agents | profile | `6471b780-a48a-4247-a71a-6912c61c1c96` | `6ac2b575766c16cf4c02ff396aba190f` | 5499 |
| 20:22:32.619 | `cfacb8b9-0358-4598-8aa5-df0f85b0f2c9` | DelegateProfile | agents | profile | `f3799126-76e8-4eee-984c-ce42d85271fc` | `6ac2b58864b059601d6e04d93a4aa5bd` | 4730 |
| 20:22:41.639 | `cfacb8b9-0358-4598-8aa5-df0f85b0f2c9` | DelegateProfile | agents | profile | `4f8480fc-df26-460e-943a-5dcc7f84b226` | `6ac2b5911dc8aed04f0e87766c523866` | 1489 |
| 20:22:56.967 | `6da0565d-857c-46fd-9d4d-42852de004f9` | PolicySearch | tools | docs | `76755b65-201c-43ac-9de5-d9b4acbe7f62` | `6ac2b5a0784507af28a80a41328e9f76` | 727 |
| 20:23:19.366 | `ed74cbd8-aca6-4173-bcbb-2f4710304965` | DelegateTravel | agents | travel | `17404d9b-0a5e-40e0-81d9-5d739942f251` | `6ac2b5b771732f9015872813325e6836` | 5868 |
| 20:23:21.992 | `ed74cbd8-aca6-4173-bcbb-2f4710304965` | travel sub-agent search | tools | docs | `3c05d414-ce89-401f-b142-6a3336f29016` | `6ac2b5b7559f08cf1adae9525d2da1e4` | 748 |
| 20:23:29.608 | `ed74cbd8-aca6-4173-bcbb-2f4710304965` | DelegateTravel | agents | travel | `19e821c2-3e73-426c-8613-5090b38d0a43` | `6ac2b5c12f26881f7b598ea06bde9aad` | 3188 |
| 20:23:29.985 | `ed74cbd8-aca6-4173-bcbb-2f4710304965` | travel sub-agent search | tools | docs | `b7d0844f-7a8e-4bf5-8b13-d2529667c3bc` | `6ac2b5c173b458314161af823cc73b95` | 705 |
| 20:23:46.682 | `af2494cc-ecd3-4b55-800e-62c40dfb6120` | DelegatePay | agents | pay | `64994363-0693-4869-b043-94186cdf7e54` | `6ac2b5d22da4d23120b41f02320fac4a` | 6684 |
| 20:23:57.584 | `af2494cc-ecd3-4b55-800e-62c40dfb6120` | DelegatePay | agents | pay | `32968d25-1f82-434b-94b7-bc49ddf9f44e` | `6ac2b5dd7257ce7a436b17af1bf14e9b` | 1365 |
| 20:24:16.748 | `cda42b04-85ed-478d-b7ca-3a44ae86583f` | DelegateProfile | agents | profile | `8d34f0fe-6692-422e-8f07-fa7eda9aeedf` | `6ac2b5f03ff68cd206beeb8f7181590a` | 5542 |
| 20:24:36.105 | `32f6a73b-e9e3-4a51-b994-616e9ffc5b31` | DelegateProfile | agents | profile | `1b64aef2-593e-451f-87bf-243f730ed337` | `6ac2b604077fa2817211a12441352c19` | 4588 |
| 20:24:44.882 | `32f6a73b-e9e3-4a51-b994-616e9ffc5b31` | DelegateProfile | agents | profile | `ec36f90a-2b00-40f0-8794-1931ed5aa9a2` | `6ac2b60c4ba6c06016ba8bfa437e44a2` | 1448 |
| 20:25:00.175 | `02a4898f-3278-4b23-8217-344fd3f568ef` | PolicySearch | tools | docs | `88ea4d3c-d3bd-4290-88ad-6db37c9a98f8` | `6ac2b61c11c23d6475cf707011ccb911` | 793 |
| 20:25:22.774 | `ae9113a3-b377-4aad-8d7a-c1b2e9a20ed9` | DelegateTravel | agents | travel | `e3cd814c-6cf4-4275-8a52-976dcbb906f9` | `6ac2b63274e921376d90a66b487e003f` | 5861 |
| 20:25:24.792 | `ae9113a3-b377-4aad-8d7a-c1b2e9a20ed9` | travel sub-agent search | tools | docs | `d57987cc-b95d-4c61-b51b-5ea09b9765f0` | `6ac2b63212c1559928c39b1068d88018` | 691 |
| 20:25:32.693 | `ae9113a3-b377-4aad-8d7a-c1b2e9a20ed9` | DelegateTravel | agents | travel | `120b07fa-a0ad-47c0-8b33-a9c9a07f86f9` | `6ac2b63c3d3e5d610336eea30657d643` | 2457 |
| 20:25:33.062 | `ae9113a3-b377-4aad-8d7a-c1b2e9a20ed9` | travel sub-agent search | tools | docs | `5de235a0-0f90-4ef6-8afa-5996f09cce6c` | `6ac2b63c5bf7da85647ec3cb57e63004` | 668 |
| 20:25:53.074 | `ec9ce1dc-084b-4e70-9f80-e2e34c76ab32` | DelegateProfile | agents | profile | `21965ed9-65c4-4af5-98c6-504e9e5693b7` | `6ac2b65147560d320feaafde1ea6b0fc` | 4325 |
| 20:26:11.132 | `73cc55da-9edd-49ed-afd1-24b84d5b57f1` | DelegateProfile | agents | profile | `26b1e6b7-0e42-4a6d-a11a-dfa30cb45a11` | `6ac2b663559fa5597a43dbd5192c1704` | 4420 |
| 20:26:19.501 | `73cc55da-9edd-49ed-afd1-24b84d5b57f1` | DelegateProfile | agents | profile | `71a4d6ef-2e84-4833-9b6a-ac3f619fed04` | `6ac2b66b582d2b337f62bd3a39481ab9` | 1471 |
| 20:26:34.980 | `a95c6ecf-19af-4c76-b467-3801c61a2e4b` | PolicySearch | tools | docs | `02deebe5-03aa-4d89-a29c-584710fa12f5` | `6ac2b67a77c8abbe07c70fe10188fe77` | 627 |
| 20:26:57.178 | `5d7149af-22f4-4024-abd2-a78a6b9fe5be` | DelegateTravel | agents | travel | `bfcc3bf4-a839-4988-94ad-4e1d072a766d` | `6ac2b69133596dd31fd6b8c359282a8f` | 4479 |
| 20:26:59.120 | `5d7149af-22f4-4024-abd2-a78a6b9fe5be` | travel sub-agent search | tools | docs | `b980a531-b689-49aa-8ef9-406f505d9498` | `6ac2b6913a68024a47fcab4e56d099a5` | 652 |
| 20:27:05.678 | `5d7149af-22f4-4024-abd2-a78a6b9fe5be` | DelegateTravel | agents | travel | `1f37de90-aaa9-4076-b257-fce5accad980` | `6ac2b699182a7c0c2e6050e77673abd5` | 3317 |
| 20:27:06.047 | `5d7149af-22f4-4024-abd2-a78a6b9fe5be` | travel sub-agent search | tools | docs | `762e75a6-6387-471f-997e-e1d36e24dbf3` | `6ac2b699366c62057190588b6fc3d875` | 693 |
| 20:27:22.678 | `dfec37f3-344c-4a68-b2b6-f5a26c4e921c` | DelegatePay | agents | pay | `2c65d7c8-65c8-47fe-a689-93bf220085e8` | `6ac2b6aa310fcce23b0963da060927c0` | 8162 |
| 20:27:34.910 | `dfec37f3-344c-4a68-b2b6-f5a26c4e921c` | DelegatePay | agents | pay | `aa300fe8-6120-4010-96ea-a804da806aa2` | `6ac2b6b61858eb0258018bd9070cc97d` | 1327 |
| 20:27:54.340 | `f776633d-b974-49f8-a83d-552cd0d4add2` | DelegateProfile | agents | profile | `1499753a-9259-448c-99ff-a20a024af99c` | `6ac2b6ca51a27a8d3a7df5656d3ca352` | 5047 |
| 20:28:13.355 | `ccdc8c33-8408-4b35-be10-4755bc79138d` | DelegateProfile | agents | profile | `4c9094d2-101d-4e8f-9a3f-674477cbbcfa` | `6ac2b6dd0ad7a76a13fc7e17063c3df4` | 4802 |
| 20:28:22.199 | `ccdc8c33-8408-4b35-be10-4755bc79138d` | DelegateProfile | agents | profile | `b8fd7310-2bff-44ca-9d4e-dbf0bc3d97cb` | `6ac2b6e6466e810730ebf7605d5dc65b` | 2111 |
| 20:28:38.005 | `12b6aebc-fcaa-444c-9367-f537d454c460` | PolicySearch | tools | docs | `1a542bde-d755-411e-a7c9-a8e2f74ef87d` | `6ac2b6f64ca77b166870f3241345eab7` | 737 |
| 20:29:00.118 | `770f8eb9-0b88-4376-aae0-a322cac770e8` | DelegateTravel | agents | travel | `59a71b95-631c-49e6-852b-8f7c8eb55e97` | `6ac2b70c2bedc6d61b99f5e31aebd6d4` | 5767 |
| 20:29:02.737 | `770f8eb9-0b88-4376-aae0-a322cac770e8` | travel sub-agent search | tools | docs | `0aed469b-b8ee-41fa-b748-6c79e303e59a` | `6ac2b70c36b6f70a0d3818aa5e1bcd63` | 689 |
| 20:29:09.968 | `770f8eb9-0b88-4376-aae0-a322cac770e8` | DelegateTravel | agents | travel | `2280229f-b5c4-42c0-bc88-e4950a644a03` | `6ac2b715389e189126dc75c065679d6d` | 3110 |
| 20:29:10.339 | `770f8eb9-0b88-4376-aae0-a322cac770e8` | travel sub-agent search | tools | docs | `282c0365-c1f0-4d6f-ace5-bf464c7fa6a9` | `6ac2b71650ea7ebd7f25a3580b5337cb` | 795 |
| 20:29:45.183 | `23afae83-0f81-4c9a-95e3-e30e47ae534b` | DelegateProfile | agents | profile | `b1189b6a-e9d8-48e8-a107-04f5e38aa284` | `6ac2b739051ac389485ea3492902005a` | 5838 |
| 20:30:52.501 | `e1e049bf-fb20-43d9-91e9-bd7064b73d07` | DelegateProfile | agents | profile | `5c791ee6-69ed-417a-88fd-5b1cb408d98e` | `6ac2b77c236067bf0fdf66236bda0a49` | 5010 |
| 20:31:11.492 | `d8aca622-381c-49ac-aca9-0396caaed7a1` | DelegateProfile | agents | profile | `948b770d-8b0a-48db-9ff6-ac1e06cc57f3` | `6ac2b78f70a795db79826d8f2e09c00a` | 5210 |
| 20:32:17.977 | `12fcb31b-c340-40ad-a82a-da7b9057a88f` | DelegateProfile | agents | profile | `80f28222-a681-41cd-b850-49ffbc870420` | `6ac2b7d11bd921a141253228007fe669` | 5419 |
| 20:32:37.145 | `c660689d-98a0-47fa-ab86-e66a91d9233e` | DelegateProfile | agents | profile | `0e5d07d2-8853-4d22-9778-961586e6df2f` | `6ac2b7e51dbcd4d756acfb775cefdcc0` | 4606 |
| 20:33:42.915 | `83e8cfb2-e30a-492a-8343-1d6df0b4b70f` | DelegateProfile | agents | profile | `2c6e8b40-0fcd-492a-a10b-6dce53abc0a7` | `6ac2b826174525cf353aea507725f9a8` | 4618 |

## Chat starts (time sink 9, question 6)

One per page load. The greeting columns are the designer's WelcomeFlow; the function's own steps
and the four hop token exchanges of each start are in the JSON file.

| Navigation | Contact | API Gateway request id | Lambda request id | X-Ray trace | Lambda log stream | Instance | Function ms | Browser ms | Greeting correlation id | Designer greeted |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20:19:38.434 | `5f22aca7-7997-4941-b9f0-661ee9e5c1df` | `366439d9-aa20-424d-af55-a181c37d36eb` | `b5ea599c-ba78-4a14-a18a-674456196820` | `1-6ac2b4db-0a346e524eaa3962565f6e54` | `d74504dac5eb498ab5df55d0411049bb` | cold | 3912 | 4428 | `58d57fd4-d1f4-442c-a605-2de46a67d31f` | 20:19:43.563 |
| 20:20:18.303 | `48e7b0a1-5754-40ef-93a1-4998ae7f8fdd` | `401945b8-2e92-48e8-a420-06f95b28892b` | `7f303de0-2f50-44bf-a0ab-f04bac5982d9` | `1-6ac2b503-5e2b8d102ba7b56a6b44cfbf` | `d74504dac5eb498ab5df55d0411049bb` | warm | 2419 | 2531 | `76be23c0-25bd-4314-afba-b7cf2ae20a5c` | 20:20:21.285 |
| 20:20:42.547 | `6dfeece8-8827-40b9-9d0f-23d831147306` | `6f73ab18-55c5-4239-8dc3-b0e584581597` | `c3ebd6e1-5f52-4646-9c18-b2e0c04dc06a` | `1-6ac2b51b-75455ec721159d4a68965dc4` | `2ba8540566e54e558184e9690e4e41e9` | warm | 2708 | 2790 | `2133eaf4-1092-4629-94f7-3cc728a45f29` | 20:20:45.451 |
| 20:21:08.081 | `8a8a1a63-33be-4f59-9294-aa0df1ae7f6e` | `ffa5841b-db09-4b4f-bd1c-510b47301f9a` | `fd8a6105-e52a-4dc8-8488-c15879ed63ea` | `1-6ac2b534-086b78b35afb561f79d01870` | `2ba8540566e54e558184e9690e4e41e9` | warm | 2416 | 2467 | `aa2a4155-9874-4d22-8ee3-31081743aaf4` | 20:21:10.719 |
| 20:21:31.080 | `e2ceda77-100c-4ea2-bc32-d346935a6fef` | `b0028c63-c5e0-4f16-bd7d-6fd9ac0e27b9` | `4dcd02ab-fff9-40e5-a710-1d66d096004a` | `1-6ac2b54b-717e17850b3a4e1b42b6a24d` | `2ba8540566e54e558184e9690e4e41e9` | warm | 2393 | 2508 | `87842555-415e-41ad-a9ef-4f93f6f260f2` | 20:21:33.734 |
| 20:21:57.261 | `f538cb39-a04d-433b-aed5-468d1aa2e6f5` | `8cab91cc-cedc-4d29-95de-77f8ce3c8539` | `3ca0fe92-44d8-4c63-b779-d9950906e0d6` | `1-6ac2b566-4761ef575af6128a2e84fc42` | `2ba8540566e54e558184e9690e4e41e9` | warm | 2331 | 2389 | `8ddf8f05-6f92-44a1-8e44-d1bb79a3c288` | 20:21:59.809 |
| 20:22:20.605 | `cfacb8b9-0358-4598-8aa5-df0f85b0f2c9` | `ab14a6bc-ae78-490b-b4e3-48c2a66e7a90` | `c9f36f86-06f6-48db-94c2-f20300e3aa28` | `1-6ac2b57d-2b61d48e4ea612105a0ebc29` | `2ba8540566e54e558184e9690e4e41e9` | warm | 2136 | 2194 | `fe9001cb-0537-4f92-8bca-100466610115` | 20:22:23.030 |
| 20:22:44.920 | `6da0565d-857c-46fd-9d4d-42852de004f9` | `3c1acf90-fbc4-43a4-b72d-aac9ae0af17c` | `420a5f6e-7cd9-43d8-ae29-d4b13af3205e` | `1-6ac2b595-5c3288101177ea5d1bc17d3d` | `2ba8540566e54e558184e9690e4e41e9` | warm | 2186 | 2274 | `aa7016d2-81fd-429f-9d5e-11355be9ba16` | 20:22:47.421 |
| 20:23:07.415 | `ed74cbd8-aca6-4173-bcbb-2f4710304965` | `833ef665-ce11-4cf7-afb9-09abf4068f4c` | `a7c1f422-0969-43d7-a128-552662241f10` | `1-6ac2b5ac-3ec66697053d269f21bd7091` | `2ba8540566e54e558184e9690e4e41e9` | warm | 2333 | 2392 | `ac3d9537-9ad0-42e0-9304-8d02fad0598c` | 20:23:09.945 |
| 20:23:34.618 | `af2494cc-ecd3-4b55-800e-62c40dfb6120` | `36e78368-1163-4078-a68a-7ba0124c930b` | `16c1f5e9-c5c2-4987-99fa-456f15ddbaea` | `1-6ac2b5c7-1547cee13fc9797625be6ac8` | `2ba8540566e54e558184e9690e4e41e9` | warm | 2210 | 2297 | `5eda9179-8210-4dae-bbee-2a15b597e180` | 20:23:37.213 |
| 20:24:00.834 | `cda42b04-85ed-478d-b7ca-3a44ae86583f` | `c2d77f0d-61ed-4511-b6be-e4a55843b161` | `3dd4a81c-3570-4369-aa6e-e8f2b8d7ff85` | `1-6ac2b5e1-0780914874a9ff0f5c8e5e0d` | `2ba8540566e54e558184e9690e4e41e9` | warm | 2333 | 2397 | `75978577-4ae1-4ae1-aaa6-af745b65ab0b` | 20:24:03.380 |
| 20:24:24.103 | `32f6a73b-e9e3-4a51-b994-616e9ffc5b31` | `b08bd04b-f44f-427f-9fcc-38a4d270b1fa` | `eb2c49f2-28a3-42bc-9777-2ab93a0072f1` | `1-6ac2b5f8-0520ea844232ddc56c1ca8c8` | `2ba8540566e54e558184e9690e4e41e9` | warm | 2247 | 2304 | `c953ad17-c2b2-438b-9ec9-35272a34ca51` | 20:24:26.601 |
| 20:24:48.152 | `02a4898f-3278-4b23-8217-344fd3f568ef` | `3bd9a01d-99da-4561-904e-5209134ff383` | `8c8ce59f-3f90-46b6-b2a7-da46aad94a4d` | `1-6ac2b611-0b06b1a70f44ea2b23f7a180` | `2ba8540566e54e558184e9690e4e41e9` | warm | 2296 | 2347 | `69c81029-0808-4f91-848a-878aadda5e62` | 20:24:50.818 |
| 20:25:10.799 | `ae9113a3-b377-4aad-8d7a-c1b2e9a20ed9` | `fa852166-127c-4699-8f67-60f5444fd4bd` | `c0e80478-a381-43c0-b7cf-93dec9e09fcc` | `1-6ac2b627-1d9dfa016f7855793d5dea64` | `2ba8540566e54e558184e9690e4e41e9` | warm | 1991 | 2088 | `fb0b0c63-5c3b-4387-8463-c049b9fe31ff` | 20:25:13.208 |
| 20:25:36.925 | `ec9ce1dc-084b-4e70-9f80-e2e34c76ab32` | `d03cc296-c3fe-408e-9150-4fe5e7d74709` | `008614be-1af9-4729-8cdd-35efd2a58726` | `1-6ac2b641-001403456d71fd7f1024a4f9` | `2ba8540566e54e558184e9690e4e41e9` | warm | 2251 | 2306 | `b5d3f776-18fc-4ef7-a7bf-6dce362104a4` | 20:25:39.433 |
| 20:25:59.182 | `73cc55da-9edd-49ed-afd1-24b84d5b57f1` | `722f9203-a016-4503-a369-2fbb180e1e4e` | `cdbb80dd-07fa-4969-b0a3-427149166e62` | `1-6ac2b658-3288511b61ca488d15cba655` | `2ba8540566e54e558184e9690e4e41e9` | warm | 2083 | 2145 | `f67f0041-2c64-4af1-8863-323149a3200e` | 20:26:01.547 |
| 20:26:22.815 | `a95c6ecf-19af-4c76-b467-3801c61a2e4b` | `a4348324-ab4e-4206-a3b9-e1618b218354` | `89198a3c-7f91-4b72-be4b-4dee8160720d` | `1-6ac2b66f-4b86e131534e8f4603702e5b` | `2ba8540566e54e558184e9690e4e41e9` | warm | 1933 | 2029 | `54028952-feac-468e-a2d9-92d816f8fa5d` | 20:26:25.114 |
| 20:26:45.259 | `5d7149af-22f4-4024-abd2-a78a6b9fe5be` | `b6701e31-da03-45e5-96fc-8486fe28da22` | `3fcc04cc-ecd7-4ba7-ac25-c634ac145d37` | `1-6ac2b686-1623aa6f51bb850f2730a514` | `2ba8540566e54e558184e9690e4e41e9` | warm | 2482 | 2547 | `a612b2cd-bace-4d12-ab3e-982353f913be` | 20:26:47.604 |
| 20:27:10.761 | `dfec37f3-344c-4a68-b2b6-f5a26c4e921c` | `ee9f83f4-8727-4cc3-a1cd-3290328e88ac` | `e5bb49d6-ffa7-4243-ac97-708c8c62603f` | `1-6ac2b69f-73e4593b7271c4f42171722d` | `2ba8540566e54e558184e9690e4e41e9` | warm | 2176 | 2240 | `8610b383-f2b5-425e-9129-8e711044cc51` | 20:27:13.274 |
| 20:27:38.035 | `f776633d-b974-49f8-a83d-552cd0d4add2` | `bc4ed260-89e7-4b5f-ac5f-52f309720ccc` | `34e704cf-d57f-416e-9d5d-a278d7dc3904` | `1-6ac2b6ba-7d19aad9313c71b85cfcf8e9` | `2ba8540566e54e558184e9690e4e41e9` | warm | 1873 | 1953 | `fc96fdc7-91b5-4345-b282-62799ca5204d` | 20:27:40.222 |
| 20:28:01.216 | `ccdc8c33-8408-4b35-be10-4755bc79138d` | `26883a4e-b722-4a28-b19b-f2d60d2da0b8` | `a53ad2dc-8f38-414d-ab8c-4a461d691530` | `1-6ac2b6d2-5c30ba965bc2a76b1825fcf6` | `2ba8540566e54e558184e9690e4e41e9` | warm | 2276 | 2334 | `77196d3f-d7d5-493d-829c-b7ec4b059749` | 20:28:03.683 |
| 20:28:26.155 | `12b6aebc-fcaa-444c-9367-f537d454c460` | `b260afe8-57ee-4888-ae1f-2f8af7610f13` | `423235c3-9fa8-487b-8def-39baafefd156` | `1-6ac2b6ea-0eee0975168df6f37cfc36b8` | `2ba8540566e54e558184e9690e4e41e9` | warm | 1991 | 2044 | `3a8e3d7e-cf98-4206-a20a-7e14e55137c3` | 20:28:28.358 |
| 20:28:48.230 | `770f8eb9-0b88-4376-aae0-a322cac770e8` | `acde4c4e-d3e9-4f21-9d71-c0b7222a1b6d` | `6b7be157-786a-49b9-a6f0-a8f2ad83bdea` | `1-6ac2b701-7fcedf8b68c1827a53e07f4e` | `2ba8540566e54e558184e9690e4e41e9` | warm | 2046 | 2134 | `40b23d43-1f2b-4746-9113-195fc6390c7a` | 20:28:50.639 |
| 20:29:32.964 | `23afae83-0f81-4c9a-95e3-e30e47ae534b` | `c1576ad4-20e4-45fc-b0b6-9c2d5f8bb769` | `f12ba1bc-bff4-4833-a5e1-5a6c6892c1d9` | `1-6ac2b72e-4396713b775d24fa460aad5b` | `2ba8540566e54e558184e9690e4e41e9` | warm | 2313 | 2411 | `d0e00e4b-7951-486d-8200-ce2335a36b23` | 20:29:35.985 |
| 20:30:40.358 | `e1e049bf-fb20-43d9-91e9-bd7064b73d07` | `0ecf9f49-bd2b-43ca-9eec-2949d5dd5309` | `41d576df-c34e-4796-8b94-2d6e1a296f75` | `1-6ac2b771-13c42f9b428043ab71ffd9c8` | `2ba8540566e54e558184e9690e4e41e9` | warm | 2311 | 2396 | `61df3887-0d16-4226-8877-d8ca0d9bc9a2` | 20:30:42.996 |
| 20:30:59.404 | `d8aca622-381c-49ac-aca9-0396caaed7a1` | `bde4f8dc-6699-4154-8ee9-45ef21b0c9d3` | `be8ff753-c3c3-4532-922d-39d19354fbd2` | `1-6ac2b784-6dfdcbac0e68125836092453` | `2ba8540566e54e558184e9690e4e41e9` | warm | 2222 | 2286 | `6de56073-a05e-4a4d-b05d-0aeda1ebe791` | 20:31:01.896 |
| 20:32:06.019 | `12fcb31b-c340-40ad-a82a-da7b9057a88f` | `a7f7167b-831d-49bd-a148-7deb4377c184` | `2a98aa21-85e2-4981-b421-69ed4a55bfef` | `1-6ac2b7c6-50387a767f293df071f2d7c9` | `2ba8540566e54e558184e9690e4e41e9` | warm | 2144 | 2232 | `5d38888a-69dc-491e-af28-0cbf7804ee2c` | 20:32:08.416 |
| 20:32:25.216 | `c660689d-98a0-47fa-ab86-e66a91d9233e` | `32e161be-ffa6-4207-9382-edb822f74ad3` | `d508224b-c21c-4420-85b4-940be9b3dabc` | `1-6ac2b7da-3bb212d20054451c6e25dcf0` | `2ba8540566e54e558184e9690e4e41e9` | warm | 2067 | 2149 | `cc7b7aec-97c9-414e-9be0-ad0df4fa7f7a` | 20:32:27.573 |
| 20:33:31.010 | `83e8cfb2-e30a-492a-8343-1d6df0b4b70f` | `2b27f8eb-44b8-481a-9ff8-f09f27b037e4` | `c8be9500-5833-43f8-81cb-581214c0586a` | `1-6ac2b81b-4fc1082c375e6066389fcb7e` | `2ba8540566e54e558184e9690e4e41e9` | warm | 2276 | 2424 | `d106c00e-880f-4f50-ba0f-9c6241ea2a03` | 20:33:33.676 |

### Hop token exchanges at chat start

The four on-behalf-of exchanges of each start, at the issuer (credential provider `guppi-obo-hr-bridge`).

| Time | Contact | Audience | Issuer API Gateway request id | Issuer Lambda request id | X-Ray trace | Handler ms | Instance |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 20:19:41.419 | `5f22aca7` | api://hr-tools | `cec04961-3f7c-4c6c-b7bf-000c522abf18` | `6a7e6003-3fb2-4e67-8993-17e42769f799` | `1-6ac2b4dd-096328866f527c8e0cd486d7` | 8.21 | cold |
| 20:19:41.424 | `5f22aca7` | api://hr-agents/pay | `16068f92-1177-413e-93bb-1cc6fbab145f` | `69a0b344-ad32-4f92-a851-295e97cd0156` | `1-6ac2b4dd-3808ae1a122cbc9c47b02664` | 8.28 | cold |
| 20:19:41.430 | `5f22aca7` | api://hr-agents/profile | `b0b68bfa-67fd-472a-88f1-86599dfb210b` | `c0cc2b0c-6c21-406f-b835-5d7f8f4a32ea` | `1-6ac2b4dd-208e93383288c2b424f1d425` | 8.61 | cold |
| 20:19:41.482 | `5f22aca7` | api://hr-agents/travel | `04ab3386-8730-4bb6-a742-ddc47f31428f` | `408810c6-82d2-4c05-a00f-dbe407754cca` | `1-6ac2b4dd-41ef61a8373144744309df67` | 8.85 | cold |
| 20:20:19.623 | `48e7b0a1` | api://hr-tools | `2ad3a989-91cb-485a-a369-c7d8e72cdfa5` | `d56ac616-6b77-49c8-b0fa-9d14439cecba` | `1-6ac2b503-532fcb8905a5856b4e0b9a92` | 21.05 |  |
| 20:20:19.631 | `48e7b0a1` | api://hr-agents/travel | `cc257b69-fbac-4f50-8e6f-935675943888` | `85e400e6-5304-4bd3-ab79-6c243d9a0c03` | `1-6ac2b503-3a02b9aa7b477cc8683c07b4` | 21.36 |  |
| 20:20:19.641 | `48e7b0a1` | api://hr-agents/profile | `3b1f729e-2bbe-4aec-9e58-c38ef5f1a731` | `ace85e1c-2c99-446b-8f6d-914cae2318b2` | `1-6ac2b503-2474b9641f31a3261b960702` | 22.63 |  |
| 20:20:19.662 | `48e7b0a1` | api://hr-agents/pay | `d620f385-708a-4ea5-b8f5-d089f4065f5f` | `441895e4-787b-411c-aebb-318f02d47765` | `1-6ac2b503-222ade941b96f01659488f90` | 7.62 |  |
| 20:20:43.516 | `6dfeece8` | api://hr-agents/profile | `08b07e50-427c-4d05-a5c6-e7af3c3ae38c` | `80a8b975-fea5-4118-acb0-b3289e758108` | `1-6ac2b51b-2e4be93b5b87618569b61e9c` | 21.61 |  |
| 20:20:43.520 | `6dfeece8` | api://hr-tools | `e8897a24-f586-40f9-a4e6-c903f1e2e003` | `63150e73-8965-4fbf-972a-5fe3a9344ba8` | `1-6ac2b51b-0ea2f4d45104d0595aa9a3d2` | 20.99 |  |
| 20:20:43.524 | `6dfeece8` | api://hr-agents/travel | `00850e22-d58f-48b9-91e1-3e7c361ead37` | `6c560774-6fb6-441f-b6d8-af751f7a64f4` | `1-6ac2b51b-7fcff0c0624696710cf0dadb` | 24.56 |  |
| 20:20:43.531 | `6dfeece8` | api://hr-agents/pay | `53924e37-6784-4111-9117-f4fa6b44a671` | `afd3e010-8b5f-4008-9e8d-81a7a3795d09` | `1-6ac2b51b-598d91236ffe39c9769683f0` | 20.81 |  |
| 20:21:09.064 | `8a8a1a63` | api://hr-tools | `0bbaaa99-261d-4b04-beef-d400d4e1d732` | `eb3e43f0-80f8-4be1-abc2-f8230306b7e0` | `1-6ac2b535-391c82a06fe659d8301afd49` | 26.81 |  |
| 20:21:09.067 | `8a8a1a63` | api://hr-agents/travel | `d8661445-8233-4222-853b-827aa341cf33` | `9ca22394-4480-474c-96b5-7970c37d9885` | `1-6ac2b535-54f9022d54bf4582483b8486` | 24.75 |  |
| 20:21:09.080 | `8a8a1a63` | api://hr-agents/pay | `af60c516-e3e4-4624-8756-39c7bbfae0fb` | `050fc108-7427-4bad-ad5e-4e75a088f5a1` | `1-6ac2b535-73752eee2c1dfb2e617cd9c7` | 21.21 |  |
| 20:21:09.092 | `8a8a1a63` | api://hr-agents/profile | `eeacc941-42f6-4087-b8ee-3667583c709c` | `5f335d97-5095-43c2-b3e0-bcfa06c68ddb` | `1-6ac2b535-16031e0a5029e6561111c854` | 22.56 |  |
| 20:21:32.053 | `e2ceda77` | api://hr-tools | `013a9d35-1228-4307-b0b2-34deb7212d2f` | `3a0b0e48-fa90-4eae-8143-bf04bad8ab9b` | `1-6ac2b54c-37fa3cfe6b6372ad5249e789` | 20.48 |  |
| 20:21:32.057 | `e2ceda77` | api://hr-agents/pay | `594b5fd8-2880-481a-88d9-58075092e3d5` | `40518ce5-e311-48d5-9e92-b93bf4ee73d1` | `1-6ac2b54c-3ec68b8d51ae61ba4d8731eb` | 23.4 |  |
| 20:21:32.061 | `e2ceda77` | api://hr-agents/travel | `79a3ff32-1764-4ea3-a36b-3554db378e6b` | `4284f85a-dd90-4571-822c-346ac6936e92` | `1-6ac2b54c-0bdda59a609f3d23493dae84` | 25.32 |  |
| 20:21:32.064 | `e2ceda77` | api://hr-agents/profile | `55bd9113-3a79-467f-970b-0fec25e22799` | `a99b1f4b-79d9-4d26-8718-76917be0c992` | `1-6ac2b54c-085fdad44d2bffdb312e0df3` | 20.11 |  |
| 20:21:58.192 | `f538cb39` | api://hr-agents/travel | `ec484f4d-2d46-4c52-9409-47d4af15128a` | `087c12f3-67a3-4145-a41d-d47fea58f559` | `1-6ac2b566-4d2a3b6f2977cca17ed03187` | 23.95 |  |
| 20:21:58.198 | `f538cb39` | api://hr-agents/pay | `796e01e1-4766-4994-bb76-5acf522f44d6` | `3032b954-5a28-49f7-8a81-982626c812eb` | `1-6ac2b566-0d4e9e5e701e4b9d3b5cf8d0` | 23.55 |  |
| 20:21:58.200 | `f538cb39` | api://hr-agents/profile | `c1c86d97-00cb-4777-838d-7dec0c031356` | `77307c8a-fc40-4edf-9988-4d3822fb5926` | `1-6ac2b566-532980416e214fa54d289999` | 24.18 |  |
| 20:21:58.204 | `f538cb39` | api://hr-tools | `64461337-e1e0-4a30-ba19-330be386af83` | `8d4c35be-fda1-4e22-bb28-1c71752d2b1c` | `1-6ac2b566-78f3411d2dc5002d328aa885` | 23.23 |  |
| 20:22:21.562 | `cfacb8b9` | api://hr-agents/pay | `eeb2085f-aae7-49e5-b30e-99a54a39b57f` | `219f0454-11c2-437b-9f59-a9dd193829d1` | `1-6ac2b57d-2faaa0b83b263bd42302c776` | 7.97 |  |
| 20:22:21.573 | `cfacb8b9` | api://hr-tools | `a866d80c-054c-448f-90d9-a2dc474d3d81` | `b135ad24-bcca-473a-906f-87485d89f41c` | `1-6ac2b57d-59b686d51798846c3cb799f2` | 20.68 |  |
| 20:22:21.574 | `cfacb8b9` | api://hr-agents/travel | `b44bbf75-0513-41a2-83cb-17243d174ed4` | `29118dd9-0d8a-4720-9d60-7e52e30c22f5` | `1-6ac2b57d-2819b30361bac9423a3f8c1a` | 25.46 |  |
| 20:22:21.577 | `cfacb8b9` | api://hr-agents/profile | `ecd83f8d-70f0-454e-9956-5b927216cf1e` | `67bdfead-eac9-4de7-8f76-13e633a60b18` | `1-6ac2b57d-4cfaf5a6156f4eed436ac0af` | 7.67 |  |
| 20:22:45.907 | `6da0565d` | api://hr-agents/profile | `ae34c165-75d4-4b03-a282-f1e5b791e7dc` | `78f6b7a1-bd87-4834-8fc5-0399e77aeeca` | `1-6ac2b595-0e72697d0748993e453ec53e` | 23.9 |  |
| 20:22:45.917 | `6da0565d` | api://hr-tools | `22c3acc4-05be-4dcb-afce-3edcbf907edd` | `569d9ddc-18fa-4f56-b9a1-ee7f510e8340` | `1-6ac2b595-698b8ab62e7f9ef562d1b817` | 22.19 |  |
| 20:22:45.924 | `6da0565d` | api://hr-agents/pay | `a050b9fe-1b93-468a-b506-caeca5374ead` | `fa67457d-479e-4c48-80cf-d38820e87d3a` | `1-6ac2b595-5e296774404ba62d7f1a90be` | 23.92 |  |
| 20:22:45.925 | `6da0565d` | api://hr-agents/travel | `56e7d8fa-bf4b-44b2-b6ff-1d6c7335a768` | `1606e6a2-c6dd-4724-8e59-8d67993a6a57` | `1-6ac2b595-3661e3490c385c6643b293f7` | 25.04 |  |
| 20:23:08.381 | `ed74cbd8` | api://hr-tools | `bc2404d5-106e-4744-a97d-aee5fa230d80` | `f9e988a5-42c2-4644-abc9-6a0347ef7689` | `1-6ac2b5ac-24e607c635d7e87507ef0093` | 22.35 |  |
| 20:23:08.387 | `ed74cbd8` | api://hr-agents/travel | `855cd99d-1f5f-4793-87de-b026df6357ab` | `b4f6130b-d262-4758-b58a-a61fe511acc5` | `1-6ac2b5ac-67c6f7120604d653793693c8` | 24.27 |  |
| 20:23:08.396 | `ed74cbd8` | api://hr-agents/pay | `49dc5207-921e-4a23-8dda-91e78f1df776` | `6bbdd450-f20a-4c90-8788-34aed675d503` | `1-6ac2b5ac-09a53eb26916b7fd0cbf7a80` | 22.32 |  |
| 20:23:08.396 | `ed74cbd8` | api://hr-agents/profile | `4439a0f9-fa09-4194-9f6c-c5e6d736f399` | `b89cfbcc-ec06-43bd-830c-977c08cc5919` | `1-6ac2b5ac-71f8dd0226e88d087b5448f7` | 19.3 |  |
| 20:23:35.658 | `af2494cc` | api://hr-agents/travel | `2787f356-e3f7-4cef-bdf1-7de350258437` | `64d68754-b26c-4f93-9359-16636a0badbc` | `1-6ac2b5c7-4dea9c3554a081a017e100ae` | 26.77 |  |
| 20:23:35.660 | `af2494cc` | api://hr-agents/profile | `c006dd78-6478-4ee4-aa94-6040963b138b` | `f79d74ab-fb8f-4a5e-81a7-0655367d9ffa` | `1-6ac2b5c7-1e3c18bd52c13d9469b694cc` | 19.8 |  |
| 20:23:35.673 | `af2494cc` | api://hr-tools | `3c587100-6a61-4db0-b369-5d596653d8a5` | `11778f6b-02ce-49cf-b16a-bf2e79231b97` | `1-6ac2b5c7-4026cc6422d11b696fabcb0a` | 20.72 |  |
| 20:23:35.674 | `af2494cc` | api://hr-agents/pay | `f081f91a-f8fe-4be3-bd36-ca3399474ca5` | `b230c528-03ed-4395-973e-f317d6adc196` | `1-6ac2b5c7-17a450e64131d27971a2a142` | 21.9 |  |
| 20:24:01.797 | `cda42b04` | api://hr-agents/pay | `c4867147-d26a-40f1-986b-95ce134a06d4` | `45322561-6798-433e-8bb5-e3a4e6e41941` | `1-6ac2b5e1-31ae2d9d53879dfb36e0d9eb` | 21.23 |  |
| 20:24:01.804 | `cda42b04` | api://hr-agents/profile | `4999c6aa-1d66-49a6-8920-8a5417a4642d` | `00e7c0fe-ef30-4a8a-bf12-9c96065324c2` | `1-6ac2b5e1-769aba6b60bef85a6792b03c` | 23.51 |  |
| 20:24:01.809 | `cda42b04` | api://hr-tools | `ca99e7ce-86aa-4cf3-b5f3-e87eacf54fba` | `5bad4004-405b-469b-bf38-dec20563eb7e` | `1-6ac2b5e1-07b736ca6fae8d6573c3f77e` | 21.97 |  |
| 20:24:01.813 | `cda42b04` | api://hr-agents/travel | `881bafaf-2a45-4ec1-a881-195c6830d2e2` | `4608f371-e9a8-4320-b4ed-797be34ce1c9` | `1-6ac2b5e1-17a1c888581a7b363a9e7765` | 23.47 |  |
| 20:24:25.078 | `32f6a73b` | api://hr-agents/travel | `568aac27-cc4d-4970-840b-f84dd9b761d7` | `aabbfb70-fd4a-42a0-aaba-e0e29312862e` | `1-6ac2b5f9-2ce37ba96ef64193099e51c9` | 7.84 |  |
| 20:24:25.080 | `32f6a73b` | api://hr-agents/profile | `f8bf0a34-4db9-400f-aed9-3ed753f7bf86` | `bbcd261e-7e00-4ebc-bdb9-172bb7e3d2c2` | `1-6ac2b5f9-6d5237f773ade64234be0e45` | 22.87 |  |
| 20:24:25.090 | `32f6a73b` | api://hr-agents/pay | `52ef8dfb-3fe3-41c5-b8b2-b114012f0647` | `cc5336c8-1130-4cba-bc3c-4a689418c3ee` | `1-6ac2b5f9-08572cf258718a1a72c4c24f` | 23.77 |  |
| 20:24:25.095 | `32f6a73b` | api://hr-tools | `0de9acaf-9e29-49ac-ac57-1e6c6e4564fc` | `d0404a9d-3d4c-4420-944b-e8b6df1fd56c` | `1-6ac2b5f9-5bcfb52d79dc412a785b9cdc` | 8.27 |  |
| 20:24:49.208 | `02a4898f` | api://hr-agents/travel | `dd0d9857-2308-4b61-ac26-aed1f5c7ae11` | `1ade7a94-481c-4c8a-a3c2-cae2b55265dd` | `1-6ac2b611-1196c76f3ebc4cf726c595f7` | 24.22 |  |
| 20:24:49.208 | `02a4898f` | api://hr-tools | `68b3df32-5d8f-4da6-922d-4fdb95f05d8d` | `402b5b50-fbfa-4723-82a4-2a496d391a29` | `1-6ac2b611-765f94c408832cb369693b5a` | 21.7 |  |
| 20:24:49.215 | `02a4898f` | api://hr-agents/profile | `48a6b179-97eb-4b68-aeea-52304e4e42aa` | `319cbb12-da28-43f5-8ed8-950c1adfe31a` | `1-6ac2b611-55fbc0bd151ed00e533b8575` | 22.41 |  |
| 20:24:49.217 | `02a4898f` | api://hr-agents/pay | `96334f8d-aabb-4b7a-95d5-ee162d4a20f3` | `e1c94518-f550-461c-ab23-f87e43db0472` | `1-6ac2b611-6d661f1d1b0670e87f910758` | 23.22 |  |
| 20:25:11.873 | `ae9113a3` | api://hr-agents/pay | `a29d6302-a6ca-49ef-9b27-4a877010cf21` | `edcbbf2f-136f-4ef5-a2f8-4a1bbec8ced2` | `1-6ac2b627-06e709a35b754eb96987a0af` | 20.54 |  |
| 20:25:11.874 | `ae9113a3` | api://hr-agents/travel | `0384abc3-cfa8-49b4-8982-a7ce5be177ab` | `b4025202-0dc3-458f-960a-2684e82e4d91` | `1-6ac2b627-187e5024489955716f0eadcc` | 22.68 |  |
| 20:25:11.887 | `ae9113a3` | api://hr-tools | `12c140c0-aed2-4906-af32-c44c742ebf6d` | `fc75e49c-f931-4f54-8aa3-a424f24348dc` | `1-6ac2b627-756b83c656322e854e07cdf1` | 20.65 |  |
| 20:25:11.890 | `ae9113a3` | api://hr-agents/profile | `06f9e97b-9b9f-4d17-9398-e4ef1be1ce52` | `b2c7f627-20fa-4034-931b-1755b0560929` | `1-6ac2b627-7ad02d2a1ad8bf624bdf6ed2` | 23.28 |  |
| 20:25:37.819 | `ec9ce1dc` | api://hr-agents/travel | `9c70f8ad-79bb-4d2f-bf88-b88a2268a7c6` | `a4e58bd1-dcf6-445e-85b9-4e6f70a4e536` | `1-6ac2b641-22db23a63a5be8d968ce1d1b` | 21.04 |  |
| 20:25:37.823 | `ec9ce1dc` | api://hr-agents/pay |  | `78f063a8-a79c-43d3-bf03-c47bf9ecaa98` |  | 19.04 |  |
| 20:25:37.827 | `ec9ce1dc` | api://hr-tools | `3ad2e5e0-82ca-4fc7-a7a4-37304d532d39` | `a4b90488-f319-4b0e-aa4d-c97f7f30426d` | `1-6ac2b641-001a7ff9162bc57d2bf3b9e4` | 25.53 |  |
| 20:25:37.836 | `ec9ce1dc` | api://hr-agents/profile | `ca02fe16-3f2a-4b53-a8e1-c80e9900f202` | `587e0de5-6931-48ac-b3e0-a9e738d3871d` | `1-6ac2b641-11c62f5848d7ed9726f0fa7e` | 20.34 |  |
| 20:26:00.199 | `73cc55da` | api://hr-agents/pay |  | `f21478e2-3eab-4f36-97fe-46740bf3a967` |  | 7.92 |  |
| 20:26:00.205 | `73cc55da` | api://hr-agents/profile | `a3b64b5c-402d-4286-8228-7676afcf2bcd` | `d8a94d53-b95b-469d-879a-15eb7fa9ac57` | `1-6ac2b658-25625db861000bea101582aa` | 20.58 |  |
| 20:26:00.216 | `73cc55da` | api://hr-agents/travel | `e37f0a8f-25a9-4383-aae7-9b9595235c35` | `ce5c2a57-f1b1-4b41-badc-52653561b4bb` | `1-6ac2b658-4c6154f673643cca665ec180` | 7.99 |  |
| 20:26:00.225 | `73cc55da` | api://hr-tools | `5cc9cb86-1645-4f27-91d4-d1391ccdf534` | `74d12a27-f391-4b8e-b8c3-4efe0ccbdac7` | `1-6ac2b658-3d3b5e08444d80db1303dcb2` | 22.18 |  |
| 20:26:23.820 | `a95c6ecf` | api://hr-tools | `32fe5aa1-f3fc-4e52-a2f0-078502d488bb` | `295df6d8-0683-42d0-b2f7-d1f0115d90f7` | `1-6ac2b66f-6f1f1e157816a0112cae61e7` | 19.04 |  |
| 20:26:23.830 | `a95c6ecf` | api://hr-agents/profile | `c6be410e-d0c0-4983-95ae-ffcbef48f004` | `277b8d56-4ec3-4b40-98f0-f5bd71e69b28` | `1-6ac2b66f-04c726e95513431d09d52972` | 20.78 |  |
| 20:26:23.830 | `a95c6ecf` | api://hr-agents/travel | `57ace334-774c-4abb-8209-8968818f0092` | `e4f8a86a-ceb6-4219-bfdb-84d6e7a89fc7` | `1-6ac2b66f-419563f8025b53394ee286e1` | 23.31 |  |
| 20:26:23.835 | `a95c6ecf` | api://hr-agents/pay | `6d48e8ed-f897-4f08-955d-ff47c667b65f` | `0866361a-8013-4acd-828a-d3ab25c22344` | `1-6ac2b66f-19083ea161d38ab43ebd5868` | 24.37 |  |
| 20:26:46.170 | `5d7149af` | api://hr-agents/travel | `2eead082-7412-442d-811c-05d056cb8c67` | `e49f4184-5c31-4d1d-81b0-6fef2a5b35fa` | `1-6ac2b686-2368320047ec2a28049b670c` | 23.59 |  |
| 20:26:46.172 | `5d7149af` | api://hr-agents/profile | `d0855622-1bd6-4db1-a15b-d58e7fad9175` | `e9dcd29d-0cd0-4561-a760-c14d71a62804` | `1-6ac2b686-6d043bde40701e8c01cbe5b3` | 22.37 |  |
| 20:26:46.187 | `5d7149af` | api://hr-tools | `e6d04b07-0f87-43da-8742-8aa855e8a34c` | `1d3b5ba6-a439-441f-a666-0430d55a2877` | `1-6ac2b686-6ee0f5bc542ea92925a6fdaa` | 22.74 |  |
| 20:26:46.194 | `5d7149af` | api://hr-agents/pay | `9bdcc16c-74a4-4af7-b622-985d7587bb40` | `62c57408-ca76-4790-8413-971676c5eb45` | `1-6ac2b686-3a1bc740778894ee083e97ec` | 19.87 |  |
| 20:27:11.716 | `dfec37f3` | api://hr-agents/pay | `2fab76e2-3673-407b-8c4f-e833131d793e` | `449caf4d-6abc-469e-8e7b-4e3fc90126ef` | `1-6ac2b69f-35ed6be40145486e61c61525` | 21.08 |  |
| 20:27:11.719 | `dfec37f3` | api://hr-tools | `d7219051-71c9-40b9-b789-10c4ae19bef0` | `7d9e4e7f-0870-44cd-98fe-04613e7ba0a3` | `1-6ac2b69f-2184f14d2c719bee16027524` | 23.74 |  |
| 20:27:11.729 | `dfec37f3` | api://hr-agents/profile | `431feeb1-0790-425e-8b24-3361f6742046` | `b5f3fde0-a4c5-413b-89a0-d49bf2fc2f1d` | `1-6ac2b69f-6a09be462f7d568f1cb48be1` | 22.61 |  |
| 20:27:11.732 | `dfec37f3` | api://hr-agents/travel | `35d5d1bf-37ac-4ef1-981e-3038c3e3a3e5` | `fb2959aa-a4ad-48ce-b414-5b7497cd0ff2` | `1-6ac2b69f-6cc230dd41cd2dd844a450aa` | 20.9 |  |
| 20:27:39.020 | `f776633d` | api://hr-agents/pay | `fad66da3-ba77-4429-a17c-c8ea788bb052` | `bc4f7f35-dd3d-4f9d-ae75-e3cce0c214d5` | `1-6ac2b6bb-3abf478669bd751d3e29cef8` | 23.65 |  |
| 20:27:39.024 | `f776633d` | api://hr-agents/profile | `e9c0c21c-051c-4461-8d90-6988061ba4e5` | `a9b0987b-baef-427f-a466-0da80fb129be` | `1-6ac2b6bb-450853607c85ac4368b3e3b2` | 20.72 |  |
| 20:27:39.027 | `f776633d` | api://hr-agents/travel | `b2f30356-003c-40d0-9e14-2f76863b4bac` | `c6b2bff1-bdd7-4f5c-b647-3ccc583f180c` | `1-6ac2b6bb-5aabbca76ba1e8df75aced6f` | 20.64 |  |
| 20:27:39.028 | `f776633d` | api://hr-tools | `c2d3e783-1f0e-400c-a8b8-a7edc8f87717` | `abcabd74-70f7-42b8-b9c8-d44b7afe7e7a` | `1-6ac2b6bb-7a516fcc114b477429837aa3` | 18.02 |  |
| 20:28:02.178 | `ccdc8c33` | api://hr-agents/profile | `6bc9acaa-fe46-4258-b5bb-4030fe247073` | `2abcf27b-ea7f-47ed-9135-6b0cd3dbf973` | `1-6ac2b6d2-2a60333834233cc446588534` | 8.22 |  |
| 20:28:02.179 | `ccdc8c33` | api://hr-agents/travel | `c0cd9e3d-a3a1-4bc7-ae17-186df52aa51b` | `c358439a-de69-477a-8611-94490f53951e` | `1-6ac2b6d2-4264baae4f24c04c743a4689` | 22.37 |  |
| 20:28:02.215 | `ccdc8c33` | api://hr-tools | `f7bce073-8861-4fb2-8092-59f401169880` | `97b02ea7-0357-42ad-af3b-4a55138906cb` | `1-6ac2b6d2-0d7654dc117e90e474a42f81` | 7.86 |  |
| 20:28:02.262 | `ccdc8c33` | api://hr-agents/pay | `c23739dc-1726-4c01-88b8-c1392c35af1b` | `d893cb23-8e10-4679-b83e-08786a20385b` | `1-6ac2b6d2-56cb44cc7065db1c2b31bab1` | 7.55 |  |
| 20:28:27.049 | `12b6aebc` | api://hr-agents/profile | `8a720894-425e-4e42-9b33-93cbcc60958f` | `fdd9cc69-fe26-4bc8-9a92-cb557b7c7eb0` | `1-6ac2b6eb-1625b8cf5f2f86380db2891b` | 21.0 |  |
| 20:28:27.050 | `12b6aebc` | api://hr-agents/travel | `7eb6cbc3-5c40-4e73-9561-7715bd0988fe` | `12ab84e0-1b2f-4267-ba24-2544a224f333` | `1-6ac2b6eb-2888eb733c23efc836266ea8` | 21.96 |  |
| 20:28:27.079 | `12b6aebc` | api://hr-tools | `df7c3104-cb1a-4551-89bd-183267e95b11` | `a3f82a3b-62d5-4604-b312-bc15032caf33` | `1-6ac2b6eb-08ea580a35b8cb3a7be830bf` | 8.71 |  |
| 20:28:27.092 | `12b6aebc` | api://hr-agents/pay | `c080667f-33ee-4998-b65e-a65e0c6d7c7d` | `e94de0fa-9c19-4f30-a3ff-d46a575c1e4f` | `1-6ac2b6eb-7c9a78463e73f5fe2a543772` | 8.23 |  |
| 20:28:49.237 | `770f8eb9` | api://hr-tools | `761d0dd9-6b58-46f2-ba31-d77a12777a61` | `8d5213e8-7df7-4a01-a0eb-c6ad0b82a413` | `1-6ac2b701-77960b341511079d6d55a7e5` | 21.57 |  |
| 20:28:49.242 | `770f8eb9` | api://hr-agents/pay | `f88c24fe-b67e-4cd9-9cd2-2741bfd9a0c2` | `6ad77c0b-3011-43c4-a759-3c1774f4f08a` | `1-6ac2b701-0a14f4774f6853cb68382ed7` | 24.6 |  |
| 20:28:49.245 | `770f8eb9` | api://hr-agents/profile | `cba1ba44-c85f-43c5-b3d7-764c8671a824` | `975bd72c-2b20-446e-8262-b507fa96c6ce` | `1-6ac2b701-7dcd569974e419cc757e213f` | 22.35 |  |
| 20:28:49.248 | `770f8eb9` | api://hr-agents/travel | `c72cf167-98ea-41ec-b783-0ab9c133bc66` | `512d79a9-dda2-45c3-a613-10824a1591e4` | `1-6ac2b701-1e721769407b21001aeb5884` | 25.55 |  |
| 20:29:34.332 | `23afae83` | api://hr-tools | `455dcf03-db90-4df4-8316-2e3655d1f648` | `cd60bb28-a116-4cab-aaa4-b88ba5fde1e4` | `1-6ac2b72e-10aeb43a61f8a2a16d42f7e4` | 21.71 |  |
| 20:29:34.338 | `23afae83` | api://hr-agents/pay | `6f84c060-3eac-4481-a370-c2e399bd3679` | `f867a824-e1c1-4b41-bba6-f66b0fd4738a` | `1-6ac2b72e-2c73b4976804ef381d7bbd28` | 22.63 |  |
| 20:29:34.338 | `23afae83` | api://hr-agents/profile | `c462c44f-a301-4546-8018-0555096822a1` | `0b657dbf-d330-426b-b9c8-ea9e6128e044` | `1-6ac2b72e-14893e5d254dd3225322118e` | 18.05 |  |
| 20:29:34.352 | `23afae83` | api://hr-agents/travel | `672395e0-a89a-4cda-a2ab-87608c6c5158` | `3a52c57f-13da-4a6d-8230-dd94056fdbf2` | `1-6ac2b72e-2cf7b7542cbe9a5a432aaa3b` | 21.71 |  |
| 20:30:41.410 | `e1e049bf` | api://hr-agents/pay | `f81a530e-53a8-4d19-90a4-1f12b7454cbe` | `b20964f1-9c0e-464e-b75b-4fa336ab2d8b` | `1-6ac2b771-4091da966f11cbd326729f44` | 23.18 |  |
| 20:30:41.412 | `e1e049bf` | api://hr-agents/travel | `c694a3f4-c0fe-44b9-9124-1991037bc4ab` | `57a5ef4d-3d82-41e2-ac74-17c3746ae1c0` | `1-6ac2b771-7fcc62580bcd6f4b7d6314ac` | 22.19 |  |
| 20:30:41.415 | `e1e049bf` | api://hr-tools | `95dc965f-659c-4e58-bea2-ee8c775c3a54` | `06cb079f-bb6a-4a28-b64b-dbd422ea1579` | `1-6ac2b771-701cf24964dea5e22030e538` | 26.31 |  |
| 20:30:41.427 | `e1e049bf` | api://hr-agents/profile | `88468121-87a0-476d-aef6-86c28eb30496` | `0d181a21-1004-4016-b0c2-c862a16c1254` | `1-6ac2b771-310c51c536f88ab428069a67` | 23.13 |  |
| 20:31:00.368 | `d8aca622` | api://hr-agents/pay | `17f7ef4c-ee03-40a6-a15c-96dc46517e0b` | `da4f02b6-15bf-49a2-85eb-6110c7757269` | `1-6ac2b784-2b7b622d7f5f78560b44d122` | 7.86 |  |
| 20:31:00.378 | `d8aca622` | api://hr-agents/profile | `83fe32f3-f7ee-47a6-932e-ff1bc3b07398` | `9191afa5-749f-4a7a-a77e-a61e13fcd242` | `1-6ac2b784-76ed1e763e6074a041b25d83` | 22.76 |  |
| 20:31:00.388 | `d8aca622` | api://hr-tools |  | `dfed2c78-8dda-4122-80ea-224b76715774` |  | 7.43 |  |
| 20:31:00.391 | `d8aca622` | api://hr-agents/travel |  | `9e42a074-e749-4be0-825d-e81e51b34b53` |  | 20.85 |  |
| 20:32:06.979 | `12fcb31b` | api://hr-agents/pay | `1586ef52-3230-4558-b285-6d383e99ee61` | `974b6ac0-4734-4333-a9f8-d1fbf6fac18b` | `1-6ac2b7c6-5f575bee2be8ecc43a8cd40f` | 22.32 |  |
| 20:32:06.981 | `12fcb31b` | api://hr-agents/profile | `5f826d1a-37b2-4f5a-a35a-4cbe9a0f0e10` | `fe8403c3-8caa-4139-a183-bf81fc18f156` | `1-6ac2b7c6-3aa4e1f12d2fe2912b95d237` | 28.99 |  |
| 20:32:06.981 | `12fcb31b` | api://hr-tools | `8dc9a3ab-ddb6-4996-a112-d7e05deb2e36` | `d1485f7e-1502-4e26-a42b-31eb5acd8c25` | `1-6ac2b7c6-1a83597774035cba75ccf9d2` | 27.04 |  |
| 20:32:06.983 | `12fcb31b` | api://hr-agents/travel | `d17f9255-dcd1-462c-8b14-a5700e717afb` | `6629a8d1-51c3-498d-b058-20feffebfb44` | `1-6ac2b7c6-448f7a3e5c5c849149d6d838` | 26.24 |  |
| 20:32:26.176 | `c660689d` | api://hr-agents/travel | `29a5ceef-84b6-42de-87fa-6cf3281d1dac` | `206bf58a-0f01-4645-82ff-1648ffd50121` | `1-6ac2b7da-64f125a846114f09744483ba` | 8.68 |  |
| 20:32:26.179 | `c660689d` | api://hr-agents/pay | `f5489e5e-cd93-41c4-a334-2720d38e6c70` | `6156032b-7daf-4f33-a695-8bcdf05be081` | `1-6ac2b7da-43c9e7977f5e2cee3630e61b` | 21.44 |  |
| 20:32:26.185 | `c660689d` | api://hr-agents/profile | `48fc253a-1e11-47db-b3a8-2da8bc43c45a` | `aecf2dca-42ec-4c41-a79b-57752d9d7453` | `1-6ac2b7da-38e9cbb24e55dc5b67267739` | 20.75 |  |
| 20:32:26.198 | `c660689d` | api://hr-tools | `3af6880f-fa24-41a2-9bb3-852fb753234b` | `9b999ebc-b8ab-4c0f-99a2-ce6ef54138ba` | `1-6ac2b7da-15fa650d2c1fe9d309bed0d0` | 8.84 |  |
| 20:33:32.088 | `83e8cfb2` | api://hr-agents/profile | `2b34f26f-f86d-41fd-8830-578337fe53ef` | `8de13e5a-45cc-40c1-8a04-d80668722140` | `1-6ac2b81c-53a3f4d05e14020e5f8e3329` | 27.0 |  |
| 20:33:32.099 | `83e8cfb2` | api://hr-tools | `ea4a7602-332a-4694-954f-df4368c5b38f` | `0577f508-b137-4a8f-a414-ce913652b45b` | `1-6ac2b81c-3868f38d5d5933c753e91d6c` | 22.89 |  |
| 20:33:32.104 | `83e8cfb2` | api://hr-agents/travel | `102431f6-9fb6-45da-b1f6-c3bd98321e50` | `1a418f18-3205-413e-81b4-aad0f5b48a9e` | `1-6ac2b81c-12e6c34808eaac9615b9044d` | 27.39 |  |
| 20:33:32.112 | `83e8cfb2` | api://hr-agents/pay | `970a4b30-7db1-4214-8af1-01acc69dfa6a` | `53d18928-1641-426f-8da6-915e44eb6262` | `1-6ac2b81c-3965895b2115257022f21f95` | 28.42 |  |

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
fetch spans, from: "2026-10-04T20:16:00Z", to: "2026-10-04T20:35:00Z"
| filter session.id == "48e7b0a1-5754-40ef-93a1-4998ae7f8fdd-profile"
| fields start_time, end_time, span.name, trace.id, span.id, service.instance.id, aws.request_id
| sort start_time asc
```

The designer's events for one contact: `node connect/acxd/logs.js <contactId> 3600000 --json`
in guppi-hr.
