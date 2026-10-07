# Touchpoint in front of the HR assistant: experiment plan, 6 October 2026

AWS publishes Touchpoint (`@amazon-connect-touchpoint/web`, MIT,
https://github.com/amazon-connect/touchpoint) as the reference front end for Amazon Connect:
one widget for chat and voice, plus Live Sync, which lets the Agentic CX designer drive the
page. D55 and D57 already gave the `/p/hr/` chat start the shape of Touchpoint's
StartChatContact backend, and `docs/proposals/touchpoint-alignment.md` ("A Touchpoint widget
on the same backend") listed eight conditions for putting the widget itself in front of it,
in a plan of its own. This is that plan.

The question: can AWS's own widget replace the chat.dengler.io page for the HR assistant on
Connect, over the same chat start, contact flow, canvas, sub-agents and tools, and what does
it cost in time, behavior and project rules?

## What stays the same

- The chat start `hr-chat-start` (`POST /api/hr/chat/start`, D57): the Okta check, the hop
  token exchanges, StartChatContact, the greeting wait on its own socket and the token
  blanking.
- The HR contact flow, the Agentic CX canvas (`acxd/hr.js`), the Profile, Pay and Travel
  sub-agents, the tools gateway.
- `/p/hr/`, the `GuppiConnect` and `HrSuperAgent` stacks and guppi-gpt are not changed. T1
  adds no AWS resource and no Lambda, and deploys nothing.

## Steps

| Step | What | State |
| --- | --- | --- |
| T1 | The Touchpoint chat widget on a local page, over the live `/p/hr/` backend | Built in `connect/touchpoint/`; smoke run passed on 6 Oct (Results); timed runs not made |
| T2 | Live Sync: the canvas shows a proposed change on the page for the employee to confirm | Planned; needs Sam |
| T3 | Voice through Touchpoint's `voice` and `voiceMini` inputs | Planned; needs a StartWebRTCContact endpoint, so a Lambda decision |
| T4 | A hosted Touchpoint page on chat.dengler.io | Built as `/p/hr-widget/` (D62, guppi-gpt decision 23), 7 Oct |

## T1: the chat widget on the live backend

### How the page works

- `connect/touchpoint/` is a Vite page on `127.0.0.1:5173` with Touchpoint 1.0.2 (the
  published version, 2 Oct) pinned. The page mounts the widget with `create()`, input
  `text`, window `side-by-side`, and keeps a plain-text run log beside it.
- Touchpoint's `config.details` is a function of the page's that posts to
  `/api/hr/chat/start` with `Authorization: Bearer <Okta token>` and `{previousContactId}`
  when one is known. The dev server forwards `/api/hr/chat/*` to chat.dengler.io, so the
  browser calls the chat start on its own origin, as the platform page does (E11).
- The Okta token comes from the harness session (`~/.config/guppi/test-session.json`,
  written by guppi-gpt `scripts/test-token.sh`), refreshed with the harness client, which
  the chat start accepts (`OKTA_CLIENTS`). The dev server answers `POST /dev/token` to
  same-origin requests only, keeps the token in memory, and stores each rotated refresh
  token under the lock the A/B bench uses. It stands in for the sign-in a hosted page would
  have (T4).
- Delivered and read receipts stay off through `globalConfig`, as D57 keeps them off on
  `/p/hr/`.
- The greeting is read from the transcript (`conversationHandler.getConnectTranscript()`)
  and added to the widget with `appendMessageToTranscript`, then
  `setInterimMessage(undefined)` clears "Thinking...". The marks and hidden lines follow
  the `/p/hr/` manifest (`connect/web/manifest.json`), which the page imports.
- The run log records the chat start's time at the client and inside the function, the
  greeting replay, the first reply to each question, any hidden flow line the widget shows,
  and a contact passing its `expiresAt`.
- Buttons send the `/p/hr/` suggestions through `conversationHandler.sendText`. "New chat"
  calls Touchpoint's `reset`, which asks `details` again; the page passes the last contact
  as `previousContactId`, so the chat start ends it (E9).

### The eight conditions, rechecked on 6 October

Checked against the published 1.0.2 bundle and the repository at ae6b2d8 (6 Oct). The
repository has moved on since 1.0.2 without a new version number; the behaviors below are
the same in both.

| # | Condition (touchpoint-alignment.md) | On 6 October | What T1 does | What T1 checks |
| --- | --- | --- | --- | --- |
| 1 | `chatEndpoint` carries no credential | Still true: `fetchChatDetails` posts with `Content-Type` only. The NDJSON half no longer applies, since D57 answers one JSON body | Uses `details` | The chat start answers 200 and the widget connects |
| 2 | The greeting is spent before the widget connects | Still true: the handler shows only `onMessage` events and never reads the transcript on connect | Replays the greeting from the transcript | The welcome screen shows the greeting once, the input appears, "Thinking..." clears |
| 3 | The platform's CSP blocks Touchpoint's participant host | Not tested by T1: the local page has no CSP. Touchpoint's default host is `participant.connect.us-east-1.api.aws` | Keeps Touchpoint's default host | The widget's participant calls go to the `api.aws` host and work; T4 needs this answer |
| 4 | chatjs's client-side metrics (CSM) cannot be turned off | Still true: `disableCSM` is a `ChatSession.create` argument Touchpoint never passes | Nothing; no CSP to block it | Requests to `ieluqbvv.telemetry.connect.us-east-1.amazonaws.com`; under T4's CSP these become console errors |
| 5 | Hidden flow lines show | Still true: every non-customer `text/plain` message is shown | Logs each hidden line the widget shows | The escalation path ("I want to talk to a person") and its `[flow]` lines |
| 6 | Receipts and typing come back on | Receipts can be turned off through `globalConfig`; typing cannot | Receipts off | `/participant/event` calls carry typing only |
| 7 | No restart before `expiresAt` | Still true | Logs the expiry; "New chat" restarts through `reset` | A restart ends the previous contact (`chat_start` log line names it) |
| 8 | No Markdown or interactive messages from this backend | The chat start declares `text/plain` only, and Touchpoint renders every text message through `marked` and DOMPurify anyway | Nothing | Whether any canvas reply reads differently as Markdown: lists, asterisks, underscores, addresses with `#` |

### Measurements

Each against the `/p/hr/` number from the same hour, since the canvas and the sub-agents
are the same and only the front end differs.

- Chat start at the client: the page's time from the request to the answer, and the
  function's `total_ms`. Reference: L30, a median 2.16 s at the client and 1.99 s inside.
- Page load to greeting on screen: the chat start plus the widget's participant connection
  plus the transcript read.
- First reply per question for the four `/p/hr/` suggestions, five presses each, each on a
  new chat 10 s after the greeting, as L31 measured: "Change my address" a median 6.50 s and
  "Buddy passes" 6.35 s on a contact's first sub-agent question. The page's clock runs from
  `sendText` to the first bot response in Touchpoint's list; the `/p/hr/` harness runs from
  the click to the first reply in the DOM, so a small offset is expected.
- Touchpoint's own cost on the page: bundle size (the published bundle is 3.5 MB before
  minification) and time to mount.

Results go to `docs/latency-log.md` (L48 on) and to a results section at the end of this
file; findings about Touchpoint, chatjs or Connect go to `docs/aws-feedback.md` the day they
are found.

### Running T1

On a machine with the harness session and AWS credentials for the account (the Mac mini
has both since 6 Oct; a session is seeded with guppi-gpt `scripts/okta-harness-signin.py`):

```sh
cd connect/touchpoint
npm ci
npm test
npm run dev        # then open http://127.0.0.1:5173/ in Chrome, DevTools open on Network
```

Each page load starts a real contact on the test employee and costs Connect messages
(0.01 dollars each). The four scenarios at five presses each, on both pages, are about 40
contacts and 300 messages: about 3 dollars, plus the usual AgentCore and Bedrock time per
turn.

### What T1 leaves out

- The `/p/hr/` turn rules (end mark, quiet end, 28 s turn limit, late replies). Touchpoint
  has no turn: it shows each message as it arrives and clears "Thinking..." on the first.
- The report route (`/api/hr/chat/report`). Touchpoint never calls it, so the chat start's
  no-reply alarm does not see widget turns.
- The 1,024 character limit the page applies before sending.
- Reconnect and catch-up: Touchpoint shows "Connection lost. Please try again." and stops.
- Persistent chat (V9).

## T2: Live Sync for the confirmation step

Live Sync lets the canvas drive the page through actions the page declares with a JSON
Schema. Touchpoint opens a receive-only WebSocket to
`ws.nlu.acxd.connect.<region>.amazonaws.com` with the deployment key and the API key in the
query string, and posts page context to `/nlu/c/<deploymentKey>/connect-<lang>/context` with
the API key in an `nlx-api-key` header. The designer SDK in `acxd/` (0.2.0) has `multimodal`
flow nodes and Live Sync script resources (scripts, builds, deployments).

For HR, the obvious use is the propose and commit pair (D7): when a sub-agent proposes a
change, the page shows the address or account on file and the proposed one, and the
employee confirms on the page. Today the confirmation is a text turn (D12).

What it needs:

- A Live Sync node in the canvas and a place for it next to the domain flows, built first
  on the designer's development environment (`node deploy.js --env development`, mock
  sub-agents) so `/p/hr/`'s production canvas is untouched.
