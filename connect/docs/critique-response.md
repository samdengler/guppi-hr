# Response to the critique of the Connect HR super-agent

The critique ("Critique of the Connect HR super-agent", 3 October 2026, reviewed against
guppi-hr `fefcb5d`) found 21 problems. Sam chose to harden the Connect build rather than
change its shape, to warm on engagement, and to have "talk to a person" open a ticket and
end the chat. The work is on the `connect-hardening` branch of guppi-hr and guppi-gpt,
deployed from that branch on 3 October; `main` is the state the critique reviewed.

Every finding was checked against the code or live data before it was fixed. None was
rejected; two were only partly addressed because the full fix is a pilot decision.

## Findings and what changed

| # | Finding | Status | What changed, and the evidence |
| --- | --- | --- | --- |
| 1 | Employee tokens stay on contact records | fixed | The bridge blanks `hrToken` right after the canvas's greeting, on every path, since the designer keeps the value it read at start (C2). Live check: a contact opened at 11:53 UTC holds `cleared`, and the Profile agent still answered with the token. The two warm-only contacts the critique found were cleared, and all 27 test contacts ended. D42 |
| 2 | Every page load held a chat for 25 hours | fixed | Chats start with a 60-minute duration; the bridge ends the contacts it leaves (replaced, failed start, the thread the page left, `previousThreadId`); the page warms on engagement, not page load (D44); an alarm fires at 300 concurrent chats. Sizing quotas for a pilot's shift changes is still to do |
| 3 | A turn with no reply breaks the thread | fixed | The bridge says "No answer came back" instead of an empty run; a contact that never greets is a failed start that ends the contact and releases the claim; the page never stores an empty assistant turn and offers Retry |
| 4 | Replies cross turns | fixed, except journeys | Every canvas reply node ends its text with an invisible end mark and the bridge ends the turn on it (no extra billed message); transcript items older than the run's own message are not shown; relayed items are saved in a `finally`; a socket that fails mid-turn falls back to polling. A generative journey's own answer still ends on 0.8 s of silence (it cannot be followed by a node); the journey is told to write nothing before a hand-off. D42 |
| 5 | Prompts and tool data in Dynatrace | fixed | `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_unredacted_attributes=` on every Strands runtime; checked in Dynatrace: span events read `[REDACTED]`, token counts remain. Retention and processing terms with the trace backend are Sam's call |
| 6 | Escalation went to an unstaffed queue | fixed | EscalationFlow opens an HR ticket through the tools gateway, gives its id, and ends the conversation; the bridge ends the thread on Connect's end event. D43 |
| 7 | The bridge rebuilds a chat client from heuristics | kept, by decision | The shape stays (Sam: harden). The heuristics shrank: a turn ends on the canvas's line or Connect's event, not on silence or English text, except journey answers |
| 8 | A token refresh restarts the canvas | partly | The bridge ends the old contact and tells the employee the conversation restarted. Deferring the rotation while a change is pending was not built; the pilot answer is a token exchange or proxy (D20, D42) |
| 9 | Any `ValidationException` meant a gone contact | fixed | Messages over 1,024 characters are answered without sending; only `AccessDeniedException` counts as gone, and a fresh connection on the participant token is tried before a new contact |
| 10 | Participant tokens in plain DynamoDB | fixed | The session table is encrypted with the stack's own KMS key (checked: `SSEType KMS`); contacts last an hour. CloudTrail data events on the table were not added |
| 11 | Latency claims were single runs | fixed | `connect/scripts/latency_bench.py` runs 10 rounds per configuration on the client clock, with medians, p90 and trace ids; A7 was remeasured on one clock (0.47 s through the edge, 0.33 s direct) |
| 12 | The routing eval scored failures as correct | partly | Failure and help lines now score as `failed`; escalation is detected by the ticket line; `--repeat` runs the corpus several times. A held-out set and a production run with a test employee are not built |
| 13 | Tests could not fail like Connect and DynamoDB | fixed | A store that copies on read and write, Connect fakes that honor sort order and page size, tests for the critique's failure paths (no greeting, stale items, socket failure, retired token, ended contact, long message, restart, canvas error), concurrent MCP leases, and CDK tests for GuppiConnect. No tests at real timing |
| 14 | Diagnosing a bad answer took four systems | mostly | The bridge's span has `connect.contact_id`; the sub-agent's A2A span has `hr.thread_id` and the trace id is in its record, so one attribute joins the two traces (checked in Dynatrace). Alarms on bridge problems, failed runs and concurrent chats go to an SNS topic (email when `GUPPI_ALARM_EMAIL` is set at deploy). Canvas errors show and alarm. The page no longer says it logs. Runtime log groups keep 30 days. No conversation record is kept |
| 15 | Deploys depended on local files | fixed | The contact flow id, canvas alias and gateway and mock URLs are in SSM, written by the stacks and `contact_flow.py`; `connect/acxd/domains.json` is the one domain list; `connect/scripts/deploy-all.sh` runs the order. A drift check for the designer resources was not built |
| 16 | D39 and D41 left out costs | fixed | D39 revised, D41 narrowed, D42 to D44 added |
| 17 | HR gateways had no rate limits | partly | Per-user limits on the agents gateway (120 a minute, 10 connections) and the tools gateway (240, 20). An HR audience or scope, and offboarding through the airline's identity provider, are pilot work |
| 18 | aws-feedback entries misstated the POC's part | fixed | C3, C4, C13, TC1, TC6, TC7 corrected; A7 remeasured; C14 to verify |
| 19 | Diagnostic probes live in production | fixed | Removed from both canvas applications |
| 20 | Confirmation took any reply starting with yes | partly | Only a bare confirmation commits; "yes, but make it Apt 4B" goes back to the sub-agent without the pending change. A re-proposal returned on the commit branch is still not routed to the confirm step |
| 21 | Smaller races | mostly | The start claim lasts 45 s; the transcript read takes the newest 100 items; MCP session opening is locked per key; idle sessions close at any lease. The canvas still reuses the conversation id as the A2A `messageId` (no designer variable for a per-call id was verified) |

