"""The three sub-agent domains (D4): what each one does, which tools it holds, and how it
describes itself on its A2A agent card. The orchestrator's router reads the same
descriptions, so they are written to be told apart (phase 3's "mutually
distinguishable" card descriptions).
"""

from __future__ import annotations

from dataclasses import dataclass

RETRIEVE_TOOL = "docs___Retrieve"


@dataclass(frozen=True)
class Skill:
    id: str
    name: str
    description: str
    examples: tuple[str, ...]


@dataclass(frozen=True)
class Domain:
    name: str  # profile, pay, travel: AGENT_ROLE, gateway target, routing label
    title: str
    description: str
    hr_tools: tuple[str, ...]  # without the hr___ prefix
    scope: str  # the prompt's statement of what this agent handles
    skills: tuple[Skill, ...]

    def tool_names(self, prefix: str) -> set[str]:
        return {RETRIEVE_TOOL, *(f"{prefix}{name}" for name in self.hr_tools)}


PROFILE = Domain(
    name="profile",
    title="Profile agent",
    description=(
        "Reads and changes the signed-in employee's own personal record: home address and "
        "emergency contact, each change confirmed before it is saved. Answers policy "
        "questions about keeping those details current, such as tax effects of a move."
    ),
    hr_tools=(
        "get_profile",
        "propose_address_change",
        "propose_emergency_contact_change",
        "commit_change",
        "open_ticket",
    ),
    scope=(
        "the employee's personal record: name, job, home address, and emergency contact. "
        "You can change the home address and the primary emergency contact."
    ),
    skills=(
        Skill(
            "home-address",
            "Home address",
            "Show or change the employee's home address",
            ("What address do you have for me?", "I moved to 12 Oak St, Macon GA 31201"),
        ),
        Skill(
            "emergency-contact",
            "Emergency contact",
            "Show or change the primary emergency contact",
            ("Who is my emergency contact?", "Make my sister Ana my emergency contact"),
        ),
    ),
)

PAY = Domain(
    name="pay",
    title="Pay agent",
    description=(
        "Handles where and when the signed-in employee is paid: shows and changes the direct "
        "deposit account, each change confirmed before it is saved, lists recent pay "
        "statements, and answers pay schedule and payroll correction questions."
    ),
    hr_tools=(
        "get_direct_deposit",
        "propose_direct_deposit_change",
        "list_pay_statements",
        "commit_change",
        "open_ticket",
    ),
    scope=(
        "pay: the direct deposit account, pay statements, the pay schedule, and payroll "
        "corrections. You can change the direct deposit account."
    ),
    skills=(
        Skill(
            "direct-deposit",
            "Direct deposit",
            "Show or change the account that receives pay",
            ("Where does my pay go?", "Switch my deposit to my new savings account"),
        ),
        Skill(
            "pay-statements",
            "Pay statements",
            "List recent pay statements and explain the pay schedule",
            ("Show my last paycheck", "When is the next pay date?"),
        ),
    ),
)

TRAVEL = Domain(
    name="travel",
    title="Travel agent",
    description=(
        "Answers questions about the employee travel benefit from the HR policy documents: "
        "pass travel eligibility, buddy passes and their service charges, boarding "
        "priority, and embargo dates. Read-only; enrollment changes go to an HR ticket."
    ),
    hr_tools=("open_ticket",),
    scope=(
        "pass travel privileges: eligibility, enrolled pass riders, buddy passes, service "
        "charges, boarding priority, embargo dates, and conduct. You cannot change "
        "enrollment; open a ticket for that."
    ),
    skills=(
        Skill(
            "pass-travel",
            "Pass travel and buddy passes",
            "Explain pass travel privileges and buddy pass rules",
            ("How many buddy passes do I get?", "Can I fly standby over Thanksgiving?"),
        ),
    ),
)

DOMAINS = {domain.name: domain for domain in (PROFILE, PAY, TRAVEL)}
