# Handoff: HR Super Agent MVP

Written 28 Sep 2026 by Claude in a Cowork session with Sam, for the Claude Code session
that builds the MVP. Sam reviews the plan in the Claude Docs artifact "HR Super Agent
MVP: Plan and Handoff" (https://claude.ai/code/artifact/656e39e0-4038-4509-ad94-91c6ad671a3e);
this file and its two neighbors are the repo copy.

## What the MVP is

An HR employee assistant with the guppi-gpt page in front and a new agent layer behind:

- One orchestrator (Strands agent on AgentCore Runtime, AG-UI over SSE, as guppi-gpt)
  that routes each turn to one of three A2A sub-agents or answers from the knowledge base.
- Three sub-agents (Profile, Pay, Travel) as Strands `A2AServer`s on their own Runtimes,
  reached through an agents gateway with runtime targets and JWT passthrough.
- One HR tools MCP server on Runtime behind the existing tools gateway, backed by
  DynamoDB, with task-shaped tools and a propose/commit pair for every write.
- Four conversational behaviors the ASAPP analysis names as Build: routing with a
  confidence band, one clarifying question when confidence is low, sticky domain across
  turns via the AG-UI `state` round trip, and confirmation before any write.

Everything else in guppi-gpt (sign-in, edge gateway, knowledge base, conversation
logging, feedback, flags, Dynatrace, alarms) carries over with names and hostnames
changed. See `docs/plan.md` for the phases and `docs/decision-log.md` for D1 to D15.

## Sources

1. ASAPP vs AWS AgentCore: Platform Capability Analysis (Claude Docs artifact
   5197bf00-b1a9-4cca-8c98-27dd8116f5d0). The NFRs, the Buy/Build matrix, the MVP cut
   line, the routing measurement approach (domain, confidence band, alternatives, logged).
2. MCP Tools and A2A Sub-Agents as Reusable Capabilities (Claude Docs artifact
   8760dd90-43fa-419b-9d20-aba31f2f7246). Code decides the next step: MCP tool. The
   model decides with domain judgment: A2A sub-agent. Tools are task-shaped.
3. guppi-gpt at commit 8baf911. Read its `AGENTS.md` and `README.md` first, then
   `agent/src/guppi_agent/agent.py`, `app.py`, `web/src/app.js`,
   `infra/guppi_gpt_infra/stack.py`. The Claude Docs artifacts are readable only from a
   Claude session with the Claude Docs connector; if this session lacks it, the plan and
   decision log carry what matters.

Platform facts checked on 28 Sep 2026:

- AgentCore Runtime hosts A2A agents with protocol `A2A` on port 9000, agent card at
  `/.well-known/agent-card.json`, invoked with `Authorization: Bearer` and the
  `X-Amzn-Bedrock-AgentCore-Runtime-Session-Id` header
  (https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-a2a.html).
- A gateway fronts a runtime through the HTTP runtime target
  (`http.agentcoreRuntime.arn`), path-based routing at `/{targetName}/invocations`,
  credential provider JWT passthrough; this is the target type guppi-gpt's edge gateway
  already uses (https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-target-http-runtime.html).
  The runtime's agent card advertises the runtime's own URL, so set
  `AGENTCORE_RUNTIME_URL` on each sub-agent runtime to its gateway path or the A2A client
  will bypass the gateway (https://dev.classmethod.jp/en/articles/agentcore-gateway-agent-target-a2a/).
- Strands: `A2AServer` from `strands-agents[a2a]`; `A2AAgent(endpoint=..., client_config=...)`
  for authenticated calls to a remote agent; `A2AClientToolProvider` from
  `strands-agents-tools[a2a_client]` (https://strandsagents.com/docs/user-guide/concepts/multi-agent/agent-to-agent/).
- MCP on Runtime is protocol `MCP`, port 8000, streamable HTTP. Verify the current
  FastMCP stateless-HTTP requirement in the AgentCore docs before building phase 2.

## How to start

1. Confirm with Sam that the Google OAuth client for GuppiGPT has the redirect URI
   `https://auth-hr.dengler.io/oauth2/idpresponse` (decision D10). Without it the
   federated sign-in fails after the first deploy. If Sam prefers a new client, add a
   1Password item `HR Super Agent Google OAuth` in the same shape and point
   `scripts/deploy.sh` at it.
2. Phase 1: commit these four files first (they are untracked as handed over), then
   `git remote add guppi ~/src/github.com/samdengler/guppi-gpt && git fetch guppi &&
   git merge guppi/main --allow-unrelated-histories` (decision D9), keeping this repo's
   `CLAUDE.md` over guppi-gpt's in the one conflict. Then rename in one commit:
   `guppi_agent` to `hr_agent`, `guppi-agent` to `hr-agent`, `guppi-gpt` to
   `hr-super-agent`, stack `GuppiGpt` to `HrSuperAgent`, constants `SITE_URL`,
   `AUTH_HOST`, `GATEWAY_NAME`, `RUNTIME_NAME`, `TARGET_NAME`, bucket and bus names,
   1Password item names left as they are, the brand `GuppiGPT` to `HR Assistant` (D15).
   Keep the Guppi tests green after the rename before changing behavior.
3. Deploy: `scripts/deploy.sh` on the Mac (Colima running, 1Password CLI signed in, AWS
   credentials for the dengler.io account, region us-east-1). Watch `.deploy/latest.log`.
   Open `https://hr.dengler.io`, sign in, ask a question, confirm the stream works.
4. Then phases 2 to 7 in `docs/plan.md`.

## Working conventions

- Every phase ends deployed and checked in the browser; do not stack phases undeployed.
- Record every choice not already in `docs/decision-log.md` as a new entry (D16 on),
  status Proposed, and list the new numbers in the next message to Sam.
- The runtime, the sub-agents and the tools server share one image; a role is chosen by
  `AGENT_ROLE`. Add a role, not a Dockerfile.
- Tests never reach Bedrock or a gateway; replace `build_strands_agent` (orchestrator)
  and the A2A client factory (sub-agents) the way guppi-gpt's tests do.
- Prose in docs and comments: no em-dashes or en-dashes, no second person.

## Things to ask Sam about when he is back

- The assistant's name (D15) and whether the Profile, Pay, Travel split is right (D4).
- Whether Dynatrace parameters from 1Password should be reused for this stack.
- The Sonnet model id on Bedrock, if a newer one than 4.5 is preferred (D8).
- The routing threshold after the first `evals/route.py` run.
