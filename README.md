# guppi-connect

The HR assistant with Amazon Connect Customer's Agentic CX designer as its super-agent,
in place of hr-super-agent's Strands orchestrator. The Profile, Pay and Travel A2A
sub-agents, the HR tools MCP server and both AgentCore gateways are hr-super-agent's,
unchanged. It is a project on the chat.dengler.io platform
([guppi-gpt](https://github.com/samdengler/guppi-gpt)), live at
`https://chat.dengler.io/p/hr-connect/`, beside hr-super-agent's own page at
`https://chat.dengler.io/p/hr/`. Both pages run the same four scenarios, so the two
super-agents can be compared turn by turn.

How a turn travels: the page posts AG-UI to `/api/hr-connect/invocations`; a bridge on
the platform agent kit (`agent/`) turns each run into a Connect chat turn on a contact
flow that holds the Agentic CX block; the canvas routes the turn and calls the
sub-agents over A2A and the tools gateway over MCP with the employee's token; the bridge
relays the canvas's replies back as AG-UI text messages.

The canvas is built from code with the designer SDK (`acxd/`), and can also be driven
over Connect chat directly (`scripts/chat.py`, `scripts/route_eval.py`). A small Lambda
(`mock/`) echoes headers and imitates the sub-agents, so the canvas can be tested
without an employee token.

## Documentation

| Document | Contents |
| --- | --- |
| [`docs/connect-super-agent.html`](docs/connect-super-agent.html) | The first analysis: Connect's options for an orchestrating agent, four ways to put Connect in front, a comparison with the custom super-agent and ASAPP, gaps, pricing |
| [`docs/acxd-super-agent.html`](docs/acxd-super-agent.html) | The design this repository built: the designer canvas as the super-agent over the existing sub-agents and tools, with the spike's results |
| [`docs/spike-report.md`](docs/spike-report.md) | What the spike proved over Connect chat, with real and mock sub-agents, and what is still open |
| [`docs/platform-plan.md`](docs/platform-plan.md) | How the project joined chat.dengler.io: the token gate, the bridge design, the phases |

The HTML documents are self-contained copies of two Claude Docs; open them in a browser.

## Prerequisites

- AWS credentials for account 009080466601, us-east-1
- `~/.config/guppi-connect/acxd_api_key`: the designer API key (mode 600)
- hr-super-agent checked out beside this repository (its `cdk-outputs.json` supplies the
  gateway URLs)
- Node 20+, uv, AWS CDK

## Layout

```
acxd/       designer resources as data (hr.js, probes.js), deploy.js, logs.js
agent/      the AG-UI to Connect bridge on the platform agent kit (connect_bridge)
infra/      CDK app: the mock and echo Lambda, the bridge Runtime, table and edge target
mock/       the Lambda handler
web/        the hr-connect project manifest for chat.dengler.io
scripts/    contact flow, chat harness, routing eval, HR token minting, deploy, bridge check
docs/       spike report, platform plan
```

## Commands

```
(cd acxd && node deploy.js --env production)              # build and deploy the canvas
uv run scripts/contact_flow.py --env production            # the contact flow bound to it
scripts/deploy.sh --require-approval never                 # the stack, then publish web/
scripts/deploy.sh --site-only                              # publish web/ only
(cd agent && uv run -- pytest)                             # the bridge's tests
```
