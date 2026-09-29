# HR Super Agent

An MVP of an HR employee assistant, shown on the page as "HR Assistant", live at
`https://hr.dengler.io`. An orchestrator on Amazon Bedrock AgentCore Runtime routes each
turn to a Profile, Pay, or Travel sub-agent over A2A, or answers general questions from
an HR policy knowledge base; sub-agents act on the employee's own records through an HR
tools MCP server, and every change is proposed, read back, and committed only after the
employee says yes. All employee data and policies are synthetic.

It is an iteration of guppi-gpt, a one page plain text chat behind Google sign-in, merged
in with its history and renamed. [`docs/design.md`](docs/design.md) describes the system
as built; [`docs/demo.md`](docs/demo.md) walks the four scenarios.

## What it does

- **Routing.** A Sonnet 4.6 routing step names an area, a confidence band, and the
  alternatives; code decides whether to delegate, answer, or ask one clarifying question.
  Follow-ups stay with the active area; a clear topic shift re-routes.
- **Sub-agents.** Profile (home address, emergency contact), Pay (direct deposit, pay
  statements), and Travel (pass travel policy, read-only) run as separate A2A servers
  behind their own AgentCore Gateway, each on Haiku 4.5.
- **Confirmation before writes.** Every change is a propose tool, the exact change read
  back, and a `commit_change` that only a confirmed, unexpired proposal from the same user
  and conversation passes. The commit writes an audit entry with the turn's trace id.
- **Escalation.** Asking for a person opens an HR ticket with an id.
- **The page.** Plain text, as in guppi-gpt, with a status line per delegation ("Asking
  the Pay agent...") and the answering agent on each reply label.

Inherited from guppi-gpt unchanged: Google sign-in through Cognito with PKCE and a rotated
refresh token, the edge gateway with AWS WAF and a per-user rate limit, feature flags
(`web/features.json`, `/flags.html`), browser-local history behind a flag, pseudonymous
conversation logging to S3 for 30 days, reply feedback to EventBridge, OpenTelemetry
traces, vended logs, and CloudWatch alarms. guppi-gpt's documents describe those parts.

## Documentation

| Document | Contents |
| --- | --- |
| [`docs/design.md`](docs/design.md) | Components, one turn end to end, routing policy, confirmation, identity per hop, tools, observability, limits |
| [`docs/demo.md`](docs/demo.md) | The four scenarios, what to type and what to expect, and how to check the logs and audit entries |
| [`docs/decision-log.md`](docs/decision-log.md) | Every decision, D1 to D28, with status |
| [`docs/plan.md`](docs/plan.md) | The seven phases (all done), the four scenarios, the first-cut routing policy |
| [`docs/handoff.md`](docs/handoff.md) | The brief this repository started from, and its sources |
| `docs/guppigpt-*.html`, `docs/proposals/` | guppi-gpt's design, decision log, diagrams, and proposals, kept unchanged (D17) |

## Layout

| Path | Contents |
| --- | --- |
| `agent/` | One container image for every runtime; `AGENT_ROLE` picks orchestrator, tools, profile, pay, or travel |
| `infra/` | AWS CDK app (Python), one stack `HrSuperAgent` |
| `web/` | The static page: sources in `src/`, esbuild bundle in `dist/` |
| `content/hr/` | The synthetic HR policy documents the knowledge base indexes |
| `evals/` | 60 labeled routing utterances and the offline routing evaluation |
| `scripts/` | `deploy.sh`, `seed-content.sh`, `ingest.sh` |

## Prerequisites

- AWS credentials for the account that holds the `dengler.io` hosted zone and guppi-gpt's
  `GuppiGpt` stack, region `us-east-1`, with Bedrock access to Claude Sonnet 4.6 and
  Haiku 4.5 through the `us.` inference profiles
- [uv](https://docs.astral.sh/uv/), Node 22 or later, a Docker daemon for the arm64 image
  build (Colima works; `colima start` first), `jq`, and the AWS CLI
- The [1Password CLI](https://developer.1password.com/docs/cli/) signed in, holding
  `GuppiGPT Google OAuth` in the `Personal` vault (API Credential: `username` is the client
  id, `credential` the secret); `GuppiGPT Dynatrace` there too turns on Dynatrace export
- The Google OAuth client lists `https://auth-hr.dengler.io/oauth2/idpresponse` as an
  authorized redirect URI (D10)

## First deploy and demo

```sh
uv sync --all-packages --dev   # install everything
uv run -- pytest               # agent and stack tests, no AWS needed
(cd web && npm ci && npm test) # page tests
scripts/deploy.sh              # image, stack, and page; about 15 minutes the first time
scripts/seed-content.sh        # sync content/hr/ to the knowledge base bucket
scripts/ingest.sh              # index it and wait
```

Then open `https://hr.dengler.io`, sign in, and follow [`docs/demo.md`](docs/demo.md).

In an account without guppi-gpt's `GuppiGpt` stack, run `npx aws-cdk@2 bootstrap` once and
deploy with `scripts/deploy.sh -c own_account_singletons=true`, so this stack creates the
zone apex record and Transaction Search itself (D16). The hostnames are constants at the
top of `infra/hr_super_agent_infra/stack.py`.

## Everyday commands

```sh
scripts/deploy.sh --reuse-parameters     # skip 1Password, reuse the stack's secrets (unattended)
scripts/deploy.sh --require-approval never  # no terminal to answer cdk's IAM prompt
scripts/deploy.sh --site-only            # publish the page only
uv run python evals/route.py             # routing accuracy against Bedrock, about 35 seconds
uv run -- ruff check .
```

Every deploy is logged to `.deploy/deploy-<timestamp>.log`, with `.deploy/latest.log`
pointing at the newest and a final `deploy exit=<code>` line. Flipping a feature flag is
an edit to `web/features.json` and `scripts/deploy.sh --site-only`.

## Status

All seven phases of [`docs/plan.md`](docs/plan.md) are deployed. The four scenarios
passed in the browser on 29 Sep 2026, and the routing evaluation scores 60 of 60 on its
own corpus (58 of 60 before D28). Notes:

- Waiting for review as Proposed: D24 to D28 from phases 3 to 6, and D1 to D3, D5 to D7,
  and D9 to D14 from the original brief, which the build followed.
- The stack shares its account and the `dengler.io` zone with `GuppiGpt`; the zone apex
  record and CloudWatch Transaction Search belong to `GuppiGpt`, and
  `-c own_account_singletons=true` makes this stack create them if `GuppiGpt` is removed
  (D16).
- Trace export to Dynatrace answers HTTP 404; the tenant needs a look
  ([design.md, known limits](docs/design.md#known-limits-and-open-items)).
- No alarm email is subscribed; set `HR_ALARM_EMAIL` on a deploy to add one.
- The edge gateway's front door answers 403 for any message containing a localhost or
  loopback URL; because the page resends the thread, New chat is the way out.
- On-behalf-of token exchange between agents and tools is the Delta version's identity
  model on PingFederate (D20).
