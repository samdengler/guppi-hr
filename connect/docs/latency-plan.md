# Latency plan for /p/hr/

Status: change 4 built and measured (D39, results below); changes 6 and 7 measured with nothing to build (`docs/latency-log.md`, L9 and L10); change 10 built and measured (D41): a new chat's first reply at the bridge is 5.06 s, from 8.8 s before change 4. Change 5 built and measured: replies arrive over a WebSocket the run opens after its send, 0.2 s after the canvas answers instead of 0.35 to 0.55 s. Changes 1 to 3 built and measured on 3
October 2026 (results below): a follow-up's first reply went from 5.8 s to 4.1 s and a new
chat's from 12.1 s to 8.8 s. Two of them changed on the way, after a test on the
development flow:

- Change 2 needs no canvas marker. Each canvas turn arrives as one message, and a
  generative journey (PolicyFlow) cannot be followed by a marker node anyway, so the bridge
  ends a turn 0.8 s after a reply, and 3 s after the canvas's hand-off line, since the
  contact flow's escalation notice follows it by about 1.5 s.
- Change 3 keeps waiting for the greeting. A message sent before the canvas greets is
  never answered (tried: the greeting came 1.5 s after the connect, the message got no
  reply in 15 s). What goes is the fixed 1.5 s WebSocket wait (the socket closes on
  Connect's acknowledgement) and the 1.5 s of quiet after the greeting. Polling also went
  from every 0.6 s to every 0.3 s, a small part of change 5.

`/p/hr/` is the Connect version since D37. A message travels page → bridge → Connect chat
→ the designer's canvas → agents gateway → a sub-agent (Strands, Haiku 4.5) → tools
gateway → the HR tools server, and the reply comes back through the canvas and the
bridge's transcript polling. Every hop below was measured on 3 October with the bridge's
run lines (CloudWatch), the designer's `QueryLogs`, and spans in Dynatrace (`zfr04910`,
D36), over five turns.

## Where the time goes

| Turn | First reply on the page | Turn finished |
| --- | --- | --- |
| First message of a new chat (4 turns) | 11.6 to 12.1 s | 14.6 to 15.0 s |
| A second message in the same chat | 5.8 s | 8.6 s |

The second message, "And what is my emergency contact?" (04:18:39 UTC), broken down:

| Step | Time | Source |
| --- | --- | --- |
| Canvas routing and the agents gateway, before the sub-agent starts | 1.9 s | bridge run start to the Profile agent's `POST /` |
| Profile agent: a new MCP session to the tools gateway and `tools/list` | 0.55 s | `mcp.session`, `mcp tools/list` |
| Profile agent: Haiku decides to call `get_profile` | 0.74 s | `chat` span |
| Profile agent: the tool call | 1.17 s, of which the tools server 0.17 s | `mcp tools/call` against the server span |
| Profile agent: Haiku writes the answer | 0.67 s | `chat` span |
| Canvas reply and the bridge's polling (every 0.6 s) | 0.7 s | Profile end to the bridge's first reply |
| The bridge waits for 2.5 s of quiet before ending the turn | 3.0 s | first reply to run end |

A new chat adds about 6.2 s before the canvas sees the message: a new bridge microVM (one
runtime session per thread), `StartChatContact`, the participant connection, a fixed
1.5 s WebSocket wait, and waiting for the canvas's greeting plus 1.5 s of quiet so the
greeting is not shown.

The 1 s inside the tool call looked like a cold start: the tools runtime opened a new
runtime session, so a new microVM, at each tool call (log streams created at 04:18:26.06
and 04:18:43.33), and the sub-agent opened a new MCP session for every request
(`docs/aws-feedback.md`, A5). Change 1 showed that this is only part of it; see the
results.

Every technique tried, with its measured effect, is also in `docs/latency-log.md`.

## Results of changes 1 to 3

Measured at 04:40 UTC on 3 October with the same three turns, after deploying both stacks.

| Turn | First reply, before | First reply, after | Turn finished, before | Turn finished, after |
| --- | --- | --- | --- | --- |
| New chat, "What is my home address on file?" | 12.1 s | 8.8 s | 15.0 s | 10.2 s |
| Same chat, "And what is my emergency contact?" | 5.8 s | 4.1 s | 8.6 s | 5.3 s |
| New chat, "How many buddy passes do I get?" | 12.0 s | 9.2 s | 15.0 s | 10.5 s |

The follow-up's Profile agent took 2.44 s against 3.15 s: no session setup and no
`tools/list` (the session was reused), Haiku 0.76 s, the tool call 0.97 s, Haiku 0.62 s.

The tool call still spends 0.8 s outside the tools server (965 ms at the client, 157 ms in
the server), on a microVM that was already running. The tools server's log shows why: the
gateway opens a new MCP session on the target for every `tools/call`, with an
`initialize` and a `notifications/initialized` before the call, on a new connection. The
target answered `initialize` 0.54 s after the client sent the call, and each handshake
step took about 0.12 s (`docs/aws-feedback.md`, A6). Keeping the client's session removed
what the client controls; the rest is inside the gateway, and change 9 below is the only
way around it in this design.

## Results of change 4

Measured at 05:01 to 05:04 UTC on 3 October, with the page's network timings beside the
bridge's run lines.

