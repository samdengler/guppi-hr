# hr-agent

The HR Super Agent's runtimes in one package. The orchestrator implements the AgentCore
Runtime AG-UI contract through the chat.dengler.io platform kit (`guppi-agent`, a git
dependency on guppi-gpt pinned to `kit-v0.2.0`): `app.py` is `create_app(build_strands_agent)`,
so `POST /invocations` (AG-UI events as server-sent events), `GET /ping`, validation,
keepalive pings, the run log line and the conversation log are the kit's. See the
repository AGENTS.md for how it fits the whole system.

## Modules

| Module | Role |
| --- | --- |
| `app.py` | `create_app` from `guppi_agent` with the orchestrator as the per-request agent |
| `orchestrator.py` | The routing step, the routing policy, A2A delegation, AG-UI state |
| `agent.py` | The knowledge base agent for general questions, and `build_strands_agent`, the seam the tests replace |
| `pending.py` | The pending change between turns |
| `agents/` | The Profile, Pay and Travel A2A servers |
| `tools/` | The HR tools MCP server |
| `__main__.py` | The container entrypoint; `AGENT_ROLE` picks the server |

## Environment

| Variable | Meaning | Default |
| --- | --- | --- |
| `TOOLS_GATEWAY_URL` | MCP endpoint of the tools gateway (required) | none |
| `MODEL_ID` | Bedrock model or inference profile id | `us.anthropic.claude-haiku-4-5-20251001-v1:0` |
| `RETRIEVE_TOOL` | The policy search tool the general agent is given | `docs___Retrieve` |
| `AWS_REGION` | Bedrock region | `us-east-1` |
| `LOG_LEVEL` | Python logging level | `INFO` |

The agent forwards the request's bearer token to the tools gateway unchanged; it decodes
the token only to hash the `sub` claim for the per-run log record.

## Tests

`uv run -- pytest agent/tests` replaces `agent.build_strands_agent` with a fake, so the
tests need no network and no AWS credentials.
