# Phase 8: re-home on the platform

The standalone instruction for moving this repository onto the chat.dengler.io platform
as an agent project (`../guppi-gpt/docs/proposals/platform.md`, phase 5 there). Read that
file, this repository's `AGENTS.md`, `docs/plan.md`, `docs/design.md` and
`docs/decision-log.md`, then `../guppi-gpt/docs/proposals/platform-phase-5a-report.md`.
If that report says the kit tag `kit-v0.2.0` or the extension members it names did not
land, write `docs/phase-8-report.md` saying so and stop; the steps below depend on them.

This run is unattended, under the rules of `docs/phase-2.md` in guppi-mcp-app: never
wait for an answer, make the smaller reversible choice and record it in
`docs/decision-log.md` (D29 on), blockers to `docs/phase-8-report.md`, never touch
guppi-gpt except to read it, tokens from `../guppi-gpt/scripts/test-token.sh` never in
logs, reports, commits or fixtures. Never run `cdk destroy`: the resources this phase
removes leave through the stack's own update, and the report lists every one. If the
report already exists, continue from its first unfinished step. Commit per step, push at
the end; do not merge or rebase anything.

What moves and what stays. The platform provides the page, sign-in, CloudFront, WAF, the
edge gateway and its per-user limits, so this repository stops owning its copies of
them: the `web/src` page and its tests, the Cognito pool and Google client, DNS records
and certificates for `hr.dengler.io` and `auth-hr.dengler.io`, the edge gateway, the WAF,
the rate limits, the feedback API and bus, the site bucket and distribution, and the
Dynatrace RUM parameters. Everything that is HR stays in this stack: the orchestrator,
the three sub-agents and their agents gateway, the HR tools server and its four tables,
the tools gateway and knowledge base with its content bucket and nightly ingestion, the
conversation log, the alarms and log deliveries for what remains, and the Dynatrace OTLP
export. The stack keeps its name, `HrSuperAgent`, and is updated in place, so the
knowledge base, its ingested corpus and the tables are untouched. The page becomes
`https://chat.dengler.io/p/hr/`, and the orchestrator answers at `/api/hr/invocations`
through the platform's edge gateway.

Work in this order.

1. Agent on the kit. `agent/pyproject.toml` depends on
   `guppi-agent @ git+https://github.com/samdengler/guppi-gpt@kit-v0.2.0#subdirectory=agent`;
   `hr_agent/app.py` becomes `app = create_app(build_strands_agent)` from `guppi_agent`;
   `keepalive.py`, `validation.py` and `conversation_log.py` are deleted and their imports
   point at `guppi_agent`. HR's copies were identical to the kit apart from the name, so
   nothing is lost; check with a diff before deleting and record it. `uv lock`,
   `uv run -- pytest` green, the Dockerfile unchanged (`python -m hr_agent` still picks
   the role by `AGENT_ROLE`). Build the image locally to confirm the git dependency
   installs in the container.
2. Stack, in place. In `infra/hr_super_agent_infra/stack.py`, read the platform's
   `/guppi/platform/*` parameters with `ssm.StringParameter.value_for_string_parameter`
   (edge gateway id, ARN and role ARN; the JWT discovery URL and client id). Remove the
   sections named above. Point every JWT authorizer that remains (the orchestrator
   Runtime, the sub-agent Runtimes, the agents gateway, the tools gateway, the HR tools
   Runtime) at the platform's discovery URL and client id, so the user's Cognito token
   from chat.dengler.io is the one accepted on every hop. Add a `CfnGatewayTarget` named
   `hr` on the platform's edge gateway with the orchestrator Runtime as its target and
   `JWT_PASSTHROUGH` credentials, exactly as the platform's own `api` target is built,
   and an `iam.Policy` granting `bedrock-agentcore:InvokeAgentRuntime` on the
   orchestrator Runtime to the platform's edge gateway role imported by ARN. Bind the
   orchestrator Runtime's authorizer to the platform gateway ARN only if guppi-gpt's
   decision log says that binding works; it did not, so default to leaving it off. Drop
   the parameters, conditions, alarms, log deliveries and outputs that belonged to the
   removed resources; the site bucket has `RemovalPolicy.RETAIN`, so note in the report
   that it will be orphaned for Sam to delete. Update `infra/tests/test_stack.py`;
   `uv run -- cdk synth -c image_uri=<any ecr uri>` green. Save `cdk diff` to
   `.deploy/phase8-diff.txt` and summarize the removals in the report before deploying.
