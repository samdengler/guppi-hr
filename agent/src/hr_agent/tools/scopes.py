"""Which scope each HR tool needs (D47).

Gateway Policy on the tools gateway allows each tool only for a caller token that holds its
scope; the server checks the same table again on the runtime token, which carries the
caller's scopes, so a Policy engine left in LOG_ONLY, detached, or bypassed by a runtime
token minted outside the gateway still refuses (critique of the build, finding 2). The
infra's TOOL_SCOPES (hr_super_agent_infra/obo.py) is the same table by gateway tool name;
a test holds them together. `commit_change` needs a write scope here, and the store checks
that it is the one for the proposal's field.
"""

from __future__ import annotations

WRITE_SCOPES = ("hr.tools.profile.write", "hr.tools.pay.write")

TOOL_SCOPES: dict[str, tuple[str, ...]] = {
    "get_profile": ("hr.tools.profile.read",),
    "propose_address_change": ("hr.tools.profile.write",),
    "propose_emergency_contact_change": ("hr.tools.profile.write",),
    "list_pay_statements": ("hr.tools.pay.statements.read",),
    "get_direct_deposit": ("hr.tools.pay.read",),
    "propose_direct_deposit_change": ("hr.tools.pay.write",),
    "commit_change": WRITE_SCOPES,
    "open_ticket": ("hr.tools.policy",),
}


def allowed(tool: str, scopes: frozenset[str]) -> bool:
    """True when the scopes hold one of the tool's; an unknown tool is refused."""
    return any(scope in scopes for scope in TOOL_SCOPES.get(tool, ()))
