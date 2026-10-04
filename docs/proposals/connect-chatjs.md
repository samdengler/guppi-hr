# Plan: questions straight to Connect with amazon-connect-chatjs

Status: approved direction (D55, Sam, 4 October 2026); plan revision 2 after the independent
review of revision 1 (findings H1 to H4, M1 to M9, L1 to L7, V1 to V8). Not built.

/p/hr/ takes the shape of AWS's Touchpoint front end. A chat-start function (Rust, Lambda)
starts the chat; the browser sends each question to Amazon Connect's participant service and
reads the reply on its own WebSocket through `amazon-connect-chatjs` 5.2.0. Nothing behind
Connect changes: the designer still calls the agents gateway and the tools gateway with the
on-behalf-of tokens minted at chat start. The bridge on AgentCore Runtime, its store and the
edge gateway's `hr` target retire once the new path has run a week without a stuck turn;
until then the bridge stays deployed as the fallback and the rollback.

Why: the bridge's per-question path costs 0.26 to 0.38 s in AgentCore Runtime plus about
0.1 s through the edge gateway on every question (A21), and 8 to 10 s on a fresh microVM after
a deploy; a page load pays a new runtime session (0.7 to 1.5 s). Expected first words for
"update my information" about 1.2 to 1.3 s against 1.74 s; the saving is the same absolute
amount on every question, about a quarter of the fastest suggestion and under a tenth of a
delegated one.

## The chat-start function

