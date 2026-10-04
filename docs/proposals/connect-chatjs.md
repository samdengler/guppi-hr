# Plan: questions straight to Connect with amazon-connect-chatjs

Status: approved direction (D55, Sam, 4 October 2026); plan revision 2 after the independent
review of revision 1 (findings H1 to H4, M1 to M9, L1 to L7, V1 to V8). Built and deployed
4 October 2026 as the default for /p/hr/; the bridge path stays behind `?ff=connect-bridge` for
rollback. Stage 1's pass mark passed on every suggestion (L29); results below.

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

## Results, 4 October

The new path has been the page's default since D55; the bridge answers with
`?ff=connect-bridge`. Measured live on chat.dengler.io from 16:51 to 17:21 UTC by a headless
Playwright page signed in with the harness's test session: the page's IndexedDB session was
seeded before load, as guppi-gpt `scripts/browser-check.mjs` does, and `/config.json` was
routed so the page refreshes with the harness's Okta client (M7), which was in place from the
first load; the page was not tried without it. Signed in this way, /p/hr/ showed the chat
and its four suggestions, not the sign-in screen. No deploy fell in the window (GuppiConnect last
updated 16:43:52 UTC, GuppiGpt 16:27:59 UTC). Every test contact was ended with
`StopContact` afterwards.

### Stage 1 measurement (step 5)

Two browser contexts, A (default) and B (`?ff=connect-bridge`), both with `?ff=debug`;
presses interleaved A, B, A, B; each press on a fresh page 10 s after the chat showed; 8
presses per suggestion per arm (64), 17:01 to 17:17 UTC. First words run from the click to
the first reply text in the DOM, done to the debug block's "done". p90 is linearly
interpolated. Times in seconds.

| Suggestion | Arm | First words median | p90 | min | max | Done median | p90 | min | max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Update my information | new | 1.08 | 1.31 | 1.04 | 1.38 | 1.08 | 1.31 | 1.04 | 1.38 |
| Update my information | bridge | 1.54 | 1.81 | 1.36 | 1.89 | 1.55 | 1.81 | 1.36 | 1.89 |
| Change my address | new | 2.40 | 2.84 | 2.33 | 3.55 | 2.40 | 2.84 | 2.33 | 3.55 |
| Change my address | bridge | 2.84 | 3.00 | 2.72 | 3.08 | 2.84 | 3.00 | 2.72 | 3.09 |
| PTO policy | new | 3.07 | 3.44 | 2.81 | 3.48 | 3.87 | 4.24 | 3.61 | 4.27 |
| PTO policy | bridge | 3.68 | 4.12 | 3.35 | 4.36 | 4.50 | 4.92 | 4.14 | 5.18 |
| Buddy passes | new | 4.44 | 4.86 | 4.06 | 5.03 | 4.44 | 4.86 | 4.06 | 5.03 |
| Buddy passes | bridge | 4.75 | 5.60 | 4.53 | 5.70 | 4.75 | 5.60 | 4.53 | 5.70 |

The pass mark passes on all three parts: the median saving is 0.47, 0.44, 0.61 and 0.31 s
(at least 0.25 s on every suggestion), no suggestion is slower, and "Change my address" is at
2.40 s against the bridge's 2.84 s. All 64 presses answered; the debug blocks name transport
`connect` for every A press and the bridge for every B press.

Quick presses, 1 s after the chat showed, 2 per suggestion per arm (16), 17:18 to 17:21 UTC,
first words median new against bridge: 2.40 against 3.18 s, 4.63 against 5.40 s, 4.41 against
5.33 s, 6.29 against 6.69 s. Every new-path quick press waited for the chat start (median
0.76 to 1.27 s per suggestion), as the page's "waiting for the chat start" step shows.

A cross-check with `turn_timeline.py`: at 17:05:30 UTC a new-path "Change my address" had
Connect's first reply item 2.10 s after the question and first words on the page at 2.33 s;
at 17:05:45 the bridge's first delta came 2.34 s after the bridge got the run and first
words at 2.86 s. The designer's own time was about the same on both (1.77 and 1.69 s).

### Live checks on the new path

