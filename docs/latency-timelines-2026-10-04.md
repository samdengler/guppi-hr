# HR assistant latency timelines on /p/hr/, 4 October 2026 (after D57)

Every step of every main path of `chat.dengler.io/p/hr/` as it runs after D57: the chat start at page load, ClarifyFlow, PolicyFlow (first turn and journey follow-up), and the Profile, Travel and Pay sub-agents (first call in a chat and follow-up), each with an owner, a median start and end in ms from the click, and a spread. Nothing was changed or deployed. Measured 4 October 2026, 20:19 to 20:34 UTC: 29 chats, 52 turns, 133 billed Connect messages, no deploys in the window.

## Summary

First words, from the click to the first reply text in the DOM (median, p10 to p90, turns):

| Path | Question | First words | p10 to p90 | Turns |
| --- | --- | --- | --- | --- |
| ClarifyFlow | "Update my information" | 1.13 s | 0.99 to 1.31 s | 5 |
| PolicyFlow, first turn | "PTO policy" | 3.45 s | 3.18 to 3.73 s | 5 |
| PolicyFlow, journey follow-up | "Does unused PTO carry over?" | 1.72 s | 1.57 to 2.10 s | 5 |
| Profile, first call in a chat | "Change my address" and others | 6.19 s | 5.62 to 7.14 s | 17 |
| Profile, follow-up | "And what is my emergency contact?" | 2.75 s | 2.51 to 3.38 s | 6 |
| Travel, first call | "Buddy passes" | 6.88 s | 5.92 to 6.99 s | 5 |
| Travel, follow-up | "Can my parents use them?" | 4.13 s | 3.72 to 4.40 s | 5 |
| Pay, first call | "When was my last paycheck and how much was it?" | 8.62 s | 7.92 and 9.31 s | 2 |
| Pay, follow-up | "And the one before that?" | 2.47 s | 2.31 and 2.62 s | 2 |
| Chat start at page load (warm function) | none | chat ready 3.48 s after navigation | 3.26 to 3.93 s | 28 |

The largest costs, in the order they add to a first answer:

1. **Every snapshot read through the tools gateway takes 1.87 s, about 1.5 s of it in the gateway and Runtime.** The tools gateway sends each tool call to the HR tools runtime on a new runtime session: 21 tool calls landed on 21 different tools runtime microVMs. The first MCP request takes 0.71 s to reach the new session, the gateway's `initialize` and `notifications/initialized` round trips take 0.61 s, and the tool itself 0.17 s. Pay reads two records one after the other and pays it twice (3.9 s).
2. **A chat's first call to a sub-agent starts a new runtime session: 0.93 s against 0.29 s on an existing session.** The designer names the session `{contactId}-{domain}`, so nothing is reused across chats; three pairs of chats 66 s apart each got a new microVM.
3. **The sub-agent's per-session setup is about 1.1 s:** the MCP client start (0.31 s, ours), `initialize`, `initialized` and `tools/list` through the tools gateway (0.37 s), the tools token through Identity (0.22 s), and the first request in a new process (0.21 s).
4. **Models take 0.4 to 2.7 s a turn:** the designer's routing model 0.44 s on every turn except a journey follow-up; a sub-agent's time to first token 0.56 s with 2,000 to 4,400 input tokens; generation 0.22 s for 38 tokens (Profile) and 1.73 s for about 150 tokens (Travel); the PolicyFlow journey 1.49 s first and 0.99 s on a follow-up.
5. **Connect's own path is about 0.6 s of every turn:** 0.15 s for the browser's message to be stamped, 0.26 s to hand it to the designer, 0.12 s to post the reply and 0.09 s to push it to the page.

A first Profile answer (6.19 s): about 5.3 s is inside services (Connect 0.64, designer 0.24, models 1.21, Gateway 0.57, Runtime 2.24, Identity 0.37) and about 0.8 s is our code.

## How it was measured

Headless Playwright on the harness session, one fresh `/p/hr/?ff=debug` page per chat, the first question 10 s after the chat showed and the follow-up 1.5 s after the first turn ended. Order: the four suggestions for five rounds with a typed Pay chat after rounds 2 and 4, then three reuse pairs (a new chat 66 s after the previous answer). All 29 contacts were stopped afterwards. Stack update times were the same before (20:16 UTC) and after (20:34 UTC); every designer event carried one build.

Server sources joined per turn by contact id and time: the chat-start function's lines, X-Ray spans of the token issuer, the designer's step log, the agents and tools gateways' vended logs, the sub-agent and tools runtime logs and log streams, the issuer's log, and Dynatrace spans of the four HR runtimes (Strands `chat` spans with tokens and time to first token, httpx spans for MCP, botocore spans for Identity). Connect's `AbsoluteTime` for each question fell inside the browser's SendMessage request every time, so the laptop's and AWS's clocks agree to well under 0.1 s. Sub-agent spans are joined by `session.id` and time, because a follow-up's MCP spans carry the first request's trace id.

## Owners

