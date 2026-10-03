# Phase 8 report

Run unattended on 2 October 2026 from a Claude Code session on `main`, following
`docs/phase-8.md`. Sam approved running it straight through, including the in-place update
of `HrSuperAgent` in step 6.

The precondition held: `../guppi-gpt/docs/proposals/platform-phase-5a-report.md` records
`kit-v0.2.0` (commit 763fe42, tag on github.com/samdengler/guppi-gpt) and the extension
members `TOOL_CALL_START` and `TOOL_CALL_END` renderers, `ctx.setLabel`, `guppi.onThread`
and `state` from `onSend`, with no blockers.

## What landed

| Step | Commit | Change |
| --- | --- | --- |
| 1 | `fe05cde` | The orchestrator on the kit: `app = create_app(build_strands_agent)`; `keepalive.py`, `validation.py`, `conversation_log.py` deleted after a diff against `kit-v0.2.0` showed them identical apart from the package name; the image installs git and reads a GitHub token as a BuildKit secret (D29, D30) |
| 2 | `3e0d51b` | The stack on the platform contract: `/guppi/platform/*` from SSM, the platform-owned sections removed, every JWT authorizer and the HR tools issuer on the platform pool, the target `hr` on the platform edge gateway and the `InvokeAgentRuntime` policy on its role (D31); stack tests rewritten (174 Python tests green), `cdk synth -c image_uri=...` green |
| 3 | `06be59d` | `web/src` page and its tests deleted; `web/manifest.json` (no `theme`), `web/src/ext.js` as an ES module, `copy.js` cut to its pure helpers; 14 `node:test` cases (D32, D33) |
| 4 | `5eafcc3` | `scripts/deploy.sh`: no Google OAuth read, Dynatrace from 1Password with fallback, `--reuse-parameters` and `--site-only` kept, `HR_GITHUB_TOKEN` from `gh auth token`, manifest and extension to `projects/hr/` with `no-cache`, `/projects/hr/*` invalidated |
| 5 | `a5123eb` | README, AGENTS.md, design.md, plan.md (phase 8), demo.md, agent/README.md; D34 records the move and marks D9, D10 and D17 Reversed |
| 6 | `39b3ffe` | `scripts/deploy.sh --reuse-parameters --require-approval never`: `deploy exit=0` (`.deploy/deploy-20261002-073017.log`, 1433 s of `cdk deploy`) |
| 7 | `8ac6dbe` | `scripts/browser-check.mjs` and Playwright as a `web/` dev dependency; the checks below |
| 8 | this commit | This report's decisions, blockers and manual list |

## Resources removed

From `cdk diff HrSuperAgent` (saved to `.deploy/phase8-diff.txt`), taken before the deploy.
No resource is replaced; the agents and tools gateways are updated in place (authorizer
only), so `AgentsGatewayUrl` and `ToolsGatewayUrl`, which guppi-connect reads, keep their
values.

| Area | Resources deleted |
| --- | --- |
| Sign-in | `UserPool`, its `Web` client, the `Google` identity provider, the `auth-hr.dengler.io` user pool domain, `Branding` |
| DNS and certificates | `AuthRecord` (auth-hr.dengler.io), `ChatARecord` and `ChatAAAARecord` (hr.dengler.io), `ChatCertificate`, `AuthCertificate` |
| Edge gateway | `EdgeGateway` (hr-super-agent-edge), its `RuntimeTarget` (`api`), `GatewayRole`, `GatewayInvokePolicy`, `EdgeGatewayPerUserRateLimit` |
| WAF | `EdgeWebAcl`, `EdgeWebAclAssociation`, `OriginVerifySecret`, the `WafBlocks`, `WafFailCloses` and `WafFailOpens` alarms |
| Page | `Distribution`, its origin access control, `SecurityHeadersPolicy`, the site bucket's policy |
| Feedback | `FeedbackApi` with its deployment, `prod` stage, resources, method, validator, model, two gateway responses and Cognito authorizer; `FeedbackApiRole`; `FeedbackBus` and `FeedbackArchive`; the Dynatrace business events connection, API destination, its role and policy, rule, dead letter queue and queue policy, and `FeedbackDeadLetterAlarm` |
| Edge observability | `EdgeGateway5xxAlarm`, `EdgeGateway4xxRateAlarm`, the edge gateway's vended log group, delivery source, destination and delivery, and its Dynatrace subscription filter |
| Template | Parameters `GoogleClientId`, `GoogleClientSecret`, `DynatraceBeaconOrigin`; condition `HasDynatraceBeaconOrigin`; the CloudFront hosted zone mapping; outputs `SiteBucketName`, `DistributionId`, `UserPoolId`, `UserPoolClientId`, `AuthDomain`, `GatewayUrl`, `GatewayArn`, `FeedbackApiUrl`, `FeedbackApiEndpoint`, `FeedbackBusName`, `RumScriptPath`, `RumBeaconOrigin` |