| Turn | First reply at the bridge, before | After | Warm start |
| --- | --- | --- | --- |
| New chat, "What is my home address on file?" | 8.8 s | 6.9 s | 3.6 s, at page load |
| Same chat, "And what is my emergency contact?" | 4.1 s | 4.9 s | none |
| New chat, "How many buddy passes do I get?" | 9.2 s | 7.3 s | 2.3 s, at "New chat" |
| New chat, a message 1.1 s after "New chat" | | 6.7 s, waited for the warm start's contact | 2.1 s |

The contact start is off the first message's path. The follow-up's difference is the
canvas and the sub-agent varying run to run (the Profile agent took 2.8 s against 2.4 s).

The page's own numbers show one more hop: the bridge's handler starts 0.5 to 0.6 s after
the page sends, through CloudFront, the edge gateway and the runtime
(`docs/aws-feedback.md`, A7). The first reply on the page is that much later than the
bridge's `first_delta_ms`, and was before change 4 as well. The full split per hop is in
`docs/latency-log.md`.

## Targets

Median first reply: 3 s for a follow-up and 5 s for a new chat; a turn ends within 1 s
of its last reply.

## Changes, in the order to make them

| # | Change | Where | Saves | Effort |
| --- | --- | --- | --- | --- |
| 1 | **Keep the tools runtime warm.** Each sub-agent keeps one MCP session to the tools gateway open per process (or per conversation) and caches `tools/list`, instead of a new session per request | guppi-hr `agent/` (sub-agents; `hr-diy`'s orchestrator gets it too) | about 1.4 s per sub-agent call (the cold start and the session setup) | small |
| 2 | **End the turn on a marker, not on silence.** Every canvas reply path ends with a `[flow] end` message, which the bridge already hides; the bridge ends the run when it sees it, and keeps the quiet window only as a fallback | `acxd/hr.js` and `agent/` | 3.0 s of "working" after each reply; the next message can go at once | medium |
| 3 | **Start a contact without fixed waits.** Close the WebSocket as soon as it connects instead of after 1.5 s, and stop waiting for the greeting: ignore transcript items older than the bridge's own `SendMessage` | `agent/src/connect_bridge/turn.py` | about 3 s on a new chat | small |
| 4 | **Open the contact before the first message.** When a new thread starts, the page sends a warm start (a run with no messages) on the thread's runtime session, and the bridge starts the contact and its microVM then. Built as a platform capability, `warm-start`, instead of an `hr` extension, since only the page knows the runtime session id (D39) | guppi-gpt page and kit (kit-v0.3.0), `connect/web/manifest.json` and `agent/` | the rest of a new chat's start, about 3 s, hidden behind the visitor's typing | medium |
| 5 | **Push instead of polling.** Keep the participant WebSocket open for the length of a run and relay each message as it arrives | `agent/` | up to 0.6 s per reply, about 0.3 s on average | medium |
| 6 | **Prompt caching for the sub-agents.** Cache the system prompt and tool definitions (about 1,700 tokens) on Bedrock for Haiku 4.5 | guppi-hr `agent/` | about 0.1 to 0.3 s per model call, two calls per turn | small |
| 7 | **Measure the canvas's routing step.** Split the 1.9 s between the canvas's routing model and the agents gateway with `QueryLogs` node timings; then pick the routing model per node (Nova Micro or Haiku) on the eval's accuracy | `acxd/` | to be measured | small to measure |
| 8 | **Optional, an architecture choice: reads without a sub-agent.** For read-only questions (an address, pay statements) the canvas calls the HR tool directly over HTTP, as PolicySearch already does, and phrases the answer itself; sub-agents keep changes and confirmation | `acxd/hr.js` | about 2 s on a read (two model calls and a hop) | medium; moves logic into the canvas |
| 9 | **Declined (D40): sub-agents call the tools runtime directly.** Each sub-agent keeps an MCP session to the tools runtime's own endpoint instead of the tools gateway, for the `hr` tools; the gateway stays for `docs___Retrieve` | guppi-hr `agent/` and the HR stack | about 0.6 to 0.8 s per tool call (A6), to be confirmed with one direct call | medium; gives up the gateway's single tool list and its policy for those tools |
| 10 | **Warm the sub-agents too.** The warm start sends each sub-agent an A2A warm message on the canvas's runtime session and thread, so a contact's first delegation finds the runtime session and the MCP session open (D41). Found by change 7's designer log | `agent/` (sub-agents), the HR stack, `connect/agent/` and the bridge stack | about 1.7 s on a new chat's first reply | small |

Changes 1 to 3 are code in this repository with no new services; the forecast was a
follow-up at about 4 s and a new chat at about 7 s, and the measured result is 4.1 s and
8.8 s (the new chat kept its greeting wait, see the status). Change 4 brings a new chat close to
a follow-up. Changes 8 and 9 change the design and each gets its own decision; Sam declined 9 (D40), so tool calls stay on the gateway.

## How each change is checked

A baseline before the first change and the same turns after each: a new chat with "What
is my home address on file?", then "And what is my emergency contact?" in the same chat,
and a new chat with "How many buddy passes do I get?". For each turn, the bridge's
`first_delta_ms` and `total_ms` (the `guppi-connect-bridge` dashboard) and the sub-agent's
spans in Dynatrace. A Dynatrace notebook with these queries replaces the hand work.

## What this plan does not change

The canvas's routing design, the confirmation step, the sub-agents' prompts and models,
and `hr-diy`, except where change 1 or 6 lands in the shared agent code.
