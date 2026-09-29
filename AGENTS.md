# HR Super Agent instructions

## Project Overview

HR Super Agent is an MVP of an HR employee assistant, branded "HR Assistant" on the page.
It is an iteration of guppi-gpt (`~/src/github.com/samdengler/guppi-gpt`), merged in with
its history at commit 8baf911 and renamed. Today the code is guppi-gpt's chat under new
names at `https://hr.dengler.io`: one page, plain text conversation, Google sign-in, and
answers grounded in a Bedrock Knowledge Base. The agent holds nothing between runs, but
three things are kept: the sign-in session in IndexedDB, one pseudonymous record per
thread in S3 for 30 days, and a vote on a reply as a business event.

The MVP replaces the single agent with an orchestrator that routes each turn to Profile,
Pay, and Travel sub-agents over A2A, and adds an HR tools MCP server with a propose and
commit pair for every write. `docs/plan.md` has the target architecture and the seven
phases; `docs/decision-log.md` records every choice (D1 on); `docs/handoff.md` explains
the sources. guppi-gpt's design document (`docs/guppigpt-design.html`), decision log
(`docs/guppigpt-decision-log.html`), and diagrams (`docs/guppigpt-architecture.html`)
stay unchanged as the record of what was inherited (D17). When code and a decision
disagree, change one of them in the same commit.

## Tech Stack

- Infrastructure: AWS CDK v2 in Python, one stack `HrSuperAgent`, region `us-east-1`, in
  the same account and `dengler.io` zone as guppi-gpt's `GuppiGpt` stack
- Agent: Python 3.12, FastAPI, AG-UI over SSE, Strands Agents with the `ag-ui-strands` adapter, arm64 container on AgentCore Runtime
- Model: Claude Haiku 4.5 through the `us.` cross-region inference profile (`MODEL_ID` in the stack)
- Edge: CloudFront in front of an AgentCore Gateway runtime target, plus an `/api/feedback` behavior in front of a small API Gateway REST API that puts reply votes straight onto an EventBridge bus; Cognito user pool federated to Google
- Page: static HTML and vanilla JavaScript in `web/src/`, bundled once by esbuild into `web/dist/` with `@ag-ui/client` as the stream reader, served from S3 through CloudFront
- Package manager: uv workspace (`infra` and `agent` are members)
- Secrets: 1Password CLI at deploy time for the Google OAuth client; the origin header value is generated in Secrets Manager by the stack; nothing secret is checked in

## Project Structure