| Owner | What it covers |
| --- | --- |
| internet | CloudFront, API Gateway in front of the chat start, the page's network legs |
| connect | Connect's participant service, contact flow, transcript and WebSocket delivery |
| designer | The Agentic CX designer's own work and its HTTP calls out to the gateways |
| model | Bedrock model calls: the routing model, the journey, the sub-agents' Haiku 4.5 |
| gateway | AgentCore Gateway (agents and tools gateways) with Cedar Policy |
| runtime | AgentCore Runtime: session placement, request delivery, instance credentials |
| identity | AgentCore Identity, the token issuer, and Okta at page load |
| ours | The chat start function, the page, the sub-agents' code, the HR tools server |

## Inside the sub-agents

### First call in a chat (Profile, 17 turns)

The sub-agent's request takes 3.83 s (3.62 to 4.34 s).

| Step | Median | p10 to p90 | Owner | Paid once per |
| --- | --- | --- | --- | --- |
| Runtime: new session, delivery to the microVM (before the request) | 933 ms | 586 to 1,310 | runtime | session (chat and domain) |
| A2A handling before the first outbound call | 154 ms | 142 to 178 | ours | process |
| Our code before the workload token | 58 ms | 55 to 75 | ours | process |
| Workload access token | 59 ms | 55 to 67 | identity | session |
| Tools token exchange (issuer handler 20 to 25 ms) | 157 ms | 139 to 172 | identity | session |
| MCP client start (thread, connection) | 310 ms | 279 to 388 | ours | session |
| MCP `initialize`, `notifications/initialized`, `tools/list` | 98, 80, 188 ms | | gateway | session |
| Snapshot read `hr___get_profile` through the tools gateway | 1,865 ms | 1,690 to 2,243 | gateway, runtime | session (kept 5 minutes) |
| (in it) gateway authorizer, Cedar Policy, routing | 100 ms | 88 to 121 | gateway | call |
| (in it) exchange for the runtime token | 152 ms | 145 to 170 | identity | call |
| (in it) first MCP request reaches a new tools runtime session | 708 ms | 593 to 1,036 | runtime | call |
| (in it) gateway's `initialize` and `initialized` round trips | 611 ms | 562 to 662 | runtime | call |
| (in it) the tool (JWT check with JWKS read, DynamoDB) | 168 ms | 157 to 209 | ours | call |
| Agent build (Strands Agent, Bedrock client) | 57 ms | 52 to 71 | ours | call |
| Model: time to first token (about 2,015 input tokens) | 539 ms | 500 to 583 | model | call |
| Model: generation (30 to 38 output tokens) | 224 ms | 195 to 300 | model | call |

Before its model call the sub-agent spends about 2.9 s a session. Every runtime session had its own microVM (24 sessions, 24 microVMs), each already running in the runtime's pool (started 89 s to 40 minutes earlier).

### The tools runtime is a new session for every tool call

Each of the 21 snapshot reads reached a different tools runtime microVM, which served exactly three requests: `initialize`, `notifications/initialized` and the `tools/call`. The first took 744 ms median (557 to 1,391 ms) from the issuer's answer to the tools server; the second and third came about 0.29 s apart. Because each call lands on a new process, the tools server also reads the issuer's keys on every call.

### Follow-up (Profile, 6 turns)

The request takes 1.00 s: delivery on the existing session 289 ms, agent build 49 ms, then the model (588 ms to first token, 333 ms of generation). Nothing else runs. Travel's follow-up adds its search (0.71 s); Pay's follow-up matches Profile's.

### Model calls

| Sub-agent turn | Input tokens | Output tokens | Time to first token | Generation |
| --- | --- | --- | --- | --- |
| Profile first | 2,013 to 2,017 | 30 to 38 | 539 ms | 224 ms |
| Profile follow-up | 2,065 | 37 to 39 | 588 ms | 333 ms |
| Travel first | 2,407 | 151 to 192 | 538 ms | 1,729 ms |
| Travel follow-up | 4,343 to 4,384 | 44 to 53 | 594 ms | 1,227 ms |
| Pay first | 2,158 | 38 to 43 | 562 ms | 608 ms |
| Pay follow-up | 2,205 to 2,210 | 41 | 565 ms | 209 ms |

Every turn made one model call with no tool use. Time to first token is steady (0.49 to 0.66 s); generation speed is not: Profile about 170 tokens a second, Travel's first answer about 90, its follow-up about 40, on the same model through the `us.` cross-region inference profile.

## Chat start

At page load (warm function, 28 page loads): page HTML 96 ms, scripts 139 ms, config 96 ms, the Okta refresh 438 ms, then `POST /api/hr/chat/start` 2.31 s at the browser: front door both ways 73 ms, Okta check under 1 ms, hop token exchanges 218 ms (142 ms inside Identity before the issuer, then four issuer calls of about 22 ms at once), StartChatContact 484 ms, CreateParticipantConnection 216 ms, WebSocket 92 ms, the greeting wait 1.09 s (Connect runs the flow 0.64 s, the designer greets in 18 ms, Connect delivers the greeting 0.41 s later), blanking 146 ms. Then the browser's chatjs connect, socket and transcript, about 0.4 s. The chat is ready 3.48 s after navigation. No start reused cached hop tokens, because each fresh page refreshes its Okta token. One cold start (new function instance and four new issuer instances) took 4.43 s at the browser.

