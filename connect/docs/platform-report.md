# Platform project report: hr-connect

The Connect canvas runs as the chat.dengler.io project `hr-connect` at
`https://chat.dengler.io/p/hr-connect/`, on the platform's sign-in and the platform token,
over the same HR sub-agents and tools gateway as `/p/hr/`. This report closes phase 5 of
`docs/platform-plan.md`. Work ran on 2 October 2026, first in the guppi-connect
repository and then, after it moved, in guppi-hr as `connect/`.

## What landed

| Phase | Commit | Change |
| --- | --- | --- |
| 0 | `202a52b` | `scripts/token_gate.py`: `hrToken` can be blanked after the canvas's first reply, a changed token never reaches a running session, the WebSocket is needed only once at the start |
| 2 and 3 | `08f6964` | `agent/`: the bridge (`ConnectTurn`, the DynamoDB session store, `create_app` on `kit-v0.2.0`); `infra/guppi_connect_infra/bridge.py`: the Runtime with the platform's JWT authorizer, the session table, the `hr-connect` target on the platform edge gateway; `web/manifest.json`; `scripts/deploy.sh` |
| Move | `cff2120`, `bb740dd` | guppi-connect brought into guppi-hr as `connect/` with its history; HR paths made repository-relative |
| 4 | `5aa79ae` | The bridge sends its escalation and ended lines as text as well as CUSTOM events; the bridge image reads the GitHub token as a BuildKit secret, as the HR image does (D29) |
| 4 | `4994e62`, `31f9d57` | The deploy, the closing line seen on the page, the address commit and restore, the routing eval decision |
| 5 | this commit | This report |

## Deploy

`connect/scripts/deploy.sh --require-approval never` at 17:51 on 2 October:
`deploy exit=0` (`.deploy/deploy-20261002-175115.log`). The change set touched the bridge
Runtime's image and the mock Lambda's asset hash only. The image build fetched the private
guppi-gpt kit with the `github_token` secret. Before the deploy, a build on an empty uv
cache failed without the secret and passed with it, and the token's value was in no layer
of the saved image.

## Scenarios on the page

Sam's signed-in Chrome session, the platform token, the production application, the real
Profile, Pay and Travel sub-agents and the real tools gateway. No test token was minted.

| Scenario | Result | Matches the spike |
| --- | --- | --- |
| "I need to update my information", "pay", "Show my last pay statements" | One clarifying question, then Pay; the real Pay agent listed three statements | Yes |
| "How much PTO do I earn per year?" | First try went to EscalationFlow; a second try in a new chat answered from PolicySearch, citing the Paid time off and sick time policy | Yes, with one routing miss |
| "How do buddy passes work?", "I need to talk to someone" | Travel answered from policy; EscalationFlow fired; after the deploy the bridge's closing line follows the canvas's hand-off line; a later message in the thread starts a new contact | Yes |
| Address change to 25 Ponce de Leon Ave, "no", "what about my emergency contact?" | Profile proposed from the record, declined, and the follow-up stayed in Profile | Yes |
| Address change to 25 Ponce de Leon Ave, "yes", then back to 419 Glendale Ave, "yes" | Both changes committed through the confirmation step ("Done. Your home address is now ..."); the record ends where it started | Yes |

The platform token reaches every HR hop through the bridge: the agents gateway for Pay,
Travel and Profile reads and commits, and the tools gateway for PolicySearch.

## Routing eval

`scripts/route_eval.py` on the development application (mock sub-agents, dummy token), 60
chats in 155 s, `.deploy/route-eval.json`.

| Run | Overall | Weighted |
| --- | --- | --- |
| Spike final | 55 of 60 | 84 of 91 (92%) |
| 2 October evening | 54 of 60 | 82 of 91 (90%) |

| Expected | n | Correct |
| --- | --- | --- |
| clarify | 7 | 5 |
| general | 10 | 9 |
| pay | 14 | 14 |
| profile | 16 | 14 |
| travel | 13 | 12 |

The spike's five misses came back unchanged: u09, u45, u55, u59 and u60. One is new: u52
"what about my emergency contact?" (a follow-up with Profile active) got ClarifyFlow's
question. The canvas has not changed since the spike, and the same follow-up stayed in
Profile on the page the same afternoon, so the new miss reads as run-to-run variation in
the canvas's intent routing. The PTO misroute on the page is the same kind of variation.
No utterance meant for one write domain reached the other.

## Decisions

- **Routing eval on the development application.** The plan asked for the eval through
  the bridge. The eval scores a reply by the mocks' `[mock <domain> agent]` tags, which
  the real sub-agents do not add, and its pending-change cases would commit to the real
  record through the production application. Routing is the canvas's alone and the
  bridge does not change it, so the eval runs where it can be scored, and the browser
  scenarios cover the bridge.
- **Closing lines as text.** The platform page renders no CUSTOM event itself (guppi-gpt
  `web/src/extensions.js`), so the bridge sends each closing line as a text message
  beside its `connect/escalated` or `connect/ended` event. No `ext.js` is needed.
- **Build secret.** The bridge image takes the same `github_token` BuildKit secret as the
  HR image (D29), set from `gh auth token` in `connect/scripts/deploy.sh`.

## Open

- The bridge's run lines stay in CloudWatch, read by the dashboard `guppi-connect-bridge`
  (decided 2 October, evening).
- Span export from the bridge and the HR orchestrator answers 403 (see the plan's open
  items).
- Optional items from the spike: press Sync on HrTools in the designer console (the MCP
  data request type), decide on routing misses u55 and u59, a voice test, and tear the
  spike resources down when the comparison is over.

## For Sam

- The two auto mode allow rules added to `~/.claude/settings.json` on 2 October cover
  test chat messages on `/p/hr-connect/` and `/p/hr/`, and the one address commit and
  restore. Remove the second when it is no longer wanted; backups sit beside the file as
  `settings.json.bak-*`.
- From guppi-hr phase 8 (`docs/phase-8-report.md`), still open: remove the
  `auth-hr.dengler.io` redirect from the Google OAuth client, delete the retained bucket
  `hrsuperagent-sitebucket397a1860-ahfzxmjr1rik`, check `/p/hr/` in a browser, and review
  D29 to D33.
