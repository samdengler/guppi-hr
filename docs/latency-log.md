# Latency log

Every technique tried to make the HR projects on chat.dengler.io answer sooner, with what
it did when measured. One row per technique, in the order they were tried. A technique
that is reverted or made no difference keeps its row with that status, so the log also
says what not to try again. The plan behind the current round is
`connect/docs/latency-plan.md`; service behavior found on the way goes to
`docs/aws-feedback.md`.

Measurements use the same turns each time on `/p/hr/`: a new chat with "What is my home
address on file?", "And what is my emergency contact?" in the same chat, and a new chat
with "How many buddy passes do I get?". The numbers are the bridge's `first_delta_ms` and
`total_ms` run lines and the spans in Dynatrace (`zfr04910`).

Status values: **kept** (deployed and measured), **built** (deployed, not yet measured),
**dropped** (tried and reverted), **declined** (not built, by decision), **idea** (not built).

## Techniques

| # | Date | Technique | Hop | Measured effect | Status | Where |
| --- | --- | --- | --- | --- | --- | --- |
| L1 | 3 Oct | Keep each sub-agent's MCP session to the tools gateway open between requests, per caller and thread, with its `tools/list` | sub-agent to tools gateway | Follow-up's Profile agent 3.15 s to 2.44 s: the session setup and `tools/list` (0.2 to 0.55 s) are gone on a reused session, and the tool call went from 1.17 s to 0.97 s | kept | D38, `agent/src/hr_agent/agents/mcp_sessions.py` |
| L2 | 3 Oct | End the bridge's turn 0.8 s after a reply instead of after 2.5 s of quiet; 3 s after the canvas's hand-off line, which the escalation notice follows | bridge transcript polling | Follow-up's turn finished 8.6 s to 5.3 s; a turn now ends about 1.2 s after its last reply instead of 3 s | kept | change 2, `connect/agent/src/connect_bridge/turn.py` |
| L3 | 3 Oct | Close the customer WebSocket on Connect's subscribe acknowledgement instead of after a fixed 1.5 s | contact start | About 1.5 s on a new chat; with L4 and L5, a new chat's first reply 12.1 s to 8.8 s | kept | change 3 |
| L4 | 3 Oct | Send the first message as soon as the canvas's greeting arrives instead of after 1.5 s of quiet | contact start | About 1.5 s on a new chat (see L3) | kept | change 3 |
| L5 | 3 Oct | Poll the transcript every 0.3 s instead of every 0.6 s | reply relay | About 0.15 s per reply on average (see L3) | kept | part of change 5 |
| L6 | 3 Oct | Send the first message without waiting for the canvas's greeting | contact start | The canvas never answered: the greeting came 1.5 s after the connect and the message got no reply in 15 s | dropped | change 3 |
| L7 | 3 Oct | Warm start: when a new thread starts, the page sends a run with no messages on the thread's runtime session, and the bridge starts the Connect contact and waits out the greeting then | bridge microVM and contact start | The contact start (2.2 to 2.8 s) left the first message's path: a new chat's first reply at the bridge 8.8 s to 6.9 s (address) and 9.2 s to 7.3 s (buddy passes). A message sent 1.1 s after "New chat" waited for the warm start's contact instead of opening a second one | kept | D39, change 4; guppi-gpt kit-v0.3.0 |
| L8 | 3 Oct | Sub-agents call the tools runtime directly instead of through the tools gateway | sub-agent to tools | Not built; would save about 0.8 to 1.4 s per tool call (aws-feedback A6) | declined | D40, change 9 |
| L9 | 3 Oct | Prompt caching for the sub-agents' system prompt and tools on Bedrock | sub-agent model calls | Not possible: Haiku 4.5 on Bedrock caches a prefix of 4,096 tokens or more, and the sub-agents' calls send 1,048 to 3,009 input tokens (`chat` spans, 05:01 to 05:04 UTC); a cache point below the minimum is ignored | dropped | change 6 |
| L10 | 3 Oct | A faster model for the canvas's routing step | canvas routing | Not needed: the designer's log puts the routing model at 0.43 to 0.47 s (`ModelStart` to `ModelEnd`); the rest of the 1.2 to 2.2 s is Connect handing the message to the designer (0.32 s) and the agents gateway reaching the sub-agent (0.4 s, 1.3 s on a contact's first call) | dropped | change 7 |
| L11 | 3 Oct | Warm the sub-agents during the warm start: an A2A warm message per sub-agent on the canvas's runtime session and thread, which opens the runtime session and the sub-agent's MCP session without a model call | agents gateway and sub-agent | A new chat's first reply at the bridge 6.9 s to 5.06 s (address, 05:16:24 UTC): `SendMessage` to the Profile agent 2.19 s to 1.42 s, and the Profile agent 4.07 s to 2.83 s with no `tools/list` (first model call 0.08 s after the request, against 0.84 s). The warm start itself grew from about 2.3 s to 4.8 s, still inside a pause for typing | kept | D41, change 10 |
| L12 | 3 Oct | Relay replies as Connect pushes them: each run opens a customer WebSocket from a fresh `CreateParticipantConnection` on the stored participant token, right after its send, and keeps the new connection token; polling stays as the fallback | reply relay | From the designer's `NluResponded` to the bridge's first delta: 0.35 s and 0.55 s polling (05:01:57, 05:02:23 UTC) to 0.22 s and 0.19 s pushed (05:23:58, 05:24:10). What is left is Connect's own delivery to the socket. A follow-up's first reply at the bridge was 4.36 s | kept | change 5 |
| L13 | 3 Oct | Warm the sub-agents as soon as `StartChatContact` returns the contact id, during the greeting wait, instead of after the contact is ready | warm start | The warm start 5.46 s (05:32:09 UTC) to 2.84 s (05:34:39) with all three sub-agents warmed inside it; from a page load, the contact and the sub-agents are ready about 5 s after the page starts (token refresh 0.6 to 0.9 s, the hop to a new runtime session about 1 s, the warm start 2.8 s) | kept | D41 |
| L14 | 3 Oct | Keep the page's runtime session id across reloads in the tab, so the first request after a reload reaches a running bridge session (about 0.5 s) instead of a new one (about 1.0 s) | page to bridge | Not built: one session id per page load is guppi-gpt's design (`docs/guppigpt-design.html`, `docs/proposals/traceability.md`), and the saving is one request per reload | idea | guppi-gpt platform |
| L15 | 3 Oct | Read the employee's record (profile; direct deposit and pay statements) through the tools gateway at the warm start and put it in the sub-agent's prompt, so a read is one model call instead of two with a tool call between; cached per conversation for five minutes, dropped after a commit | sub-agent | To be measured with the harness; expected about 1.8 s off a profile or pay read | built | `agent/src/hr_agent/agents/snapshot.py` |
| L16 | 3 Oct | Travel searches the policy documents with the question before its first model call, and the passages go in the prompt | sub-agent | To be measured; expected about 0.7 to 0.9 s off a travel answer (one model call saved, the search still paid) | built | `snapshot.py` |
| L17 | 3 Oct | End a turn on the canvas's hidden `[flow] end` line instead of 0.8 s of silence (D42) | bridge turn end | First smoke run: the turn finished 0.14 s and 0.15 s after its reply, against 0.8 to 1.2 s; correctness was the reason (finding 4) | kept | D42 |
| L18 | 3 Oct | Warm start on engagement (focus, keystroke, suggestion) instead of page load (D44) | contact start | Not a saving: a cost for an employee who clicks a suggestion at once, who now waits for part of the warm start; it ends the contacts and tokens readers held | kept | D44 |
| L19 | 3 Oct | Call the bridge's runtime directly (`bedrock-agentcore` `InvokeAgentRuntime` with the employee's JWT) instead of through CloudFront and the platform's edge gateway, which would mean a CloudFront route around the gateway's rate limits and WAF | page to bridge | No difference over 10 rounds each: new chat median 5.36 s direct against 5.34 s through the edge, follow-ups 5.83 s against 5.96 s (`direct-warm`, `hardened-warm`) | dropped | harness, 3 Oct 12:05 UTC |

## Time found but not yet cut

Where a turn's time went on 3 October after L1 to L7 (05:01 to 05:04 UTC):

| Hop | New chat, first message | Follow-up |
| --- | --- | --- |
| Page to the bridge's handler (CloudFront, edge gateway, runtime; aws-feedback A7) | 0.5 s | 0.6 s |
| Bridge reads its contact and sends (`SendMessage`) | 0.2 s | 0.15 s |
| Connect hands the message to the designer | 0.33 s | 0.32 s |
| Canvas routing model (Connect's NLU) | 0.43 s | 0.47 s |
| Agents gateway to the sub-agent (C14) | 1.31 s | 0.40 s |
| Sub-agent (two model calls and one tool or search call) | 4.1 to 4.5 s | 2.8 s |
| Canvas relays the reply to the bridge (0.2 s after L12) | 0.45 to 0.7 s | 0.65 s |

- The tools gateway adds about 0.8 s to every tool call on a warm target, because it
  runs an MCP `initialize` and `notifications/initialized` on the target before each call
  (aws-feedback A6). Skipping the gateway was declined (D40); the ask is with the AWS team.
- Canvas routing and the agents gateway take about 1.9 s before a sub-agent starts; change
  7 splits that time before choosing anything.