- The proposed change as structured data reaching the canvas. Today it is text in the
  sub-agent's A2A reply.
- The deployment key and an API key in the browser. They stay out of the repository; the
  dev server would read them from `~/.config/guppi-connect/` as it reads the test session.
  What the API key allows beyond this deployment's socket and context endpoint is not
  documented, and needs an answer before T4.

Questions for Sam: whether a confirmation on the page is wanted at all, given D12; whether
the canvas may change for an experiment, or a copy of it is used.

## T3: voice

Touchpoint's `voice` and `voiceMini` inputs need a StartWebRTCContact endpoint that returns
the Chime meeting and attendee. That is a new route on `hr-chat-start` (the same Okta check
and hop tokens, StartWebRTCContact in place of StartChatContact) or AWS's sample Lambda;
either puts Lambda code in the request path, which needs Sam's approval (AGENTS.md). The
chat start's greeting wait relies on a chat socket to know the canvas has read the token
attributes before they are blanked; a voice contact needs another signal. `voiceMini` with
`animate` loads a Rive animation from `assets.nlx.ai` and the Rive runtime from unpkg.com
(jsDelivr as a fallback). Not started.

## T4: the widget at /p/hr-widget/

Sam named it on 7 October: `/p/hr-widget/`, with a card on the chat.dengler.io home page,
built on the platform page with a portal and the widget's launcher (D62). How it is put
together:

