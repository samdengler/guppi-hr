# AWS feedback from the HR super-agent POC

What building chat.dengler.io, the HR super-agent on Amazon Connect (`/p/hr/`) and its
Strands version (`/p/hr-diy/`, named `/p/hr-connect/` and `/p/hr/` before D37) taught about AWS services, kept for the AWS teams. Each entry
says what was expected, what happened, where the evidence is, and what would help. Entries
are added as things are found; an entry is not removed when it is worked around, only
marked.

Status values: **open** (no workaround, or one that should not be needed), **worked
around** (the POC has a workaround; the ask stands), **confirmed** (expected behavior
verified, kept as a positive data point), **to verify** (observed once, not yet repeated).

## Trace context across the hops

The page mints one W3C `traceparent` per message (guppi-gpt
`docs/proposals/traceability.md`), and the goal is one trace from the click to the last
tool call. Every hop below is AWS.

### TC1. Connect's Agentic CX designer drops trace context

- Date: 3 Oct 2026. Service: Amazon Connect, Agentic CX designer. Status: **open**.
- Expected: a turn sent with `SendMessage` (participant API) carries its trace context
  into the designer's data requests, so the sub-agent's spans join the caller's trace.
- Happened: there is no field for trace context on `SendMessage` or the chat contact,
  and no designer variable that holds one. A data request header can carry a context
  variable, but a contact attribute changed during a running session never reaches it
  (phase 0, `connect/docs/platform-plan.md`), so a per-turn value cannot get in at all.
  The bridge's trace and the Profile agent's trace for the same turn are unrelated in
  Dynatrace.
- Evidence: `connect/docs/platform-plan.md` (phase 0 results). Confirmed in Dynatrace on
  3 Oct for contact `f15499c1-…` (03:40 UTC): the bridge's trace `6ac0791a48b553ed…` and
  the Profile agent's trace `6ac0792b69f685ec…` for the same message share nothing.
- Ask: accept `traceparent` on `SendMessage` (or message metadata) and expose it to data
  requests, for example as `{System.traceparent}`; or let the designer emit OTLP spans for
  its nodes with the incoming trace as parent.
- Workaround: link by id. Corrected 3 Oct: until `connect-hardening` no span carried the
  id (critique finding 18). Now the bridge's run span has `connect.contact_id`, and each
  sub-agent's A2A request handler span (`DefaultRequestHandler._run_event_stream`) has
  `hr.thread_id` (the contact id the canvas sends as the A2A context) and `hr.domain`,
  with the trace id in the sub-agent's run record, so the two traces of one turn join on
  that attribute (checked in Dynatrace, 3 Oct 11:57 UTC, contact `4953554e-…`).

### TC2. The designer's own steps have no traces, and logs arrive late

- Date: 2 Oct 2026. Service: Amazon Connect, Agentic CX designer. Status: **open**.
- Expected: node timings (routing model, data requests, journeys) in the same backend as
  the rest of the turn.
- Happened: the only source is `QueryLogs`, one to two minutes after the turn, by
  conversation id. A 14.6 s turn on 3 Oct could be split only by reading `QueryLogs` by
  hand (`connect/acxd/logs.js`): data request `DelegateProfile` 4,750 ms, routing model
  under a second.
- Evidence: `connect/docs/spike-report.md` (fact 14); contact `3781cf27-…`, 3 Oct 03:28 UTC.
- Ask: OTLP export or CloudWatch vended logs for designer events, with the contact id and
  any incoming trace id on each event.

### TC3. AgentCore drops headers it was not told to keep, and refuses the X-Ray header

- Date: 3 Sep 2026. Service: AgentCore Runtime and Gateway. Status: **worked around**.
- Expected: trace context passes through by default, in the X-Ray form or the W3C form.
- Happened: the runtime's request header allowlist refuses every `x-amzn-` header except
  its own prefix, so `X-Amzn-Trace-Id` cannot be used; `traceparent` passes only when
  named in both the gateway target's allowed request headers and the runtime's
  allowlist. Without the allowlist the runtime also drops `Authorization` after validating
  it, so the container cannot call the next gateway (observed as `RUN_ERROR UNAUTHORIZED`).
- Evidence: guppi-gpt `infra/guppi_gpt_infra/stack.py` (`TRACE_HEADER` and the runtime's
  `request_header_allowlist` comments); guppi-hr `infra/hr_super_agent_infra/sub_agents.py`
  and `hr_tools.py` (`FORWARDED_HEADERS`).