```
docs/
  handoff.md              # what the MVP is, its sources, how to start
  plan.md                 # target architecture, the seven phases, the four scenarios
  decision-log.md         # D1 on, one row per decision, status Proposed, Approved or Reversed
  guppigpt-*.html         # guppi-gpt's design, decision log, and diagrams, kept unchanged (D17)
  proposals/              # guppi-gpt's backlog proposals, unchanged; new proposals are added beside them
  dynatrace/dashboard.json  # draft DQL dashboard tiles for the queries in docs/proposals/dynatrace.md
infra/
  app.py                  # CDK app entry
  hr_super_agent_infra/stack.py
  tests/                  # assertions against the synthesized template
agent/
  src/hr_agent/app.py         # FastAPI app: POST /invocations (SSE), GET /ping, per-run log record with trace id
  src/hr_agent/agent.py       # per-run MCP client with the user token, Strands agent, AG-UI adapter
  src/hr_agent/validation.py  # run input validation and front trimming
  src/hr_agent/keepalive.py   # CUSTOM ping event after 15 silent seconds
  src/hr_agent/conversation_log.py  # thread record: pseudonym, merge, conditional write to S3
  Dockerfile                     # arm64, uvicorn on 8080; built from the repo root so uv.lock is in context
  tests/
web/
  package.json            # esbuild, @ag-ui/client, @openfeature/web-sdk, idb; `npm run build` writes dist/, `npm test` runs node --test
  src/index.html          # the page; no inline script or style (CSP is default-src 'self')
  src/app.js              # PKCE sign-in by hand, HttpAgent subscriber, plain text rendering
  src/session.js          # idb-backed session store: refresh token, header claims, rotated on use
  src/app.css
  src/history.js          # local chat history: idb wrapper around one "threads" object store, behind the history flag
  src/feedback.js         # up/down reply control: vote toggle, "hr:feedback" CustomEvent, history write, POST to /api/feedback, behind the feedback flag
  src/features.js         # OpenFeature static provider; initFeatures() and isEnabled()
  src/copy.js             # the hint and empty-state wording for each combination of the history and logging flags
  src/flags-core.js       # pure override parsing and default/override overlay, tested without a DOM
  src/flags.js            # the /flags.html settings page: rows per flag, browser-wide override controls, reset
  src/flags.html          # that page, reachable by URL only (no link from the chat page)
  src/privacy.html        # privacy policy, served at /privacy.html for the Google consent screen
  src/terms.html          # terms of service, served at /terms.html
  src/rum.js              # Dynatrace RUM: script injection, OpenFeature hook, behind the rum flag
  features.json           # committed feature flag defaults, merged into config.json at deploy time
  vendor/ruxitagentjs.js  # the Dynatrace RUM script itself; gitignored, not committed
  test/features.test.mjs  # node:test coverage for flags-core.js, run by `npm test`
  test/feedback.test.mjs  # node:test coverage for feedback.js's DOM-free functions
  test/flags.test.mjs     # node:test coverage for the flags page helpers in flags-core.js
  test/legal.test.mjs     # the privacy and terms pages: date, cross links, no inline style or script
  test/copy.test.js       # node:test coverage for copy.js's wording per flag combination
  test/rum.test.mjs       # node:test coverage for rum.js's pure property-building functions
  test/session.test.mjs   # node:test coverage of session.js's pure decision and shaping functions
  dist/                   # build output plus config.json written by deploy.sh; not committed
scripts/
  deploy.sh
  seed-content.sh         # clone the docs repositories at pinned revisions, sync Markdown to S3
  ingest.sh               # StartIngestionJob and wait
```

## Rules

- No Lambda functions in the request path or the content sync path by default. Lambda is
  a preference, not a ban: when a function is the right tool, propose it and get Sam's
  approval before building it. Approved so far: the Lambda functions inside Dynatrace's
  own AWS activation stack (`GuppiGPT-Dynatrace`, 7 Sep 2026), which sits outside
  `HrSuperAgent`.
- Secrets never enter files, `cdk.context.json`, or `-c` context values. Values the stack
  cannot produce (the Google OAuth client) are CloudFormation parameters with `no_echo`
  supplied by `scripts/deploy.sh` from 1Password; values it can produce (the
  `X-Origin-Verify` header) live in Secrets Manager and reach the template only as
  dynamic references.
- The agent image installs dependencies from `uv.lock` in a layer before the source is
  copied, so a code change rebuilds only the last layer; `.dockerignore` at the repo root
  limits the build context (and the CDK asset hash) to the agent files and the lockfile.
- Every change to the stack must keep `uv run -- pytest` green and
  `uv run -- cdk synth -c image_uri=<any ecr uri>` working without Docker.
- Prose in docs and comments: no em-dashes or en-dashes, no second person.
- The page renders plain text only: no Markdown parser, no `innerHTML` with model or user text.
- Tests replace `hr_agent.agent.build_strands_agent` (and, from phase 3, the A2A client
  factory); nothing in `agent/tests` reaches Bedrock or a gateway.
- The orchestrator, the sub-agents, and the tools server share one container image; a
  role is chosen by `AGENT_ROLE`. Add a role, not a Dockerfile (D11).
- Every phase in `docs/plan.md` ends deployed and checked in the browser; phases are not
  stacked undeployed.
- Every choice not already in `docs/decision-log.md` gets a new entry with status
  Proposed, listed in the next message to Sam.
- Every named AWS resource differs from its `GuppiGpt` counterpart, since both stacks
  share the account (D18). The zone apex record and Transaction Search stay with
  `GuppiGpt` (D16).
- Observability that reads state already reaching the browser is never behind a feature
  flag. `web/features.json` and the OpenFeature provider in `web/src/features.js` mostly
  gate product features (`docs/proposals/feature-flags.md`); the one exception is `rum`,
  since turning it on inserts a script element and starts a vendor library running,
  which is a page behavior change, not a passive read (`docs/proposals/dynatrace.md`).