- guppi-gpt (decision 23) has a new kind of project: a manifest with
  `"surface": "extension"` and an `extension` module under `/projects/<name>/`, and no
  agent. Once the employee is signed in, the page hides its thread, composer, history and
  New chat and hands the screen below its header to the extension (`guppi.onSurface`). The
  header, the project switcher, sign-in and sign-out stay the platform's, and the extension
  calls the chat start with `guppi.token()` on the same origin.
- `/projects.json` lists `hr-widget`, so the home page's project cards and the switcher show
  "HR Assistant (Widget)".
- CloudFront serves `/p/hr-widget/*` with the page's CSP plus `style-src 'unsafe-inline'`
  for the `<style>` element in Touchpoint's shadow root. Connect's participant service is
  set to its amazonaws.com host, which the platform's CSP already allows. chatjs's
  client-side metrics stay blocked.
- The extension (`connect/touchpoint/src/widget.js`, built into `dist/widget/ext.js`) draws a
  stand-in HR portal in plain text: four topic tiles and the four `/p/hr/` suggestions as
  buttons that open the widget and send the question. Touchpoint mounts with its launcher in
  the lower right corner; the chat panel opens over the dimmed page.
- The greeting replay starts from `details`, so it follows every start, including
  Touchpoint's own restart button.
- On that page only, Touchpoint renders replies as Markdown through DOMPurify (approved by
  Sam as an exception to the plain-text rule).

