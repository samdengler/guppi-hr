"""The HR tools server over its real HTTP surface: MCP JSON-RPC posts to /mcp, DynamoDB in
moto, user tokens signed with a test key. Nothing here reaches AWS."""

from __future__ import annotations

import datetime as dt
import json
import time

import boto3
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from hr_agent import __main__ as entrypoint
from hr_agent.tools import records
from hr_agent.tools.identity import (
    IdentityError,
    TokenVerifier,
    caller_from_headers,
    trace_id_from,
)
from hr_agent.tools.server import Dependencies, build_server
from hr_agent.tools.store import PROPOSAL_TTL_SECONDS, HrStore, Tables
from moto import mock_aws
from starlette.testclient import TestClient

REGION = "us-east-1"
ISSUER = "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TEST"
CLIENT_ID = "test-client"
TRACE_ID = "0af7651916cd43dd8448eb211c80319c"
TRACEPARENT = f"00-{TRACE_ID}-b7ad6b7169203331-01"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
TABLES = Tables(employees="employees", proposals="proposals", tickets="tickets", audit="audit")


def token(sub="user-1", key=KEY, **overrides) -> str:
    claims = {
        "sub": sub,
        "iss": ISSUER,
        "client_id": CLIENT_ID,
        "token_use": "access",
        "exp": int(time.time()) + 600,
        **overrides,
    }
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test"})


def verifier() -> TokenVerifier:
    return TokenVerifier(ISSUER, frozenset({CLIENT_ID}), lambda _token: KEY.public_key())


class Clock:
    def __init__(self) -> None:
        self.now = 1_790_000_000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def aws(monkeypatch):
    for name, value in {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_SESSION_TOKEN": "testing",
        "AWS_DEFAULT_REGION": REGION,
    }.items():
        monkeypatch.setenv(name, value)
    with mock_aws():
        db = boto3.resource("dynamodb", region_name=REGION)
        for name, keys in (
            ("employees", [("sub", "HASH")]),
            ("proposals", [("proposal_id", "HASH")]),
            ("tickets", [("ticket_id", "HASH")]),
            ("audit", [("sub", "HASH"), ("audit_id", "RANGE")]),
        ):
            db.create_table(
                TableName=name,
                KeySchema=[{"AttributeName": k, "KeyType": t} for k, t in keys],
                AttributeDefinitions=[{"AttributeName": k, "AttributeType": "S"} for k, _ in keys],
                BillingMode="PAY_PER_REQUEST",
            )
        yield db


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def client(aws, clock):
    deps = Dependencies(
        store_factory=lambda: HrStore(TABLES, region=REGION, clock=clock),
        verifier_factory=verifier,
        today=lambda: dt.date(2026, 9, 28),
    )
    with TestClient(build_server(deps).streamable_http_app()) as test_client:
        yield test_client


def call(client, tool, arguments=None, sub="user-1", thread="thread-1", headers=None):
    """One tools/call; returns (is_error, payload) where payload is the result dict or text."""
    sent = {
        "accept": "application/json, text/event-stream",
        "content-type": "application/json",
        "traceparent": TRACEPARENT,
    }
    if sub is not None:
        sent["x-hr-user-token"] = token(sub)
    if thread is not None:
        sent["x-hr-thread-id"] = thread
    sent.update(headers or {})
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": arguments or {}},
    }
    response = client.post("/mcp", json=body, headers=sent)
    assert response.status_code == 200, response.text
    result = response.json()["result"]
    text = result["content"][0]["text"]
    if result.get("isError"):
        return True, text
    return False, result.get("structuredContent") or json.loads(text)


ADDRESS = {"line1": "419 Glendale Ave", "city": "Decatur", "state": "GA", "postal_code": "30030"}


# ---- identity -----------------------------------------------------------------------


def test_caller_comes_from_the_verified_header_token():
    headers = {"X-Hr-User-Token": token("abc"), "X-Hr-Thread-Id": "t1", "traceparent": TRACEPARENT}
    caller = caller_from_headers(headers, verifier())
    assert (caller.sub, caller.thread_id, caller.trace_id) == ("abc", "t1", TRACE_ID)


@pytest.mark.parametrize(
    "bad",
    [
        token(key=OTHER_KEY),
        token(iss="https://example.com/other"),
        token(client_id="someone-else"),
        token(token_use="id"),
        token(exp=int(time.time()) - 5),
        "not-a-jwt",
    ],
)
def test_tokens_that_fail_verification_are_refused(bad):
    with pytest.raises(IdentityError):
        caller_from_headers({"x-hr-user-token": bad}, verifier())


def test_a_request_without_the_token_header_is_refused():
    with pytest.raises(IdentityError):
        caller_from_headers({"authorization": f"Bearer {token()}"}, verifier())


