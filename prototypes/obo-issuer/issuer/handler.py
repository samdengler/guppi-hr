"""Throwaway prototype (D20): an RFC 8693 token-exchange issuer on API Gateway and Lambda.

Routes: GET /.well-known/openid-configuration, GET /jwks.json, POST /token. The token
endpoint verifies the caller's client secret (its SHA-256 is in CLIENTS), verifies the
subject token (RS256 against Okta's keys, or this issuer's own key for a second hop),
checks the requested scopes against the client's, and mints a token signed by a KMS key:
`sub` the employee, `aud` the target, `scope`/`scp`, `client_id`, and `act` naming the
client that asked (nested for each hop). No dependencies beyond the Lambda runtime.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request
import uuid

import boto3

KMS = boto3.client("kms")
KEY_ID = os.environ["KEY_ID"]
UPSTREAM_ISSUER = os.environ["UPSTREAM_ISSUER"]  # Okta's guppi server
UPSTREAM_AUDIENCE = os.environ["UPSTREAM_AUDIENCE"]  # api://guppi
CLIENTS = json.loads(os.environ["CLIENTS"])  # {client_id: {"secret_sha256": .., "scopes": [..]}}
# Each scope maps to the audience a token for it is issued to.
SCOPE_AUDIENCE = json.loads(os.environ["SCOPE_AUDIENCE"])
# Spike only: lets a test ask for tokens carrying `scope` or `scp` alone (form field `shape`).
ALLOW_SHAPE = os.environ.get("ALLOW_SHAPE") == "1"
TOKEN_EXCHANGE = "urn:ietf:params:oauth:grant-type:token-exchange"
ACCESS_TOKEN_TYPE = "urn:ietf:params:oauth:token-type:access_token"
LIFETIME = 3600
SHA256_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")

_jwks_cache: dict[str, dict] = {}
_public: dict | None = None


def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def unb64u(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def issuer(event) -> str:
    ctx = event["requestContext"]
    return f"https://{ctx['domainName']}"


def own_jwk() -> dict:
    """This issuer's public key as a JWK, from KMS."""
    global _public
    if _public is None:
        der = KMS.get_public_key(KeyId=KEY_ID)["PublicKey"]
        n, e = parse_rsa_spki(der)
        _public = {"kty": "RSA", "use": "sig", "alg": "RS256", "kid": key_kid(), "n": b64u(n), "e": b64u(e)}
    return _public


def key_kid() -> str:
    return hashlib.sha256(KEY_ID.encode()).hexdigest()[:16]


def parse_der(data: bytes, i: int) -> tuple[int, int, int]:
    """(tag, content start, content end) of the DER element at i."""
    tag = data[i]
    length = data[i + 1]
    i += 2
    if length & 0x80:
        count = length & 0x7F
        length = int.from_bytes(data[i : i + count], "big")
        i += count
    return tag, i, i + length


def parse_rsa_spki(der: bytes) -> tuple[bytes, bytes]:
    _, s, _ = parse_der(der, 0)  # SubjectPublicKeyInfo
    _, a, a_end = parse_der(der, s)  # AlgorithmIdentifier
    _, b, _ = parse_der(der, a_end)  # BIT STRING
    _, r, _ = parse_der(der, b + 1)  # RSAPublicKey (skip unused-bits byte)
    _, n_s, n_e = parse_der(der, r)
    _, e_s, e_e = parse_der(der, n_e)
    return der[n_s:n_e].lstrip(b"\x00"), der[e_s:e_e]


def upstream_key(kid: str) -> dict | None:
    if kid not in _jwks_cache:
        with urllib.request.urlopen(f"{UPSTREAM_ISSUER}/v1/keys", timeout=5) as response:
            for key in json.load(response)["keys"]:
                _jwks_cache[key["kid"]] = key
    return _jwks_cache.get(kid)


def rs256_verify(jwk: dict, signing_input: bytes, signature: bytes) -> bool:
    n = int.from_bytes(unb64u(jwk["n"]), "big")
    e = int.from_bytes(unb64u(jwk["e"]), "big")
    size = (n.bit_length() + 7) // 8
    em = pow(int.from_bytes(signature, "big"), e, n).to_bytes(size, "big")
    digest = SHA256_PREFIX + hashlib.sha256(signing_input).digest()
    expected = b"\x00\x01" + b"\xff" * (size - len(digest) - 3) + b"\x00" + digest
    return hmac.compare_digest(em, expected)


