# HR Super Agent design

The HR Super Agent is an HR employee assistant, shown on the page as "HR Assistant". An
orchestrator on AgentCore Runtime reads each turn, routes it to a Profile, Pay, or Travel
sub-agent over A2A (or answers a general question itself from the HR policy knowledge
base), and every change to an employee record is proposed, read back, and committed only
after the employee confirms it. This document describes the system as deployed on
2 Oct 2026, after phase 8 moved it onto the chat.dengler.io platform. The decisions behind
it are D1 on in [decision-log.md](decision-log.md). The platform (guppi-gpt's `GuppiGpt`
stack, described in guppi-gpt's `docs/proposals/platform.md` and `guppigpt-design.html`
section 13) owns the page, Google sign-in through Cognito, CloudFront, AWS WAF, the edge
gateway with its per-user limits, reply feedback and feature flags; this stack reads the
platform's identifiers from `/guppi/platform/*` SSM parameters and owns everything that is
HR (D31, D34).

## What runs where

| Component | Runs on | Protocol | Code |
| --- | --- | --- | --- |
| Page | The platform's page at `chat.dengler.io/p/hr/`, with this project's manifest and extension under `/projects/hr/` in the platform's site bucket | AG-UI over SSE to `/api/hr/invocations` | `web/manifest.json`, `web/src/ext.js` |
| Edge gateway | The platform's AgentCore Gateway with AWS WAF and per-user limits; this stack's target `hr` on it, JWT passthrough | HTTP | `infra/.../stack.py` (the target and its invoke grant) |
| Orchestrator | AgentCore Runtime `hr_super_agent`, Sonnet 4.6 | AG-UI (HTTP contract, port 8080), on the platform kit's `create_app` | `agent/src/hr_agent/orchestrator.py`, `agent.py`, `app.py` |
| Agents gateway | AgentCore Gateway `hr-super-agent-agents`, three runtime targets, JWT passthrough | HTTP | `infra/.../sub_agents.py` |
| Profile, Pay, Travel sub-agents | AgentCore Runtimes `hr_super_agent_{profile,pay,travel}`, Haiku 4.5 | A2A (port 9000) | `agent/src/hr_agent/agents/` |
| Tools gateway | AgentCore Gateway `hr-super-agent-tools`, MCP | MCP | `infra/.../stack.py`, `hr_tools.py` |
| Knowledge base target `docs` | Bedrock Knowledge Base over `content/hr/` | MCP (`docs___Retrieve`) | `content/hr/`, `scripts/seed-content.sh` |
| HR tools target `hr` | AgentCore Runtime `hr_super_agent_tools` | MCP (port 8000, `/mcp`) | `agent/src/hr_agent/tools/` |
| HR data | DynamoDB `employees`, `proposals`, `tickets`, `audit` | | `tools/store.py`, `hr_tools.py` |

Every runtime runs the same container image; `AGENT_ROLE` picks orchestrator, tools,
profile, pay, or travel (`agent/src/hr_agent/__main__.py`, D11).

## One turn, end to end

1. The platform's page posts the whole thread (text only) to `/api/hr/invocations`. The
   extension's `onSend` hook puts on it the AG-UI `state` kept from the previous run's
   `STATE_SNAPSHOT`: `activeDomain` and `pendingAction` (D6, D23, D32). The request carries
   the user's access token from the platform's Cognito pool.
2. CloudFront rewrites the path to `/hr/invocations` on the platform's edge gateway, which
   applies WAF and the per-user limits, checks the token, and passes it through to the
   orchestrator runtime through the target named `hr`; the runtime checks it again.
3. The orchestrator makes one Converse call to Sonnet 4.6 that must answer through a
   `route` tool: domain, confidence band, alternatives, follow-up flag, and a clarifying
   question (D26).
4. `orchestrator.decide` applies the routing policy in code and picks one of three actions:
   delegate to a sub-agent, ask one clarifying question, or answer as a general question.
