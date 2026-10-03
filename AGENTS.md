# guppi-hr instructions

## Project Overview

HR Super Agent is an MVP of an HR employee assistant, branded "HR Assistant" on the page,
at `https://chat.dengler.io/p/hr-diy/` (the Connect version in `connect/` is `/p/hr/`, D37). It began as an iteration of guppi-gpt
(`~/src/github.com/samdengler/guppi-gpt`), merged in with its history at commit 8baf911
and renamed (D9). Since phase 8 it is an agent project on the chat.dengler.io platform
that guppi-gpt became (`../guppi-gpt/docs/proposals/platform.md`): the platform's
`GuppiGpt` stack owns the page, Google sign-in, CloudFront, WAF, the edge gateway with its
per-user limits, reply feedback and feature flags, and publishes their identifiers as
`/guppi/platform/*` SSM parameters; this repository owns everything that is HR (D34).

An orchestrator routes each turn to Profile, Pay, or Travel sub-agents over A2A, or
answers general questions from the HR policy knowledge base; the sub-agents act on the
employee's own synthetic records through an HR tools MCP server with a propose and commit
pair for every write. The servers hold nothing between runs; the page carries
`activeDomain` and `pendingAction` in AG-UI state through this project's extension.

`docs/design.md` describes the system as built and `docs/demo.md` the four scenarios;
`docs/decision-log.md` records every choice (D1 on); `docs/plan.md` has the phases, all
done; `docs/phase-8.md` and `docs/phase-8-report.md` are the move onto the platform.
guppi-gpt's design document (`docs/guppigpt-design.html`), decision log
(`docs/guppigpt-decision-log.html`), and diagrams (`docs/guppigpt-architecture.html`) stay
as the record of what was inherited at the fork; the live platform's documents are in
guppi-gpt. When code and a decision disagree, change one of them in the same commit.

## Tech Stack

- Infrastructure: AWS CDK v2 in Python, one stack `HrSuperAgent`, region `us-east-1`, in
  the same account as guppi-gpt's `GuppiGpt` platform stack, whose `/guppi/platform/*`
  parameters it reads at deploy time
- Agent: Python 3.12, Strands Agents, arm64 container on AgentCore Runtime; the
  orchestrator's HTTP surface (AG-UI over SSE, validation, keepalive, run log, conversation
  log) is the platform kit, `guppi-agent` from guppi-gpt at tag `kit-v0.2.0`
- Model: Sonnet 4.6 for the orchestrator, Haiku 4.5 for the sub-agents, through the `us.`
  cross-region inference profiles (`ORCHESTRATOR_MODEL_ID` and `MODEL_ID` in the stack)
- Edge: the platform's CloudFront and edge gateway; this stack adds the runtime target
  `hr-diy`, so the orchestrator answers at `/api/hr-diy/invocations`
- Page: the platform's page at `/p/hr-diy/`, configured by `web/manifest.json`, with this
  project's extension `web/src/ext.js` bundled by esbuild as an ES module into
  `web/dist/ext.js` and published to `/projects/hr/`
- Package manager: uv workspace (`infra` and `agent` are members)
- Secrets: the Dynatrace values are CloudFormation parameters supplied from 1Password at
  deploy time; the image build reads a GitHub token as a BuildKit secret; nothing secret
  is checked in

## Project Structure

