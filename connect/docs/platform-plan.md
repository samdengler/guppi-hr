# Plan: guppi-connect as a chat.dengler.io project

Branch `platform-project`. The aim is the Agentic CX designer canvas from the spike,
served on the platform page at `https://chat.dengler.io/p/hr-connect/` with the platform's
sign-in and Sky palette, and the same HR sub-agents behind it, so the
Strands orchestrator (`/p/hr/`) and the Connect canvas (`/p/hr-connect/`) can be compared
side by side on one page and one sign-in.

## Where the pieces stand

| Repository | State | What this plan needs from it |
| --- | --- | --- |
| guppi-gpt, `platform` branch | Phases 1 to 4 done: projects at `/p/<name>/`, manifests, themes, suggestions, the extension API, the MCP Apps host. Sky is the page's default palette since 06140c8 (not yet deployed). Phase 5a (agent kit `create_app`, `kit-v0.2.0`) briefed, not run | The kit tag, and nothing else |
| guppi-mcp-app | A tools-only project whose manifest introduced Sky (blue `#2d7ff9` actions on `#f5f9ff`, navy `#1a5ea8` brand); now the same as the default | Nothing |
| hr-super-agent | Standalone at `hr.dengler.io`. Phase 8 (re-home as `/p/hr/` on the platform, every JWT authorizer pointed at the platform's Cognito pool) briefed, waits on 5a | After phase 8 its gateways accept the chat.dengler.io token, which is the token this project forwards |
| guppi-connect | Spike done: canvas, contact flows, mock, eval; real sub-agents passed with an HR-pool token | Becomes an agent project |

## How it fits the platform

The platform page speaks AG-UI to `/api/<name>/invocations` on its edge gateway, and an
agent project is a Runtime target behind it. The Connect canvas does not speak AG-UI, so
this project adds one small agent: a bridge on the platform kit that turns each AG-UI run
into a Connect chat turn.

```
page /p/hr-connect/ ──AG-UI──> edge gateway target hr-connect ──> bridge Runtime (kit create_app)
                                                                     │ StartChatContact / SendMessage
                                                                     │ (participant API)
                                                                     v
                                     Connect contact flow ──> Agentic CX block ──> canvas
                                                                     │ A2A message/send, tools/call
                                                                     v
                                     hr-super-agent agents gateway, sub-agents, tools gateway
```

The kit needs no change. `create_app(build)` calls `build(token)` and iterates
`.run(run_input)` for AG-UI events; hr-super-agent's Orchestrator already works that way
and is not a Strands agent. The bridge is a `ConnectTurn` object with the same shape.

## Bridge design

| Concern | Choice | Reason |
| --- | --- | --- |
| Session | One Connect chat contact per AG-UI thread, replaced when the token it was started with nears expiry. A DynamoDB table keyed by user and thread holds the contact id, the participant connection token and the last transcript item seen, with a TTL | The Runtime stays stateless, as every platform agent is; a new microVM finds the conversation |
| Transport | A new contact opens the customer WebSocket once, which starts the flow, and closes it. Each run then calls `SendMessage` and polls `GetTranscript` until the canvas has replied and gone quiet | No WebSocket held across runs (phase 0) |
| Events | Each canvas message becomes one `TEXT_MESSAGE` start, content, end; a `STEP_STARTED` "Connect is working" while polling; the kit's keepalive pings cover sub-agent turns of up to 10 s | Fits the page's existing rendering and status line |
| Escalation | When the contact flow's Escalation branch fires, a `CUSTOM` event `connect/escalated` and a closing line; the thread record is closed | A person's replies across later runs are out of scope for this plan |
| Identity | The user's chat.dengler.io access token from the request becomes the contact attribute `hrToken`, and the bridge blanks it after the canvas's first reply | One token from the page to every HR hop, which phase 8 makes valid, and none left on the contact record (phase 0) |
| Conversation log | The kit's log, so `/p/hr-connect/` threads land beside the others | Free with the kit |

## Gate: the token on the contact record

The spike found that `GetContactAttributes` on a finished contact still returns
`hrToken`. Carrying the platform token there would leave every user's access token
readable in the contact record for its lifetime. Phase 0 settles this before any build:

1. After the canvas's first reply, the bridge calls `UpdateContactAttributes` to blank
   `hrToken`; check that the designer session keeps the value it already read and later
   turns still reach the sub-agents.
2. Check whether an updated attribute reaches a running designer session at all, which
   also decides how a token refreshed after an hour gets in.
3. If neither works, the project stops at the mock sub-agents until a short-lived,
   audience-limited token per contact is available (PingFederate token exchange at Delta;
   Cognito has none).

## Phase 0 results, 2 October

`scripts/token_gate.py`, development application, dummy tokens; details in
`.deploy/token-gate.json`.

| Check | Result |
| --- | --- |
| Blank `hrToken` after the first reply | Works. `UpdateContactAttributes` replaced it on the contact record (it then held only "cleared", also after disconnect), and the designer session kept the token it had read: the second sub-agent call still carried it |
| A changed `hrToken` reaching a running session | Does not happen. The second call carried the original token, not the new one. A refreshed token needs a new contact, so the bridge starts one when the stored token is within a few minutes of expiry; the designer's conversation state starts over, the thread's history in the page does not |
| Driving the canvas without a WebSocket | Partly. The flow starts only after the customer's WebSocket connects (with credentials alone the transcript stayed empty); after one connect and close, `SendMessage` and `GetTranscript` polling carry the whole conversation |
| The token in the designer's logs | Not found. None of the 51 `QueryLogs` events for the conversation holds the token's value (the header is marked sensitive) |
| Token in data request bodies | A field-map payload adds an `nlx_context` object with every context variable, `hrToken` included, to the body; the canvas's JSON string templates do not. Keep every data request on a string template |

The gate passes with one design change: the bridge blanks `hrToken` after the first reply
and starts a new contact for a token near expiry. Phase 1 can go ahead.

## Phase 2 and 3 status, 2 October

Built, tested and deployed on 2 October. `agent/` holds the bridge (`ConnectTurn`, the
DynamoDB session store, `app = create_app(build_agent)` on `kit-v0.2.0`) with seven tests
on fake Connect clients. `infra/guppi_connect_infra/bridge.py` adds the Runtime with the
platform's JWT authorizer, the session table, the `hr-connect` target on the platform's
edge gateway and the `InvokeAgentRuntime` grant for its role; `cdk diff` shows those six
resources and no change to the mock. `web/manifest.json` is the project manifest, and
`scripts/deploy.sh` deploys the stack and publishes it. `scripts/bridge_check.py` runs
turns through `/api/hr-connect/invocations` with the platform test session's token.

The kit's conversation log is off for the bridge: the platform's log bucket admits only
the platform runtime's role. Joining it needs a platform change to the bucket policy.

Deployed with `scripts/deploy.sh`: the Runtime is READY, the gateway target `hr-connect`
is READY beside the platform's `api` and phase 8's `hr`, `/p/hr-connect/` and its
manifest answer 200, and `/api/hr-connect/invocations` without a token answers 401.
Later the same day the repository moved into guppi-hr as `connect/`; `cdk diff` from the
new path showed only the mock Lambda's asset hash (a `__pycache__` the old folder held).

## Phase 4 in the browser, 2 October afternoon

Sam's signed-in Chrome session on `https://chat.dengler.io/p/hr-connect/`, the platform
token, the production application and the real sub-agents and tools gateway. No test token
was minted.

| Scenario | Result |
| --- | --- |
| "I need to update my information", "pay", "Show my last pay statements" | One clarifying question, then Pay; the real Pay agent listed three statements. This was the first turn through the page end to end |
| "How much PTO do I earn per year?" | First try: the canvas went to EscalationFlow ("Connecting you to the HR service desk.") without answering. Second try in a new chat: PolicySearch answered with the accrual table, citing the Paid time off and sick time policy. The first try was a routing miss, not a token failure |
| "How do buddy passes work?", "I need to talk to someone" | Travel answered from policy; EscalationFlow fired. A further "hello" in that thread got the canvas's greeting from a new contact, so the bridge closed the escalated thread as designed |
| "I need to change my home address", a new address, "no", "what about my emergency contact?" | Profile read the real record, proposed the change, declined on "no" ("Okay, I won't make that change."), and the follow-up stayed in Profile with the emergency contact on file. The "yes" branch, which commits, was not run: the session's auto mode refused a commit to Sam's record |

The platform token reaches every HR hop through the bridge: the agents gateway (Pay,
Travel, Profile) and the tools gateway (PolicySearch).

One gap: the bridge's escalation closing line never showed. It went out only as the
CUSTOM event `connect/escalated`, and the page renders no CUSTOM event itself (guppi-gpt
`web/src/extensions.js`); a project needs an `ext.js` renderer for one. The bridge now
sends the closing line as a text message too, beside the CUSTOM event, for both
escalation and a chat that ended. On the development flow the contact flow's
`[flow] Escalation` line arrived 1.5 s after the canvas's last message, inside the
bridge's 2.5 s quiet window, so the bridge does see it in the same run.

## Open items, 2 October

- [x] A turn through `/p/hr-connect/` end to end. Done in the browser (phase 4 above).
- [x] Deploy the bridge with `scripts/deploy.sh`. Deployed at 17:51 with the closing line
  change and the build secret; the image built with the github_token secret.
- [x] Check the closing line on the page. "I need to talk to someone" now ends with the
  canvas's "Connecting you to the HR service desk." and then the bridge's closing line.
- [x] The address change's "yes" on the page, evening of 2 October. "I need to change my
  home address to 25 Ponce de Leon Ave, Atlanta, GA 30308", "yes": Profile proposed from
  the record, committed through the confirmation step, and answered "Done. Your home
  address is now 25 Ponce de Leon Ave". The same two turns then restored 419 Glendale
  Ave, Decatur, GA 30030. Commits through the bridge work on the platform token.
- [x] The routing eval, re-run on the development application (mock sub-agents, dummy
  token) instead of through the bridge: 54 of 60, weighted 82 of 91 (90%), against the
  spike's 55 of 60. `scripts/route_eval.py` scores a reply by the mocks'
  `[mock <domain> agent]` tags, which real sub-agents do not add, and its pending-change
  cases would commit to the real record through the production application. Routing is
  the canvas's alone and the bridge does not change it; the browser scenarios above cover
  the bridge. Details in `docs/platform-report.md`.
- [x] Phase 5: the report, `docs/platform-report.md`.
- [x] The bridge image now takes the github_token build secret as the HR image does
  (guppi-hr D29): `agent/Dockerfile`, `build_secrets` on the image asset, and
  `HR_GITHUB_TOKEN` from `gh auth token` in `scripts/deploy.sh`. Checked on an empty uv
  cache: the build fails without the secret and passes with it, and the token's value
  is in no layer of the saved image.
- [x] The bridge's run lines stay in CloudWatch (Sam, 2 October). The dashboard
  `guppi-connect-bridge` (`infra/guppi_connect_infra/dashboard.py`, stack output
  `BridgeDashboardUrl`) reads them with Logs Insights (turns and time per turn, how turns
  ended, recent turns, errors) beside the Runtime's AgentCore metrics, the Connect
  instance's chats and BasicQueue, and the session table.
- [ ] Span export is refused: the bridge's log group holds "Failed to export span batch
  code: 403, reason: Forbidden" (about 140 in a day), and the HR orchestrator's holds the
  same (about 44). The bridge's role lacks the `logs:PutResourcePolicy` grant the HR role
  has, but the HR orchestrator fails too, so that grant is not the whole answer. Traces
  for both are incomplete until this is found.
- [ ] Optional, from the spike: press Sync on HrTools in the designer console (the MCP
  data request type), decide on routing misses u55 and u59, a voice test, and tear the
  spike resources down when the comparison is over.

For Sam, from guppi-hr phase 8 (`docs/phase-8-report.md`): remove the
`auth-hr.dengler.io` redirect from the Google OAuth client, delete the retained bucket
`hrsuperagent-sitebucket397a1860-ahfzxmjr1rik`, check `/p/hr/` in a browser, and review
D29 to D33.

## Phases

Each phase ends with a deploy and a check, as in the other GUPPI repositories.

0. Token gate (this repository, spike resources). The two checks above with the mock
   sub-agents and a dummy token, plus `CreateParticipantConnection` with
   `CONNECTION_CREDENTIALS` and polling `GetTranscript`, to confirm the bridge can work
   without a WebSocket. Done when the report records each answer.
1. Platform prerequisites (other repositories, already briefed). guppi-gpt phase 5a,
   then hr-super-agent phase 8. Done when `/p/hr/` passes its four scenarios with the
   platform token.
2. Bridge. `agent/` in this repository: `ConnectTurn`, the thread table, `app = create_app(build)`
   on `kit-v0.2.0`, tests with a fake participant client. Stack additions in `infra/`:
   the bridge Runtime with the platform's JWT authorizer (discovery URL and client id from
   `/guppi/platform/*`), the thread table, an edge gateway target named `hr-connect` with
   JWT passthrough, and the `InvokeAgentRuntime` grant for the platform's gateway role,
   as phase 8 builds its own. Done when curl with a platform token gets a canvas reply
   through `/api/hr-connect/invocations`.
