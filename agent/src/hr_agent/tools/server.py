"""The HR tools MCP server: streamable HTTP on 8000 at /mcp, stateless (AgentCore's MCP
runtime contract).

Tools are task-shaped. Every change is a pair: a `propose_*` tool stores the exact new
value and returns a proposal id, and `commit_change` applies it only with that id, for
the same user and conversation, once, before it expires (D7). The employee is always the
caller; no tool takes an employee id.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from hr_agent.tools import records, scopes
from hr_agent.tools.identity import Caller, IdentityError, TokenVerifier, caller_from_headers
from hr_agent.tools.store import CommitRefused, HrStore, Tables

log = logging.getLogger("hr_agent.tools")

CONFIRM_INSTRUCTION = (
    "Nothing has changed yet. Read the change back to the employee exactly as shown and ask "
    "them to confirm. Call commit_change with this proposal_id only after they say yes."
)

IDENTITY_REFUSAL = "The employee's identity could not be verified."
SCOPE_REFUSAL = "This assistant is not allowed to use that tool."

INSTRUCTIONS = (
    "HR self-service tools for the signed-in employee: profile, emergency contact, direct "
    "deposit, pay statements, and HR tickets. Changes take two steps: a propose tool, then "
    "commit_change with the returned proposal_id after the employee confirms."
)


class Dependencies:
    """Built on first use, so importing the module needs no AWS settings."""

    def __init__(
        self,
        store_factory: Callable[[], HrStore] = lambda: HrStore(Tables.from_environment()),
        verifier_factory: Callable[[], TokenVerifier] = TokenVerifier.from_environment,
        today: Callable[[], dt.date] = lambda: dt.datetime.now(dt.UTC).date(),
    ) -> None:
        self._store_factory = store_factory
        self._verifier_factory = verifier_factory
        self._store: HrStore | None = None
        self._verifier: TokenVerifier | None = None
        self.today = today

    @property
    def store(self) -> HrStore:
        if self._store is None:
            self._store = self._store_factory()
        return self._store

    @property
    def verifier(self) -> TokenVerifier:
        if self._verifier is None:
            self._verifier = self._verifier_factory()
        return self._verifier


def build_server(deps: Dependencies | None = None) -> FastMCP:
    deps = deps or Dependencies()
    # host 0.0.0.0 matters beyond the bind address: for a localhost host FastMCP turns on
    # DNS rebinding protection, which would refuse the runtime's Host header.
    mcp = FastMCP(
        "hr",
        instructions=INSTRUCTIONS,
        host="0.0.0.0",
        stateless_http=True,
        json_response=True,
    )

    def caller(ctx: Context, tool: str) -> Caller:
        request = ctx.request_context.request
        if request is None:
            raise ToolError(IDENTITY_REFUSAL)
        try:
            verifier = deps.verifier
        except Exception as exc:
            # A missing or bad setting is logged here and never described to the caller.
            log.exception("token verifier is not configured")
            raise ToolError(IDENTITY_REFUSAL) from exc
        try:
            who = caller_from_headers(request.headers, verifier)
        except IdentityError as exc:
            log.warning("tool call refused: %s", exc)
            raise ToolError(IDENTITY_REFUSAL) from exc
        if not scopes.allowed(tool, who.scopes):
            log.warning("tool call refused: %s needs a scope the token does not hold", tool)
            raise ToolError(SCOPE_REFUSAL)
        return who

    def proposal_result(proposal: dict[str, Any], before: str, after: str) -> dict[str, Any]:
        log.info("proposed %s change %s", proposal["field"], proposal["proposal_id"])
        return {
            "proposal_id": proposal["proposal_id"],
            "change": {"field": proposal["field"], "from": before, "to": after},
            "expires_at": dt.datetime.fromtimestamp(proposal["expires_at"], dt.UTC).isoformat(),
            "next_step": CONFIRM_INSTRUCTION,
        }

    @mcp.tool()
    def get_profile(ctx: Context) -> dict[str, Any]:
        """The signed-in employee's profile: name, employee id, job, home address, and
        emergency contact."""
        employee = deps.store.employee(caller(ctx, "get_profile").sub)
        return {
            "name": employee["name"],
            "employee_id": employee["employee_id"],
            "title": employee["title"],
            "department": employee["department"],
            "hire_date": employee["hire_date"],
            "home_address": records.format_address(employee["home_address"]),
            "emergency_contact": records.format_emergency_contact(employee["emergency_contact"]),
        }

    @mcp.tool()
    def propose_address_change(
        line1: str, city: str, state: str, postal_code: str, ctx: Context, line2: str = ""
    ) -> dict[str, Any]:
        """Propose a new home address for the signed-in employee. Changes nothing until
        commit_change is called with the returned proposal_id. state is a two-letter US
        code; postal_code is a 5 digit ZIP code."""
        who = caller(ctx, "propose_address_change")
        try:
            after = records.normalize_address(line1, city, state, postal_code, line2)
        except ValueError as exc:
            raise ToolError(f"Not proposed: {exc}.") from exc
        before = deps.store.employee(who.sub)["home_address"]
        proposal = deps.store.propose(who, "home_address", before, after)
        return proposal_result(
            proposal, records.format_address(before), records.format_address(after)
        )

    @mcp.tool()
    def propose_emergency_contact_change(
        name: str, relationship: str, phone: str, ctx: Context
    ) -> dict[str, Any]:
        """Propose a new emergency contact for the signed-in employee. Changes nothing until
        commit_change is called with the returned proposal_id. phone is a 10 digit US
        number."""
        who = caller(ctx, "propose_emergency_contact_change")
        try:
            after = records.normalize_emergency_contact(name, relationship, phone)
        except ValueError as exc:
            raise ToolError(f"Not proposed: {exc}.") from exc
        before = deps.store.employee(who.sub)["emergency_contact"]
        proposal = deps.store.propose(who, "emergency_contact", before, after)
        return proposal_result(
            proposal,
            records.format_emergency_contact(before),
            records.format_emergency_contact(after),
        )

    @mcp.tool()
    def get_direct_deposit(ctx: Context) -> dict[str, Any]:
        """Where the signed-in employee's pay is deposited. Account numbers are shown by
        their last four digits only."""
        deposit = deps.store.employee(caller(ctx, "get_direct_deposit").sub)["direct_deposit"]
        return {"direct_deposit": records.format_direct_deposit(deposit)}

    @mcp.tool()
    def propose_direct_deposit_change(
        routing_number: str,
        account_number: str,
        account_type: str,
        ctx: Context,
        bank_name: str = "",
    ) -> dict[str, Any]:
        """Propose a new direct deposit account for the signed-in employee. Changes nothing
        until commit_change is called with the returned proposal_id. account_type is
        checking or savings. Only the last four digits of the account number are kept."""
        who = caller(ctx, "propose_direct_deposit_change")
        try:
            after = records.normalize_direct_deposit(
                routing_number, account_number, account_type, bank_name
            )
        except ValueError as exc:
            raise ToolError(f"Not proposed: {exc}.") from exc
        before = deps.store.employee(who.sub)["direct_deposit"]
        proposal = deps.store.propose(who, "direct_deposit", before, after)
        return proposal_result(
            proposal,
            records.format_direct_deposit(before),
            records.format_direct_deposit(after),
        )

    @mcp.tool()
    def commit_change(proposal_id: str, ctx: Context) -> dict[str, Any]:
        """Apply a change proposed earlier in this conversation. Call only after the
        employee has confirmed the exact change, with the proposal_id the propose tool
        returned. Refused without a valid, unexpired, uncommitted proposal id."""
        who = caller(ctx, "commit_change")
        try:
            audit = deps.store.commit(who, proposal_id)
        except CommitRefused as exc:
            log.info("commit refused: %s", exc)
            raise ToolError(f"Refused: {exc}. Nothing was changed.") from exc
        log.info("committed %s change %s", audit["field"], audit["proposal_id"])
        return {
            "committed": True,
            "proposal_id": audit["proposal_id"],
            "field": audit["field"],
            "audit_id": audit["audit_id"],
        }

    @mcp.tool()
    def list_pay_statements(ctx: Context, count: int = 3) -> dict[str, Any]:
        """The signed-in employee's most recent pay statements, newest first (1 to 12)."""
        employee = deps.store.employee(caller(ctx, "list_pay_statements").sub)
        count = max(1, min(count, 12))
        return {
            "pay_frequency": "every two weeks",
            "statements": records.pay_statements(employee, deps.today(), count),
        }

    @mcp.tool()
    def open_ticket(summary: str, ctx: Context, domain: str = "general") -> dict[str, Any]:
        """Open a ticket for a person on the HR team to follow up with the signed-in
        employee. Use when the employee asks for a person, or when no tool or policy
        answers the request. domain is profile, pay, travel, or general."""
        who = caller(ctx, "open_ticket")
        try:
            ticket = deps.store.open_ticket(who, summary, domain)
        except ValueError as exc:
            raise ToolError(f"Not opened: {exc}.") from exc
        log.info("opened ticket %s", ticket["ticket_id"])
        return {
            "ticket_id": ticket["ticket_id"],
            "status": ticket["status"],
            "next_step": "Give the employee the ticket id; HR follows up within two business days.",
        }

    return mcp


server = build_server()
app = server.streamable_http_app()