def test_a_verifier_needs_clients_or_an_audience():
    with pytest.raises(ValueError):
        TokenVerifier(ISSUER, frozenset(), lambda _t: KEY.public_key())


def test_trace_id_parsing():
    assert trace_id_from(TRACEPARENT) == TRACE_ID
    assert trace_id_from("garbage") is None
    assert trace_id_from(None) is None


# ---- records ------------------------------------------------------------------------


def test_the_seed_is_stable_per_subject_and_differs_between_subjects():
    assert records.seed_employee("a") == records.seed_employee("a")
    assert records.seed_employee("a")["employee_id"] != records.seed_employee("b")["employee_id"]


def test_seeded_routing_numbers_pass_their_own_checksum():
    for _bank, routing in records.BANKS:
        assert records.routing_number_valid(routing)


@pytest.mark.parametrize("routing", ["061000105", "12345678", "abcdefghi"])
def test_bad_routing_numbers(routing):
    assert not records.routing_number_valid(routing)


@pytest.mark.parametrize(
    "fields",
    [
        {**ADDRESS, "state": "ZZ"},
        {**ADDRESS, "postal_code": "3003"},
        {**ADDRESS, "line1": " "},
    ],
)
def test_bad_addresses(fields):
    with pytest.raises(ValueError):
        records.normalize_address(**fields)


def test_pay_statements_are_biweekly_newest_first():
    employee = records.seed_employee("a")
    statements = records.pay_statements(employee, dt.date(2026, 9, 28), 3)
    dates = [dt.date.fromisoformat(s["pay_date"]) for s in statements]
    assert dates == sorted(dates, reverse=True)
    assert dates[0] <= dt.date(2026, 9, 28)
    assert (dates[0] - dates[1]).days == 14


# ---- tools over HTTP ----------------------------------------------------------------


def test_profile_is_seeded_once_and_stays_the_same(client, aws):
    error, first = call(client, "get_profile")
    assert not error
    assert first["name"] == records.seed_employee("user-1")["name"]
    assert call(client, "get_profile")[1] == first
    assert aws.Table("employees").get_item(Key={"sub": "user-1"})["Item"]["name"] == first["name"]


def test_a_tool_call_without_the_user_token_is_refused(client):
    error, text = call(client, "get_profile", sub=None)
    assert error and "identity could not be verified" in text


def test_a_missing_verifier_setting_is_not_described_to_the_caller(aws):
    def unconfigured():
        raise KeyError("TOKEN_ISSUER")

    deps = Dependencies(
        store_factory=lambda: HrStore(TABLES, region=REGION), verifier_factory=unconfigured
    )
    with TestClient(build_server(deps).streamable_http_app()) as test_client:
        error, text = call(test_client, "get_profile")
    assert error and "identity could not be verified" in text
    assert "TOKEN_ISSUER" not in text


def test_a_proposal_changes_nothing_until_it_is_committed(client):
    before = call(client, "get_profile")[1]["home_address"]
    error, proposal = call(client, "propose_address_change", ADDRESS)
    assert not error
    assert proposal["change"] == {
        "field": "home_address",
        "from": before,
        "to": "419 Glendale Ave, Decatur, GA 30030",
    }
    assert call(client, "get_profile")[1]["home_address"] == before


def test_commit_applies_the_change_and_writes_the_audit_record_with_the_trace_id(client, aws):
    proposal_id = call(client, "propose_address_change", ADDRESS)[1]["proposal_id"]
    error, result = call(client, "commit_change", {"proposal_id": proposal_id})
    assert not error and result["committed"]
    assert call(client, "get_profile")[1]["home_address"] == "419 Glendale Ave, Decatur, GA 30030"
    audit = aws.Table("audit").get_item(Key={"sub": "user-1", "audit_id": result["audit_id"]})
    assert audit["Item"]["trace_id"] == TRACE_ID
    assert audit["Item"]["after"]["postal_code"] == "30030"


@pytest.mark.parametrize("proposal_id", ["", "   "])
def test_commit_without_a_proposal_id_is_refused(client, proposal_id):
    error, text = call(client, "commit_change", {"proposal_id": proposal_id})
    assert error and "Refused" in text and "Nothing was changed" in text


def test_commit_with_no_arguments_is_refused(client):
    error, _text = call(client, "commit_change", {})
    assert error


def test_a_proposal_commits_only_once(client):
    proposal_id = call(client, "propose_address_change", ADDRESS)[1]["proposal_id"]
    assert not call(client, "commit_change", {"proposal_id": proposal_id})[0]
    error, text = call(client, "commit_change", {"proposal_id": proposal_id})
    assert error and "already committed" in text


def test_another_users_proposal_reads_as_not_found(client):
    proposal_id = call(client, "propose_address_change", ADDRESS)[1]["proposal_id"]
    error, text = call(client, "commit_change", {"proposal_id": proposal_id}, sub="user-2")
    assert error and "no proposal" in text


