"""Synthetic HR records and the checks on proposed values. Pure: no AWS, no clock.

Every signed-in user gets one synthetic employee, derived from a hash of the token's
`sub` so the same person always sees the same starting record. Nothing here is real
employee data.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
from typing import Any

FIRST_NAMES = ["Jordan", "Avery", "Morgan", "Riley", "Casey", "Quinn", "Taylor", "Reese"]
LAST_NAMES = ["Alvarez", "Brooks", "Chen", "Dawson", "Ellis", "Foster", "Grant", "Hayes"]
TITLES = [
    ("Flight Attendant", "In-Flight Service"),
    ("Aircraft Maintenance Technician", "Technical Operations"),
    ("Customer Service Agent", "Airport Customer Service"),
    ("Crew Scheduler", "Crew Resources"),
    ("Revenue Analyst", "Finance"),
]
ADDRESSES = [
    ("1200 Peachtree St NE", "Atlanta", "GA", "30309"),
    ("88 Lake Shore Dr", "Chicago", "IL", "60611"),
    ("450 Cedar Ave", "Minneapolis", "MN", "55454"),
    ("27 Harbor View Rd", "Seattle", "WA", "98121"),
    ("915 Magnolia Blvd", "Salt Lake City", "UT", "84101"),
]
RELATIONSHIPS = ["Spouse", "Partner", "Parent", "Sibling", "Friend"]
BANKS = [("First Harbor Bank", "061000104"), ("Summit Credit Union", "091000019")]
US_STATES = frozenset(
    "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE "
    "NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split()
)
ACCOUNT_TYPES = ("checking", "savings")
FIRST_PAY_DATE = dt.date(2026, 1, 2)  # a Friday; pay is every 14 days from here
PAY_PERIODS_PER_YEAR = 26
NET_SHARE = 0.72  # a flat stand-in for taxes and deductions on the synthetic statements


def _pick(digest: bytes, index: int, options: list | tuple) -> Any:
    return options[digest[index] % len(options)]


def seed_employee(sub: str) -> dict[str, Any]:
    digest = hashlib.sha256(sub.encode()).digest()
    first, last = _pick(digest, 0, FIRST_NAMES), _pick(digest, 1, LAST_NAMES)
    title, department = _pick(digest, 2, TITLES)
    street, city, state, postal = _pick(digest, 3, ADDRESSES)
    bank, routing = _pick(digest, 4, BANKS)
    number = int.from_bytes(digest[8:12], "big")
    return {
        "sub": sub,
        "employee_id": f"E{number % 1_000_000:06d}",
        "name": f"{first} {last}",
        "title": title,
        "department": department,
        "hire_date": f"{2008 + digest[5] % 17}-{1 + digest[6] % 12:02d}-{1 + digest[7] % 28:02d}",
        "home_address": {
            "line1": street,
            "line2": "",
            "city": city,
            "state": state,
            "postal_code": postal,
        },
        "emergency_contact": {
            "name": f"{_pick(digest, 12, FIRST_NAMES)} {last}",
            "relationship": _pick(digest, 13, RELATIONSHIPS),
            "phone": f"(404) 555-{number % 10_000:04d}",
        },
        "direct_deposit": {
            "bank_name": bank,
            "routing_number": routing,
            "account_last4": f"{(number // 7) % 10_000:04d}",
            "account_type": "checking",
        },
        "annual_salary": 42_000 + (number % 60) * 1_000,
    }


def format_address(address: dict[str, str]) -> str:
    street = ", ".join(part for part in (address["line1"], address.get("line2", "")) if part)
    return f"{street}, {address['city']}, {address['state']} {address['postal_code']}"


def format_emergency_contact(contact: dict[str, str]) -> str:
    return f"{contact['name']} ({contact['relationship']}), {contact['phone']}"


def format_direct_deposit(deposit: dict[str, str]) -> str:
    return (
        f"{deposit['account_type']} account ending {deposit['account_last4']} at "
        f"{deposit['bank_name']} (routing {deposit['routing_number']})"
    )


def normalize_address(
    line1: str, city: str, state: str, postal_code: str, line2: str = ""
) -> dict[str, str]:
    line1, line2, city = line1.strip(), line2.strip(), city.strip()
    state, postal_code = state.strip().upper(), postal_code.strip()
    if not line1 or len(line1) > 100 or len(line2) > 100:
        raise ValueError("the street line must be 1 to 100 characters")
    if not city or len(city) > 60:
        raise ValueError("the city must be 1 to 60 characters")
    if state not in US_STATES:
        raise ValueError(f"{state or 'the state'} is not a two-letter US state code")
    if not re.fullmatch(r"\d{5}(-\d{4})?", postal_code):
        raise ValueError("the ZIP code must be 5 digits, or 5 plus 4")
    return {
        "line1": line1,
        "line2": line2,
        "city": city,
        "state": state,
        "postal_code": postal_code,
    }


def normalize_emergency_contact(name: str, relationship: str, phone: str) -> dict[str, str]:
    name, relationship = name.strip(), relationship.strip()
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if not name or len(name) > 80:
        raise ValueError("the contact name must be 1 to 80 characters")
    if not relationship or len(relationship) > 40:
        raise ValueError("the relationship must be 1 to 40 characters")
    if len(digits) != 10:
        raise ValueError("the phone number must have 10 digits")
    return {
        "name": name,
        "relationship": relationship,
        "phone": f"({digits[:3]}) {digits[3:6]}-{digits[6:]}",
    }


def routing_number_valid(routing: str) -> bool:
    """The ABA checksum: 3, 7, 1 weights over the nine digits sum to a multiple of 10."""
    if not re.fullmatch(r"\d{9}", routing):
        return False
    d = [int(c) for c in routing]
    return (3 * (d[0] + d[3] + d[6]) + 7 * (d[1] + d[4] + d[7]) + d[2] + d[5] + d[8]) % 10 == 0


def normalize_direct_deposit(
    routing_number: str, account_number: str, account_type: str, bank_name: str = ""
) -> dict[str, str]:
    """Only the last four digits of the account number are kept, here and in the proposal."""
    routing_number = re.sub(r"\s", "", routing_number)
    account_number = re.sub(r"[\s-]", "", account_number)
    account_type = account_type.strip().lower()
    if not routing_number_valid(routing_number):
        raise ValueError("the routing number is not a valid 9 digit ABA routing number")
    if not re.fullmatch(r"\d{4,17}", account_number):
        raise ValueError("the account number must be 4 to 17 digits")
    if account_type not in ACCOUNT_TYPES:
        raise ValueError("the account type must be checking or savings")
    return {
        "bank_name": bank_name.strip() or "the bank on file for that routing number",
        "routing_number": routing_number,
        "account_last4": account_number[-4:],
        "account_type": account_type,
    }


def pay_statements(employee: dict[str, Any], today: dt.date, count: int) -> list[dict[str, str]]:
    """The most recent `count` biweekly statements on or before today, newest first."""
    if today < FIRST_PAY_DATE:
        return []
    periods = (today - FIRST_PAY_DATE).days // 14
    gross = int(employee["annual_salary"]) / PAY_PERIODS_PER_YEAR
    statements = []
    for n in range(periods, max(periods - count, -1), -1):
        pay_date = FIRST_PAY_DATE + dt.timedelta(days=14 * n)
        statements.append(
            {
                "pay_date": pay_date.isoformat(),
                "period": (
                    f"{(pay_date - dt.timedelta(days=19)).isoformat()} to "
                    f"{(pay_date - dt.timedelta(days=6)).isoformat()}"
                ),
                "gross_pay": f"${gross:,.2f}",
                "net_pay": f"${gross * NET_SHARE:,.2f}",
                "deposited_to": f"account ending {employee['direct_deposit']['account_last4']}",
            }
        )
    return statements