Orphaned, not deleted: the site bucket `hrsuperagent-sitebucket397a1860-ahfzxmjr1rik`
(`SiteBucket`, `RemovalPolicy.RETAIN`). It leaves the stack and stays in the account for
Sam to delete.

Added: `PlatformTarget` (target `hr` on the platform edge gateway, JWT passthrough) and
`PlatformGatewayInvokePolicy` (`InvokeAgentRuntime` on the orchestrator for the platform
gateway role), plus five SSM-typed parameters for `/guppi/platform/*`. Updated in place:
the orchestrator, sub-agent and HR tools runtimes (new image; authorizers or token
settings on the platform pool), the agents and tools gateways (authorizer), the
investigator role's policy (`ListUsers` on the platform pool). Outputs: `SiteUrl` is
`https://chat.dengler.io/p/hr/`, `AgentPath` is new.

## Deploy

`HrSuperAgent` reached `UPDATE_COMPLETE` with no failed resource. The image built under
CDK with the `github_token` build secret and was pushed; the four runtimes took it. The
cleanup phase deleted every resource listed above; the one `DELETE_SKIPPED` event is
`SiteBucket397A1860`, the retained site bucket, which still exists. The platform edge
gateway lists two targets, `api` and `hr`, both `READY`. `hr.dengler.io` and
`auth-hr.dengler.io` no longer resolve. `AgentsGatewayUrl` and `ToolsGatewayUrl` in
`cdk-outputs.json` are unchanged:
`https://hr-super-agent-agents-rfkdgz7314.gateway.bedrock-agentcore.us-east-1.amazonaws.com`
and `https://hr-super-agent-tools-7bi54dgr6g.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp`.
Both now accept only the platform pool's token, which is what guppi-connect's plan expects.

## Checks

With curl, 2 Oct 2026 after the deploy:

| Request | Result |
| --- | --- |
| `https://chat.dengler.io/p/hr/` | 200 `text/html` |
| `/projects/hr/manifest.json` | 200 `application/json` |
| `/projects/hr/ext.js` | 200 `text/javascript`, `cache-control: no-cache` |
| `POST /api/hr/invocations` without a bearer | 401 from the platform gateway (`www-authenticate: Bearer error="invalid_token"`, body `Missing Bearer token`) |
| `/` and `/p/mcp-app/` | 200 |

The four scenarios as AG-UI runs against `/api/hr/invocations` with a token from
`../guppi-gpt/scripts/test-token.sh` (held in the process environment, never printed),
`forwardedProps.project` `hr`, each run's `STATE_SNAPSHOT` sent back as the next run's
`state`. Thread A held the first scenario, thread B the other three in order. Raw events
are in `.deploy/phase8-scenarios.json` (gitignored); keepalive pings are left out below.

| Scenario | Turn | Events | Reply | State after |
| --- | --- | --- | --- | --- |
| Disambiguation | "I need to update my information" | `RUN_STARTED`, text, `STATE_SNAPSHOT`, `RUN_FINISHED`; no step | "Is this about your personal details, such as your home address or emergency contact, or about your pay, such as your direct deposit account or pay statements?" | `pendingAction: null` |
| Confirmation | "Change my home address to 419 Glendale Ave, Decatur GA 30030" | `STEP_STARTED profile`, `STEP_FINISHED profile`, text, `STATE_SNAPSHOT` | "I'm proposing to change your home address from 88 Lake Shore Dr, Chicago, IL 60611 to 419 Glendale Ave, Decatur, GA 30030. Is that correct?" | `pendingAction` with proposal `6226f303...`, from, to, expiry, domain `profile` |
| | "yes" (with that state) | profile step, text, snapshot | "Done. Your home address has been changed to 419 Glendale Ave, Decatur, GA 30030." | `activeDomain: profile`, `pendingAction: null` |
| Sticky context | "what about my emergency contact?" | profile step, no re-route | "Your emergency contact on file is Jordan Grant (Partner), (404) 555-7167. Would you like to change it?" | `activeDomain: profile` |
| Topic shift | "How many buddy passes do I get?" | `STEP_STARTED travel` | "each eligible employee receives 8 buddy passes per calendar year..." | `activeDomain: travel` |
| | "I need to talk to someone" | travel step | "Your ticket ID is HR-206993. Someone from the HR team will follow up with you within two business days." | `activeDomain: travel` |

The audit table's entry for proposal `6226f303...` carries trace id
`102c075a7f784cd9bee6a145fb256088`, the `traceparent` the "yes" run sent, so the trace
survives the platform's gateway and every hop after it.