## Latency after the hardening

Measured with the harness, 10 rounds each, on the client (`connect/docs/latency-plan.md`,
`docs/latency-log.md`):

| Question | Before the snapshot (L15, L16) | After |
| --- | --- | --- |
| New chat: home address | 4.79 s | 2.63 s |
| Follow-up: emergency contact | 4.79 s | 2.64 s |
| New chat: buddy passes | 5.71 s | 4.27 s |
| Follow-up: can my parents use them | 7.12 s | 4.13 s |

A new chat without a warm start took 9.05 s. A turn finishes 0.1 to 0.2 s after its reply.
Calling the bridge's runtime directly instead of through the edge gateway saved nothing
measurable (L19), so that route was dropped.

## Connect cost

Connect bills chat by the message, in both directions. The hardening keeps the count down:
the end-of-turn and closed signals ride on the reply as one invisible character (L20), so
a turn is the employee's message and one reply; the contact flow no longer adds its own
goodbye line; the warm start opens a contact only when the employee engages (D44), and the
bridge ends contacts it leaves, so none sits open for 25 hours. Each new chat still pays
for the canvas's greeting, which the bridge waits for and hides.

Testing was kept to a budget: the harness ran 10 rounds per configuration for the
baseline and the snapshot, then 5 for checks, and the 60-chat routing eval was not rerun,
since nothing in this work changed routing.

## Seen while testing

- A policy question asked after a domain question stayed with that domain's sub-agent,
  which declined it ("How much PTO do I earn per year?" after a profile question). The
  domain flows treated every PolicyFlow capture as "unrecognized", because the designer
  files unmatched input under PolicyFlow too. Changed (D45): a capture with an intent
  (`System.capturedIntent` not `NLX.Unknown`) now leaves the domain flow for PolicyFlow.
  Checked live on 3 Oct: the PTO question got the policy answer, while "And what is my
  emergency contact?" and "Can my parents use them?" stayed with their sub-agents and
  "Thanks, that works" reached GoodbyeFlow.
- "thanks, that's all" in a new conversation went to the journey instead of GoodbyeFlow
  once (routing varies run to run, C12).

## What is left for a pilot

- A token exchange or server-side proxy so no bearer token reaches the designer (D20).
- A turn-complete signal from the designer for generative journeys (C13).
- Quota sizing for shift-change peaks: concurrent chats, `StartChatContact` rate,
  AgentCore sessions.
- A held-out routing eval run against the production application.
- An HR audience or scope on tokens, and offboarding through the identity provider.
- The critique's open questions for Sam, unchanged: whether the airline's HR desk runs on
  Connect, whether voice or business-owned flows are requirements, and trace retention.