Checked before the deploy with `widget.html`, the built bundle under the same CSP in Chrome
on the Mac mini: no CSP violation; the chat start answered after 4.24 s (3.34 s inside the
function) and the greeting was added 0.75 s later (contact 9e76a0c7); a typed buddy pass
question was answered; Touchpoint's restart button ended that contact and started 6743a7a7,
whose greeting was replayed.

## Records

- D61 (Proposed): the experiment's shape, this plan.
- `docs/aws-feedback.md` C21 to C26: what Touchpoint does that the HR backend has to work
  around, found while building T1.
- Results: the T1 smoke run below. The timed runs have not been made.

## Results

### T1 smoke run, 6 October

One page load in Chrome on the Mac mini, 23:22 to 23:25 EDT (03:22 to 03:25 UTC on
7 October), harness session from a fresh `okta-harness-signin.py` sign-in. Two contacts:
`61e42ee1-d487-4458-850b-6823fe7b29f3` (four questions) and
`a2237456-bcf1-47dd-a36c-c07087552f14` (after "New chat", no questions). The chat start's
`chat_start` lines for both are in `/aws/lambda/hr-chat-start`; neither start logged a
`chat_problem`.

| # | Condition | Result |
| --- | --- | --- |
| 1 | `details` in place of `chatEndpoint` | Works: both starts answered 200 with credentials and the widget connected |
| 2 | Greeting replay | Works: the greeting was in the transcript on the first read after the participant connection, the welcome screen showed it once, the input appeared and "Thinking..." cleared. 1.16 s from the chat start's answer to the greeting on screen, 1.36 s after "New chat" |
| 3 | Participant host | Touchpoint's default `participant.connect.us-east-1.api.aws` served the connection, the transcript, the messages and the typing event |
| 4 | CSM | Not seen: CSM posts from a SharedWorker, which the page's resource timing does not show. Still to verify, with DevTools on the worker |
| 5 | Hidden flow lines | None appeared; the escalation path was not run |
| 6 | Receipts and typing | No receipt events. One `/participant/event` (typing) before the typed message, none before messages sent with the page's buttons |
| 7 | Restart | "New chat" works: Touchpoint's `reset` disconnected the old participant (contact 61e42ee1 ended with `CUSTOMER_DISCONNECT`), then the chat start found it ended (`previous_outcome: ended`) and started a2237456. Expiry was not reached |
| 8 | Markdown | The four replies were plain prose and rendered as plain prose; nothing in them reads differently as Markdown |

Not run: the confirmation's "yes". The session's auto mode refused to send it, since it
commits a write to the test employee's record that was not asked for directly; the
proposal (419 Glendale Ave, Decatur to 25 Ponce de Leon Ave, Atlanta) was left
unconfirmed.

Times, one sample each, so they compare with L30 and L31 only as a sanity check:

| What | Touchpoint page | /p/hr/ reference |
| --- | --- | --- |
| Chat start at the client (inside the function) | 4.45 s (3.57 s) on a new Lambda instance: exchanges 0.85 s, greeting wait 1.52 s. 2.70 s (2.41 s) on the warm instance with cached exchanges: greeting wait 1.23 s, `StopContact` of the old contact beside the start | L30: median 2.16 s (1.99 s) |
| Page load to greeting on screen | 5.61 s | not measured on /p/hr/ |
| "I need to change my home address", the contact's first sub-agent question, about 25 s after the greeting | 8.43 s | L31: median 6.50 s (5.92 to 7.16 s), 10 s after the chat showed |
| The new address (the Profile sub-agent's proposal) | 7.30 s | not measured |
| "How do buddy passes work?", the contact's first Travel question | 6.82 s | L31: median 6.35 s (5.48 to 6.80 s) |
| "How much PTO do I earn per year?" (knowledge base) | 4.33 s | not measured |

The page's clock runs from `sendText` (or the Return key) to the first bot response in
Touchpoint's list. The canvas sends each reply as one message (C19), so the first response
is the whole reply.

### What is left of T1

- The timed runs: the four suggestions, five presses each on a new chat, on this page and
  on /p/hr/ in the same hour (about 3 dollars of Connect messages).
- The escalation path, for condition 5.
- CSM, for condition 4.
- The confirmation's commit, if Sam wants it run.