def verify_subject(token: str, own_issuer: str) -> dict:
    head, body, sig = token.split(".")
    header = json.loads(unb64u(head))
    claims = json.loads(unb64u(body))
    if header.get("alg") != "RS256":
        raise ValueError("subject token is not RS256")
    if claims.get("iss") == UPSTREAM_ISSUER:
        key = upstream_key(header.get("kid", ""))
        audience = UPSTREAM_AUDIENCE
    elif claims.get("iss") == own_issuer:
        key = own_jwk() if header.get("kid") == key_kid() else None
        audience = None  # any of this issuer's audiences may be exchanged again
    else:
        raise ValueError("subject token issuer is not trusted")
    if not key or not rs256_verify(key, f"{head}.{body}".encode(), unb64u(sig)):
        raise ValueError("subject token signature is invalid")
    if claims.get("exp", 0) < time.time():
        raise ValueError("subject token is expired")
    if audience and claims.get("aud") != audience:
        raise ValueError("subject token audience is not accepted")
    return claims


def client_from(event, form) -> str:
    header = (event.get("headers") or {}).get("authorization", "")
    if header.lower().startswith("basic "):
        client_id, _, secret = base64.b64decode(header[6:]).decode().partition(":")
        client_id, secret = urllib.parse.unquote(client_id), urllib.parse.unquote(secret)
    else:
        client_id, secret = form.get("client_id", ""), form.get("client_secret", "")
    entry = CLIENTS.get(client_id)
    if not entry or not hmac.compare_digest(hashlib.sha256(secret.encode()).hexdigest(), entry["secret_sha256"]):
        raise PermissionError("invalid_client")
    return client_id


def sign(claims: dict) -> str:
    header = {"alg": "RS256", "typ": "JWT", "kid": key_kid()}
    signing_input = f"{b64u(json.dumps(header, separators=(',', ':')).encode())}.{b64u(json.dumps(claims, separators=(',', ':')).encode())}"
    signature = KMS.sign(KeyId=KEY_ID, Message=signing_input.encode(), MessageType="RAW", SigningAlgorithm="RSASSA_PKCS1_V1_5_SHA_256")["Signature"]
    return f"{signing_input}.{b64u(signature)}"


def respond(status: int, body: dict) -> dict:
    return {"statusCode": status, "headers": {"content-type": "application/json", "cache-control": "no-store"}, "body": json.dumps(body)}


def token(event) -> dict:
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode()
    form = {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}
    try:
        client_id = client_from(event, form)
    except PermissionError:
        return respond(401, {"error": "invalid_client"})
    if form.get("grant_type") == "client_credentials" and ALLOW_SHAPE:
        return client_token(event, client_id, form)
    if form.get("grant_type") != TOKEN_EXCHANGE:
        return respond(400, {"error": "unsupported_grant_type"})
    own = issuer(event)
    try:
        subject = verify_subject(form.get("subject_token", ""), own)
    except (ValueError, KeyError, json.JSONDecodeError) as error:
        return respond(400, {"error": "invalid_grant", "error_description": str(error)})
    requested = form.get("scope", "").split()
    allowed = CLIENTS[client_id]["scopes"]
    if not requested or any(s not in allowed for s in requested):
        return respond(400, {"error": "invalid_scope"})
    audiences = {SCOPE_AUDIENCE[s] for s in requested}
    if len(audiences) != 1:
        return respond(400, {"error": "invalid_scope", "error_description": "scopes for one audience at a time"})
    now = int(time.time())
    act = {"sub": client_id}
    if "act" in subject:
        act["act"] = subject["act"]
    shape = form.get("shape", "both") if ALLOW_SHAPE else "both"
    claims = {
        "iss": own,
        "sub": str(subject.get("uid") or subject["sub"]),
        "aud": audiences.pop(),
        "scope": " ".join(requested),
        "scp": requested,
        "client_id": client_id,
        "act": act,
        "iat": now,
        "exp": min(int(subject["exp"]), now + LIFETIME),
        "jti": uuid.uuid4().hex,
    }
    if shape == "scope":
        del claims["scp"]
    elif shape == "scp":
        del claims["scope"]
    return respond(200, {
        "access_token": sign(claims),
        "issued_token_type": ACCESS_TOKEN_TYPE,
        "token_type": "Bearer",
        "expires_in": claims["exp"] - now,
        "scope": " ".join(requested),
    })


