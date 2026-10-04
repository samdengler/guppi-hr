# /p/hr/ chat start and client against AWS's Touchpoint reference

Review of 4 October 2026. Read only: no code was changed and nothing was deployed. Two
read-only CloudWatch Logs Insights queries and two read-only Lambda calls
(`get-function-url-config`, `get-policy`) were run against the live account.

Decision D55 (Approved, Sam, 4 Oct) says /p/hr/ "follows the shape of AWS's Touchpoint front
end: a chat-start endpoint (API Gateway, Okta JWT check, a Rust Lambda function)"
(guppi-hr `docs/decision-log.md:65`). This review compares what was built that day with the
reference D55 names: Touchpoint and the StartChatContact backend sample its documentation
points to.

## Sources

AWS reference:

- Touchpoint, `github.com/amazon-connect/touchpoint` at 56f6bd9 (2 Oct 2026), package
  `@amazon-connect-touchpoint/web` 1.0.2: `README.md`, `docs/README.md`,
  `src/connect/index.ts`, `src/connect/conversation.ts`, `src/App.tsx`,
  `src/components/SafeMarkdown.tsx`, `package.json` (chatjs `^5.2.0`).
- The AWS developer guide page for Touchpoint,
  https://docs.aws.amazon.com/connect/latest/devguide/touchpoint.html (its prerequisites
  table: "An API Gateway/Lambda route that calls Amazon Connect's StartChatContact and
  returns participant credentials. Deploy the StartChatContact API").
- The StartChatContact sample, `github.com/amazon-connect/amazon-connect-chat-ui-examples`
  at 1d548e0, folder `cloudformationTemplates/startChatContactAPI`: `cloudformation.yaml`,
  `js/startChatContact.js`, `README.md`, and the SDK layer `ChatSDK.zip` (`aws-sdk`
  2.1320.0).
- amazon-connect-chatjs 5.2.0 source at b76a259 (`src/client/client.js`,
  `src/core/chatSession.js`, `src/core/chatController.js`, `src/service/csmService.js`).
