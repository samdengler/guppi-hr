"""Container entrypoint. One image serves every runtime; AGENT_ROLE picks the server (D11).

The orchestrator speaks AG-UI on 8080 (the HTTP runtime contract); the tools server
speaks MCP on 8000 at /mcp (the MCP runtime contract).
"""

from __future__ import annotations

import os

import uvicorn

ROLES = {
    "orchestrator": ("hr_agent.app:app", 8080),
    "tools": ("hr_agent.tools.server:app", 8000),
}


def main() -> None:
    role = os.environ.get("AGENT_ROLE", "orchestrator")
    if role not in ROLES:
        raise SystemExit(f"unknown AGENT_ROLE {role!r}; expected one of {sorted(ROLES)}")
    target, port = ROLES[role]
    uvicorn.run(target, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