- Ask: pass `traceparent` and `tracestate` by default, or document the two allowlists
  together with trace propagation.

### TC4. AgentCore's own OTEL settings in the container are undocumented

- Date: 3 Oct 2026. Service: AgentCore Runtime (observability). Status: **worked around**.
- Expected: setting `OTEL_EXPORTER_OTLP_TRACES_HEADERS` inside the process before
  `opentelemetry-instrument` starts, when the variable is absent from the runtime's
  configuration, gives the exporter that header.
- Happened: a launcher that kept an existing value of the variable sent spans to the
  third-party endpoint without its `Authorization` header (401 on every batch). AgentCore
  puts OTEL settings of its own into the container; the launcher now overwrites the value.
- Evidence: guppi-hr D35 and `agent/src/hr_agent/otel_headers.py`; HR orchestrator log
  group, 3 Oct 02:09 UTC (`Failed to export span batch code: 401`).
- Ask: document the OTEL variables AgentCore sets, and which a customer's values override.

### TC5. No first-class way to send traces to a second OTLP backend with a secret

- Date: 3 Oct 2026. Service: AgentCore Runtime. Status: **worked around**.
- Expected: send spans to a third-party OTLP endpoint (Dynatrace) with its API token kept
  in Secrets Manager.
- Happened: runtime environment variables are the only setting, and `GetAgentRuntime`
  returns them in plain text, so the token was readable by anyone allowed to describe the
  runtime. The POC added a launcher that reads Secrets Manager and execs
  `opentelemetry-instrument`. OTEL's variables also carry one endpoint per signal, so the
  spans go to Dynatrace instead of CloudWatch, not to both.