Browser check: `scripts/browser-check.mjs` (adapted from guppi-gpt's, Playwright as a dev
dependency of `web/`) seeded the session from `$HOME/.config/guppi/test-session.json`, ran
the same four scenarios on `/p/hr/` and saved `.deploy/phase-8-disambiguation.png`,
`phase-8-confirmation.png`, `phase-8-sticky.png` and `phase-8-topic-shift.png`; results in
`.deploy/phase8-browser.json`. The page's brand reads "HR Assistant" on the Sky palette,
and the four suggestions show under the empty state.

| Scenario | Label | Status lines seen | Outcome |
| --- | --- | --- | --- |
| Disambiguation | "HR Assistant" | none | the clarifying question naming both areas |
| Confirmation | "HR Assistant · Profile" on both turns | "Asking the Profile agent…", "Profile agent answered" | the proposal read back; on "yes" "Your address change has been completed"; a new audit entry (proposal `63aa53f3...`, trace `6abf9bcd...`) shows the commit |
| Sticky context | "HR Assistant · Profile" | the same two | the emergency contact on the same record |
| Topic shift | "HR Assistant · Travel" on both turns | "Asking the Travel agent…", "Travel agent answered" | 8 buddy passes, then ticket HR-848114 |

The browser ran after the curl scenarios with the same test user, so its address proposal
read back the address curl had just written (from and to the same); the agent said so and
committed on "yes". `https://chat.dengler.io/` (brand "GuppiGPT") and `/p/mcp-app/` (brand
"MCP App Lab") reached the chat screen as before (`.deploy/phase-8-root.png`,
`phase-8-mcpApp.png`).

The page's console on `/p/hr/` showed the platform's Dynatrace RUM beacon refused
(CORS on `https://bf49265sdi.bf.dynatrace.com/bf`, two 400s). RUM is the platform's
(`rum` is on in its `config.json` and in this manifest, as it was in HR's flags); nothing
of HR's failed.

## Decisions

All Proposed, in `docs/decision-log.md`:

- D29: the unchanged Dockerfile could not install the kit (no git in `python:3.12-slim`,
  and `samdengler/guppi-gpt` is private). The image installs git and reads a GitHub token
  as the BuildKit secret `github_token`, which the stack's image asset takes from
  `HR_GITHUB_TOKEN` and `scripts/deploy.sh` sets from `gh auth token`. Checked: the token
  is in no layer, file or image history of the built image. guppi-connect's bridge will
  meet the same problem when it depends on the kit.
- D30: `app.py` passes `create_app` a three line `build_strands_agent` that looks up
  `hr_agent.agent.build_strands_agent` per request, so the tests' seam still works; the
  three deleted modules diffed identical to `kit-v0.2.0` apart from the package name; the
  run line now comes from the `guppi_agent` logger.
- D31: the platform parameters read, the issuer cut from the discovery URL, new logical
  ids for the target and its policy (an add and a delete, no replacement), the
  investigator's `ListUsers` on the platform pool, and what stays (billing alarm, log
  forwarding, `own_account_singletons` for Transaction Search, `target_credentials`).
- D32: the manifest and extension; the extension keeps the last `STATE_SNAPSHOT` it sees,
  where phase 5 kept it only after `RUN_FINISHED`.
- D33: the reply's agent tag is not kept in the platform's text-only history; the one thing
  phase 5's page had that the extension does not.
- D34 (Approved, the brief's own decision): the move onto the platform, reversing D9, D10
  and D17.

## Blockers

None. Nothing rolled back.

## For Sam

- Remove `https://auth-hr.dengler.io/oauth2/idpresponse` from the Google OAuth client's
  authorized redirect URIs (and `https://auth-hr.dengler.io` from its JavaScript origins,
  if listed); the user pool and its domain are gone.
- Delete the retained site bucket `hrsuperagent-sitebucket397a1860-ahfzxmjr1rik`
  (empty it first: `aws s3 rb s3://hrsuperagent-sitebucket397a1860-ahfzxmjr1rik --force`).
- Check `https://chat.dengler.io/p/hr/` in a signed-in browser of your own: the four
  suggestions, "HR Assistant · Profile" with "Asking the Profile agent…", and a "yes" that
  commits.
- Optional: the platform's Dynatrace RUM beacon is refused by CORS on `/p/hr/` (Checks).
- Review D29 to D33. The private kit dependency (D29) goes away if guppi-gpt becomes
  public or the kit moves to a package index.

Status on 2 October, evening: `/p/hr/` checked in Sam's signed-in browser (the four
suggestions, "HR Assistant · Profile" with its status line, and a "yes" that committed a
test address, then restored the original); D29 to D33 Approved, D33 with a note that the
manifest keeps no history. Still open: the redirect URI on the Google OAuth client (the
client is "GuppiGPT Cognito" in project guppi-gpt; the row is redirect URI 2) and the
retained site bucket, which held 8 files of the old page and is used by no
distribution.