def test_a_proposal_from_another_conversation_is_refused(client):
    proposal_id = call(client, "propose_address_change", ADDRESS)[1]["proposal_id"]
    error, text = call(client, "commit_change", {"proposal_id": proposal_id}, thread="thread-2")
    assert error and "different conversation" in text


def test_an_expired_proposal_is_refused(client, clock):
    proposal_id = call(client, "propose_address_change", ADDRESS)[1]["proposal_id"]
    clock.now += PROPOSAL_TTL_SECONDS
    error, text = call(client, "commit_change", {"proposal_id": proposal_id})
    assert error and "expired" in text


def test_invalid_values_are_not_proposed(client):
    error, text = call(client, "propose_address_change", {**ADDRESS, "state": "ZZ"})
    assert error and "Not proposed: ZZ is not a two-letter US state code" in text


def test_direct_deposit_keeps_only_the_last_four_digits(client, aws):
    arguments = {
        "routing_number": "061000104",
        "account_number": "000123456789",
        "account_type": "savings",
    }
    error, proposal = call(client, "propose_direct_deposit_change", arguments)
    assert not error
    assert "ending 6789" in proposal["change"]["to"]
    stored = aws.Table("proposals").get_item(Key={"proposal_id": proposal["proposal_id"]})
    assert "000123456789" not in json.dumps(stored["Item"], default=str)
    call(client, "commit_change", {"proposal_id": proposal["proposal_id"]})
    assert "savings account ending 6789" in call(client, "get_direct_deposit")[1]["direct_deposit"]


def test_emergency_contact_change_round_trip(client):
    arguments = {"name": "Sam Rivera", "relationship": "Spouse", "phone": "404-555-0142"}
    proposal_id = call(client, "propose_emergency_contact_change", arguments)[1]["proposal_id"]
    call(client, "commit_change", {"proposal_id": proposal_id})
    contact = call(client, "get_profile")[1]["emergency_contact"]
    assert contact == "Sam Rivera (Spouse), (404) 555-0142"


def test_pay_statements_count_is_clamped(client):
    assert len(call(client, "list_pay_statements", {"count": 50})[1]["statements"]) == 12
    assert len(call(client, "list_pay_statements", {"count": 0})[1]["statements"]) == 1


def test_open_ticket_stores_the_ticket_with_the_trace_id(client, aws):
    error, ticket = call(client, "open_ticket", {"summary": "Talk to someone", "domain": "Travel"})
    assert not error and ticket["ticket_id"].startswith("HR-")
    item = aws.Table("tickets").get_item(Key={"ticket_id": ticket["ticket_id"]})["Item"]
    assert (item["domain"], item["trace_id"], item["sub"]) == ("travel", TRACE_ID, "user-1")


# ---- entrypoint ---------------------------------------------------------------------


def test_an_unknown_role_stops_the_container(monkeypatch):
    monkeypatch.setenv("AGENT_ROLE", "nope")
    with pytest.raises(SystemExit):
        entrypoint.main()


def test_each_role_runs_its_own_app_and_port(monkeypatch):
    started = []
    monkeypatch.setattr(
        entrypoint.uvicorn, "run", lambda target, **kw: started.append((target, kw["port"]))
    )
    for role in ("orchestrator", "tools"):
        monkeypatch.setenv("AGENT_ROLE", role)
        entrypoint.main()
    assert started == [("hr_agent.app:app", 8080), ("hr_agent.tools.server:app", 8000)]


def test_an_okta_shaped_token_is_accepted_and_keyed_on_uid():
    # Okta's custom authorization server: cid and aud, no token_use; sub is the login.
    okta = TokenVerifier(
        ISSUER, frozenset({CLIENT_ID}), lambda _token: KEY.public_key(), token_use="", audience="api://guppi"
    )
    claims_token = jwt.encode(
        {"sub": "quinn@example.com", "uid": "00u1abcd", "cid": CLIENT_ID, "aud": "api://guppi",
         "iss": ISSUER, "exp": int(time.time()) + 600},
        KEY, algorithm="RS256", headers={"kid": "test"},
    )
    caller = caller_from_headers({"X-Hr-User-Token": claims_token}, okta)
    assert caller.sub == "00u1abcd"


def test_an_okta_shaped_token_for_another_audience_is_refused():
    okta = TokenVerifier(
        ISSUER, frozenset(), lambda _token: KEY.public_key(), token_use="", audience="api://guppi"
    )
    other = jwt.encode(
        {"sub": "q@example.com", "uid": "00u1", "cid": CLIENT_ID, "aud": "api://other", "iss": ISSUER,
         "exp": int(time.time()) + 600},
        KEY, algorithm="RS256", headers={"kid": "test"},
    )
    with pytest.raises(IdentityError):
        okta.verify(other)