- Evidence: guppi-hr D35, D36; guppi-gpt `docs/proposals/dynatrace.md` ("The token in
  Secrets Manager").
- Ask: secret-backed runtime environment variables, or an observability setting for an
  extra OTLP destination with headers from Secrets Manager; dual export.

### TC6. The bridge's exports to the AgentCore default endpoints fail a third of the time

- Date: 2 Oct 2026. Service: AgentCore Runtime (default trace and log export). Status:
  **to verify** (retest with the documented role; traces avoided by sending them to
  Dynatrace).
- Expected: the default OTLP export from a runtime succeeds or fails consistently.
- Happened: on the connect bridge runtime, about a third of span and log batches answered
  `403 Forbidden` from the plain OTLP exporter, during turns, while the rest arrived. The
  HR sub-agents showed none. Pinning ADOT 0.19.0 instead of 0.21.0 did not change it.
  Corrected 3 Oct (critique finding 18): the two roles are not the same. The bridge's
  hand-written role (`connect/infra/guppi_connect_infra/bridge.py`) lacks
  `logs:PutResourcePolicy` and the workload access token actions that the HR runtimes'
  role grants (`infra/hr_super_agent_infra/runtime_role.py`), so the comparison does not
  isolate AgentCore. Log export still fails (X7); span failures stopped once traces went
  to Dynatrace.
- Evidence: log group `/aws/bedrock-agentcore/runtimes/guppi_connect_bridge-6MsqS747nh-DEFAULT`,
  2 Oct (about 140 errors that day); `connect/docs/platform-plan.md` (open items).
- Ask, after a retest with the documented execution role: a look at what differs per
  batch. The bridge starts its process 10 to 45 times an hour without traffic (the
  critique's count), so the 11 starts noted first are its normal state, not a lead.

### TC7. Transaction Search at 1 percent hides most spans

- Date: 3 Oct 2026. Service: X-Ray Transaction Search. Status: **confirmed** (the POC's
  own setting).
- Happened: with indexing at 1 percent (the account's rule comes from the GuppiGpt stack;
  guppi-hr's copy is created only with `own_account_singletons`, which is off; corrected 3
  Oct), the sub-agents' spans
  for a slow turn were not in `aws/spans`, so the slow call could not be explained there.
- Ask: index error and slow spans regardless of the percentage, or make the setting's
  effect clearer where spans are searched.

### TC8. Trace context through AgentCore Gateway to a runtime

- Date: 3 Oct 2026. Service: AgentCore Gateway. Status: **confirmed** for the tools
  gateway; the edge and agents gateways on `/p/hr/` still to check.
- Expected: with `traceparent` in the allowlists (TC3), one trace covers the edge gateway,
  the orchestrator, the agents gateway, a sub-agent, the tools gateway and the tools
  server.
- Happened: the Profile agent's `mcp tools/call` and the tools server's span carry the
  same trace id (`6ac0792b69f685ec…`, 3 Oct 03:40 UTC), so the tools gateway passes trace
  context. When a request arrives with none (the canvas's call, TC1), the agents gateway
  starts a trace itself and the runtime joins it.

### TC9. AgentCore Gateway's own spans never reach the customer's trace backend

- Date: 3 Oct 2026. Service: AgentCore Gateway. Status: **open**.
- Expected: the gateway's span for a hop sits in the same trace as the runtimes on
  either side, in whatever backend the runtimes export to.
- Happened: in Dynatrace the Profile agent's root span and the tools server's span both
  name parents (`2dec31f446c40bed`, `cbde195c21bd5990`) that are not there: the agents and
  tools gateways' spans go only to AgentCore's own destinations. The trace has a hole at
  every gateway, and the hole is where time goes missing: the Profile agent's
  `hr___get_profile` call took 1.21 s, the tools server 0.22 s of it (DynamoDB 33 ms), and
  about 1 s sat in the gateway hop with nothing to say whether it was the gateway or a
  cold start of the freshly deployed tools runtime.
- Evidence: Dynatrace `fetch spans` for 3 Oct 03:40:00 to 03:41:00 UTC, services
  `hr_super_agent_profile.DEFAULT` and `hr_super_agent_tools.DEFAULT`.
- Ask: export gateway spans over OTLP to the destination the customer configures (or the
  runtimes'), with the incoming trace as parent; until then, gateway timing (queueing,
  authorization, target invocation, cold start) as span attributes or vended logs with
  the trace id.

## Amazon Connect

| Id | Date | Finding | Status |
| --- | --- | --- | --- |
| C1 | 2 Oct | The chat contact flow starts only after the customer's WebSocket connects; with connection credentials alone the transcript stays empty. One connect and close is enough, then `SendMessage` and `GetTranscript` carry the conversation (phase 0). | worked around |
| C2 | 2 Oct | A contact attribute updated with `UpdateContactAttributes` never reaches a running designer session, so a refreshed token needs a new contact (phase 0). | worked around |
| C3 | 2 Oct | `GetContactAttributes` on a finished contact still returns `hrToken`, so the employee's token stays on the contact record for its lifetime unless cleared (spike fact 13). Corrected 3 Oct: the first workaround blanked it after the first relayed reply, which left it on warm-only and failed contacts (two live contacts held one; critique finding 1). Since `connect-hardening` the bridge blanks it right after the greeting on every path, since the designer keeps the value it read at start (C2). The ask stands: a way to pass a credential to the designer that is not a contact attribute. | worked around (blanked after the greeting) |
| C4 | 3 Oct | A new chat costs about 5 s before the first message can be sent: `StartChatContact`, the participant connection, the WebSocket connect, and the flow's greeting. The POC hides it with its own warm start (D39); the ask is for Connect to make the start faster or let a client start a contact ahead of the first message without holding a chat for its whole duration. | open |
| C5 | 2 Oct | The designer's MCP data request type fails every call with "data request could not be prepared" before any HTTP request; a plain HTTP JSON-RPC `tools/call` works. The console's Sync may be the missing step; the SDK has no call for it (spike fact 11). | open |
| C6 | 2 Oct | Headers set only on a flow node's data request are not sent; they must be declared on the data request itself (spike fact 1). | worked around |
| C7 | 2 Oct | A field-map payload fills only top-level placeholders and over-escapes quotes; a JSON string payload works (spike fact 2). A field-map payload also adds every context variable, the token included, to the body as `nlx_context` (phase 0). | worked around |
| C8 | 2 Oct | A `user_input` node with an unconditional edge does not wait for input, and a second `user_input` in the same turn re-reads the utterance (spike facts 4, 5). | worked around |
| C9 | 2 Oct | One deployment per application (`LimitExceededException`); each environment is its own application (spike fact 7). | worked around |
| C10 | 2 Oct | The Agentic CX block needs speech and audio filler configuration even for chat, or the contact flow import fails (spike fact 10). | worked around |
| C11 | 2 Oct | A data request node's timeout caps at 30 s, where the code orchestrator allows 120 s (spike report). | open |
| C12 | 2 Oct | Intent routing varies run to run on the same canvas: the PTO question went to EscalationFlow once and answered the next time; the routing eval's u52 follow-up missed once in a re-run (54 of 60 against 55); a PTO question right after a buddy pass question stayed in Travel. No setting pins routing for a test run (`connect/docs/platform-report.md`). | to verify |
| C13 | 3 Oct | The transcript has no "turn complete" signal, and the canvas can send several messages for one input (ClarifyFlow's re-ask sends two), so a client can only guess the end of a turn from silence: the bridge waited 2.5 s, then 0.8 s, and a reply after the window showed up as the answer to the next question (critique finding 4). Corrected 3 Oct: since `connect-hardening` every reply node ends its text with an invisible mark (U+2063; a separate hidden line would be one more billed message), which the bridge ends the turn on; a generative journey's own answer cannot be followed by a node, so it still ends on silence. The ask: a turn-complete event from the designer, journeys included. | worked around (except journeys) |
| C14 | 3 Oct | The first data request of a contact to a sub-agent reaches it much later than the next one: the designer's `DataRequestsRequested` at 05:01:52.473 UTC and the Profile agent's request at 53.785 (1.31 s), against 0.40 s for the follow-up at 05:02:20.400. The canvas names the runtime session `{conversationId}-{domain}`, so the first call opens a new runtime session through the agents gateway (AgentCore); the Profile microVM itself had been running since 04:38, so it is session setup, not a container start. The routing model step is 0.43 to 0.47 s and Connect hands a message to the designer in 0.32 s. | to verify (one pair of runs) |
| C15 | 3 Oct | About 1.2 s of every turn is Connect's own path, before and after the work: Connect hands a customer message to the designer in 0.32 s (bridge `SendMessage` end to the designer's `NluRequestReceived`), the designer's routing model takes 0.43 to 0.47 s even when the conversation is already in a flow (`ModelStart` to `ModelEnd`), and a reply reaches the customer's WebSocket about 0.2 s after `NluResponded`. With the agents gateway's 0.4 s (AgentCore) a sub-agent starts about 1.6 s after the message is sent, and a profile read that the sub-agent answers in 0.8 s reaches the page at 2.6 s or more. A new contact adds 2 to 3 s more (C4) and its first routing is slower (C14). Measured from the designer's `QueryLogs`, the bridge's spans and the harness, 3 Oct. The asks: lower the hand-off and delivery times; let a flow skip the routing model when it keeps the turn (sticky context); and say what latency a chat turn through the Agentic CX block should expect. | open |

## Amazon Bedrock AgentCore

| Id | Date | Finding | Status |
| --- | --- | --- | --- |
| A1 | 3 Sep | Binding a JWT runtime to a gateway (`allowedWorkloadConfiguration`) cannot be combined with token passthrough: the runtime demands a transaction token, and the gateway supplies one only when it signs as itself, which the JWT runtime refuses as an authorization method mismatch (guppi-gpt decision 8). | open |
| A2 | 3 Sep | `CreateGatewayRateLimit` refuses two rate limits on one gateway with the same dimension keys, so request and concurrency limits share one entry (guppi-gpt stack). | worked around |
| A3 | 4 Sep | A CloudWatch Logs destination for a gateway's `TRACES` log type is rejected by CloudFormation; gateways deliver `APPLICATION_LOGS` only (guppi-gpt stack tests). | open |
| A4 | 2 Oct | A runtime's execution role reading a private git dependency at image build needs a BuildKit secret; nothing AgentCore-specific, noted because the starter kit's Dockerfile has no hook for it (guppi-hr D29). | worked around |
| A5 | 3 Oct | Behind a gateway, an MCP server runtime starts a new runtime session, so a new microVM, for every new MCP session. A client that opens a session per request pays a cold start on every tool call: the tools runtime's log streams were created at 04:18:26.06 and 04:18:43.33 UTC, one per Profile agent request, and each `tools/call` took about 1.2 s against 0.2 s inside the server. Nothing in the gateway's responses or spans says a cold start happened (see TC9). Revised the same day: with the client's session kept (guppi-hr D38), the two calls of one kept client session reached two different microVMs, both already running (log streams created at 04:38:49 and 04:38:51), and each still spent about 0.8 s outside the server (A6). How the gateway maps a client session to runtime sessions is not visible, and the cold start explains only part of the 1 s. | to verify |
| A6 | 3 Oct | Behind a gateway, every `tools/call` to an MCP server runtime is its own MCP session on the target: the server logs an `initialize`, a `notifications/initialized` and the `tools/call` as three requests on a new connection, after one "Invalid HTTP request received" warning, even when the client reuses one gateway session. On a warm microVM the follow-up's call (trace `6ac087344e428cc85ef240f016d342ec`) took 965 ms at the client against 157 ms in the server: 0.54 s from the client's send to the target answering `initialize`, then about 0.12 s for each of the two handshake steps. Every running tools microVM also gets an MCP ping every 2 s on a second connection. The ask: reuse the target session for a client session, or skip the handshake for a stateless target, and say in a span where the time goes (TC9). | open |
| A7 | 3 Oct | A request through CloudFront and an AgentCore Gateway runtime target reaches the runtime's handler later than a direct `InvokeAgentRuntime`. First estimate, comparing the browser's clock with the server's: 0.5 to 0.6 s. Remeasured on one clock (the time to the bridge's immediate `RUN_STARTED`, 10 runs each, 3 Oct 12:10 UTC): median 0.47 s through the edge gateway against 0.33 s straight to the runtime, so the gateway path adds about 0.14 s and the runtime's own round trip is most of the rest. | confirmed (small) |
| A8 | 3 Oct | Strands Agents (AWS's agent SDK, 1.54.0): with redaction on (`OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_unredacted_attributes=`), messages and tool data are redacted, but the `invoke_agent` span still carries the whole system prompt in the legacy `system_prompt` attribute. Anything an application puts in the system prompt (here the employee's record, for a one-call read) reaches the trace backend in clear. Found by searching Dynatrace for the test employee's details, 3 Oct 12:19 UTC. The POC keeps the system prompt static and sends personal context with the message. The ask: redact `system_prompt` under the same policy as `gen_ai.system_instructions`. | worked around |
| A9 | 3 Oct | AWS Distro for OpenTelemetry (`aws-opentelemetry-distro` 0.19.0): its MCP instrumentation (`aws_mcp`) sets `gen_ai.tool.call.arguments` and `gen_ai.tool.call.result` on every `mcp tools/call` span, with no setting to leave them out, so a profile read or a direct deposit change puts personal data in the trace (66 spans with the test employee's address in 30 minutes, 3 Oct). The POC turns the instrumentation off (`OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=aws_mcp`) and keeps tool timing from Strands' redacted spans. The ask: honor the GenAI content-capture switch, or a redaction list, for MCP spans. | worked around |
| A10 | 3 Oct | AWS Distro for OpenTelemetry under AgentCore Runtime: when agent observability is on, the distro sets `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true` by default (`aws_opentelemetry_distro.py`, `setdefault`), so the Bedrock instrumentation writes every prompt and model reply, system prompt and tool results included, as OpenTelemetry log records to the runtime's `otel-rt-logs` stream in CloudWatch. 387 records with the test employee's details in a day, found by a Logs Insights search on 3 Oct. Nothing in the AgentCore setup says content is captured. The POC sets the variable to `false` on every HR runtime. The ask: default to off, or say plainly that it is on. The six log streams (`otel-rt-logs` and `spans` on the orchestrator, Profile, Travel and tools runtimes) that held the synthetic employee's details from before the A8 to A10 fixes were deleted on 4 Oct. | worked around |
| A11 | 3 Oct | AgentCore's `CUSTOM_JWT` authorizer (gateway and runtime): `allowedClients` matches only the `client_id` claim, which Cognito's access tokens carry; Okta's access tokens name the client in `cid` (and Entra's in `azp` or `appid`), so a client allow-list cannot be used with them and the POC checks the audience instead (D46). An authorizer that took the client claim's name, or recognized the common ones, would keep client binding for any issuer. | worked around |
| A12 | 3 Oct | AgentCore's `CUSTOM_JWT` authorizer refuses `scp` as a custom claim ("Custom claim name can't be 'scp'. Please configure claims in the allowed_scopes field"), so a scope check goes through `allowedScopes`, which is not documented in two respects the spike settled on 3 Oct: it reads either the RFC 9068 `scope` string or Okta's `scp` list, and it passes a token holding any one of the listed scopes (any-of, not all-of). `allowedClients` and `allowedScopes` both work on a runtime's authorizer as well as a gateway's. Two smaller points: the same failure is 403 at a gateway and 401 at a runtime, and a runtime's 401 names the claim that failed ("Claim 'client_id' value mismatch with configuration"), which tells a caller what to forge. Otherwise the gateway accepted a self-hosted RFC 8693 issuer by its discovery document, and AgentCore Identity's on-behalf-of credential provider exchanged an Okta token through it (prototype, 3 Oct). | answered |
| A13 | 3 Oct | AgentCore Gateway accepts and stores OAuth `grantType: TOKEN_EXCHANGE` on HTTP targets (an AgentCore runtime target and a passthrough target), but at call time asks the token endpoint for `client_credentials` with no subject token, so the target receives a token naming only the gateway's client, with no user in it. Nothing in the response or the target's status says so; the request reached the runtime with a token its authorizer accepted. MCP server targets with the same credential provider do a real RFC 8693 exchange with the inbound user token. The outbound authorization guide's table lists token exchange as unsupported for AgentCore Runtime (HTTP) targets, so the gap is documented, but `CreateGatewayTarget` accepts and stores the setting. Either the API should refuse `TOKEN_EXCHANGE` on HTTP targets or the gateway should exchange there too; per-agent on-behalf-of tokens on an agents gateway depend on it (spike, 3 Oct). | open |
| A14 | 3 Oct | AgentCore Gateway's on-behalf-of exchange on an MCP server target: (1) against a target that issues no MCP session id, it exchanged the token again and opened a new MCP session with the target (initialize, initialized, call) on every tool call, also within one client session: fourteen calls, fourteen exchanges, about 500 ms per call from a laptop; against a copy of the HR tools runtime (an MCP runtime with a JWT authorizer) the same held: eight `get_profile` calls in one client session made eight exchanges and took a median of 1.92 s, against 1.49 s through today's tools gateway (SigV4 target) with the same client, so the exchange adds about 430 ms to every tool call. Reusing an exchanged token until it expires, per user and target, would remove that. No AgentCore page documents a cache or TTL for gateway or Identity on-behalf-of tokens; AWS's July 2026 blog post on gateway OBO says Identity "might cache OBO tokens within their lifetime" and advises long token lifetimes for reuse, yet tokens with about 59 minutes left were exchanged again on every call. The cache with a TTL capped by the subject token's expiry that searches turn up is agentgateway's (Solo.io), a different product; (2) a target listed at sync asks for a `client_credentials` token at creation, so the issuer must grant tokens with no user, unless the target is given an inline tool schema; (3) the gateway forwards its workload access token to every target in `x-amz-bedrock-agentcore-identity-wat`, HTTP and MCP alike, which a third-party target has no use for; (4) `JWT_PASSTHROUGH` is refused on MCP server targets ("MCP server target does not support JWT_PASSTHROUGH credential provider type"), so a user's own token still cannot reach an MCP target (D19). | open |
| A15 | 3 Oct | Policy in AgentCore on an MCP gateway did what the POC needs on the first try (spike, 3 Oct): Cedar rules on the inbound token's `scope` (`principal.getTag("scope") like "*hr.tools.pay.read*"`) allowed each tool only to tokens holding its scope, filtered `tools/list` to the tools each token may call, refused everything else as "denied by default", and added no measurable time per call (median 1.90 s with the engine in ENFORCE, 1.92 s without). Two rough edges: every claim arrives as a string tag, so a scope check is a substring match (`*hr.tools.pay*` would also match `hr.tools.payroll`), and a matching rule needs the gateway's ARN, so the same rules cannot be written once for several gateways without `ManageAdminPolicy`. A scope-aware operator would remove the first. | open |
| A16 | 3 Oct | Two things learned building D47 with CloudFormation. (1) Attaching a policy engine to a gateway checks the gateway role's `GetPolicyEngine` grant at update time: a stack that added the grant and the attachment together failed with "Access denied while calling GetPolicyEngine on Policy Engine ... with Gateway role" because the gateway updated before the role's policy, and rolled back; the Policy permissions page says a missing grant shows up as an InternalServerException when attaching, which is not what happened. A `DependsOn` from the gateway to the role's policy fixed it. (2) `AWS::BedrockAgentCore::OAuth2CredentialProvider` with `ClientSecretSource: EXTERNAL` and a `ClientSecretConfig` pointing at a stack-generated Secrets Manager secret created on the first deploy, with a resource policy on the secret letting `bedrock-agentcore.amazonaws.com` call `GetSecretValue` as AWS's blog post on external secrets describes. But at call time Identity reads the secret as the caller of `GetResourceOauth2Token`: CloudTrail showed `GetSecretValue` denied to the tools gateway's role and to a sub-agent's runtime role, and the exchange failed with "Token exchange failed: insufficient permissions for token exchange" (a 200 tool result through the gateway). An administrator's test calls had masked it. Each caller's role now reads its own client's secret, and only that one. The blog post and the credential provider pages do not say the caller needs the grant; the error message could name the secret. | worked around |
| A17 | 4 Oct | AgentCore Identity appears to re-read a credential provider's discovery document on about half of all on-behalf-of exchanges: over six hours the issuer's access log showed 27 discovery reads against 61 `/token` calls, from the same Identity addresses, although the document is served with `cache-control: public, max-age=300` (critique of the build, round 2). Each re-read is one more round trip before the exchange, on the bridge's warm start and on every tool call through the tools gateway (A14). Caching the document for its max-age, or at least for minutes, would remove it. | open |
| A18 | 4 Oct | X-Ray with CloudWatch Transaction Search: with the trace segment destination set to CloudWatch Logs (Transaction Search), Lambda's active tracing writes every sampled segment to the `aws/spans` log group, but X-Ray's `GetTraceSummaries` returned nothing for the issuer's cold starts: only 1% of traces are indexed by default (the Default indexing rule). The traces are complete in `aws/spans` and open by id in the console's trace view; nothing on the Lambda tracing page says that a search will miss 99% of them. Also seen: the `LambdaService` segment of a cold start spends 217 to 300 ms before `Init` on a 22 KB zip with no layers, the share of a cold start the function cannot change | confirmed |
| A19 | 4 Oct | Amazon Connect's Agentic CX designer: no documented OpenTelemetry or X-Ray export for the designer was found, and its runtime log, reachable only through the designer's own `QueryLogs` API keyed by the contact id (its `conversationId`), is the only per-step timing source found. Checked on 4 Oct 2026: the `amazon-connect-acxd-sdk` 0.2.0 read operations are `QueryLogs`, `GetConversation`, `ListConversations`, `StartTrailQuery` and `GetTrailQueryResults`; none exports traces or accepts trace context. Connect's "AI agent traces" (June 2026) cover Connect AI agents in self-service voice, in the contact details page and through Connect APIs; a third-party write-up found them unavailable for chat, and none of it names OpenTelemetry or the Agentic CX designer. Observed on /p/hr/: the designer writes to no CloudWatch log group in the account; during the PTO turn on contact 1b067d05 (12:22:36 UTC) the `aws/spans` log group held only the token issuer's Lambda and API Gateway spans, none naming the contact; and the designer's call out to a sub-agent ran under a trace of its own (contact f8937a18, 11:59:52 UTC: the Profile agent's run under trace `6ac23fb7...`, the bridge's run for that turn under `6ac23fb5...`), as TC1 found for `SendMessage`. So a Connect turn cannot be joined with the bridge's Dynatrace trace or an X-Ray trace by trace id: its routing model, data requests and journey agent are timed only in the designer's log. The POC joins the four logs by time and contact id instead (`connect/scripts/turn_timeline.py`, [hr-page-sequence.md](hr-page-sequence.md)). An OpenTelemetry export of the designer's steps, or `traceparent` accepted on `SendMessage` and passed on its data requests, would make one trace of a turn. | open |

## Amazon Cognito

| Id | Date | Finding | Status |
| --- | --- | --- | --- |
| G1 | 3 Oct | Invite-only sign-in with Google federation needs a pre sign-up Lambda trigger; there is no setting that admits only listed addresses from a federated provider (guppi-gpt `docs/proposals/invites.md`). | worked around |
| G2 | 3 Oct | The error a refused federated sign-up returns to the callback is not documented; the POC assumes it carries the trigger's message in `error_description`, as `AdminCreateUser` does ("PreSignUp failed with error not-invited."). | to verify |

## API Gateway, EventBridge Pipes, SES

| Id | Date | Finding | Status |
| --- | --- | --- | --- |
| P1 | 3 Oct | After a CloudFormation deploy that added methods, the new routes answered `Missing Authentication Token` for about a minute, though the stage pointed at the new deployment. | confirmed (propagation) |
| P2 | 3 Oct | An EventBridge Pipe whose filter was just updated by CloudFormation missed a matching DynamoDB stream record about a minute after the update; the same event a minute later matched. The missed record was not retried. | to verify |
| P3 | 3 Oct | A REST API with a Cognito user pool authorizer reads the bearer as an id token unless a scope is named; with an access token it needs `authorization_scopes` (guppi-gpt feedback API). | worked around |
| P4 | 3 Oct | SES production access is a request reviewed by AWS; until then a sandbox account sends only to verified addresses, which a "you're in" email to a new user cannot be. | waiting (requested 3 Oct) |
| P5 | 3 Oct | CloudFormation's template validation warns "SecretString: length 0 is below minimum 1" for a secret whose value is `Fn::If` on a condition with a non-empty fallback; the warning reads the blank parameter default, not the deployed value. | open (noise) |

## Not AWS: other tools in the POC

Kept here so every finding is in one place; these are not for the AWS teams.

| Id | Date | Tool | Finding | Status |
| --- | --- | --- | --- | --- |
| X1 | 2 Oct | Dynatrace | An expired trial tenant answers 404 on its OTLP path even without a token (a live one answers 401), so exporters log 404 rather than an auth or tenant error. | confirmed |
| X2 | 2 Oct | Dynatrace | Each app in the new platform UI runs in a cross-origin frame, and API calls from the outer page carry the shell's OAuth scopes; the token API answered 403 "missing required scope" and the classic config API "404 Api Gateway error". Browser automation cannot create tokens or RUM applications there; the old tenant's runbook relied on it. | worked around (by hand) |
| X3 | 3 Oct | Dynatrace | The local MCP server (`@dynatrace-oss/dynatrace-mcp-server`) is deprecated; the remote MCP server takes a platform token only, with no browser sign-in. | confirmed |
| X4 | 2 Oct | AWS Distro for OpenTelemetry | 0.21.0 and 0.19.0 behave the same for the bridge's 403s (TC6); version is not the cause. | confirmed |
| X5 | 3 Oct | A2A Python SDK | Its instrumentation records each 500 ms `EventQueue.dequeue_event` poll as a server span, so a 3.8 s sub-agent call shows eight "requests" in Dynatrace's request list that are only the queue waiting. | open |
| X6 | 3 Oct | ADOT (`aws-opentelemetry-distro`) or the POC's launcher | Every span of the Connect bridge reaches Dynatrace twice with the same span id (for example `5547197c4e9caf60`, `POST /invocations` at 04:40:19.798 UTC), so counts and sums over bridge spans double. The sub-agents, on the same launcher pattern, were not checked yet; the cause is not known, and may be the POC's own exporter settings. | to verify |
| X7 | 3 Oct | ADOT on AgentCore Runtime, or the POC's setup | The bridge's OTLP log exporter fails batches with 403 Forbidden ("Failed to export logs batch code: 403", 05:34:39 UTC and dozens a day). The POC's launcher sets only `OTEL_EXPORTER_OTLP_TRACES_HEADERS`, so the log exporter keeps the endpoint and headers AgentCore injects; the cause, perhaps the role's permissions for OTLP logs, is not known. Traces are unaffected. | to verify |
| X8 | 3 Oct | Okta Integrator Free Plan | Custom authorization servers are included, but token exchange is not: the exchange grant answers "The NHI Authentication Tokens SKU is not enabled", and trust between authorization servers (`associatedServers`) answers "You do not have permission to access the feature". The POC chose Okta for D20 on the first fact without testing the second; a self-hosted RFC 8693 issuer on API Gateway and Lambda does the exchange instead (prototype). | worked around |
| X9 | 4 Oct | Okta Integrator Free Plan | A new OIDC app gets the default authentication policy "Any two factors", whose catch-all rule requires a possession factor that is phishing resistant, device bound and proves user presence (Okta FastPass or a passkey). A person who enrolls a password and Okta Verify push during activation passes enrollment, then every sign-in from a browser without FastPass is denied: the page says only "Unable to sign in. Contact support for assistance.", and the system log says `policy.evaluate_sign_on` UNSATISFIABLE (05:35:25 UTC). The enrollment policy offers authenticators the app policy will not accept. The POC gave both apps a policy of its own (D49). | worked around |
