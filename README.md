# guppi-connect

A spike: Amazon Connect Customer's Agentic CX designer as the HR super-agent, in place
of hr-super-agent's Strands orchestrator, over the same A2A sub-agents and MCP tools.

The canvas is built from code with the designer SDK (`acxd/`), reached through a Connect
contact flow (`scripts/contact_flow.py`), and driven over Connect chat
(`scripts/chat.py`, `scripts/route_eval.py`). A small Lambda (`mock/`, stack
`GuppiConnect` in `infra/`) echoes headers and imitates the sub-agents, so the canvas can
be tested without an employee token.

Results and what is left: [docs/spike-report.md](docs/spike-report.md). The design it
tests: the Claude Doc "Agentic CX designer as the HR super-agent".

## Prerequisites

- AWS credentials for account 009080466601, us-east-1
- `~/.config/guppi-connect/acxd_api_key`: the designer API key (mode 600)
- hr-super-agent checked out beside this repository (its `cdk-outputs.json` supplies the
  gateway URLs)
- Node 20+, uv, AWS CDK

## Layout

```
acxd/       designer resources as data (hr.js, probes.js), deploy.js, logs.js
infra/      CDK app: the mock and echo Lambda
mock/       the Lambda handler
scripts/    contact flow, chat harness, routing eval, HR token minting
docs/       spike report
```