5. To delegate, the orchestrator emits `STEP_STARTED` (the page shows "Asking the Pay
   agent...") and sends one A2A `message/send` to `{agents gateway}/{domain}/invocations`
   with the user's token, the last ten turns, the pending change if it belongs to that
   domain, and the thread id as the A2A `contextId` (D27).
6. The sub-agent builds a Strands agent for this request only, with MCP tools that carry
   the user's token and thread id to the tools gateway, runs it, and answers with a text
   part and a data part: the pending change its run left and whether it committed one
   (D24).
7. The orchestrator emits the reply text, `STEP_FINISHED`, and a `STATE_SNAPSHOT` with the
   new `activeDomain` and `pendingAction`. The extension keeps that state for the next run,
   and on `STEP_STARTED` it tagged the reply "HR Assistant · Pay" through `ctx.setLabel`
   and set the status line.
8. The run log line gains `domain`, `confidence`, `alternatives`, `follow_up`, `action`,
   `delegated_to`, and `confirmed`.

A general question skips steps 5 to 7: the knowledge base agent in `agent.py` answers with
the policy search and, for escalation, `hr___open_ticket` (D14, D27).

## Routing policy

| Router says | Active domain | Pending change | Action |
| --- | --- | --- | --- |
| a follow-up, or the pending change's domain | any | in domain X | delegate to X |
| a follow-up | X | none | delegate to X |
| general, low, with real areas as alternatives | any | none | clarify |
| general otherwise | any | none | answer from the knowledge base |
| domain Y, high | any | any | delegate to Y (a pending change elsewhere is dropped) |
| domain Y, medium | Y, or no other area among the alternatives | | delegate to Y |
| anything else | | | clarify |

The clarifying question names the two leading candidate areas in plain words ("your
personal details, such as your home address or emergency contact, or your pay, such as
your direct deposit account"). The medium rule for an uncontested area came from the first
evaluation run (D28).

## Confirmation before writes

A write is two tool calls on the HR tools server (D7, D21):

- `propose_address_change`, `propose_emergency_contact_change`, or
  `propose_direct_deposit_change` validates the new value, stores a proposal (owner,
  thread, exact before and after, 15 minute expiry), and returns its id. Nothing changes.
- `commit_change(proposal_id)` refuses an empty or unknown id, another user's proposal
  (it reads as not found), a proposal from another conversation, an expired one, or one
  already committed. Otherwise one DynamoDB transaction marks the proposal committed,
  updates the employee record, and writes the audit entry with the trace id.

The page resends only text, so the proposal id would be lost between the proposing turn
and the "yes". The pending change therefore travels in AG-UI state: the sub-agent returns
it, the orchestrator puts it in `STATE_SNAPSHOT`, the page sends it back, and the
orchestrator hands it to the domain that made it, whose prompt spells it out for that one
turn. The state is written by the page and is only a hint to the model; the commit checks
above are what protect the record. A pending change lives for one turn: any turn that
does not propose again drops it.

## Identity on every hop

| Hop | Credential presented | Checked by |
| --- | --- | --- |
| Page to the platform's edge gateway | User's access token from the platform's Cognito pool | Platform gateway JWT authorizer |
| Platform edge gateway to orchestrator | Same token (passthrough) | Runtime JWT authorizer, on the platform pool and client |
| Orchestrator to agents gateway | Same token | Gateway JWT authorizer |
| Agents gateway to sub-agent | Same token (passthrough) | Runtime JWT authorizer |
| Sub-agent or orchestrator to tools gateway | Same token | Gateway JWT authorizer |
| Tools gateway to HR tools runtime | Gateway role (SigV4); user token in `X-Hr-User-Token` | Runtime IAM; the server verifies the header token against the platform pool's keys |
| Tools gateway to knowledge base | Gateway role | Bedrock |

The tools hop differs because an MCP gateway accepts only MCP targets, and an MCP target
cannot pass the caller's bearer token through: its outbound options are none, OAuth,
SigV4, or API key, and `Authorization` cannot be allowlisted for propagation (D19). The HR
tools server therefore trusts neither the gateway nor the header's presence: it verifies
the token's signature, issuer, expiry, token use, and client itself and takes `sub` from
it. Issuer, keys, clients, and audience are environment settings; the stack sets the
issuer from the platform's discovery URL and the client from its app client id. Every
JWT authorizer in this stack names the same pool and client, so the token the page holds
on chat.dengler.io is the one accepted on every hop. The Delta version
replaces token passthrough with on-behalf-of token exchange (RFC 8693) on PingFederate,
which Cognito cannot do (D20); with those settings the change is configuration.

## HR tools and data

| Tool | Domain | Effect |
| --- | --- | --- |
| `get_profile` | Profile | Name, employee id, job, home address, emergency contact |
| `propose_address_change` | Profile | Proposal only |
| `propose_emergency_contact_change` | Profile | Proposal only |
| `get_direct_deposit` | Pay | Account by its last four digits |
| `propose_direct_deposit_change` | Pay | Proposal only; keeps the last four digits of the account |
| `list_pay_statements` | Pay | Most recent biweekly statements |
| `commit_change` | Profile, Pay | Applies a confirmed proposal, writes the audit entry |
| `open_ticket` | all, and the general agent | Ticket for the HR team, id `HR-nnnnnn` |

Each signed-in user gets one synthetic employee record, derived from a hash of the token's
`sub` on first read. Nothing is real employee data. The knowledge base holds the
synthetic policies in `content/hr/` (D5).

## Sub-agents

| Domain | HR tools | Card description (first clause) |
| --- | --- | --- |
| Profile | get_profile, both address and contact proposals, commit_change, open_ticket | Reads and changes the employee's own personal record |
| Pay | get_direct_deposit, propose_direct_deposit_change, list_pay_statements, commit_change, open_ticket | Handles where and when the employee is paid |
| Travel | open_ticket | Answers travel benefit questions; read-only |

Every sub-agent also has `docs___Retrieve`. The descriptions, tools, and skills live in
`agents/domains.py`, which both the agent cards and the router read. A sub-agent shows the
value on file before asking for new values, and opens a ticket at once when the employee
asks for a person.

## Observability

- One trace per turn: the page mints `traceparent`, and it survives every hop, so the
  audit entry of a commit carries the orchestrator run's trace id (checked 29 Sep 2026).
- The orchestrator's run line, written by the kit's `guppi_agent` logger, carries the
  routing fields above; sub-agents log one line
  per request (domain, outcome, tool calls, duration); the tools server logs proposals,
  commits, refusals, and tickets without values.
- Every gateway and runtime in this stack delivers application logs to
  `/aws/vendedlogs/bedrock-agentcore/`, forwarded to Dynatrace when its parameters are set,
  and has a 5xx alarm on the alarm topic. The edge gateway's logs, WAF metrics and 4xx
  alarm are the platform's.
- `docs/dynatrace/dashboard.json` has three draft routing tiles over the run line, not yet
  run against the tenant.

## Routing evaluation

`evals/route.py` runs the 60 labeled utterances in `evals/utterances.jsonl` through the
real routing step and policy against Bedrock (about 35 seconds) and prints accuracy per
expected outcome, accuracy with write domains counted twice, a confusion table, and the
misses. The first run scored 58 of 60; the two misses led to D28, after which it scored
60 of 60. The corpus is small and was written by the same session that wrote the router,
so these numbers overstate real accuracy; a held-out set written by someone else is the
next step.

## Known limits and open items

- Trace export from the orchestrator to Dynatrace answers HTTP 404 (90 failures in the 24
  hours to 29 Sep 2026). The endpoint and token are the ones guppi-gpt uses, which had no
  traffic in the same week to compare against; the tenant needs a look.
- Sub-agent replies arrive whole rather than streamed, because the A2A call is
  `message/send`. The status line covers the wait.
- A sub-agent receives the last ten turns as text; it does not see earlier tool results.
- The runtimes accept any token from the platform pool's client; there is no allow-list
  of users (guppi-gpt's backlog item 8). The platform's per-user rate limit counts every
  project's requests together.
- Stored browser history keeps text only: AG-UI state and the reply's agent tag do not
  survive a reload or a switched thread, so a pending change is proposed again and a
  reopened reply shows the plain "HR Assistant" label (D33).