- Connect guidance: security best practices
  (https://docs.aws.amazon.com/connect/latest/adminguide/security-best-practices.html,
  sections "Chat security" and "WebRTC security"), "Set up your network"
  (https://docs.aws.amazon.com/connect/latest/adminguide/ccp-networking.html, option 1).
- API Gateway REST response streaming: the announcement of 19 November 2025
  (https://aws.amazon.com/about-aws/whats-new/2025/11/api-gateway-response-streaming-rest-apis)
  and the developer guide pages `response-transfer-mode.html` and
  `response-streaming-lambda-configure.html`. CloudFront OAC for function URLs
  (`private-content-restricting-access-to-lambda.html`), AWS WAF supported resources
  (`how-aws-waf-works-resources.html`), Lambda runtimes (`lambda-runtimes.html`), and the
  Connect, Lambda and API Gateway pricing pages.

What was built:

- guppi-hr at da745e9: `docs/decision-log.md` (D41, D42, D48, D50, D53, D54, D55, D56),
  `docs/proposals/connect-chatjs.md` (revision 2 and "Results, 4 October"),
  `docs/aws-feedback.md` (A22, C18, F1, X10), `docs/latency-log.md` (L28, L29), `AGENTS.md`,
  `connect/chat_start/` (`src/lib.rs`, `src/main.rs`, `Cargo.toml`, `Cargo.lock`),
  `connect/infra/guppi_connect_infra/chat_start.py`, `connect/web/manifest.json`,
  `connect/acxd/hr.js`, `connect/scripts/contact_flow.py`,
  `connect/agent/src/connect_bridge/turn.py`.
- guppi-gpt at 870864b: `web/src/connect-chat.js`, `web/src/connect-agent.js`,
  `web/src/app.js`, `web/package.json`, `infra/guppi_gpt_infra/stack.py`,
  `docs/proposals/platform.md` ("Connect chat transport"), `docs/guppigpt-decision-log.html`
  (decision 22).
- The reviews: scratchpad `proposed-design-critique.md` (F1 to F11) and
  `chatjs-plan-critique.md` (H1 to L7, V1 to V8).

## How the front door was decided

The order of commits explains the deviation Sam found.

| Time (4 Oct, EDT) | Commit | What it says about the front door |
| --- | --- | --- |
| 11:44 | 3cc276e, plan revision 1 | Chat start stays on the bridge; "No new Lambda function" |
| (before 11:54) | `chatjs-plan-critique.md:221-264` | A section on a Lambda "behind API Gateway". F7 reopens: an HTTP API has a JWT authorizer but no WAF; a REST API has WAF but needs a Lambda authorizer or an in-function check. V3 offers two shapes for the warm-ups: inside the handler bounded by the greeting wait, or "a function URL with `RESPONSE_STREAM`" |
| 11:54 | 811264d, D55 Approved | "a chat-start endpoint (API Gateway, Okta JWT check, a Rust Lambda function)", warm-ups "through an asynchronous self-invocation", returns "the body of AWS's StartChatContact sample" |
| 11:56 | 3c19635, plan revision 2 | "Reached at `https://chat.dengler.io/api/chat/*` through a CloudFront behavior to the function's URL ... The function URL streams its response (`RESPONSE_STREAM`)" (`connect-chatjs.md:26-31`). Its status line reads "approved direction (D55)" |
| 12:22 | 57d9209, `AGENTS.md` | The approved Lambda list now reads "`hr-chat-start` ... (Rust behind a streaming function URL) ... (D55, 4 Oct 2026)" (`AGENTS.md:110-113`) |
| 12:29 | 3e7c3d4, D56 Proposed | "a function URL with `RESPONSE_STREAM` and no IAM auth ... no API Gateway and no asynchronous self-invocation". Alternatives weighed: "An HTTP API with a JWT authorizer in front (one more hop and no streaming)" (`decision-log.md:66`) |

Sam approved API Gateway in D55. The function URL appears two minutes later in a plan
revision, and the only decision that records it, D56, is still Proposed. `AGENTS.md`
attributes the function URL to D55, which does not say it. D56's alternatives do not include
a REST API with response streaming, which API Gateway has supported since 19 November 2025
and which the first critique named as a streaming option ("a function URL with
`RESPONSE_STREAM`, or a REST API", `proposed-design-critique.md:31`).

## Every difference at a glance

Classes: **deviation** (the reference does it one way and the build another, with no need
that forces it), **justified extension** (the reference has no such need), **aligned**.
"Sam agreed" means an Approved decision or Sam's own words name the choice; "plan" means
it is written in plan revision 2 or a review and was not put to Sam as a decision.

| # | Topic | Reference | Built | Class | Sam agreed |
| --- | --- | --- | --- | --- | --- |
| V1 | Front door type | API Gateway REST API, stage `Prod`, `POST /`, Lambda proxy | Lambda function URL, `RESPONSE_STREAM`, behind a CloudFront path `/api/hr/chat/*` | deviation | No. D55 says API Gateway; D56 (function URL) is Proposed |
| V2 | Origin reachable without CloudFront | execute-api host is public too | Function URL auth `NONE`, resource policy `Principal: *`; callable on its `lambda-url` host, bypassing CloudFront | deviation (part of V1) | No |
| V3 | WAF | README: "highly recommended to implement AWS WAF" | None on the chat start; a function URL cannot take a web ACL; the distribution has none | deviation | No. D48 declined a web ACL for the token issuer only |
| V4 | Throttling | None in the template (account defaults) | Reserved concurrency 10, shared by start and report; no per-route or per-employee limit | deviation from the README's advice, partly an extension | Plan only ("Accepted for the POC") |
| V5 | Message receipts and typing events | Touchpoint turns receipts on and sends typing (throttled 2.5 s) | Receipts off, no typing, no `SendEvent` | deviation with a recorded reason (F3) | Plan and guppi-gpt decision 22 |
| V6 | Participant service host | Touchpoint sets `https://participant.connect.{region}.api.aws` | chatjs default `participant.connect.us-east-1.amazonaws.com`; CSP allows only that | deviation | guppi-gpt decision 22 (host shapes), not discussed against Touchpoint |
| V7 | `SupportedMessagingContentTypes` | Touchpoint sends five types (plain, Markdown, JSON, interactive, interactive response); the sample passes them through | `["text/plain"]` fixed on the server | deviation | Inherited from the bridge; consistent with the plain-text page rule |
| V8 | Participant display name and `customerName` | From the browser; the sample also sets `Attributes.customerName` | `"Employee"` fixed; no `customerName` | deviation | Inherited from the bridge (`turn.py:616`); no decision |
| V9 | Persistent chat | Sample passes `PersistentChat` through | Not supported; a reopened thread starts a new chat | deviation | Plan ("Accepted for the POC", critique V1) |
| V10 | Function memory and timeout | 128 MB, 30 s | 1024 MB (33 MB used), 60 s | deviation (memory); timeout justified | No |
| V11 | Runtime, language, SDK | `nodejs18.x` (deprecated 1 Sep 2025), `aws-sdk` v2 2.1320.0 in a layer | Rust on `provided.al2023`, arm64, AWS SDK for Rust (`aws-sdk-connect` 1.211.0) | deviation | Yes (D55: "Rust for the cold start", Node alternative set aside) |
| V12 | Rendering | Touchpoint renders Markdown through `marked` and DOMPurify | The page renders plain text (`textContent`) | deviation | Yes (D55 set aside "Touchpoint for the full page"; project rule) |
| E1 | Caller authentication | None ("does not come with built-in authentication") | Okta JWT verified in the function (issuer, RS256, audience, client, `uid`, expiry) | justified extension | Yes (D55: "Okta JWT check") |
| E2 | Who sets attributes | Browser chooses instance, flow, display name; README shows forwarding browser `Attributes` | Server only: three agents tokens, the tools token, `employeeId`; the body is ignored except `previousContactId` | justified extension | Yes (D55: "attributes set on the server only") |
| E3 | Hop token exchange | None | Four on-behalf-of exchanges through AgentCore Identity, one workload token (A22), cached per Okta token | justified extension | Yes (D47, D48); one workload token is D56 (Proposed) |
| E4 | Greeting wait and token blanking | None; the browser's socket starts the flow | Server opens its own customer socket, waits for the greeting (12 s limit), blanks four attributes, then returns credentials | justified extension | Yes (D42, D53) |
| E5 | Sub-agent warm-ups | None | Three A2A warm messages during the greeting wait, reported on line 2 | justified extension | Yes (D41); the in-invocation mechanism is D56 (Proposed), following critique V3 |
| E6 | Response contract | One JSON body `{data:{startChatResult, featurePermissions}}` | NDJSON: line 1 `{data:{startChatResult}, region, startedAt, expiresAt, restarted, timing}`, line 2 `{warmed, timing}` | justified extension (needed by E5) | D56 (Proposed) |
| E7 | Error shapes | AWS error object returned with its status code | Fixed codes: 401, 400, 404, 405, and in-stream `{"error":"signin"}` or `{"error":"unavailable"}` | justified extension | Plan |
| E8 | Chat duration | Browser may set it; Connect default 1,500 minutes | 60 minutes, fixed | justified extension | Yes (D42) |
| E9 | Ending the left chat | Touchpoint `reset` calls `disconnectParticipant` | `previousContactId` on the next start; `StopContact` after an `employeeId` check; sign-out disconnects | justified extension | Behaviour yes (D42); mechanism plan (F5) |
| E10 | Expiry and restart | None | `expiresAt` from the hop tokens and the chat; the page restarts with 5 minutes left | justified extension | Plan (F4) |
| E11 | Same-origin path, no CORS | Cross-origin, CORS `*` with an `OPTIONS` mock | Same origin through CloudFront; no CORS headers | justified extension | Plan; guppi-gpt decision 22 |
| E12 | IAM scope | `connect:StartChatContact` on the instance and every flow in it | One flow ARN plus `contact/*`; Identity and one secret | justified extension | Plan |
| E13 | Logging | Logs the whole event and the StartChatContact response, which holds the participant token; default retention | JSON lines with codes only, no tokens; one month retention; X-Ray | justified extension | Plan |
| E14 | Alarms and turn reports | None | `chat_problem` filter and three alarms; `/chat/report` route per turn | justified extension | Plan; report route in D56 (Proposed) |
| E15 | Client-side metrics (CSM) | Touchpoint leaves chatjs CSM on | `disableCSM: true` | justified extension (forced by the CSP) | guppi-gpt decision 22 |
| E16 | Turn handling | Each message appended as it arrives; no turn | End marks, quiet end, turn limit, late replies, dedupe, hidden lines | justified extension | Yes (D42 for the rules) |
| E17 | Reconnect and catch-up | `onConnectionBroken` shows "Connection lost. Please try again." | One reconnect, `getTranscript` on connect, on visible and on `online`; bridge fallback | justified extension | Plan |
| E18 | Rollback | None | Bridge behind `?ff=connect-bridge` | justified extension | Yes (D55) |
| E19 | Region source | Page config | Line 1 carries `region`, checked by pattern | justified extension | Plan |
| A1 | Credentials body | `data.startChatResult` with `ContactId`, `ParticipantId`, `ParticipantToken` | Same keys on line 1 | aligned | Yes (D55) |
| A2 | `ClientToken` | Not set; SDK v2 fills idempotency tokens | Not set; SDK for Rust fills it | aligned | n/a |
| A3 | Browser library and session | chatjs `^5.2.0`, `ChatSession.create({chatDetails, type: CUSTOMER})`, `sendMessage` text/plain | chatjs 5.2.0 pinned, same calls | aligned | Yes (D55) |
| A4 | When the contact starts | Touchpoint opens the chat when its app mounts | At page load when signed in and visible | aligned | Yes (D50) |
| A5 | Contact flow into the designer | "Route your contact flow into" the ACXD application | `UpdateContactData` then `ConnectParticipantWithAgenticCX` | aligned | Yes |
| A6 | Infrastructure as code | One CloudFormation template launched from AWS's buckets | CDK in `GuppiConnect` plus one CloudFront behavior in guppi-gpt | aligned in resources; tool per project rule | Project rule |
| A7 | chatjs logger | Not configured | Not configured | aligned | n/a |
| A8 | Participant token in the browser | In memory (Touchpoint keeps responses, not the token, in `sessionStorage`) | In memory only | aligned | Plan (F8 accepted) |

## Deviations

### V1. The front door is a Lambda function URL

Reference. The sample creates `AWS::ApiGateway::RestApi` "StartChatContact"
(`cloudformation.yaml:158-163`), a deployment to stage `Prod` (`:174-181`), and one
`POST` method on the root resource with `AuthorizationType: "NONE"` and an `AWS_PROXY`
integration to the function (`:183-209`). The README tells the integrator to take "the
`Prod` stage ... `Invoke URL`" (`README.md:98`). Touchpoint's README and the developer
guide describe `chatEndpoint` as "An API Gateway/Lambda route" (`README.md:20`) and "e.g.
an API Gateway route" (`src/connect/index.ts:30-31`).

Built. `add_function_url(auth_type=NONE, invoke_mode=RESPONSE_STREAM)`
(`chat_start.py:230-233`); the host goes to SSM `/guppi/hr/chat-start-host`
(`:236-242`); guppi-gpt's distribution sends `/api/hr/chat/*` to it as an `HttpOrigin` with
no custom header and no OAC (`stack.py:1111-1123`, `:1286-1293`). The Rust handler reads
the function URL's event shape: `rawPath` and `requestContext.http.method`
(`lib.rs:504-516`).

Why. D56: "Streaming lets the page connect at the greeting while the warm-ups finish, in one
invocation" (`decision-log.md:66`). Plan revision 2: "(V3: no asynchronous self-invocation,
so no hop tokens in Lambda's event queue)" and "a function URL has no JWT authorizer (V5,
F7)" (`connect-chatjs.md:28-35`). The need is streaming. The choice of a function URL to get
it has no recorded reason beyond D56's comparison with an HTTP API, which cannot stream.

Sam agreed. No. D55 names API Gateway; D56 is Proposed; Sam reports he did not agree.

Effect.
- Security: see V2 and V3. A function URL cannot be protected by AWS WAF (WAF lists API
  Gateway REST APIs, ALB, AppSync, Cognito, App Runner, AgentCore Gateway, Verified Access
  and Amplify as regional resources; `how-aws-waf-works-resources.html`).
- Operations: no stage, no access log, no per-route throttle, no usage metrics per route.
  F1 in `aws-feedback.md:233` (a 204 through the streaming prelude reached the browser as
  503 through CloudFront) is a function-URL-specific failure already met.
- Latency: line 1 inside the function at 2.70 s warm; at the client 2.83 s straight to the
  function URL and 3.42 s through chat.dengler.io on a cold instance (`latency-log.md:49`,
  L28). An API Gateway hop would add its own time, not measured here.
- Compatibility: none with Touchpoint, which takes any URL.

Option to align. A regional REST API with a Lambda proxy integration in streaming mode.
API Gateway supports `responseTransferMode: STREAM` for `AWS_PROXY` integrations, invokes
the function through `.../response-streaming-invocations`, and keeps the same metadata
prelude the function writes today (`response-transfer-mode.html`,
`response-streaming-lambda-configure.html`). Limits that matter: streams up to 15 minutes,
5-minute idle timeout on a regional endpoint, no endpoint caching, no content encoding, no
VTL response mapping; none of these is used. The installed CDK, `aws-cdk-lib` 2.268.0,
exposes `response_transfer_mode` in `aws_apigateway` (guppi-hr `.venv`). REST APIs have no
native JWT authorizer, so the function keeps verifying the Okta token (a Lambda authorizer
would be a second Lambda function needing Sam's approval). Work: CDK `RestApi` with two
`POST` methods (or a proxy resource), stage `prod` with method throttles and access logs;
`route()` and the event reading in `lib.rs` and `main.rs` changed to the REST v1 shape
(`path` or `resource`, `httpMethod`, `headers`, `body`, `isBase64Encoded`); the SSM
parameter carries the API host and stage path; guppi-gpt's origin gains `origin_path`, as
the invites origin already does (`stack.py:1105-1109`). Cost: $3.50 per million requests
(a 5 KB streamed response is one request; API Gateway pricing), so under a cent a month at
POC volume. Gives up: nothing the page uses; adds one managed hop.

A second option keeps the function URL and adds CloudFront OAC with `AuthType: AWS_IAM`.
OAC signs with SigV4 and overwrites the viewer's `Authorization` header unless set to
`no-override`, and every `POST` must carry `x-amz-content-sha256` with the body's hash
(`private-content-restricting-access-to-lambda.html`). The page would move the Okta bearer
to another header and hash each body. It closes V2 but not V3 or V4, and is not the
reference's shape.

### V2. The origin can be called without CloudFront

Reference. The sample's execute-api URL is public as well; the README asks for WAF on it
(`README.md:5`) and warns the API "is accessible to anyone with the API Gateway endpoint"
(`README.md:74`).

Built. The live function URL is `AuthType NONE`, `RESPONSE_STREAM`, `Cors null`, and its
resource policy grants `lambda:InvokeFunctionUrl` and `lambda:InvokeFunction` to
`Principal: *` (`aws lambda get-function-url-config` and `get-policy`, 4 Oct). Every
request, signed in or not, runs the function; an unauthenticated one ends at
`chat_unauthorized` with 401 (`main.rs:321-327`). The logs for the last 24 hours show four
(three "no bearer token", one "undecodable token"), and plan revision 2 records "requests
without a token to the start route" during the measurement (`connect-chatjs.md:259-260`).

Why. No recorded reason; it follows from V1. The CloudFront comment says "this origin
carries no secret header" because the function verifies the token
(`stack.py:1111-1114`).

Sam agreed. No.

Effect. Anyone who learns the host can spend the function's 10 reserved slots. A start
holds a slot for its whole invocation, 6.07 s median and 7.07 s p90 over 53 starts on
4 Oct (Logs Insights on `chat_start` lines), so about 1.6 starts a second fill the
reservation; a refused call holds a slot for milliseconds, so a flood of them is needed.
While the bridge is deployed, a page whose start fails goes on through the bridge
(`connect-chat.js:718-724`); once the bridge retires, a full reservation is a chat outage.

Option to align. V1's REST API with a regional web ACL (V3), or OAC on the function URL.
Either closes it; the REST API also brings V4's per-route throttles.

### V3. No WAF on the chat start

Reference. "It is highly recommended to implement AWS WAF for the API Gateway"
(`README.md:5`).

Built. No web ACL on the chat start. The platform's regional `EdgeWebAcl` (CloudFront-only
header rule, `AWSManagedRulesCommonRuleSet`, per-IP rate 60 in 5 minutes, all in block mode,
`WAF_BLOCK = True`) is associated only with the edge gateway (`stack.py:166`, `:649-731`).
The distribution has no `web_acl_id` (`stack.py:1242-1251`). Before D55 the warm start went
through that edge gateway, so the move took chat start out from behind the web ACL and the
gateway's per-user limits (30 a minute, 2 concurrent; `proposed-design-critique.md:47`).

Why. No recorded reason for the chat start. Critique F7 asked to "decide on WAF
explicitly" (`proposed-design-critique.md:79`). For the token issuer Sam judged a web ACL
"unnecessary for a POC and accepted the risk" (D48, `decision-log.md:58`).

Sam agreed. Not for this path.

Effect. Security: no managed rules and no per-IP rate in front of an endpoint that mints
four hop tokens and a contact per call. Cost: none today.

Option to align. With V1's REST API: either a new regional web ACL in `GuppiConnect` (D48
puts one with a per-IP rate rule at about 6 dollars a month), or an association of the
existing `EdgeWebAcl` with the new stage, which adds only request charges and needs the HR
chat origin to send the `X-Origin-Verify` header that the CloudFront-only rule checks. The
per-IP rate must key on `X-Forwarded-For` as the edge ACL does, since requests arrive from
CloudFront. Gives up: about 6 dollars a month or a cross-stack association. This is Sam's
decision; D48 is the precedent for declining.

### V4. Throttling: one reservation for everything

Reference. The template sets no stage or method throttle and no usage plan
(`cloudformation.yaml:158-240`); API Gateway's account defaults apply.

Built. `reserved_concurrent_executions=10` (`chat_start.py:50`, `:204`) with an alarm on
throttles (`:265-269`). Starts and per-turn reports share the 10. No per-employee cap.

Why. Plan revision 2, "Accepted for the POC (D55)": "chat starts are limited by reserved
concurrency and the invite list, not per employee (F3, V5)" (`connect-chatjs.md:141-143`).
V5 notes API Gateway throttles are per stage or key, not per Okta subject
(`chatjs-plan-critique.md:258`).

Sam agreed. Not as a decision; the plan section title names D55, which does not mention
throttling.

Effect. A burst of reports (one per turn per open tab) competes with starts. The edge
gateway's per-user limits no longer apply to chat start.

Option to align. On the REST API, method-level throttles: for example `POST /chat/start`
at 2 a second with a burst of 5, `POST /chat/report` at 10 with a burst of 20, below
StartChatContact's 5 a second account-wide (`chatjs-plan-critique.md:258`). Keep the
reservation as a ceiling. The numbers are Sam's call.

### V5. Message receipts and typing are off

Reference. Touchpoint sets `features.messageReceipts.shouldSendMessageReceipts: true`
(`conversation.ts:789-796`), maps delivered and read receipts to message status
(`:978-990`), shows the agent's typing (`:954-967`) and sends the customer's typing every
2.5 s at most (`:1904-1916`).

Built. `setGlobalConfig({region, features: {messageReceipts: {shouldSendMessageReceipts:
false}}})` (`connect-chat.js:655-658`); no typing call anywhere. The live check found no
`/participant/event` call in five turns (`connect-chatjs.md:205-208`).

Why. Critique F3: receipts and typing are `SendEvent` calls, which share the instance's
10-a-second send quota with every employee's `SendMessage`, and the pricing page does not
say whether events are billed (`proposed-design-critique.md:51`). Connect's pricing page
lists "$0.010 per message sent or received" and says nothing about events (checked 4 Oct).

Sam agreed. Through guppi-gpt decision 22 and the plan; not asked directly.

Effect. The page has no delivery ticks or typing indicator, which its UI does not show.
No quota or cost risk from events.

Option to align. Turn receipts on with a long `throttleTime`. Gives up quota headroom for a
feature the page does not display. Not recommended.

### V6. The participant service host

Reference. Touchpoint sets chatjs's endpoint to `https://participant.connect.{region}.api.aws`
unless the page overrides `globalConfig.endpoint` (`index.ts:86-90`, `:130-137`).

Built. No endpoint override, so chatjs uses `https://participant.connect.${region}.amazonaws.com`
(chatjs `client.js:99`). The CSP allows that host and
`wss://*.transport.connect.us-east-1.amazonaws.com` (`stack.py:250-253`), which are the
hosts Connect's "Set up your network" option 1 lists.

Why. guppi-gpt decision 22: "AWS's documented host shapes for the region". Touchpoint's
choice was not discussed.

Sam agreed. Through decision 22 only.

Effect. None for /p/hr/. A Touchpoint widget on chat.dengler.io would call the `api.aws`
host and be blocked by the CSP unless it sets `globalConfig.endpoint` or the CSP adds that
host.

Option to align. Leave the page as built; handle it in the widget page (see "A Touchpoint
widget on the same backend").

### V7. Text only as the supported content type

Reference. Touchpoint sends `text/plain`, `text/markdown`, `application/json` and the two
interactive types by default (`conversation.ts:125-131`); the sample passes
`SupportedMessagingContentTypes` through (`startChatContact.js:41`) and derives
`featurePermissions.MESSAGING_MARKDOWN` from it (`:66-79`).

Built. `content_types: vec!["text/plain"]` (`lib.rs:943`), carried over from the bridge
(`turn.py:622`).

Why. No recorded decision; it matches the rule that the page renders plain text only
(guppi-hr `CLAUDE.md`).

Sam agreed. Implicitly through the plain-text rule.

Effect. The designer's replies are plain text today, so nothing is lost on /p/hr/. A
Touchpoint widget would get no Markdown or interactive messages from this backend.

Option to align. When a widget page exists, let the request name content types from an
allowlist, or give the widget page its own route.

### V8. Display name "Employee"

Reference. The browser sends `ParticipantDetails.DisplayName`; the sample also sets
`Attributes.customerName` from it (`startChatContact.js:34-39`).

Built. `display_name: "Employee"` and attribute `employeeId` = Okta `uid`
(`lib.rs:937-941`), as the bridge did (`turn.py:616`).

Why. No recorded reason. It keeps the employee's name and email out of the contact record.

Sam agreed. No decision.

Effect. Contact records and any agent view show "Employee". Nobody staffs a queue (D43), so
nobody sees it.

Option to align. Use a name claim, if the Okta access token carries one, at the cost of
personal data on every contact record. Not recommended.

### V9. No persistent chat

Reference. The sample forwards `PersistentChat` (`startChatContact.js:45-51`;
`README.md:482-499`).

Built. Not supported. A thread reopened from history starts a new chat with the restart
line (`platform.md`, "Chat start"; `connect-chat.js:695-731`).

Why. Critique V1: there is no store, and the participant token must not be stored
(`chatjs-plan-critique.md:250`). Plan revision 2 accepts it for the POC
(`connect-chatjs.md:144`).

Sam agreed. Plan only.

Effect. The designer forgets earlier turns of a reopened thread.

Option to align. `PersistentChat` with `SourceContactId` from the thread's last contact,
checked against `employeeId` as `previousContactId` is. About 1 to 2 hours plus a check that
the designer rehydrates context. A Sam decision for later.

### V10. Memory and timeout

Reference. `MemorySize: 128`, `Timeout: 30` (`cloudformation.yaml:99-100`).

Built. `memory_size=1024`, `timeout=60` (`chat_start.py:201-203`). Maximum memory used over
123 invocations in 24 hours: 33 MB; 7 cold starts with 106 ms mean init (Logs Insights,
`REPORT` lines, 4 Oct).

Why. The 60 s timeout is explained ("Exchanges, the start, a 12 s greeting limit and 15 s
warm-ups, with room", `chat_start.py:202`). The memory size has no recorded reason.

Effect. Cost only: about $0.00008 per start at 1 GB for 6.07 s (arm64 $0.0000133334 per
GB-second, Lambda pricing). The work is mostly waiting on the network; CPU share falls with
memory, which could slow the RS256 check and TLS a little.

Option to align. 256 MB and measure line 1 (L28 numbers as the baseline). Small gain; low
priority.

### V11. Rust in place of Node.js

Reference. `Runtime: "nodejs18.x"` with the `aws-sdk` v2 layer (`cloudformation.yaml:72-102`;
`aws-sdk` 2.1320.0 in `ChatSDK.zip`). Lambda deprecated `nodejs18.x` on 1 September 2025
(`lambda-runtimes.html`).

Built. Rust 2024 edition, `provided.al2023`, arm64, built by cargo-lambda at synth
(`Cargo.toml`, `chat_start.py:55-100`).

Why. D55: "Rust for the cold start (D51)"; a Node.js Lambda like the sample was listed and
set aside. L28 measured a 0.11 s init.

Sam agreed. Yes.

Effect. Faster cold start; one more build toolchain. Aligning literally would mean a
deprecated runtime.

Option to align. None recommended. A Node.js 22 or 24 port with SDK v3 would match the
sample's language at the cost of a rewrite and a slower init.

### V12. Plain text in the page, Markdown in Touchpoint

Reference. Touchpoint renders bot text with `marked` and `DOMPurify.sanitize`
(`SafeMarkdown.tsx:3-4`, `:25`).

Built. The page sets `textContent` (`app.js:385`, `:775`). Connect's chat security advice
is to avoid `innerHTML` and sanitize (security best practices, "Chat security").

Why. D55 set aside "Touchpoint for the full page (a widget that renders Markdown HTML)";
the project rule is plain text only.

Sam agreed. Yes.

Option to align. Not recommended for /p/hr/.

## Justified extensions

These exist because the HR assistant needs something the reference does not: an
authenticated employee, hop tokens on the contact, warm sub-agents, and an AG-UI page.

- **E1 Authentication.** The sample warns "this API does not come with built-in
  authentication" (`README.md:74`); Connect's advice is "Authenticate users before token
  issuance" ("WebRTC security"). The function checks issuer, RS256 signature with built-in
  Okta keys, `aud`, `cid`, `uid`, `exp`, `iat`, `nbf` (`lib.rs:197-256`) before anything
  else (`main.rs:321-327`).
- **E2 Attributes on the server only.** The sample lets the caller choose `InstanceId` and
  `ContactFlowId` (`startChatContact.js:18-33`) inside an IAM grant on the whole instance
  (`cloudformation.yaml:148-153`), and its README shows forwarding browser `Attributes`
  (`README.md:558-594`). The build sets the four hop tokens and `employeeId` itself
  (`lib.rs:934-945`) and reads only `previousContactId` from the body (`lib.rs:583-586`).
- **E3 Hop tokens.** One `GetWorkloadAccessTokenForJWT` and four `GetResourceOauth2Token`
  calls at once, cached per Okta token (`lib.rs:626-658`; A22). Fails closed with
  `{"error":"signin"}` (`lib.rs:920-930`).
- **E4 Greeting and blanking.** The server opens the customer socket so the flow starts
  (C1), waits for the greeting (`lib.rs:736-777`), blanks four attributes
  (`lib.rs:791-801`, `:992`), and on any failure blanks before `StopContact`
  (`lib.rs:979-990`). D42 and D53 require it; C3 says attributes stay readable after the
  contact ends.
- **E5 Warm-ups.** Three A2A `message/send` calls with `metadata.warm` started right after
  `StartChatContact` (`lib.rs:831-870`, `:958-972`); line 2 says how many succeeded. D55's
  "asynchronous self-invocation" was replaced on critique V3's grounds: it would put
  bearer tokens in Lambda's event queue and dead-letter queue.
- **E6 NDJSON.** Line 1 after the blanking, line 2 after the warm-ups (`lib.rs:998-1022`;
  `main.rs:347-353`). Line 1 keeps the sample's `data.startChatResult` keys. The page reads
  line 1 as soon as it arrives (`connect-chat.js:251-299`). A single-JSON alternative exists:
  a separate `POST /chat/warm` route the page calls after line 1, checked against
  `employeeId`, which costs one more request per page load and a second exchange when
  another instance serves it.
- **E7 Error shapes.** The sample answers `statusCode: err.statusCode` with the raw error
  object (`startChatContact.js:101-117`); the build never returns AWS error text
  (`main.rs:34-43`).
- **E8 Duration.** 60 minutes (`lib.rs:50`) against Connect's default 1,500, because 27
  chats held for 25 hours against the 500-chat quota (D42).
- **E9 Ending the left chat.** `previousContactId`, `GetContactAttributes` ownership check,
  then `StopContact` (`lib.rs:816-829`); sign-out awaits `disconnectParticipant` capped at
  2 s (`connect-chat.js:803-811`). Touchpoint only disconnects from the browser
  (`conversation.ts:1542-1576`).
- **E10 Expiry.** `expiresAt` is the earlier of hop-token expiry and chat end less 2 minutes
  (`lib.rs:613-616`); the page restarts with 5 minutes left (`connect-chat.js:24`,
  `:752-754`). Critique F4.
- **E11 Same origin.** The page posts with its bearer to its own origin, so `connect-src`
  keeps `'self'` for it and no CORS is needed (`stack.py:239-242`). The sample answers
  `Access-Control-Allow-Origin: *` (`cloudformation.yaml:211-240`;
  `startChatContact.js:85-88`).
- **E12 IAM.** `StartChatContact` on one flow ARN and `contact/*`; `UpdateContactAttributes`,
  `StopContact`, `GetContactAttributes` on `contact/*` (`chat_start.py:127-148`); Identity
  grants and the `guppi/obo/hr-bridge` secret (`:150-183`). It reuses the bridge's client,
  so the audit names `hr-bridge` (F9, `connect-chatjs.md:35-37`).
- **E13 Logging.** The sample logs the full event (`startChatContact.js:6`) and the
  StartChatContact response twice (`:58`, `:97`), so every participant token lands in
  CloudWatch; Connect says "Do not log participant tokens" ("WebRTC security"). The build
  logs codes and ids only (`lib.rs:1-24`, `main.rs:34-43`, `:207-219`), with one-month
  retention and X-Ray (`chat_start.py:185-207`).
- **E14 Alarms and reports.** Metric filter `{ $.event = "chat_problem" }` and alarms for
  problems, errors and throttles (`chat_start.py:244-281`); the report route checks
  `employeeId` and writes one line per run (`lib.rs:1129-1183`). Live checks 2 and 7 passed
  (`connect-chatjs.md:209-211`, `:241-249`). The no-reply alarm depends on the tab sending
  its report (plan, "Accepted for the POC").
- **E15 CSM off.** chatjs loads CSM by appending an inline `<script>` and a blob worker
  (`csmService.js:24-31`, `:41-48`) unless `disableCSM` is set (`chatSession.js:313-315`).
  The page's CSP has `script-src 'self'` (`stack.py:1155`), which blocks both, so
  `disableCSM: true` (`connect-chat.js:482`) is forced. Touchpoint does not pass it
  (`conversation.ts:798-801`).
- **E16 Turn handling.** `classify` and `createTurnAssembler` (`connect-chat.js:65-89`,
  `:115`) implement the bridge's rules from manifest data (`manifest.json:11`): end mark
  U+2063 and closed mark U+2064 from the designer (`hr.js:47-50`), quiet end after 0.8 s,
  turn limit 28 s, late answers after the no-reply line, dedupe by `Id`.
- **E17 Reconnect and catch-up.** One reconnect on a broken socket
  (`connect-chat.js:496-524`), `getTranscript` after each `onConnectionEstablished`, on
  `visibilitychange` and on `online` (`:460-477`, `app.js:298`, `:721-725`), then the bridge
  (`connect-chat.js:744-748`). X10 explains the `online` read.
- **E18 Rollback.** `?ff=connect-bridge` selects `HttpAgent` and the bridge's warm start
  (`app.js:143-144`, `:1172-1182`); live check 6 passed.
- **E19 Region on line 1.** `"region": REGION` (`lib.rs:1005`), validated by pattern
  (`connect-chat.js:260`).

## Aligned

- **A1** Line 1 carries `data.startChatResult` with `ContactId`, `ParticipantId`,
  `ParticipantToken` (`lib.rs:1002-1008`), the keys Touchpoint reads
  (`conversation.ts:144-153`). `featurePermissions` is absent; only the prebuilt widget
  reads it (`README.md:447`).
- **A2** Neither sets `ClientToken`, and both SDKs fill it: SDK v2 fills members marked
  `idempotencyToken` (`aws-sdk/lib/model/operation.js:79`, `lib/event_listeners.js:145-151`
  in the layer; the Connect model marks `ClientToken`); the SDK for Rust installs an
  `IdempotencyTokenRuntimePlugin` for `StartChatContact`
  (`aws-sdk-connect-1.211.0/src/operation/start_chat_contact.rs:73-77`). The Rust client
  retries at most twice (`main.rs:291`), with the same token.
- **A3** chatjs 5.2.0 (`web/package.json:14`; Touchpoint `^5.2.0`), `ChatSession.create`
  with `type: "CUSTOMER"`, `connect()`, `sendMessage` with `text/plain`
  (`connect-chat.js:479-500`, `:568`; `conversation.ts:798-801`, `:1330-1338`).
- **A4** Touchpoint builds its handler when the app mounts (`App.tsx:128-135`), and the
  handler opens the chat at once (`conversation.ts:1212`). The page starts the chat at
  load when signed in and visible (D50; `app.js:706-733`). Both put one contact on every
  page view.
- **A5** Touchpoint: "Route your contact flow into it" (the ACXD application,
  `README.md:53-55`). The flow: `UpdateContactData` (language), then
  `ConnectParticipantWithAgenticCX` with five context variables from attributes
  (`contact_flow.py:41-65`), then disconnect. Neither reference flow turns on flow logs,
  which Connect's detective best practices recommend; the HR flow does not either.
- **A6** The sample's template holds a role, a function, an API and a metrics custom
  resource (`cloudformation.yaml:70-333`); the build holds a role, a function, its front
  door, a log group, alarms and an SSM parameter in CDK (`chat_start.py`), as the project
  rule requires (`cdk synth` green). The sample also ships an anonymous-metrics custom
  resource on by default (`:44-50`, `:307-321`); the build has none.
- **A7** Neither Touchpoint nor the page configures a chatjs logger
  (`conversation.ts:789-796`; `connect-chat.js:655-658`).
- **A8** The participant token stays in memory in both; Touchpoint saves rendered
  responses to `sessionStorage` (`App.tsx:410-418`), the page saves nothing of the chat
  session (`connect-chat.js:1-16`).

## A Touchpoint widget on the same backend

D55 says "a Touchpoint widget page can reuse the same endpoint later through Touchpoint's
`details` option". Reading Touchpoint's code, that holds, with these conditions:

1. `chatEndpoint` cannot be used. `fetchChatDetails` posts with only a `Content-Type`
   header (`conversation.ts:134-138`), so the start route answers 401; and it calls
   `res.json()` (`:144`), which fails on two NDJSON lines. A `details` function
   (`index.ts:34-38`; `docs/README.md:86-94`) that posts with the bearer and parses line 1
   works. This stays true after V1.
2. The greeting is spent before the widget connects. The server waits for the greeting on
   its own socket before returning line 1 (E4), and Touchpoint shows the welcome screen
   from "the opening assistant message", keeping the input hidden "until the first message
   arrives" (`README.md:180-187`). Touchpoint appends only `onMessage` events
   (`conversation.ts:808-937`) and does not read the transcript on connect. Likely result:
   a widget waiting on "Thinking..." with no input. To verify; `welcomeScreen: false` or a
   `getConnectTranscript` replay may be needed.
3. The CSP blocks the `api.aws` participant host (V6) unless the widget passes
   `globalConfig: { endpoint: "https://participant.connect.us-east-1.amazonaws.com" }`
   (`index.ts:132-137`: "an explicit `globalConfig.endpoint` still wins").
4. CSM cannot be turned off through Touchpoint's options (`create` takes no `disableCSM`,
   `conversation.ts:798-801`), so the CSP will block chatjs's inline CSM script. Expected
   effect: console errors, chat working. To verify.
5. Hidden lines show. `[flow] Escalation: ...` and `[flow] The Agentic CX block returned an
   error.` (`contact_flow.py:98`, `:128`) would appear as text; the invisible marks are
   harmless.
6. Receipts and typing come back on (V5) unless `globalConfig.features.messageReceipts` is
   set; Touchpoint's typing cannot be turned off by option.
7. No restart before `expiresAt` (E10): a widget chat older than the hop tokens fails
   delegated questions.
8. Markdown and interactive messages are unavailable (V7).

Effort for a sample widget page with these handled: about 3 to 5 hours, in its own plan.

## Request flows side by side

Steps are in order; each row can be drawn as one arrow. "Reference" is Touchpoint with the
StartChatContact sample; "Built" is /p/hr/ on 4 October.

### Page load

| Step | Reference (Touchpoint and the sample) | Built (/p/hr/) |
| --- | --- | --- |
| 1 | Page calls `create({config: {chatEndpoint, instanceId, contactFlowId, region, participantDisplayName}, input: "text"})` | Page loads from CloudFront and S3; Okta session restored; manifest `connectChat` read; when signed in and visible (D50) the page refreshes the token if under 50 minutes and loads the chatjs module |
| 2 | App mounts; handler built; `initSession` shows "Connecting..." | `connectChats.start(thread)`; one start in flight per thread |
| 3 | Browser `OPTIONS` preflight to the execute-api URL; API Gateway's mock answers CORS `*` | No preflight (same origin) |
| 4 | `POST {chatEndpoint}` with `{InstanceId, ContactFlowId, ParticipantDetails, Attributes, SupportedMessagingContentTypes}`, no credential | `POST /api/hr/chat/start` with `Authorization: Bearer <Okta token>` and `{}` or `{previousContactId}` |
| 5 | API Gateway REST API, stage `Prod`, no authorizer, no WAF | CloudFront behavior `/api/hr/chat/*` to the function URL (auth `NONE`, streaming), no WAF |
| 6 | Lambda (Node 18, SDK v2) logs the event | Lambda (Rust) verifies the Okta JWT; opens a 200 `application/x-ndjson` stream |
| 7 | (none) | Beside the start: `GetContactAttributes` on `previousContactId`, `StopContact` if it is the caller's |
| 8 | (none) | `GetWorkloadAccessTokenForJWT`, then four `GetResourceOauth2Token` (AgentCore Identity calls the token issuer) |
| 9 | `StartChatContact` with instance and flow from the body, `Attributes.customerName`, display name, optional types, duration, persistent chat | `StartChatContact` with the flow from config, `"Employee"`, the four hop tokens and `employeeId`, `text/plain`, 60 minutes |
| 10 | (none) | Three warm-up `message/send` calls to the agents gateway start |
| 11 | Returns 200 `{data: {startChatResult, featurePermissions}}`; logs the token | `CreateParticipantConnection` on the server; socket subscribe; the flow starts; the designer's greeting arrives on the server's socket; socket closed |
| 12 | (none) | `UpdateContactAttributes` blanks the four token attributes |
| 13 | (none) | Line 1: `{data: {startChatResult}, region, startedAt, expiresAt, restarted, timing}` (2.1 s median inside the function) |
| 14 | `setGlobalConfig({region, endpoint: participant...api.aws, receipts on})`; `ChatSession.create` (CSM on); `connect()` | `setGlobalConfig({region, receipts off})`; `ChatSession.create({..., disableCSM: true})`; `connect()` to `participant.connect.us-east-1.amazonaws.com` |
| 15 | The browser's socket connects; the flow starts now; the greeting arrives on it; welcome screen shows it; input appears | `onConnectionEstablished`; `getTranscript` catch-up; items between turns dropped; the page shows its own empty state and suggestions |
| 16 | (none) | Line 2 `{warmed, timing}` after the warm-ups (7.0 to 8.1 s at the client, L28); the invocation ends |

### One question

| Step | Reference | Built |
| --- | --- | --- |
| 1 | `sendText`: user bubble with status "sending"; interim "Thinking..." | Length check (1,024); `ready(thread)` waits for the start, or restarts if closed or near `expiresAt`; AG-UI `RUN_STARTED`, `STEP_STARTED "Amazon Connect"` |
| 2 | `sendMessage` text/plain to the participant service; status "sent" | `sendMessage` text/plain; keeps `Id` and `AbsoluteTime` |
| 3 | Flow or designer answers; messages arrive on the socket | Designer routes; domain flows call sub-agents through the agents gateway with the hop tokens from context; messages arrive on the socket |
| 4 | Each message appended and rendered as Markdown; chatjs sends delivered and read receipts (`SendEvent`); typing shown | Assembler drops older items and dupes, strips marks, emits text; turn ends on U+2063, U+2064, `chat.ended`, 0.8 s quiet, or 28 s; a ping every 15 s; plain text |
| 5 | (none) | `POST /api/hr/chat/report` with the bearer (`keepalive`); the function checks `employeeId`, writes `chat_report` and any `chat_problem`; alarm on problems |
| 6 | Broken socket: "Connection lost. Please try again." | Broken socket: one reconnect and catch-up, then the thread moves to the bridge (`/api/hr/invocations`, edge gateway, AgentCore Runtime) |

## Cost per chat

- Connect: $0.010 per message sent or received (Connect pricing). The greeting is billed
  on every page view on both the reference (A4) and the build (D50). A chat with three
  questions and one reply each: 1 + 3 + 3 = 7 messages, $0.07. Receipts and typing are
  `SendEvent` calls whose billing the pricing page does not state (V5).
- Chat start function: 6.07 s median billed per start at 1 GB on arm64 (Logs Insights),
  about $0.00008 plus $0.0000002 per request (Lambda pricing). At 256 MB, about $0.00002 if
  the duration holds. Reports are short (179 ms median billed duration across all
  invocations, most of them reports).
- AgentCore Identity exchanges and the three warm-up sessions per page view: not priced
  here; D50 accepts them.
- A REST API front door would add $3.50 per million requests (start and reports); a web ACL
  about 6 dollars a month (D48) plus request charges.

## Recommended alignment plan

In order. Efforts assume an AI agent with both repositories in hand, including deploy waits
and live checks.

1. **Sam decides the open questions below** (minutes). Nothing else starts before item a.
2. **REST API front door with streaming (closes V1, V2, V4)**, 2.5 to 4 hours.
   - CDK in `chat_start.py`: regional `RestApi`, resources `/api/hr/chat/start` and
     `/api/hr/chat/report` (keeping the paths CloudFront forwards), `POST` each,
     `LambdaIntegration(proxy=True, response_transfer_mode=STREAM)`, stage `prod` with
     method throttles and an access log that leaves out headers. Keep the function URL for
     the first deploy.
   - Rust: `route()` and the event reading accept the REST v1 event (`path`, `httpMethod`,
     `headers`, `body`, `isBase64Encoded`); `cargo test` and `uv run -- pytest` updated.
   - SSM `/guppi/hr/chat-start-host` carries the API host; a new parameter carries the
     stage path; guppi-gpt's `hr_chat_origin` adds `origin_path`, as the invites origin
     does.
   - Live checks: line 1 and line 2 stream through CloudFront and API Gateway (10 starts,
     line-1 time at the client against L28's 3.42 s); a report answers 200; a call without
     a token answers 401; a burst above the start throttle answers 429; the bridge flag
     still works.
   - Second deploy removes the function URL and its public permission; a call to the old
     host fails.
3. **WAF on the stage (closes V3), if Sam approves**, 0.5 to 1 hour. Either a new regional
   web ACL (common rule set, per-IP rate on `X-Forwarded-For`), or the existing `EdgeWebAcl`
   associated with the stage and `X-Origin-Verify` added to the HR chat origin, which also
   blocks direct execute-api calls.
4. **Memory to 256 MB (V10)**, 30 minutes with a measurement of 10 starts.
5. **Records**, 30 to 45 minutes: D56 marked Reversed for the front door (its other parts,
   streaming, one workload token, the report route, carried into a new D57 for the REST
   API); `AGENTS.md:110-113` reworded to name the API; plan revision 3 note; latency log
   entry; `aws-feedback.md` F1 retested under API Gateway (204 or 200).
6. **Later, with the widget page**: the eight conditions in "A Touchpoint widget on the
   same backend", 3 to 5 hours in their own plan.

Not recommended for alignment: Node.js (V11), Markdown rendering (V12), receipts and typing
(V5), a name in place of "Employee" (V8). Persistent chat (V9) waits for a need.

## Decisions for Sam

a. The front door: a REST API with response streaming (recommended, the reference's
   shape); keep the function URL and approve D56 as written; or keep it and add CloudFront
   OAC (page sends a body hash and moves the bearer to another header).
b. WAF on the chat start: a regional web ACL (about 6 dollars a month), reuse of
   `EdgeWebAcl`, or the D48 answer (accept the risk).
c. Throttle numbers for start and report, and whether reports get their own limit.
d. Receipts and typing stay off (V5): record it as a decision.
e. Persistent chat for reopened threads (V9): now, later, or never.
f. Memory to 256 MB (V10).
g. When a Touchpoint widget page is built, whether its chats skip the server's greeting
   wait (which changes when the tokens are blanked) or replay the greeting in the widget.
h. D56's status and the `AGENTS.md` wording once a is decided.

## Not verified here

- The extra latency of an API Gateway hop with streaming; it needs the measurement in plan
  item 2.
- Whether a 204 through API Gateway streaming fails as F1 did through the function URL.
- The Touchpoint greeting and CSM behaviour against this backend (widget conditions 2 and
  4).
- Whether Connect bills `SendEvent` receipts and typing.