`hr-chat-start`, Rust on `provided.al2023`, arm64, in guppi-hr's Connect stack, built like
the token issuer (cargo-lambda at synth, D51). Reached at `https://chat.dengler.io/api/chat/*`
through a CloudFront behavior to the function's URL, so the page calls its own origin (the
CSP keeps `'self'` for it). The function URL streams its response (`RESPONSE_STREAM`), which
lets the credentials go out at the greeting while the warm-ups finish in the same invocation
(V3: no asynchronous self-invocation, so no hop tokens in Lambda's event queue). Reserved
concurrency caps it.

The function verifies the Okta access token itself with the issuer's Rust verifier and
built-in Okta keys (issuer, audience `api://guppi`, the chat clients, expiry), since a
function URL has no JWT authorizer (V5, F7). It is the hop-token client `hr-bridge` through a
workload identity of its own, so the issuer's rules and the five gateway and runtime
authorizers stay as they are (F9); the audit's `act` keeps naming `hr-bridge` until a rename.

Routes:
- `POST /api/chat/start`, body `{ previousContactId? }`. Exchanges the Okta token through
  AgentCore Identity for the three agents tokens and the designer's tools token; when
  `previousContactId` is set and its `employeeId` attribute is the caller's, ends it
  (`StopContact`); calls `StartChatContact` with the hop tokens and `employeeId` as
  attributes, set on the server only; opens its own customer WebSocket, waits for the
  greeting, blanks the four token attributes (D42, D53) and, alongside the greeting wait,
  sends the three sub-agent warm-ups (D41). The stream's first line, after the blanking, is
  AWS's sample body plus what the page needs:
  `{"data":{"startChatResult":{"ContactId","ParticipantId","ParticipantToken"}},
  "region":"us-east-1","startedAt":...,"expiresAt":...,"restarted":bool}`. `expiresAt` is the
  earlier of the hop tokens' expiry and the chat's duration less two minutes. The last line
  says how many warm-ups succeeded. A failed exchange answers `{"error":"signin"}` (the
  bridge's sign-in line, L1).
- `POST /api/chat/report` (stage 2), body: the turn record (contact id, run id, Connect's
  `AbsoluteTime` for the sent message and the first and last reply items, end reason, error
  code, `transport`). The function checks that the contact's `employeeId` is the caller's
  (L5), writes one run line per run id, and writes `chat_problem` lines for `no_reply`,
  `designer_error` and `socket_failed`, which the alarms count (H4). No text, no tokens.

## The page

guppi-gpt gets a generic Connect chat transport; HR's conventions come from the project (M9).

- `web/src/connect-chat.js`: the chatjs session (`ChatSession.create({chatDetails, type:
  "CUSTOMER", disableCSM: true})`, `setGlobalConfig({region, features: {messageReceipts:
  {shouldSendMessageReceipts: false}}})`, no logger, no typing or receipt events) and a pure
  turn assembler over raw items, so the rules are tested without a network.
- `ConnectChatAgent` extends `AbstractAgent` and overrides `runAgent` to keep the caller's
  `abortController`, as `HttpAgent` does; on abort it stops the assembler and unsubscribes
  (M1). It emits a `ping` CUSTOM event every 15 s while waiting, so the page's 30 s stall timer
  matches the kit's behaviour, and the bridge's event order: `RUN_STARTED`, `STEP_STARTED
  "Amazon Connect"`, text, `connect/<kind>` CUSTOM events, `STEP_FINISHED`, `RUN_FINISHED`. It
  emits its own `guppi.timing` (send, first item, end, from the page's marks and Connect's
  `AbsoluteTime`), so the debug block keeps working (L1).
- The turn rules come from the manifest as data: `connectChat: { start: "/api/chat/start",
  report: "/api/chat/report", endMark: "⁣", closedMark: "⁤", hiddenPrefix:
  "[flow]", quietAfterMs: 800, turnLimitMs: 28000, maxChars: 1024, lines: {...} }` (the
  bridge's texts). The turn limit sits under the page's 30 s stall timer.
- Assembly: buffer items until `sendMessage` resolves with its `Id` and `AbsoluteTime`; drop
  items older than it and the message itself; dedupe by `Id`; end the turn on the end mark,
  the closed mark (conversation over), `chat.ended` or `participant.left`; a reply without a
  mark ends after `quietAfterMs` of quiet; no reply in `turnLimitMs` gives the no-reply line.
  Items between turns are dropped, except `chat.ended`, which marks the chat ended.
- Credentials are read only by the transport's own start path, never through the extension
  host, never stored, never logged, never in RUM (L6, F8). The page's warm start (D50) calls
  `/api/chat/start` when the transport is on; a question sent before the credentials arrive
  waits for that one in-flight start (H2).
- A new chat calls start with `previousContactId`; sign-out awaits `disconnectParticipant`
  with a 2 s cap before the redirect (L3). A refused send, `chat.ended`, the closed mark, or
  fewer than 5 minutes to `expiresAt` (after the page's token refresh) starts a new chat with
  `previousContactId` and shows the restart line (H3, F4). A thread reopened from history
  starts a new chat and shows the restart line: there is no store, so the designer forgets
  the earlier turns (V1, accepted for the POC).
- Fallback: if `connect()` fails, or the WebSocket breaks and one reconnect fails, the thread
  goes on through the bridge (`HttpAgent`) while the bridge is deployed, and the debug block
  and the report say `transport: bridge` (M6).
- Behind the feature flag `connect-chat`, off by default and on per browser with
  `?ff=connect-chat`, which also gives the A/B measurement its two arms (M4). Turning it off
  is the rollback while the bridge is deployed.
- CSP `connect-src` adds `https://participant.connect.us-east-1.amazonaws.com` and
  `wss://*.transport.connect.us-east-1.amazonaws.com` (AWS's documented host shapes) through
  a platform stack deploy, recorded as a guppi-gpt decision for every project page (M5, F10).

## Stage 1: a measured go or no-go

1. guppi-hr: the function's start route, its stack (function URL with streaming, reserved
   concurrency, IAM for Identity, `StartChatContact`, `UpdateContactAttributes`,
   `StopContact`, `GetContactAttributes`, the agents gateway), its own workload identity, the
   CloudFront behavior in guppi-gpt's stack; tests ported from the bridge's start tests.
2. guppi-gpt: the transport with the happy-path rules (marks, quiet end, late filter,
   dedupe, abort, pings, timing), the flag, the CSP; tests from recorded live items.
3. Record live items: a local Playwright page connects with credentials from the start
   route and saves the raw items for the four suggestions and a follow-up as fixtures.
4. Prove the headless sign-in for the measurement (route `/config.json` to the harness's
   client id in Playwright if the page refuses the harness session, M7).
5. Measure: one window, two browser contexts (flag on and off), presses interleaved, 8 per
   suggestion per arm, at a quiet time with no deploy in the window. Pass mark, set now:
   median first words at least 0.25 s lower on every suggestion, no suggestion slower, and
   "I need to change my home address" at or under the bridge arm's median (the warm-ups
   still land).

## Stage 2: parity and retirement, if stage 1 passes

- The report route, `chat_problem` alarms in the function's log group, and
  `turn_timeline.py` reading report lines anchored on Connect's `AbsoluteTime` (H4, V2).
- Catch-up: `getTranscript` after every `onConnectionEstablished` (it can fire twice, chatjs
  issues 124 and 298) and on `visibilitychange` to visible, idempotent by `Id`.
- Restart, replace, fallback and sign-out as above; the full per-turn behaviours (L1).
- Live checks: no CSP violations; no `SendEvent` in a five-turn network log; marks intact;
  30 s offline mid-reply recovers with no gaps or duplicates; a tab hidden over 5 minutes
  catches up; a late reply before the next question is dropped, one after it shows as today
  (L2, C13); a short `expiresAt` restarts; a report reaches the log and a forced no-reply
  raises the alarm.
- The flag on in the manifest; a week without a stuck turn; then the bridge, its table, its
  alarms and the edge `hr` target retire. The on-behalf-of rollback then means turning the
  function's exchanges off with the flag off; until retirement the bridge covers it.
- Docs: `hr-page-sequence.md` diagrams, the architecture pages, a latency-log entry,
  `aws-feedback.md`, both AGENTS.md files (the approved Lambda list), KEPT_COMMITS follow-ups.

## Accepted for the POC (D55)

- The participant token in the browser, in memory only, independent of Okta (F8).
- Per-question limits are Connect's per-instance send quota (10 a second shared); chat starts
  are limited by reserved concurrency and the invite list, not per employee (F3, V5). No
  designer turn cap for now: it could not count the policy journey's own follow-ups (M2).
- A reopened thread starts a new chat (V1).
- A stuck turn in a tab that closed sends no report; the designer's log and Connect's records
  are the backstop (H4).

## Time

Stage 1: about 2 to 3 hours of building, plus the measurement window (about 30 minutes of
presses at a quiet time). Stage 2: about 3 to 5 hours of building and 2 hours of live checks
with waiting, if stage 1 passes. The review's estimate for the bridge-hand-over version was
5 to 8 hours plus 2 to 3; the Lambda removes the kit change but adds the function and its
stack.