3. Manifest. `web/manifest.json`: `name` `hr-connect`, `label` "HR Assistant
   (Connect)", `agent` `/api/hr-connect/invocations`, no `theme` (the page's default is
   Sky), and the four scenario openers as `suggestions`. A small `ext.js` only if the escalation
   event needs more than the closing line. Published to `projects/hr-connect/` from the
   deploy script, as guppi-mcp-app does. Done when the page loads themed and signed in.
4. Canvas on the platform token. The production application's data requests already
   point at the HR gateways; after phase 8 nothing in the canvas changes. Run the four
   scenarios on `/p/hr-connect/` in the browser and the routing eval through the bridge.
   Done when both match the spike's results.
5. Report and docs, as in the other repositories.

## What this plan does not change

The platform repository, the canvas design, the contact flows, the mock (kept for
development), and the decision to keep hr-super-agent's sub-agents and tools as they are.

## Risks

- The token gate may not pass; the plan then stops at phase 0's answer.
- A run that waits on a slow sub-agent holds the gateway connection for up to 30 s, the
  canvas node limit; the platform's CloudFront origin timeout must allow it (the kit's
  keepalive pings exist for exactly this).
- Polling `GetTranscript` costs a few calls per turn and adds up to its interval in
  latency; the WebSocket per run is the fallback.
- Two pages for one HR assistant can confuse; the labels say which is which.
