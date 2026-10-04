# Plan: questions straight to Connect with amazon-connect-chatjs

Status: proposed, 4 October 2026. Not built.

The browser sends each question to Amazon Connect's participant service and reads the reply
on its own WebSocket, through `amazon-connect-chatjs` 5.2.0. The bridge on AgentCore Runtime
keeps the one job it does well and that needs server credentials: starting the chat (the
token exchange through AgentCore Identity, `StartChatContact`, the greeting, blanking the hop
tokens, warming the sub-agents, ending the chat the page left). Nothing behind Connect
changes. No new Lambda function.

Why: the bridge's per-question path costs 0.26 to 0.38 s in AgentCore Runtime and about
0.1 s more through the edge gateway, on every question (A21, the as-built architecture
page); 8 to 10 s on a fresh microVM after a deploy. Expected first words for "update my
information": about 1.2 to 1.3 s against 1.74 s. Library choice: the Touchpoint and chatjs
comparison of 4 October (chatjs is headless, keeps item ids and server times, sends no
receipts or typing on its own, adds 79 KB gzip; Touchpoint is a widget that renders Markdown
HTML). Review of the first direct-to-Connect proposal: its findings F1 to F11 shape this plan.

## The flow

1. Page load: the page sends the warm start as today (D50). The bridge starts the chat,
   waits for the greeting, blanks the hop tokens, warms the sub-agents and ends the chat the
   page left (all unchanged).
2. Hand-over: alongside the warm start the page sends a hand-over run (`forwardedProps.connect
   = "handover"`, no messages). The bridge waits for the thread's contact exactly as a
   question does today (`session_for`), then answers with one CUSTOM event
   `guppi.connect.chat`: `contactId`, `participantId`, `participantToken`, `region`,
   `startedAt`, `expiresAt` (the earlier of the hop tokens' expiry and the chat's duration
   less two minutes). The participant token already lives in the bridge's store for this
   thread (KMS-encrypted); the hand-over is the only place it leaves the server.
3. The page connects with chatjs (`ChatSession.create({chatDetails, type: "CUSTOMER",
   disableCSM: true})`, receipts off, no typing events) and keeps the session for the thread.
4. Each question: the page's Connect agent sends it with `sendMessage` and assembles the
   reply from `onMessage` with the bridge's turn rules (below), emitting the same AG-UI events
   the bridge emits today, so the chat UI, the waiting dots, suggestions, history and debug
   mode work unchanged.
5. After each turn the page sends a turn report run to the bridge (`forwardedProps.connect =
   "report"`, fire and forget, never on the answer's path): contact id, run id, send time,
   first item, end reason, error code. No text, no tokens. The bridge writes its usual run
   line, so the per-turn log, `turn_timeline.py` and the no-reply alarm keep working.
6. A reload or a reopened thread sends the hand-over again; the bridge's store gives back the
   live chat for that thread and employee (resume as today). A chat near `expiresAt` gets a
   new hand-over with `restart`, and the page shows the bridge's restart line.

## Turn rules the page takes over (from `connect_bridge/turn.py`)

- End of turn: `END_MARK` U+2063 at the end of a reply; `CLOSED_MARK` U+2064 ends the
  conversation; the legacy `[flow] end` and `[flow] closed` lines; `chat.ended` and
  `participant.left` events. The marks are stripped before display.
- A generative journey's answer has no mark: the turn ends 0.8 s after its last item
  (`QUIET_AFTER_REPLY`). A turn gives up after 32 s with the bridge's no-reply line.
- Late replies: items older than the turn's own message (`AbsoluteTime` from `sendMessage`)
  belong to an earlier turn and are dropped; items are deduplicated by `Id`.
- Hidden `[flow]` lines and the designer's error line are handled as the bridge handles them.
- Messages over 1,024 characters are refused in the page with the bridge's line.
- Catch-up: `getTranscript` after every `onConnectionEstablished` (it can fire twice, chatjs
  issues 124 and 298) and on `visibilitychange` to visible; idempotent by `Id`.

## Changes by repository

guppi-gpt (platform page):
- `web/src/connect-chat.js`: the chatjs session wrapper and the turn assembler (pure
  functions over items, so the rules are tested without a network), and a `ConnectChatAgent`
  that the page uses instead of `HttpAgent` when the project's manifest lists the
  `connect-chat` capability. Tests in `web/test/connect-chat.test.mjs`, ported from the
  bridge's relay and classify tests plus recorded live items.
- `web/src/app.js`: pick the agent by capability; send the hand-over with the warm start;
  send the turn report; restart on `expiresAt`; debug block steps from the page's own marks.
- `package.json`: `amazon-connect-chatjs` 5.2.0, pinned.
- CSP (`infra/guppi_gpt_infra/stack.py`): `connect-src` adds
  `https://participant.connect.us-east-1.amazonaws.com` and the exact WebSocket host read
  from the first live connection.
- Docs: `docs/proposals/platform.md` (the transport), README backlog, AGENTS.md file list.

guppi-hr:
- `connect/agent/src/connect_bridge/turn.py`: the hand-over and the turn report, as new
  functions on new lines (the on-behalf-of rollback reverse-applies older commits; no edits
  to their lines). Tests for both.
- `connect/web/manifest.json`: `connect-chat` added to `capabilities`. Removing it is the
  rollback: the page falls back to the bridge for questions, which stays deployed.
- `connect/acxd/hr.js`: a turn cap per conversation (for example 60 turns, then a closing
  line with `CLOSED_MARK`), since the edge gateway's per-user limit no longer sees questions.
- Docs: D55 in `docs/decision-log.md`, `docs/hr-page-sequence.md` diagrams, a latency-log
  entry with the measured result, `aws-feedback.md` for anything new.

## Decisions for Sam before building

1. The participant token reaches the browser (in memory only, never stored, never in RUM).
   It is valid for the chat's life and does not depend on Okta; sign-out does not end it.
   The page ends it with `disconnectParticipant` on sign-out and on a new chat.
2. Per-question limits become Connect's per-instance quota (10 sends a second shared by all)
   plus the designer's turn cap. The edge gateway keeps limiting chat starts. Acceptable for
   the invite-only POC?

## Order of work and time

1. Bridge hand-over and turn report, tests, deploy (about 20 minutes).
2. Record live items: a short browser script connects with a handed-over token, sends the
   four suggestions and a follow-up, and saves the raw items as test fixtures (about 10
   minutes, 15 Connect messages).
3. Page module, agent and tests from the fixtures; wiring; CSP; build (about 45 minutes).
4. Site deploy with the capability off; turn it on for a test tab first (about 10 minutes).
5. Live checks (about an hour with waiting): no CSP violations; network log shows no
   `SendEvent`; marks intact; offline 30 s mid-reply recovers with no gaps or duplicates; a
   tab hidden over 5 minutes catches up; a second question before the first answer finishes
   drops the late tail; resume after reload; restart near `expiresAt` (simulated by a short
   `expiresAt`); the turn report reaches the bridge log.
6. Latency: 8 presses per suggestion against L24, measured in the page's debug mode through
   a headless browser with the harness token, at a quiet time with no deploy in the window.
7. Turn the capability on in the manifest; docs.

About 1.5 hours of building and an hour of live checks.