## Dependency Management

```sh
uv sync --all-packages --dev        # install all workspace members and dev tools
uv add --package hr-agent httpx  # add a dependency to one member
uv run -- pytest                    # run all tests
uv run -- pytest agent/tests -v
uv run -- ruff check .
cd web && npm ci && npm run build   # bundle the page into web/dist/
cd web && npm test                  # node:test coverage for the feature flag overlay and the copy wording
```

Flipping a feature flag: edit `web/features.json`, then run `scripts/deploy.sh --site-only`
to rebuild the page and republish `web/dist/config.json` with the new defaults; no `cdk
deploy` and no CloudFormation parameter (`docs/proposals/feature-flags.md`).

- Always use `uv add --package <member>` for dependencies, not manual pyproject edits.
- Run `uv sync --all-packages --dev` after pulling changes.

## Deploying

`scripts/deploy.sh` reads the Google OAuth client id and secret from 1Password
(`op://Personal/GuppiGPT Google OAuth/...`, an API Credential item whose `username` is the client id and `credential` is the client secret), runs `cdk deploy` with them as parameters,
builds the page (`npm ci`, `npm run build` in `web/`), writes `web/dist/config.json` from the stack outputs, syncs `web/dist/` to the site bucket, and
invalidates CloudFront. When the 1Password read fails the script omits both parameters and
CloudFormation reuses the stack's existing values. `HR_ALARM_EMAIL`, when set, becomes
the `AlarmEmail` parameter and subscribes that address to the alarm topic.
`HR_INVESTIGATOR_ARN`, when set, becomes the `InvestigatorPrincipalArn` parameter and
narrows the conversation investigator role's trust to that one ARN; left unset, the role
trusts the account root. `scripts/deploy.sh --site-only` skips `cdk deploy` (so no image build or push) and
publishes the page from the last outputs file. Every run is
also written to `.deploy/deploy-<timestamp>.log` with `.deploy/latest.log` pointing at the
newest and a final `deploy exit=<code>` line, so a Claude session can watch a deploy
started from any terminal. Deploys run on Sam's Mac; the Docker image is built there for
arm64. A deploy started without a terminal (a `!` command in a Claude session) cannot
answer cdk's approval prompt for IAM changes and exits 1 before touching the stack; pass
`--require-approval never` there.

`-c own_account_singletons=true` makes the stack create the `dengler.io` apex placeholder
record and the Transaction Search configuration itself. It stays off while `GuppiGpt`
exists, since a second copy of either fails the deploy (D16).

The runtime's request header allowlist names `Authorization` and `traceparent`; without
the first the runtime validates the bearer and drops it, and the agent has no token for
the tools gateway; without the second the trace the page started ends at the runtime.
The edge gateway target's allowed request headers name the session id header and
`traceparent` for the same reason. The runtime container receives `TOOLS_GATEWAY_URL`,
`MODEL_ID`, `RETRIEVE_TOOL`, `LOG_LEVEL`, `OTEL_PYTHON_EXCLUDED_URLS`,
`CONVERSATION_LOG_ENABLED`, `CONVERSATION_LOG_BUCKET`, and `CONVERSATION_LOG_KEY_SECRET_ARN`
from the stack; the container starts under `opentelemetry-instrument` (`agent/Dockerfile`), and the
runtime supplies the ADOT exporter settings itself. `docs/proposals/traceability.md`
describes the identifiers and where each one is logged.

Conversation logging (`docs/proposals/conversation-logging.md`) is behind two switches,
both on (inherited from guppi-gpt, where they were turned on 5 Sep 2026). `CONVERSATION_LOG_ENABLED` in `stack.py` decides whether the agent writes one
record per thread to the conversation log bucket, uses the keyed pseudonym on the run line,
and tells the model that conversations are logged; `"logging"` in `web/features.json`
decides whether the page's hint and empty state say so. Flip the runtime switch and deploy
first, then the page switch, so the page never promises a record that does not exist; turn
them off in the other order. The bucket, the KMS key, the HMAC secret, and the investigator
role are created either way, so flipping a switch is one line and a deploy.