```
docs/
  handoff.md              # what the MVP is, its sources, how to start
  plan.md                 # target architecture, the eight phases, the four scenarios
  phase-8.md              # the brief that moved the project onto the platform
  phase-8-report.md       # what phase 8 landed, removed and checked
  decision-log.md         # D1 on, one row per decision, status Proposed, Approved or Reversed
  guppigpt-*.html         # guppi-gpt's design, decision log, and diagrams as at the fork
  proposals/              # guppi-gpt's backlog proposals as at the fork; new proposals are added beside them
  dynatrace/dashboard.json  # draft DQL dashboard tiles for the queries in docs/proposals/dynatrace.md
content/
  hr/                     # synthetic HR policy Markdown, synced by scripts/seed-content.sh (D5)
infra/
  app.py                  # CDK app entry
  hr_super_agent_infra/stack.py         # platform parameters, orchestrator runtime and its "hr" target, KB, tools gateway, logs, alarms
  hr_super_agent_infra/hr_tools.py      # HR tools tables, MCP runtime, hr target on the tools gateway
  hr_super_agent_infra/runtime_role.py  # the documented runtime execution role, one per runtime
  hr_super_agent_infra/sub_agents.py    # agents gateway, three A2A runtimes, runtime targets with token passthrough
  tests/                  # assertions against the synthesized template
agent/
  src/hr_agent/app.py         # app = create_app(build_strands_agent), the kit's HTTP surface
  src/hr_agent/agent.py       # build_strands_agent (the test seam) and the knowledge base agent for general questions
  src/hr_agent/__main__.py    # container entrypoint: AGENT_ROLE picks the server (D11)
  src/hr_agent/tools/         # HR tools MCP server: identity.py (X-Hr-User-Token, D19), records.py, store.py (D21), server.py
  src/hr_agent/orchestrator.py  # routing step (Sonnet), routing policy, A2A delegation, AG-UI state (D26, D27)
  src/hr_agent/pending.py       # the pending change: parsing tool results, the prompt paragraph (D23)
  src/hr_agent/agents/          # Profile, Pay, Travel sub-agents: domains.py (cards, tools), server.py (A2A executor, D24)
  Dockerfile                     # arm64; installs git and fetches the private kit with a build secret (D29)
  tests/
web/
  manifest.json           # the project on the platform: name, label, agent path, features, extension, suggestions; no theme
  package.json            # esbuild only; `npm run build` writes dist/ext.js, `npm test` runs node --test
  src/ext.js              # the extension: status lines, the agent tag via ctx.setLabel, the state round trip (D32)
  src/copy.js             # the wording: toolStatus, agentName, stepStatus, replyLabel, BRAND
  test/copy.test.js       # node:test coverage for copy.js
  test/ext.test.js        # the extension against a fake guppi object
  test/manifest.test.js   # the manifest's fields
  dist/                   # build output; not committed
evals/
  utterances.jsonl        # 60 labeled routing utterances (D13)
  route.py                # runs them through the routing step and policy against Bedrock
scripts/
  deploy.sh               # cdk deploy, then the manifest and extension to the platform's site bucket
  seed-content.sh         # clone the docs repositories at pinned revisions, sync Markdown to S3
  ingest.sh               # StartIngestionJob and wait
  browser-check.mjs       # the four scenarios on /p/hr-diy/ in a headless browser, screenshots in .deploy/
connect/                  # the Amazon Connect super-agent (/p/hr/): its own projects, lockfiles and
                          # stack GuppiConnect, excluded from this uv workspace; see connect/README.md
```

`connect/` was the guppi-connect repository until 2 October 2026. Work there runs from
that folder (`cd connect/agent && uv run -- pytest`, `connect/scripts/deploy.sh`), never
touches the HR stack, and reads the HR stack's gateway URLs from the root
`cdk-outputs.json`.

## Rules

- No Lambda functions in the request path or the content sync path by default. Lambda is
  a preference, not a ban: when a function is the right tool, propose it and get Sam's
  approval before building it. Approved so far: the Lambda functions inside Dynatrace's
  own AWS activation stack (`GuppiGPT-Dynatrace`, 7 Sep 2026), which sits outside
  `HrSuperAgent`.
- Secrets never enter files, `cdk.context.json`, or `-c` context values. Values the stack
  cannot produce (the Dynatrace token) are CloudFormation parameters with `no_echo`
  supplied by `scripts/deploy.sh` from 1Password. The GitHub token for the image build
  reaches Docker only as a BuildKit secret from the environment (D29).
- Never edit guppi-gpt from this repository. Platform changes are made there and reach
  this stack through the `/guppi/platform/*` parameters or a new kit tag.
- The agent image installs dependencies from `uv.lock` in a layer before the source is
  copied, so a code change rebuilds only the last layer; `.dockerignore` at the repo root
  limits the build context (and the CDK asset hash) to the agent files and the lockfile.
- Every change to the stack must keep `uv run -- pytest` green and
  `uv run -- cdk synth -c image_uri=<any ecr uri>` working without Docker.
- Prose in docs and comments: no em-dashes or en-dashes, no second person.
- The page renders plain text only, and the extension writes only plain text (status
  lines and the label); no Markdown parser, no `innerHTML` with model or user text.
- Tests replace the seams that reach Bedrock or a gateway: `hr_agent.agent.build_strands_agent`
  (the whole orchestrator, in the app tests), the orchestrator's `router`, `sender`, and
  `general_factory`, the sub-agent executor's `runner`, and the tools server's store and
  verifier (DynamoDB in moto, tokens signed with a test key). Nothing in `agent/tests`
  reaches Bedrock or a gateway. `evals/route.py` is the one thing that calls Bedrock on
  purpose, and it is not a test.
- The orchestrator, the sub-agents, and the tools server share one container image; a
  role is chosen by `AGENT_ROLE`. Add a role, not a Dockerfile (D11).
- Every phase in `docs/plan.md` ends deployed and checked in the browser; phases are not
  stacked undeployed.