3. Manifest and extension. Delete `web/src` and the page tests, keeping `copy.js`'s
   pure helpers (`toolStatus`, `agentName`, `stepStatus`, `replyLabel`) and
   `copy.test.js`. Write `web/manifest.json`: `name` `hr`, `label` `HR Assistant`,
   `agent` `/api/hr/invocations`, `features` from `web/features.json` (then delete that
   file), `extension` `/projects/hr/ext.js`, no `theme` (the platform's default palette, Sky,
   applies to every project since guppi-gpt 06140c8), and `suggestions` with the four scenarios' opening lines from
   `docs/plan.md`. Write `web/src/ext.js`, built by esbuild as an ES module to
   `web/dist/ext.js`: it ports phase 5's page changes onto the extension API. On
   `TOOL_CALL_START` and `TOOL_CALL_END` it sets `guppi.status` from `toolStatus`; on
   `STEP_STARTED` it calls `ctx.setLabel(replyLabel(step))` and sets the step status; on
   `STEP_FINISHED` the done status; on `STATE_SNAPSHOT` it keeps the snapshot as the
   thread's state; `guppi.onSend` puts that state on the next run; `guppi.onThread`
   resets it. The reply's agent tag is not kept in the page's history store (the
   platform stores text only); record that as the one thing phase 5 had that this does
   not. `node:test` coverage for the pure parts.
4. Deploy script. `scripts/deploy.sh` no longer reads the Google OAuth item; it keeps
   the Dynatrace item for the OTLP parameters, runs `cdk deploy HrSuperAgent`, builds
   `web/` and publishes `manifest.json` and `dist/ext.js` to
   `s3://<site bucket from SSM>/projects/hr/` with `Cache-Control: no-cache`, and
   invalidates `/projects/hr/*` on the platform distribution from SSM; `--site-only` and
   the `.deploy/` log stay. `--reuse-parameters` as in the platform.
5. Docs. `README.md` (the page is `/p/hr/`, what the stack now holds), `AGENTS.md`
   (layout, the kit, the extension), `docs/design.md` (architecture and request flow
   through the platform), `docs/plan.md` (phase 8 ticked), the decision log (the move as
   a reversal of D9 and D17, plus each choice made here).
6. Deploy. `scripts/deploy.sh --require-approval never`, following `.deploy/latest.log`
   to `deploy exit=0`. The update deletes the removed resources; if CloudFormation rolls
   back, record the failing resource and the rollback state in the report and stop, the
   old site stays up in that case.
7. Checks. With curl: `https://chat.dengler.io/p/hr/` 200, `/projects/hr/manifest.json`
   and `/projects/hr/ext.js` 200, `/api/hr/invocations` without a bearer 401 from the
   gateway. With a token from `../guppi-gpt/scripts/test-token.sh`: the four scenarios
   from `docs/plan.md` as AG-UI runs against `/api/hr/invocations`, carrying each run's
   `STATE_SNAPSHOT` back as the next run's `state` where a scenario has two turns, and
   record the events and replies. Then the browser check: adapt guppi-gpt's
   `scripts/browser-check.mjs` (seed the session from `$HOME/.config/guppi/test-session.json`)
   into `scripts/browser-check.mjs` here, run the four scenarios on `/p/hr/` and save
   `.deploy/phase-8-<scenario>.png`; confirm the label tag ("HR Assistant · Pay") and the
   step status lines appear, and that the address change commits on "yes".
   `https://chat.dengler.io/` and `/p/mcp-app/` still answer as before.
8. Report. `docs/phase-8-report.md`: what landed, the resources removed (from the diff),
   the checks, decisions, blockers, and Sam's manual list: remove
   `https://auth-hr.dengler.io/` and the old redirect URI from the Google client, delete
   the retained site bucket, and check `/p/hr/` in his own browser. Commit and push.

Done when steps 1 to 8 hold and the report is committed.
