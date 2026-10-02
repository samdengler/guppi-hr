# Spike report: Agentic CX designer as the HR super-agent

Overnight 1 to 2 October 2026. Branch `spike/acxd`, local commits only.

The Agentic CX designer can replace hr-super-agent's Strands orchestrator while the
Profile, Pay and Travel A2A sub-agents and the HR tools stay as built. Built entirely
from code through the designer SDK, the canvas routes, delegates over A2A with the
employee's token in the Authorization header, confirms writes in a fixed step, and
escalates to a Connect queue. Every scenario passed over real Connect chat against mock
sub-agents; the routing eval scored 55 of 60. What is not yet proven: a real sub-agent
turn with a real employee token, and the designer's own MCP data request type.

## Answers to the open questions in the design doc

| Question | Answer | Evidence |
| --- | --- | --- |
| Can the employee's token reach a data request's headers? | Yes. A Connect contact attribute becomes a context variable, and `Authorization: Bearer {hrToken:NLX.Context}` declared on the data request arrives at the endpoint | Echo endpoint saw `Bearer guppi-dummy-…` on every call (ProbeStatic, ProbeDynamic); the real agents and tools gateways answered 401 to the dummy, so the header reached them |
| Can the canvas send hr-super-agent's A2A `message/send`? | Yes, as a JSON string template payload. Nested placeholders are filled and quotes are escaped correctly | Mock received a well-formed JSON-RPC body with text, contextId, history and pendingAction |
| Can the canvas read a nested A2A reply? | Yes, with dot paths: `{DelegateProfile.result.parts.0.text:NLX.Variable}`, `...parts.1.data.pendingAction.proposalId` | ReplyProbe flow; every domain flow uses it |
| Does the canvas keep the identity chain? | Yes for the A2A and HTTP paths: one token from the contact flow to the gateways, `X-Hr-User-Token` and `X-Hr-Thread-Id` as D19 expects | Mock and gateway logs |
| Can routing, stickiness and confirmation be fixed canvas steps? | Yes. Intent capture plus redirects routes; a domain flow keeps follow-ups; only the confirmation step's "yes" branch sends the pending change | Scenarios 1 to 6 below |
| Data request timeout | A node's timeout caps at 30,000 ms (SDK model). The orchestrator allows 120 s today | `FlowNodeMetadata.timeout` `@range(max: 30000)` |
| Can the canvas send recent turns? | Yes, from context variables set at each reply: the last utterance and the last reply | Mock log shows `metadata.history` filled from the second turn on |
| Which models? | Nova Micro, Nova 2 Lite, Claude Haiku 4.5, Claude Sonnet 5, chosen per node | SDK `GenerativeModelType`; PolicyFlow runs on Sonnet 5 |
| Is there an API? | Yes. `amazon-connect-acxd-sdk` 0.2.0 covers applications, flows, data requests, builds, deployments and logs. Only the first programmatic user and its key need the console | This whole spike was deployed from `acxd/deploy.js` |

The design doc's claims of "console only" and "no published model list" were wrong;
both docs need correcting (done the same night).

## What was built

| Resource | Id or name |
| --- | --- |
| Connect Customer instance | `guppi-connect` (`5665011a-f5fa-40e3-92d0-85ff625d10f6`), no phone number |
| Designer workspace | `f77cf767-cecf-407a-9671-02b07d536b0f` |
| Designer API user | `guppi-connect-deploy`, account administrator; key in `~/.config/guppi-connect/acxd_api_key` |
| Application, development | `hr-assistant` (`d452f737-…`), data requests point at the spike's mock sub-agents |
| Application, production | `hr-assistant-production` (`ebbd8aef-…`), data requests point at hr-super-agent's agents and tools gateways |
| Contact flows | `guppi-connect-hr-assistant` (development) and `guppi-connect-hr-assistant-production` |
| Mock and echo endpoint | Stack `GuppiConnect`: one Lambda behind a function URL, `/echo` and `/a2a/<domain>/invocations` |
| Connect user | Sam's Admin user, created so the designer would show Admin Hub |

Canvas (acxd/hr.js): WelcomeFlow, ClarifyFlow, ProfileFlow, PayFlow, TravelFlow,
PolicyFlow, GoodbyeFlow, EscalationFlow. Diagnostics (acxd/probes.js): HeaderProbe and
ReplyProbe and McpProbe, reached by saying "run the header probe", "run the reply probe"
or "run the mcp probe".

## Scenarios over Connect chat (mock sub-agents)

| Scenario | Turns | Result |
| --- | --- | --- |
| Confirmation and stickiness | address change, "yes", "what about my emergency contact?" | Proposal, commit on "yes" with the pending change sent only then, follow-up stayed in Profile with history |
| Disambiguation | "I need to update my information", "profile" | One clarifying question, then Profile |
| Topic shift and escalation | buddy passes, "I need to talk to someone" | Travel, then EscalationFlow; the contact flow's Escalation branch transferred to BasicQueue |
| Policy question | bereavement leave | PolicySearch reached the tools gateway (401 with the dummy token); the journey offered a ticket |
| Topic shift between domains and decline | buddy passes, address change, "no" | Travel, then Profile proposed, then "Okay, I won't make that change." |
| Header probe | "run the header probe", any message | Authorization present on both declared-header probes, absent on node-only headers |