- Every finding about a service's behavior (an AWS service above all, or another tool),
  expected or not, gets an entry in `docs/aws-feedback.md` the day it is found: what was
  expected, what happened, the evidence, the ask, and a status. Update the status when it
  changes; never delete an entry.
- Every technique tried to cut latency gets an entry in `docs/latency-log.md` with its
  measured effect, including one that was dropped or made no difference.
- Every choice not already in `docs/decision-log.md` gets a new entry with status
  Proposed, listed in the next message to Sam.
- Every named AWS resource differs from its `GuppiGpt` counterpart, since both stacks
  share the account (D18). Transaction Search stays with `GuppiGpt` (D16).
- Observability that reads state already reaching the browser is never behind a feature
  flag. The `features` in `web/manifest.json` mostly gate product features
  (`docs/proposals/feature-flags.md`); `rum` is the exception, since turning it on starts
  a vendor library on the page (`docs/proposals/dynatrace.md`).

## Dependency Management

```sh
uv sync --all-packages --dev        # install all workspace members and dev tools
uv add --package hr-agent httpx  # add a dependency to one member
uv run -- pytest                    # run all tests
uv run -- pytest agent/tests -v
uv run -- ruff check .
cd web && npm ci && npm run build   # bundle the extension into web/dist/ext.js
cd web && npm test                  # node:test coverage for the extension, the wording and the manifest
```

The kit is a git dependency (`[tool.uv.sources]` in `agent/pyproject.toml`); a new kit
tag is `uv add --package hr-agent "guppi-agent @ git+https://github.com/samdengler/guppi-gpt@<tag>#subdirectory=agent"`
and a deploy. `uv lock` on the host reads the private repository through the `gh`
credential helper.

Flipping a feature flag: edit `features` in `web/manifest.json`, then run
`scripts/deploy.sh --site-only` to republish the manifest; no `cdk deploy` and no
CloudFormation parameter. The platform merges the manifest's flags over its own
`config.json` defaults, and browser overrides from `/flags.html` still win.

- Always use `uv add --package <member>` for dependencies, not manual pyproject edits.
- Run `uv sync --all-packages --dev` after pulling changes.

## Deploying

`scripts/deploy.sh` reads the Dynatrace OTLP endpoint and API token from 1Password
(`op://Personal/GuppiGPT Dynatrace/...`, an API Credential item whose `hostname` is the
endpoint and `credential` is the token) when it can; when the read fails it passes
neither and CloudFormation reuses the stack's existing values. It sets `HR_GITHUB_TOKEN`
from `gh auth token` (unless already set) for the image build, runs `cdk deploy
HrSuperAgent`, builds `web/` (`npm ci`, `npm run build`), copies `web/manifest.json` and
`web/dist/ext.js` to `s3://<platform site bucket>/projects/hr/` with
`Cache-Control: no-cache`, and invalidates `/projects/hr/*` on the platform's
distribution; the bucket and distribution come from `/guppi/platform/site-bucket-name`
and `/guppi/platform/distribution-id`. `HR_ALARM_EMAIL`, when set, becomes the
`AlarmEmail` parameter and subscribes that address to the alarm topic.
`HR_INVESTIGATOR_ARN`, when set, becomes the `InvestigatorPrincipalArn` parameter and
narrows the conversation investigator role's trust to that one ARN; left unset, the role
trusts the account root. `scripts/deploy.sh --site-only` skips `cdk deploy` (so no image
build or push) and only republishes the manifest and the extension. Every run is also
written to `.deploy/deploy-<timestamp>.log` with `.deploy/latest.log` pointing at the
newest and a final `deploy exit=<code>` line, so a Claude session can watch a deploy
started from any terminal. Deploys run on Sam's Mac; the Docker image is built there for
arm64. A deploy started without a terminal (a `!` command in a Claude session) cannot
answer cdk's approval prompt for IAM changes and exits 1 before touching the stack; pass
`--require-approval never` there. `--reuse-parameters` skips 1Password and lets
CloudFormation reuse the stack's Dynatrace values, so an unattended deploy never waits on
a locked vault.

`-c own_account_singletons=true` makes the stack create the Transaction Search
configuration itself. It stays off while `GuppiGpt` exists, since a second copy fails the
deploy (D16).