1. CSP and SendEvent: pass. A five-turn conversation (16:52 UTC, contact 2d19fbc0) raised no
   `securitypolicyviolation` event and made no `/participant/event` call; the participant
   calls were `/participant/connection`, `/participant/transcript` and five
   `/participant/message`. The 40 new-path presses of the measurement showed the same.
2. The report route: pass. The five turns' reports to `/api/hr/chat/report` answered 200,
   and so did all 40 reports of the measurement's new-path presses. The function logged a
   `chat_report` line for each.
3. 30 s offline in the middle of a reply: fail. The question went out at 16:53:30 UTC
   (contact d87de09f), the context went offline once SendMessage had answered, and came back
   online 30 s later. The designer answered at 16:53:32.9, while the page was offline. At
   28 s the turn limit ended the turn with the no-reply line, and the answer never appeared:
   20 s after the network came back the thread held only "No answer came back from the HR
   assistant." Chromium's offline emulation left the WebSocket open (no frames while
   offline, no close), so no reconnect or catch-up ran; and a turn that has ended drops a
   later reply in any case. The turn's report was sent while offline and was lost
   (`ERR_INTERNET_DISCONNECTED`), so no `chat_problem` line or alarm came from it. An outage
   longer than the 28 s turn limit loses the answer, and the report has no retry.
   Fixed the same evening (guppi-gpt 870864b): a turn that ends on the turn limit keeps its
   question waiting for a late answer until the next question; the window's `online` event
   runs the transcript catch-up; a report that fails on the network is queued and resent.
   Re-run at 17:31:42 UTC (contact 7b61eade): the PTO answer replaced the no-reply line
   once the network returned (one reply, one text), the `no_reply` report was resent and
   answered 200, and a second report (`<runId>:late`, error `late_reply`) recorded the late
   answer. Pass.
4. A hidden tab: pass. The page was set hidden (the `visibilitychange` event with
   `document.visibilityState` overridden) at 16:55:11 UTC for 5 minutes with the network up;
   it made no request while hidden, read the transcript once on becoming visible, and a
   question then got one answer in 5.17 s with nothing duplicated. Chromium does not throttle
   timers under this emulation as it would for a real background tab.
5. Restart: pass. New chat after the five turns started contact ec937473, whose `chat_start`
   line names `previous` 2d19fbc0 with `previous_outcome` ended and `restarted` true.
   `describe-contact` shows 2d19fbc0 disconnected at 16:52:45.29 UTC (reason API) and
   ec937473 initiated at 16:52:45.18 and still open.
6. The rollback flag: pass. All 32 bridge-arm pages called `/api/hr/invocations` twice (the
   warm start and the question) and made no `/api/hr/chat/start` or participant call; their
   debug blocks show the bridge's steps.
7. The alarm path: pass, by reading and a filter test, without posting a report. The metric
   filter on `/aws/lambda/hr-chat-start` is `{ $.event = "chat_problem" }` to
   `GuppiConnect/ChatStart` `Problems`, which the alarm `guppi-connect-chat-start-problems`
   (threshold 1 in 5 minutes, SNS `guppi-connect-alarms`) counts. An accepted report with
   endReason `no_reply` writes `{"event":"chat_problem","kind":"no_reply",...}`
   (`report_problems` in `connect/chat_start/src/lib.rs`, unit test
   `reports_raise_problems_for_no_reply_designer_errors_and_sockets`), and
   `aws logs test-metric-filter` matches that line. A synthetic report was not posted,
   because it would have raised the real alarm. All three alarms stayed OK.

### Other things seen

- PolicyFlow's replies carry no end mark, so a PTO turn ends 0.8 s after its reply on quiet,
  on both paths (`quiet after the reply` in every PTO debug block).
- Every page load logs CORS errors and a 400 for Dynatrace's RUM beacon
  (`bf49265sdi.bf.dynatrace.com`) in the headless browser.
- One chat start at 17:05:28 UTC (contact e7decab6) spent 1.05 s on the `api://hr-tools`
  exchange with the issuer warm, against 22 to 28 ms for the other three.
- During the window something else posted test reports to the report route (runs named
  `repro-*`, `seq-*`, `after-*`) and requests without a token to the start route.