## Runtime sessions and microVMs across chats

- The designer's A2A request sends `X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: {contactId}-{domain}` (`hr.js`); the runtime spans carry the same `session.id`.
- Within a chat the session is reused: every follow-up reached the same microVM; delivery 246 to 303 ms.
- Across chats nothing is reused: three pairs of chats 66 s apart each got a different microVM, and chat B paid the full setup again (sub-agent request 3.63 to 3.99 s against 3.67 to 4.44 s for chat A).
- The pool hides the boot, not the session start: every microVM had been up at least 89 s, yet a new session's first request took 0.56 to 1.49 s to arrive.

## Ranked time sinks

| # | Time sink | Evidence (median) | Fixed by a service | Ours | Levers |
| --- | --- | --- | --- | --- | --- |
| 1 | Snapshot read through the tools gateway to the tools runtime | 1.87 s per tool call; Pay 3.90 s for two in sequence; 21 calls on 21 microVMs | 1.50 s Gateway and Runtime; 0.15 s Identity | 0.17 s tool time; Pay's reads in sequence; reading inside the question since D57 | The gateway's session handling for MCP runtime targets (AWS); a non-Runtime target for the HR tools; parallel Pay reads; a snapshot that outlives the chat; warm-ups |
| 2 | New runtime session for each chat's first call to a sub-agent | 933 ms against 289 ms; none reused across chats | 0.64 s over a warm session plus the 0.29 s every request pays (A21) | The session id `{contactId}-{domain}` ties the session to one chat | A session id per employee and domain; warm-ups; Runtime's session start (AWS) |
| 3 | Model calls | Routing 442 ms on 47 of 52 turns; time to first token 556 ms; generation 0.2 to 1.7 s; journey 1.49 s first, 0.99 s follow-up | Per-token speed, time to first token, routing on every in-flow turn | Prompt size; Travel's answer length | Shorter Travel answers; fewer input tokens; keeping the turn without routing (C15); streaming (C19) |
| 4 | Sub-agent session setup | 1.1 s per session | 0.58 s: three MCP round trips and two Identity calls | 0.52 s: MCP client start, first-request handling | Static tool definitions instead of `tools/list`; setup in parallel with the exchange; a longer-lived process; warm-ups |
| 5 | Connect's own path per turn | about 0.6 s | all Connect | none | AWS (C15, C16) |
| 6 | The designer's HTTP hops per data request | about 0.18 s | all | none | AWS |
| 7 | Travel's search on every question | 0.69 s first, 0.71 s follow-up | about 0.6 s per search | Searching with each question; first passages not kept | Keep the first passages; search in parallel with setup |
| 8 | PolicySearch on a first policy turn | 727 ms | all | none | Fewer results did not help (A20) |
| 9 | Chat start at page load | 2.31 s at the browser, chat ready 3.48 s after navigation | Connect about 2.0 s; Identity 0.2 s warm, 1.2 s cold | The sequence of exchange, start, wait, blank | Hidden behind reading time; matters for a press in the first 3.5 s |
| 10 | Journey turn end on quiet | 0.80 s from first words to done on every PolicyFlow turn | none | The page's quiet window | A turn-complete signal from the designer (C13) |

## Questions this raises

1. Why does the tools gateway put every tool call on a new runtime session of the tools runtime? Does it send a runtime session id to an MCP runtime target, and can it keep one per user, per MCP session or per target?
2. Why does a new session on a pooled, already running microVM take 0.56 to 1.49 s to deliver its first request, against 0.25 to 0.30 s on an existing session?
3. What are the 154 ms before a sub-agent's first outbound call and the 310 ms MCP client start in a new process? Both are in our code with no spans.
4. Why does generation speed differ so much between sub-agents on the same model (170, 90 and 40 tokens a second)?
5. Why does the designer run the routing model on a follow-up inside ProfileFlow, TravelFlow and PayFlow but not inside the PolicyFlow journey?
6. Why does Connect deliver the greeting to the chat-start function's socket 0.41 s after the designer sends it, when a reply reaches the browser 0.21 s after?
7. Without warm-ups (D57), the first sub-agent question in a chat pays sinks 1, 2 and 4: about 3.6 s of 6.2 s for Profile and 5.6 s of 8.6 s for Pay. Which of this work should be paid per chat at all?

The per-path step tables are in `latency-timelines-2026-10-04-tables.md`; the waterfall charts are on the review page (https://claude.ai/artifact/GgBVLV4xTBZyLCR5Rz4D8L).

The ids behind every number (contacts, request ids, trace and span ids, runtime sessions, the log
stream of each microVM, ARNs) are in `latency-timelines-2026-10-04-evidence.md`, and every step of
every turn with its ids in `latency-timelines-2026-10-04-evidence.json`.