The platform contract. The stack reads `jwt-discovery-url` and `user-pool-client-id`
(every JWT authorizer here: the orchestrator runtime, the three sub-agent runtimes, the
agents gateway and the tools gateway, plus the HR tools server's `TOKEN_ISSUER` and
`TOKEN_ALLOWED_CLIENTS`), `edge-gateway-id` (the target `hr`), `edge-gateway-role-arn`
(the `InvokeAgentRuntime` grant on the orchestrator, attached to the platform gateway's
role as this stack's own policy), and `site-url` (the `SiteUrl` output). The platform's
CloudFront function rewrites `/api/hr-diy/invocations` to `/hr-diy/invocations` on its gateway,
and `/p/hr-diy/` to its one page, which loads `/projects/hr-diy/manifest.json` and imports the
extension it names.

The orchestrator runtime's request header allowlist names `Authorization` and
`traceparent`; without the first the runtime validates the bearer and drops it, and the
agent has no token for the tools gateway; without the second the trace the page started
ends at the runtime. The `hr` target's allowed request headers name the session id header
and `traceparent` for the same reason. The runtime container receives `TOOLS_GATEWAY_URL`,
`MODEL_ID`, `ROUTER_MODEL_ID`, `RETRIEVE_TOOL`, `ORCHESTRATOR_EXTRA_TOOLS`,
`AGENTS_GATEWAY_URL`, `LOG_LEVEL`, `OTEL_PYTHON_EXCLUDED_URLS`, `CONVERSATION_LOG_ENABLED`,
`CONVERSATION_LOG_BUCKET`, and `CONVERSATION_LOG_KEY_SECRET_ARN` from the stack; the
container starts under `opentelemetry-instrument` (`agent/Dockerfile`), and the runtime
supplies the ADOT exporter settings itself. `docs/proposals/traceability.md` describes
the identifiers and where each one is logged.

Conversation logging (`docs/proposals/conversation-logging.md`) is behind two switches,
both on. `CONVERSATION_LOG_ENABLED` in `stack.py` decides whether the agent writes one
record per thread to this stack's conversation log bucket, uses the keyed pseudonym on
the run line, and tells the model that conversations are logged; `"logging"` in the
manifest's `features` decides whether the page's hint and empty state say so. Flip the
runtime switch and deploy first, then the page switch, so the page never promises a
record that does not exist; turn them off in the other order. The bucket, the KMS key,
the HMAC secret, and the investigator role are created either way. The investigator role
may list the platform's user pool, whose users the thread records' subjects now are.

The instrumented container's spans are refused until CloudWatch Transaction Search is on
for the account; the `GuppiGpt` stack owns that setting. The billing alarm reads
`AWS/Billing EstimatedCharges`, which exists only after billing alerts are enabled in the
account's billing preferences. The two gateways' and every runtime's `APPLICATION_LOGS`
are delivered to CloudWatch Logs groups under `/aws/vendedlogs/bedrock-agentcore/`, 30 day
retention, alongside 5xx alarms on each, runtime p90 latency, and Bedrock throttling, all
notifying the alarm topic (`docs/proposals/operations.md`). The edge gateway's logs, WAF
alarms and 4xx rate alarm are the platform's.

Dynatrace: `DynatraceOtlpEndpoint` and `DynatraceApiToken` are stack parameters that
default empty, and each Dynatrace path stays dark while either is empty. With both set,
this stack exports traces and forwards its vended logs through Firehose to the same
tenant as guppi-gpt; its spans carry the service name `hr_super_agent.DEFAULT`. Real user
monitoring and reply feedback are the platform's.

The knowledge base corpus is refreshed by `scripts/seed-content.sh` (Markdown from
`content/hr/`, `aws s3 sync --delete` to `docs/` in the content bucket) followed by
`scripts/ingest.sh`. A scheduler runs the same ingestion nightly. The tools gateway target
is named `docs`, so the MCP tools are `docs___Retrieve` and `docs___AgenticRetrieveStream`.

Two context keys exist for experiments and default off: `-c bind_runtime_to_gateway=true`
adds `allowedWorkloadConfiguration` naming the platform's edge gateway to the
orchestrator's authorizer, and `-c target_credentials=GATEWAY_IAM_ROLE` makes the `hr`
target sign requests to the runtime instead of passing the user token through. Neither
works against a JWT runtime today; guppi-gpt's decision log records why.

## Checking a deploy

`scripts/browser-check.mjs` runs the four scenarios on `https://chat.dengler.io/p/hr-diy/` in
headless Chrome with the session from `$HOME/.config/guppi/test-session.json` (written by
`../guppi-gpt/scripts/test-token.sh`; Playwright is a dev dependency of `web/`) and saves
`.deploy/phase-8-<scenario>.png`. Tokens
from that script are used only inside command substitution; never print, log, or commit
one.

## Local Development

```sh
cd agent && uv run -- uvicorn hr_agent.app:app --port 8080 --reload
curl -N -X POST localhost:8080/invocations -H 'content-type: application/json' \
  -d '{"threadId":"t","runId":"r","messages":[{"id":"1","role":"user","content":"hello"}]}'
```