def handler(event, _context):
    path = event.get("rawPath", "/")
    method = event["requestContext"]["http"]["method"]
    own = issuer(event)
    if method == "GET" and path == "/.well-known/openid-configuration":
        return respond(200, {
            "issuer": own,
            "token_endpoint": f"{own}/token",
            "jwks_uri": f"{own}/jwks.json",
            "authorization_endpoint": f"{own}/authorize",
            "grant_types_supported": [TOKEN_EXCHANGE],
            "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post"],
            "response_types_supported": ["token"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256"],
            "scopes_supported": sorted(SCOPE_AUDIENCE),
        })
    if method == "GET" and path == "/jwks.json":
        return respond(200, {"keys": [own_jwk()]})
    if method == "POST" and path == "/token":
        result = token(event)
        # Spike: what a caller sent (field names only) and what it got, never a value.
        raw = event.get("body") or ""
        if event.get("isBase64Encoded"):
            raw = base64.b64decode(raw).decode()
        form = urllib.parse.parse_qs(raw)
        print(json.dumps({"route": "/token", "fields": sorted(form), "grant_type": form.get("grant_type"),
                          "subject_token_type": form.get("subject_token_type"), "scope": form.get("scope"),
                          "audience": form.get("audience"), "resource": form.get("resource"),
                          "basic_auth": (event.get("headers") or {}).get("authorization", "").lower().startswith("basic "),
                          "user_agent": (event.get("headers") or {}).get("user-agent"),
                          "status": result["statusCode"],
                          "error": json.loads(result["body"]).get("error") if result["statusCode"] != 200 else None}))
        return result
    if path in ("/mcp", "/echo") or path.startswith("/echo/"):
        return echo_or_mcp(event, own, path)
    return respond(404, {"error": "not_found"})


def bearer_claims(event, own: str) -> dict | None:
    """Claims of this issuer's bearer token on a spike route, or None. Logs no token."""
    header = (event.get("headers") or {}).get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    try:
        claims = verify_subject(header[7:], own)
    except (ValueError, KeyError, json.JSONDecodeError):
        return None
    return claims if claims.get("iss") == own else None


def summary(claims: dict) -> dict:
    return {k: claims.get(k) for k in ("aud", "scope", "scp", "client_id", "act")} | {
        "sub_is_okta_uid": str(claims.get("sub", "")).startswith("00u"), "ttl": claims["exp"] - int(time.time())}


def echo_or_mcp(event, own: str, path: str) -> dict:
    """Spike targets: /echo answers with the bearer token's claims (an HTTP target), /mcp is
    a minimal MCP server with one tool, whoami, that does the same (an MCP server target)."""
    claims = bearer_claims(event, own)
    method = event["requestContext"]["http"]["method"]
    unverified = None
    auth = (event.get("headers") or {}).get("authorization", "")
    if auth.lower().startswith("bearer ") and auth.count(".") == 2:
        try:
            raw_claims = json.loads(unb64u(auth[7:].split(".")[1]))
            unverified = {"iss_is_okta": raw_claims.get("iss") == UPSTREAM_ISSUER, "aud": raw_claims.get("aud")}
        except (ValueError, json.JSONDecodeError):
            unverified = "unparseable"
    print(json.dumps({"route": path, "method": method, "authorized": bool(claims), "bearer": unverified,
                      "headers": sorted((event.get("headers") or {}).keys()),
                      "claims": summary(claims) if claims else None}))
    if not claims:
        return {"statusCode": 401, "headers": {"www-authenticate": "Bearer"}, "body": ""}
    if path.startswith("/echo"):
        return respond(200, {"route": path, "claims": summary(claims)})
    if method != "POST":
        return {"statusCode": 405, "body": ""}
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode()
    request = json.loads(raw or "{}")
    rpc = request.get("method")
    if "id" not in request:
        return {"statusCode": 202, "body": ""}
    if rpc == "initialize":
        result = {"protocolVersion": request.get("params", {}).get("protocolVersion", "2025-06-18"),
                  "capabilities": {"tools": {}}, "serverInfo": {"name": "obo-spike", "version": "0"}}
    elif rpc == "tools/list":
        result = {"tools": [{"name": "whoami", "description": "Returns the claims of the token this server received.",
                             "inputSchema": {"type": "object", "properties": {}}}]}
    elif rpc == "tools/call":
        result = {"content": [{"type": "text", "text": json.dumps(summary(claims))}], "isError": False}
    else:
        return respond(200, {"jsonrpc": "2.0", "id": request["id"], "error": {"code": -32601, "message": "method not found"}})
    return respond(200, {"jsonrpc": "2.0", "id": request["id"], "result": result})


def client_token(event, client_id: str, form: dict) -> dict:
    """Spike only: a client credentials token naming the client alone (no employee), to see
    what a gateway does with it."""
    requested = form.get("scope", "").split()
    if not requested or any(s not in CLIENTS[client_id]["scopes"] for s in requested):
        return respond(400, {"error": "invalid_scope"})
    now = int(time.time())
    claims = {"iss": issuer(event), "sub": client_id, "aud": SCOPE_AUDIENCE[requested[0]], "scope": " ".join(requested),
              "scp": requested, "client_id": client_id, "iat": now, "exp": now + 3600, "jti": uuid.uuid4().hex}
    return respond(200, {"access_token": sign(claims), "token_type": "Bearer", "expires_in": 3600, "scope": claims["scope"]})