The instrumented container's spans are refused until CloudWatch Transaction Search (the
span destination and a 1 percent indexing rule) is on for the account; the `GuppiGpt`
stack owns that setting, and this one creates it only with `own_account_singletons` (D16).
The web ACL on the edge gateway blocks (`WAF_BLOCK = True` in `stack.py`, inherited from
guppi-gpt, where a day in COUNT produced no counts); set it to `False` to return to
counting. The billing
alarm reads `AWS/Billing EstimatedCharges`, which exists only after billing alerts are
enabled in the account's billing preferences (a console setting, not in the stack). The two
gateways' and the runtime's `APPLICATION_LOGS` (and, for the gateways, `TRACES`) are
delivered to CloudWatch Logs groups under `/aws/vendedlogs/bedrock-agentcore/`, 30 day
retention, alongside alarms on gateway 4xx rate and 5xx count, runtime 5xx count and p90
latency, and Bedrock throttling, all notifying the alarm topic (`docs/proposals/operations.md`).

Dynatrace: `DynatraceBeaconOrigin`, `DynatraceOtlpEndpoint`, and `DynatraceApiToken` are
stack parameters that default empty, and each Dynatrace path stays dark while its
parameter is empty. `scripts/deploy.sh` reads the OTLP endpoint and the API token from
1Password (`op://Personal/GuppiGPT Dynatrace/...`, an API Credential item whose
`hostname` is the endpoint and `credential` is the token) the same way it reads the
Google OAuth client, skipping them when the item does not exist. The item exists, so
this stack exports traces, forwards vended logs through Firehose, and sends feedback
business events to the same tenant as guppi-gpt; its spans carry the service name
`hr_super_agent.DEFAULT`. `HR_DYNATRACE_BEACON_ORIGIN`, when set, becomes the
`DynatraceBeaconOrigin` parameter the same way `HR_ALARM_EMAIL` becomes `AlarmEmail`;
it is unset. The RUM script itself (`web/vendor/ruxitagentjs.js`, gitignored) is copied
into the bundle at `/dt/ruxitagentjs.js` before the sync when present; this checkout has
none, so although the `rum` flag in `web/features.json` is on, the page's request for the
script gets a 403 and RUM does not run. `docs/proposals/dynatrace.md` has guppi-gpt's
flip procedure.

Reply votes take their own path, off the chat runtime and off the trace
(`docs/proposals/feedback.md`). The page posts one to `/api/feedback`, a CloudFront
behavior listed ahead of `/api/*` because behaviors are matched in the order they appear;
behind it, an API Gateway REST API validates the body, checks the same Cognito token
(naming the `openid` scope, without which the authorizer refuses the page's access token),
and integrates directly with `events:PutEvents` on the `hr-super-agent-feedback` bus. A 30 day
archive on the bus keeps every vote; the rule that forwards them to Dynatrace as business
events turns on with the same two parameters as log forwarding. The `feedback` flag in
`web/features.json` is what puts the control on the page, and it is off.

The knowledge base corpus is refreshed by `scripts/seed-content.sh` (three docs repositories
at revisions pinned in the script, Markdown only, `aws s3 sync --delete` to `docs/<source>/`
in the content bucket) followed by `scripts/ingest.sh`. A scheduler runs the same ingestion
nightly. The tools gateway target is named `docs`, so the MCP tools are `docs___Retrieve` and
`docs___AgenticRetrieveStream`.

Two context keys exist for experiments and default off: `-c bind_runtime_to_gateway=true`
adds `allowedWorkloadConfiguration` to the runtime authorizer, and
`-c target_credentials=GATEWAY_IAM_ROLE` makes the gateway sign requests to the runtime
instead of passing the user token through. Neither works against the deployed JWT runtime
today; the decision log records why.

## Local Development

```sh
cd agent && uv run -- uvicorn hr_agent.app:app --port 8080 --reload
curl -N -X POST localhost:8080/invocations -H 'content-type: application/json' \
  -d '{"threadId":"t","runId":"r","messages":[{"id":"1","role":"user","content":"hello"}]}'
```
