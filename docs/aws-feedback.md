# AWS feedback from the HR super-agent POC

What building chat.dengler.io, the HR super-agent (`/p/hr/`) and the Amazon Connect
comparison (`/p/hr-connect/`) taught about AWS services, kept for the AWS teams. Each entry
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
- Workaround planned: link by id. The canvas already sends the contact id as
  `X-Hr-Thread-Id`; spans on both sides carry it.

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
  **open** (avoided by sending the bridge's traces to Dynatrace).
- Expected: the default OTLP export from a runtime succeeds or fails consistently.
- Happened: on the connect bridge runtime, about a third of span and log batches answered
  `403 Forbidden` from the plain OTLP exporter, during turns, while the rest arrived. The
  HR sub-agents, with the same execution role policy, showed none. Pinning ADOT 0.19.0
  instead of 0.21.0 did not change it, and the IAM policy simulator gave the same answer
  for both roles.
- Evidence: log group `/aws/bedrock-agentcore/runtimes/guppi_connect_bridge-6MsqS747nh-DEFAULT`,
  2 Oct (about 140 errors that day); `connect/docs/platform-plan.md` (open items).
- Ask: a look at what differs per batch; the bridge restarts its process often (11
  starts in a few minutes), which may matter.

### TC7. Transaction Search at 1 percent hides most spans

- Date: 3 Oct 2026. Service: X-Ray Transaction Search. Status: **confirmed** (the POC's
  own setting).
- Happened: with indexing at 1 percent (set in guppi-hr's stack), the sub-agents' spans
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
| C3 | 2 Oct | `GetContactAttributes` on a finished contact still returns `hrToken`, so the employee's token stays on the contact record for its lifetime unless cleared (spike fact 13). | worked around (blanked after the first reply) |
| C4 | 3 Oct | A new chat costs about 5 s before the first message can be sent: `StartChatContact`, the participant connection, the WebSocket connect, and the flow's greeting. Nothing starts a contact ahead of the first message. | open |
| C5 | 2 Oct | The designer's MCP data request type fails every call with "data request could not be prepared" before any HTTP request; a plain HTTP JSON-RPC `tools/call` works. The console's Sync may be the missing step; the SDK has no call for it (spike fact 11). | open |
| C6 | 2 Oct | Headers set only on a flow node's data request are not sent; they must be declared on the data request itself (spike fact 1). | worked around |
| C7 | 2 Oct | A field-map payload fills only top-level placeholders and over-escapes quotes; a JSON string payload works (spike fact 2). A field-map payload also adds every context variable, the token included, to the body as `nlx_context` (phase 0). | worked around |
| C8 | 2 Oct | A `user_input` node with an unconditional edge does not wait for input, and a second `user_input` in the same turn re-reads the utterance (spike facts 4, 5). | worked around |
| C9 | 2 Oct | One deployment per application (`LimitExceededException`); each environment is its own application (spike fact 7). | worked around |
| C10 | 2 Oct | The Agentic CX block needs speech and audio filler configuration even for chat, or the contact flow import fails (spike fact 10). | worked around |
| C11 | 2 Oct | A data request node's timeout caps at 30 s, where the code orchestrator allows 120 s (spike report). | open |
| C12 | 2 Oct | Intent routing varies run to run on the same canvas: the PTO question went to EscalationFlow once and answered the next time; the routing eval's u52 follow-up missed once in a re-run (54 of 60 against 55); a PTO question right after a buddy pass question stayed in Travel. No setting pins routing for a test run (`connect/docs/platform-report.md`). | to verify |
| C13 | 3 Oct | The 2.5 s the bridge waits after the last reply, before it ends the turn, exists because the transcript has no "turn complete" signal: the canvas can send several messages for one input, and only silence says it is done. | open |

## Amazon Bedrock AgentCore

| Id | Date | Finding | Status |
| --- | --- | --- | --- |
| A1 | 3 Sep | Binding a JWT runtime to a gateway (`allowedWorkloadConfiguration`) cannot be combined with token passthrough: the runtime demands a transaction token, and the gateway supplies one only when it signs as itself, which the JWT runtime refuses as an authorization method mismatch (guppi-gpt decision 8). | open |
| A2 | 3 Sep | `CreateGatewayRateLimit` refuses two rate limits on one gateway with the same dimension keys, so request and concurrency limits share one entry (guppi-gpt stack). | worked around |
| A3 | 4 Sep | A CloudWatch Logs destination for a gateway's `TRACES` log type is rejected by CloudFormation; gateways deliver `APPLICATION_LOGS` only (guppi-gpt stack tests). | open |
| A4 | 2 Oct | A runtime's execution role reading a private git dependency at image build needs a BuildKit secret; nothing AgentCore-specific, noted because the starter kit's Dockerfile has no hook for it (guppi-hr D29). | worked around |

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
