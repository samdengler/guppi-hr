# Implementation plan

Seven phases. Each ends with a deploy and a browser check so the repository is always
one working step past guppi-gpt. Tick a phase when its "done when" holds and the decision
log has an entry for any choice made along the way.

## Target architecture

Page (plain text, Google sign-in) > CloudFront > edge gateway (JWT, WAF) > orchestrator
Runtime (AG-UI, Sonnet). Orchestrator > agents gateway (runtime targets, JWT
passthrough) > Profile, Pay, Travel sub-agent Runtimes (A2A, Haiku). Sub-agents and
orchestrator > tools gateway (MCP, JWT passthrough) > HR tools MCP server Runtime
(DynamoDB) and the Bedrock knowledge base (synthetic HR policy corpus). One container
image, role by `AGENT_ROLE`. The user's Cognito token travels every hop.

Delegation for one turn:

1. The page sends the thread plus `state` from the previous run (`activeDomain`,
   `pendingAction`).
2. The orchestrator routes: domain, confidence band, alternatives; a follow-up stays in
   `activeDomain`; below the threshold it asks one clarifying question and ends the run.
3. On delegation: `STEP_STARTED` with the domain, A2A call with recent turns and the
   user token, the sub-agent's text streamed as the reply, `STEP_FINISHED`.
4. A write goes through `propose_*` (exact change echoed, proposal id in
   `pendingAction`) and, on an affirmative next turn, `commit_*` with that id; the tool
   writes the audit record with the trace id and clears `pendingAction`.
5. The run ends with `STATE_SNAPSHOT`; the run log line gains `domain`, `confidence`,
   `alternatives`, `delegated_to`, `confirmed`.

## Phases

- [ ] **Phase 1: Bootstrap.** Fetch guppi-gpt history; rename packages, stack, hostnames
  (`hr.dengler.io`, `auth-hr.dengler.io`), brand; rewrite AGENTS.md and README for the new
  layout; Google redirect URI added by Sam. Done when `uv run -- pytest` and `cdk synth`
  pass, the stack deploys, and the unchanged chat works at the new hostname.
- [ ] **Phase 2: HR tools server.** `agent/src/hr_agent/tools/`: an MCP server (streamable
  HTTP, port 8000) with `get_profile`, `propose_address_change`, `commit_change`,
  `get_direct_deposit`, `propose_direct_deposit_change`, `list_pay_statements`,
  `open_ticket`; DynamoDB tables `employees`, `proposals`, `tickets`, `audit`, seeded per
  subject on first read; a Runtime with protocol MCP and a second MCP target on the tools
  gateway. Done when the orchestrator lists both `docs___*` and `hr___*` tools and a
  commit without a proposal id is refused.
- [ ] **Phase 3: Sub-agents.** `agent/src/hr_agent/agents/{profile,pay,travel}.py`: one
  Strands agent each with its prompt, its subset of `hr___*` tools plus `docs___Retrieve`,
  wrapped in `A2AServer`; three Runtimes with protocol A2A and JWT authorizers; the agents
  gateway with three runtime targets and `AGENTCORE_RUNTIME_URL` set to each gateway path.
  Agent card descriptions written to be mutually distinguishable. Done when each sub-agent
  answers an A2A `message/send` through the gateway with the user's token, and a proposal
  from one call is committed by the next.
- [ ] **Phase 4: Orchestrator.** Routing step as structured output before the main loop;
  sub-agents as tools built from `A2AAgent` with the caller's token; `state` in and
  `STATE_SNAPSHOT` out; clarifying question below the threshold; `STEP_*` events; run log
  fields. Done when the four scenarios pass end to end from curl.
- [ ] **Phase 5: Page.** Keep `state` from `STATE_SNAPSHOT` and send it on the next run;
  status line per step ("Asking the Pay agent...", "Pay agent answered"); domain tag on
  the reply label; brand from one constant. Done when `npm test` passes and the scenarios
  pass in the browser.
- [ ] **Phase 6: Evaluation and observability.** `evals/utterances.jsonl` (about 60
  labeled utterances: three domains, general questions, ambiguous cases) and
  `evals/route.py` reporting accuracy per domain with write-access weighting; the four
  scenarios as pytest cases against a fake sub-agent; log delivery and alarms for the four
  new runtimes; Dynatrace dashboard tiles for routing. Done when the script runs locally
  against Bedrock and prints a table, and the scenario tests are green.
- [ ] **Phase 7: Docs and handoff.** `docs/design.md` and the decision log level with the
  code; README status; `docs/demo.md` walking the four scenarios. Done when a fresh
  reader can deploy and run the demo from the README alone.

## The four scenarios

| Scenario | Turns | Expected |
| --- | --- | --- |
| Disambiguation | "I need to update my information" | One clarifying question naming Profile and Pay; no delegation; low confidence logged |
| Confirmation | "Change my home address to 419 Glendale Ave, Decatur GA 30030" then "yes" | Profile agent proposes and echoes the exact value; nothing written until the second turn; audit record carries the trace id |
| Sticky context | After the address change: "what about my emergency contact?" | Stays in Profile without re-routing; the reply refers to the same record |
| Topic shift and escalation | "How many buddy passes do I get?" then "I need to talk to someone" | Re-routes to Travel on the clear shift; `open_ticket` on the second turn with the id in the reply |

## Routing policy, first cut

Confidence bands: `high` delegates; `medium` delegates only when the domain equals
`activeDomain`, otherwise asks; `low` asks. Pronouns and ellipsis never re-route. A
clear topic shift (a named domain other than the active one at `high`) re-routes and
clears `pendingAction`. Adjust after the first eval run and record the change.

## Out of scope for the MVP

Self-service agent registration, AgentCore Memory, business dashboards, topic
clustering, QA sampling, multi-model tiering, AgentCore Evaluations (after phase 6),
Cedar per-target policies on the agents gateway.
