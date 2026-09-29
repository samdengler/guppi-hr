"""Container entrypoint. One image serves every runtime; AGENT_ROLE picks the server (D11).

The orchestrator speaks AG-UI on 8080 (the HTTP runtime contract); the tools server
speaks MCP on 8000 at /mcp (the MCP runtime contract); the profile, pay, and travel
sub-agents speak A2A on 9000 at / (the A2A runtime contract).
"""

from __future__ import annotations

import os

import uvicorn

ROLES = {
    "orchestrator": ("hr_agent.app:app", 8080),
    "tools": ("hr_agent.tools.server:app", 8000),
}
SUB_AGENT_ROLES = ("profile", "pay", "travel")


def main() -> None:
    role = os.environ.get("AGENT_ROLE", "orchestrator")
    if role in SUB_AGENT_ROLES:
        from hr_agent.agents.server import serve

        serve(role)
        return
    if role not in ROLES:
        known = sorted([*ROLES, *SUB_AGENT_ROLES])
        raise SystemExit(f"unknown AGENT_ROLE {role!r}; expected one of {known}")
    target, port = ROLES[role]
    uvicorn.run(target, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