## Routing eval

hr-super-agent's 60 labeled utterances, each run as a Connect chat
(`scripts/route_eval.py`), scored as `evals/route.py` scores them.

| Run | Overall | Weighted | What changed before it |
| --- | --- | --- | --- |
| 1 | 45 of 60 | 74% | First canvas; scorer had a bug that counted the clarifying question as Profile |
| 2 | 50 of 60 | 85% | Routing text from hr-super-agent's domain descriptions; bare-refusal regex; probes untrained; scorer fixed |
| Final | 55 of 60 | 84 of 91 (92%) | WelcomeFlow small talk, GoodbyeFlow, no topic shift from a pending change; replay confirms a committed change |

Tuning used the same 60 utterances, as hr-super-agent's D28 did; neither number is
held out. The five misses in the final run:

- u55 "I need to talk to someone" and u59 "Who do I contact about a harassment concern?"
  went to EscalationFlow. The labels expect an answer in place; a person is arguably the
  better outcome for both.
- u09 "What's my employee ID?" went to PolicyFlow instead of Profile.
- u45 "Something is wrong with my account": PolicyFlow's journey asked its own
  clarifying question instead of ClarifyFlow.
- u60 "I want to update my bank and my address" (two domains) went to Pay.

No utterance meant for one write domain reached the other.

## Platform facts learned live

1. Headers set only on a flow node's data request are not sent. Declare them on the data
   request (`webhook.environments.*.headers`), static with a placeholder or `dynamic: true`.
2. A field-map payload fills only top-level placeholders and over-escapes quotes. A JSON
   string payload fills every placeholder and escapes correctly.
3. `{System.conversationId}` is the Connect contact id.
4. A `user_input` node with an unconditional edge does not wait for input; every edge
   needs a condition.
5. A second `user_input` reached in the same turn in the same flow re-reads that turn's
   utterance. A redirect to the flow's own listen node ends the turn cleanly.
6. An utterance such as "Hi there" can be captured as WelcomeFlow itself; a redirect to it
   lands on a silent node and fails the turn with `NoMessages`.
7. One deployment per application (`LimitExceededException` on a second); each
   environment is its own application over the same flows.
8. `GetApplicationDeployment.deploymentAlias` is the Agentic CX block's Alias, so the
   contact flow can be bound from code. AWS's AICC sample had to read it from a console
   endpoint before SDK 0.2.0.
9. Updating a deployment in place works for an en-US application and keeps the alias.
10. The Agentic CX block needs `SpeechRecognitionConfiguration` and
    `AudioFillerConfiguration` in its parameters, even for chat; without them the
    contact flow import fails.
11. The designer's MCP data request, used as a journey tool, fails every call with "data
    request could not be prepared" before any HTTP request, whether exposed as one tool
    or one tool per MCP tool. Called from a fixed data_request node (McpProbe, "run the mcp
    probe") it takes the failure edge with no request logged at all. A plain HTTP data
    request that posts JSON-RPC `tools/call` to the tools gateway reaches it. The likely
    missing step is the console's Sync, which the SDK has no call for.
12. Canvas overhead per delegated turn is about 0.5 to 0.7 s on top of the sub-agent
    (designer logs: `NluResponded.responseTime` 548 to 682 ms with a 30 to 50 ms mock).
13. `QueryLogs` returns node-level events (traversals, conditions, data request status,
    journey tool calls) one to two minutes after a turn; `acxd/logs.js` prints them.

## What is left for Sam

1. Copy a refresh token from a signed-in hr.dengler.io session (DevTools, Application,
   IndexedDB) and run
   `pbpaste > ~/.config/guppi-connect/hr_refresh_token && chmod 600 ~/.config/guppi-connect/hr_refresh_token`.
2. `uv run scripts/hr_token.py`, then the real-agent runs:
   `uv run scripts/chat.py --env production --token-file ~/.config/guppi-connect/hr_access_token "Change my home address to 419 Glendale Ave, Decatur GA 30030" "yes"`.
   Watch for the 30 s node timeout on real sub-agent turns, and whether PolicySearch's
   reply from the tools gateway is JSON or an event stream.
3. In the designer console, open the `HrTools` data request and press Sync, then rerun
   the policy question, to see whether the MCP data request type works once synced.
4. Decide on the five routing misses, and whether escalation should win for u55 and u59.
5. Tear down when done: the `GuppiConnect` stack, both applications, the two contact
   flows, the API user's key, and the Connect instance if the spike ends.

## How to run

```
cd acxd && npm install && node deploy.js                 # development (mock sub-agents)
node deploy.js --env production                          # production (real gateways)
uv run scripts/contact_flow.py [--env production]        # bind the contact flow to the alias
uv run scripts/chat.py "message" "message" ...           # one Connect chat, transcript printed
uv run scripts/route_eval.py                             # the 60-utterance routing eval
node acxd/logs.js <contactId>                            # designer runtime log for a chat
```
