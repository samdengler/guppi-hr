# HR Super Agent

An MVP of an HR employee assistant, shown on the page as "HR Assistant", live at
`https://hr.dengler.io`. It starts from guppi-gpt, a one page, plain text chat behind Google
sign-in, merged in with its history and renamed. The page is served from CloudFront, the
stream runs through an AgentCore Gateway to a Strands agent on AgentCore Runtime, and the
agent reads a Bedrock Knowledge Base through a second gateway.

The MVP puts an orchestrator in front that routes each turn to Profile, Pay, or Travel
sub-agents over A2A, backed by an HR tools MCP server with a confirmation step before every
write. [`docs/plan.md`](docs/plan.md) has the target architecture and the phases.

![guppi-gpt runtime architecture, inherited unchanged](docs/guppigpt-architecture-runtime.png)

The stack is [Amazon Bedrock](https://aws.amazon.com/bedrock/) end to end, with the page
and its state kept deliberately small. In brief:

**Agent and model**

* [AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html)
  hosts the agent container, written with [Strands Agents](https://strandsagents.com/).
* Two [AgentCore Gateways](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html):
  the edge gateway holds the runtime as its target and checks the caller's JWT; the tools
  gateway exposes the knowledge base as an [MCP](https://modelcontextprotocol.io/) tool.
* [Bedrock Knowledge Bases](https://aws.amazon.com/bedrock/knowledge-bases/) holds the
  documentation the agent searches, synced nightly from S3.
* A Claude model answers through a
  [cross-region inference profile](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html).
* The wire format is [AG-UI](https://docs.ag-ui.com/): one HTTP request per turn, a
  server-sent event stream of text deltas, tool events, and run boundaries back, read by
  [`@ag-ui/client`](https://www.npmjs.com/package/@ag-ui/client). See guppi-gpt's design,
  [wire format section](docs/guppigpt-design.html#wire-format).
* No Lambda function in the request path; the only ones in the account belong to
  Dynatrace's own AWS integration stack.

**Sign-in and state**

* Google sign-in through an [Amazon Cognito](https://aws.amazon.com/cognito/) user pool,
  with [PKCE](https://datatracker.ietf.org/doc/html/rfc7636) in the browser. The user's
  token travels every hop up to the tools gateway.
* The session persists across reloads through a rotated refresh token in IndexedDB
  (guppi-gpt design section [request flow](docs/guppigpt-design.html#request-flow)).
* Chat history is browser-local and behind a flag
  ([proposal](docs/proposals/local-history.md)).
* Feature flags are an [OpenFeature](https://openfeature.dev/) provider over a committed
  JSON file, [`web/features.json`](web/features.json), with browser-wide overrides from a
  URL-only settings page at `/flags.html` ([proposal](docs/proposals/feature-flags.md)).
* Each conversation is written to a private S3 bucket for thirty days under a keyed
  pseudonym rather than the account id, readable only through a dedicated investigator
  role ([proposal](docs/proposals/conversation-logging.md)).

**Observability and guards**

* Never behind a flag. The container exports [OpenTelemetry](https://opentelemetry.io/)
  spans, the gateways and runtime ship vended logs, and a thumbs up or down on a reply
  becomes an [EventBridge](https://aws.amazon.com/eventbridge/) event through a REST API.
* All of it lands in a [Dynatrace](https://www.dynatrace.com/) tenant alongside RUM from
  the page, with one dashboard ([`docs/dynatrace/dashboard.json`](docs/dynatrace/dashboard.json)).
  The trace path, the log path, and the correlation story are in guppi-gpt's design,
  [observability section](docs/guppigpt-design.html#observability).
* CloudWatch alarms on the gateways, the runtime, the model, billing, and the feedback
  queue ([proposal](docs/proposals/operations.md)), and [AWS WAF](https://aws.amazon.com/waf/)
  in front of the edge gateway.

## Documentation

| Document | Contents |
| --- | --- |
| [`docs/handoff.md`](docs/handoff.md) | What the MVP is, its sources, the platform facts it relies on, how to start |
| [`docs/plan.md`](docs/plan.md) | Target architecture, the seven phases, the four conversation scenarios, the routing policy |
| [`docs/decision-log.md`](docs/decision-log.md) | Every decision from D1 on, with status |
| [`docs/guppigpt-design.html`](docs/guppigpt-design.html) | guppi-gpt's design: requirements, request flow, wire format, security and cost limits |
| [`docs/guppigpt-decision-log.html`](docs/guppigpt-decision-log.html) | guppi-gpt's revision history and reversed decisions |
| [`docs/guppigpt-architecture.html`](docs/guppigpt-architecture.html) | guppi-gpt's architecture diagrams; PNG exports sit beside it |

The guppi-gpt documents describe what this repository inherited and stay unchanged
(D17). The HTML documents are self-contained; open them in a browser.

## Layout

| Path | Contents |
| --- | --- |
| `docs/` | Plan, decision log, handoff, and guppi-gpt's design documents |
| `infra/` | AWS CDK app (Python), one stack named `HrSuperAgent` |
| `agent/` | The agent container: FastAPI serving AG-UI over SSE on the AgentCore Runtime contract |
| `web/` | The static page: sources in `src/`, esbuild bundle in `dist/` |
| `scripts/` | `deploy.sh`, `seed-content.sh` (refresh the knowledge base corpus), `ingest.sh` (index it) |

## Prerequisites

* AWS credentials for the account that holds the `dengler.io` hosted zone and guppi-gpt's `GuppiGpt` stack, region `us-east-1`
* [uv](https://docs.astral.sh/uv/), Node 22 or later (for the CDK CLI via `npx` and the page build), a Docker daemon for the arm64 image build (Colima with the `docker` CLI works; `colima start` before deploying)
* [1Password CLI](https://developer.1password.com/docs/cli/) signed in, holding the item
  `GuppiGPT Google OAuth` in the `Personal` vault as an API Credential (`username` is the client id, `credential` is the client secret)
* `jq` and the AWS CLI

## Commands

```sh
uv sync --all-packages --dev # install everything
uv run -- pytest             # agent and stack tests
scripts/deploy.sh            # cdk deploy with secrets read from 1Password, build and sync the page
scripts/deploy.sh --require-approval never # the same, from a shell with no terminal (a Claude `!` command)
scripts/deploy.sh --hotswap  # any extra arguments go to cdk deploy
scripts/deploy.sh --site-only # publish the page only, no cdk deploy or image push
scripts/seed-content.sh      # clone the three docs repositories and sync Markdown to the content bucket
scripts/ingest.sh            # start one ingestion job and wait for it
```

Flipping a feature flag: edit `web/features.json`, then run `scripts/deploy.sh
--site-only`. No `cdk deploy`. A visitor's own override, from `?ff=` or from the
settings page at `/flags.html` (reachable only by URL, linked from nowhere), applies to
every tab of their browser. Details in
[`docs/proposals/feature-flags.md`](docs/proposals/feature-flags.md).

## Status

Phase 1 of [`docs/plan.md`](docs/plan.md) is deployed: the stack `HrSuperAgent` was created
on 28 Sep 2026 and the chat was checked in the browser at `https://hr.dengler.io`. Behavior
is guppi-gpt's, unchanged. Notes:

* The stack shares its AWS account and the `dengler.io` zone with `GuppiGpt`. The zone apex
  placeholder record (which Cognito needs before it issues `auth-hr.dengler.io`) and
  CloudWatch Transaction Search belong to `GuppiGpt`; `-c own_account_singletons=true`
  makes this stack create them, for the day `GuppiGpt` is removed (D16).
* Sign-in reuses guppi-gpt's Google OAuth client, which lists
  `https://auth-hr.dengler.io/oauth2/idpresponse` as a second redirect URI (D10).
* The knowledge base is empty until `scripts/seed-content.sh` and `scripts/ingest.sh` run;
  phase 2 replaces its corpus with synthetic HR policy content (D5).
* No alarm email is subscribed; set `HR_ALARM_EMAIL` on the next deploy to add one.
* Conversation logging is on, 30 day retention, as in guppi-gpt; the re-identification
  procedure is in `docs/proposals/conversation-logging.md`.
* Traces, vended logs, and feedback events go to guppi-gpt's Dynatrace tenant under the
  service `hr_super_agent.DEFAULT`. RUM is off: no beacon origin is set and the RUM script
  is not vendored in this checkout.
* The edge gateway's front door answers 403 for any request body containing an http or
  https URL whose host is localhost, 127.0.0.1, or 169.254.169.254. Because the page
  resends the whole thread, one such URL ends the conversation; New chat is the way out.

## Sign-in session

The page keeps the refresh token in IndexedDB, restores the session with a silent refresh
on load, rotates the refresh token on every use (the app client has rotation enabled with a
30 second grace period), and clears it on sign out. The access and id tokens stay in memory.
