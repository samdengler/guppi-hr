# On-behalf-of token exchange for `/p/hr/` (D20)

Status: design, revision 3, 3 October 2026. Revision 1 was reviewed by an independent
critique ([OBO Exchange Design Critique](https://claude.ai/artifact/FP3jciuzGA4PVVyoPWXwJK),
16 findings), and a spike on the prototype tested the alternatives the critique raised
(revision 2). Revision 3 puts the design on the AgentCore stack the POC is committed to,
Gateway, Policy, Identity and Runtime, after a second spike tested Policy and gateway-side
exchange against a copy of the HR tools runtime.

Okta stays the sign-in provider (D46). Okta's free plan cannot exchange tokens (X8), so
the exchange happens at a small issuer of our own on API Gateway, Lambda and KMS. The
issuer is a Lambda in the request path, which needs Sam's approval (AGENTS.md).

## The AgentCore pieces and their jobs

| Piece | Job in this design |
| --- | --- |
| Identity | Every exchange: the bridge's T0 to T1 and T1p, each sub-agent's T1 to T2, through on-behalf-of credential providers that hold the client secrets |
| Gateway | Checks every inbound hop token (issuer, audience, client, scope); the agents gateway passes T1 to the sub-agents |
| Policy | Decides each tool call on the tools gateway from the caller token's scopes, and filters `tools/list` to the tools that token may call |
| Runtime | Hosts the bridge, the sub-agents and the tools server; each runtime's authorizer checks the token it receives |

The exchange service itself sits outside AgentCore, as the identity provider would in
production (PingFederate at Delta): Identity needs an authorization server that speaks
RFC 8693, and Okta's free plan does not.

## One token opens every HR hop today

The page signs in with Okta and gets an access token (T0) with audience `api://guppi`.
That one token travels the whole request path:

- The bridge runtime puts it on the Connect contact as `hrToken`, and sends it to the
  agents gateway for its own warm calls (`turn.py:391`).
- The Agentic CX designer keeps the value it read at start (C2) and sends it to the agents
  gateway, and to the tools gateway for its own tool calls: policy search, opening a
  ticket, and in PolicyFlow `get_profile` and `list_pay_statements` (`hr.js:449-461`).
- The agents gateway passes it through to the sub-agent runtimes (`JWT_PASSTHROUGH`), and
  each sub-agent sends it on to the tools gateway.
- The HR tools server verifies a second copy in `X-Hr-User-Token`, because the tools
  gateway signs its own calls to the server with SigV4 (D19).

Every gateway and runtime checks the same issuer and audience (D46). A token taken from
any hop opens every hop for the rest of its hour. Nothing in it says which agent acted.
The tools server cannot tell a call from the Travel agent from a call from the Pay agent,
so a stolen token can call any tool. This was finding 1 of the first critique of the
Connect build, and its finding 17 noted that every hop checks the same thing.

## What exchange buys, and what it does not

With hop tokens:

- a token taken from one hop opens only the next hop, for the scopes that hop needs;
- the canvas's token reads the employee's profile and pay statements but cannot change
  anything;
- each sub-agent's tools token covers only its own domain: the issuer will not mint
  anything wider, and Gateway Policy refuses any tool outside the token's scopes;
- the Okta token stops at the bridge and the `/p/hr-diy/` orchestrator (it still travels
  from the page through the edge gateway, as today);
- every tool call carries the chain of clients that acted (`act`), recorded in the audit.

Two things stay as they are, and the threat list keeps them:

- **A stolen T1 can do what the agents can do.** It drives the agents gateway, and a sub-agent
  will exchange it for its own tools token. A thief who holds T1 and talks to the Pay
  agent can propose and commit a direct deposit change, as the employee could, until T1
  expires. Rate limits per employee and the one-hour life bound it.
- **The Connect participant token** that the bridge stores in DynamoDB drives the same
  designer, with T1 attached, for the life of the chat.

## The token chain

| Token | Holder | Exchanged from, by | Audience | Scope | Used for |
| --- | --- | --- | --- | --- | --- |
| T0 | page, bridge, `/p/hr-diy/` orchestrator | sign-in | `api://guppi` | `openid email profile offline_access` | edge gateway, bridge runtime, platform |
| T1 | the designer (contact attribute `hrAgentsToken`), the bridge's warm calls | T0, by the bridge | `api://hr-agents` | `hr.agents` | agents gateway, sub-agent runtimes |
| T1p | the designer (contact attribute `hrToolsToken`) | T0, by the bridge | `api://hr-tools` | `hr.tools.policy hr.tools.profile.read hr.tools.pay.read` | the canvas's own tool calls |
| T2 | each sub-agent | T1, by that sub-agent | `api://hr-tools` | its domain's scopes (below) | the sub-agent's tool calls |

Scopes per tool, enforced by Gateway Policy on the tools gateway (and checked again by
the tools server for `commit_change`):

| Scope | Tools |
| --- | --- |
| `hr.tools.policy` | `open_ticket` (and, at the gateway, the knowledge base target `docs___Retrieve`) |
| `hr.tools.profile.read` | `get_profile` |
| `hr.tools.profile.write` | `propose_address_change`, `propose_emergency_contact_change`, `commit_change` for a profile proposal |
| `hr.tools.pay.read` | `get_direct_deposit`, `list_pay_statements` |
| `hr.tools.pay.write` | `propose_direct_deposit_change`, `commit_change` for a pay proposal |

T2 scopes by domain:

| Sub-agent | T2 scope |
| --- | --- |
| Profile | `hr.tools.policy hr.tools.profile.read hr.tools.profile.write` |
| Pay | `hr.tools.policy hr.tools.pay.read hr.tools.pay.write` |
| Travel | `hr.tools.policy` |

The read and write split answers critique finding 1: PolicyFlow keeps its two read
tools, and the token that sits in Connect cannot write.

The bridge blanks `hrAgentsToken` and `hrToolsToken` right after the greeting, as it
blanks `hrToken` today (D42). The designer keeps the values it read at start (C2).

## Where the exchanges happen

Each caller exchanges for itself, through AgentCore Identity, and caches the result.

| Exchange | When | Caller cache |
| --- | --- | --- |
| T0 to T1 and T0 to T1p, two calls in parallel | the bridge, at the warm start, before `StartChatContact` (contact attributes are read only at start, C2) | none needed: one pair per contact |
| T1 to T2 | each sub-agent, at its warm call (D44), or at its first call on `/p/hr-diy/` | in the runtime process, keyed by T1's `jti`, kept until a minute before T2 expires, apart from the MCP session cache (D38) |
| T0 to T1 | the `/p/hr-diy/` orchestrator, at its first delegation in a thread | per thread, the same way |

The spikes tested letting the gateways do the exchange instead (critique finding 9):

- **Agents gateway: not possible today.** Its targets are HTTP targets (runtime targets).
  Configured with `TOKEN_EXCHANGE`, the gateway asked the issuer for `client_credentials`
  with no subject token, and the runtime received a token naming only the gateway's
  client, with no employee in it (aws-feedback A13). Per-agent tokens on the agents side
  therefore come from the sub-agents.
- **Tools gateway: works, and costs about 430 ms on every tool call.** MCP server
  targets do a real RFC 8693 exchange with the employee's token, so the tools runtime
  could verify it with its own JWT authorizer and `X-Hr-User-Token` could go. Against a
  copy of the HR tools runtime, the gateway exchanged once for every call and never reused
  a token. `get_profile` took a median of 1.92 s through it, against 1.49 s through today's
  tools gateway with the same client (A14). A sub-agent turn with two tool calls would pay
  close to a second.

The tools path therefore keeps today's shape for the hop from gateway to runtime, and puts
the per-tool decision in Gateway Policy:

1. The caller (a sub-agent with T2, or the canvas with T1p) calls the tools gateway with
   the token in `Authorization` and again in `X-Hr-User-Token`.
2. The gateway's authorizer checks issuer, audience, client and scope.
3. Gateway Policy allows the tool only if the token holds its scope.
4. The gateway calls the tools runtime with its own role (SigV4, D19) and forwards
   `X-Hr-User-Token`.
5. The tools server verifies that token as today, which tells it the employee.

This uses all four pieces with no exchange per call. Gateway-side exchange on the tools
gateway is the Delta-shaped option D20 describes. It becomes the better choice once the
gateway reuses an exchanged token until it expires, which is the request in A14.

## The issuer

One Lambda function behind an HTTP API, with an RSA 2048 KMS key for signing. Routes:
`GET /.well-known/openid-configuration`, `GET /jwks.json` and `POST /token` (RFC 8693
only; the spike's `client_credentials` grant and test routes are dropped).

### Clients and what each may exchange

Each client has a subject policy (critique finding 2). The issuer refuses any exchange
outside it:

| Client | Used by | Subject token it may present | May request |
| --- | --- | --- | --- |
| `hr-bridge` | the bridge runtime, the `/p/hr-diy/` orchestrator | Okta, audience `api://guppi`, `cid` the chat app or the harness, `uid` present | `hr.agents`; or the three T1p scopes |
| `hr-agent-profile` | the Profile sub-agent | this issuer's, audience `api://hr-agents`, `client_id` `hr-bridge`, `act` one deep | the Profile T2 scopes |
| `hr-agent-pay` | the Pay sub-agent | the same | the Pay T2 scopes |
| `hr-agent-travel` | the Travel sub-agent | the same | `hr.tools.policy` |

So a Travel runtime cannot mint a pay token, a T1p cannot become a T1, and no token can
be exchanged more than twice from Okta. One client per domain costs three secrets more
than the shared agent client of revision 1, about 1.20 dollars a month.

AgentCore Identity's IAM actor token (`actorTokenContent: AWS_IAM_ID_TOKEN_JWT`) would
identify each runtime by its role with no client secrets. It needs outbound web identity
federation turned on for the account, an account-wide IAM setting that is off today. It
is the better long-term answer and a decision for Sam; client secrets work now.

### Tokens it mints

- Claims: `iss` (a configured URL, never taken from the request), `sub` (Okta `uid`),
  `aud`, `scope` (the RFC 9068 string), `client_id`, `act` (nested per hop), `iat`,
  `nbf`, `exp`, `jti`.
- Header `typ` `at+jwt`.
- `scp` is dropped: the gateway's `allowedScopes` reads `scope` as well (A12).
- `exp` is the subject token's expiry or one hour, whichever comes first, so no token
  outlives the one it came from.

### Verification and hardening

These answer critique findings 10 and 13:

- **Verification uses PyJWT with `cryptography`**, in a layer, the library the tools
  server already uses. It checks the RS256 signature, `kid`, `iss`, `aud`, `exp`, `nbf`,
  `iat` and `typ`. Okta's keys are cached for an hour, and an unknown `kid` refetches
  them at most once a minute.
- **Errors are generic:** `invalid_client`, `invalid_grant`, `invalid_scope`, with no
  internal reason. A malformed request gets 400, never 500.
- **The API is throttled:** a rate of 10 a second with a burst of 20, against about 5
  exchanges per chat. The Lambda has reserved concurrency of 10, and a billing alarm sits
  on the API.
- **The KMS key policy** lets only the issuer's role call `kms:Sign`.
- **Cold starts are cut:** 1024 MB of memory, with Okta's keys and the KMS public key
  fetched at init.

### Secrets

- **Client secrets.** Each one is generated in Secrets Manager by the stack. The issuer
  reads them at cold start and compares hashes. Each AgentCore Identity credential
  provider references its secret with `clientSecretSource: EXTERNAL` instead of holding a
  copy (critique finding 11; to verify, since the spike did not try it). No secret
  appears in a context value, an environment variable, a file or a deploy script.
- **IAM.** Each runtime role may call `GetResourceOauth2Token` only on its own provider's
  ARN, and `GetWorkloadAccessTokenForJWT` only for its own workload identity.
- **Rotation.** Secrets are not rotated for the POC. The signing key is single, named by
  `kid`; rotation means publishing the new key beside the old one for an hour.

## Gateway, runtime and server checks

The spike confirmed what each authorizer enforces:

- `allowedScopes` reads `scope` or `scp`, and passes a token holding any one of the
  listed scopes, so each gateway lists exactly one.
- `allowedClients` matches this issuer's `client_id`.
- Both settings work on runtimes as well as gateways (A12, critique finding 7).

| Checkpoint | Issuer | Audience | `allowedClients` | `allowedScopes` |
| --- | --- | --- | --- | --- |
| Edge gateway, bridge runtime, `/p/hr-diy/` runtime | Okta | `api://guppi` | (A11) | none |
| Agents gateway | exchange service | `api://hr-agents` | `hr-bridge` | `hr.agents` |
| Sub-agent runtimes | exchange service | `api://hr-agents` | `hr-bridge` | `hr.agents` |
| Tools gateway | exchange service | `api://hr-tools` | `hr-bridge`, the three agent clients | `hr.tools.policy` (every T1p and T2 holds it) |

Binding the runtimes to `hr-bridge` and `hr.agents` means a T1p or a T2 cannot call a
sub-agent runtime directly. A T1 still can, outside the agents gateway's rate limit (part
of what a stolen T1 can do).

Gateway Policy on the tools gateway holds one Cedar rule per scope. The spike ran these
rules on a test gateway in front of a copy of the HR tools runtime:

```
permit(
  principal is AgentCore::OAuthUser,
  action in [AgentCore::Action::"hr___get_direct_deposit", AgentCore::Action::"hr___list_pay_statements"],
  resource == AgentCore::Gateway::"<tools gateway ARN>"
)
when { principal.hasTag("scope") && principal.getTag("scope") like "*hr.tools.pay.read*" };
```

What the rules did in the spike:

- **Tool lists:** each token's `tools/list` showed only its own tools. A Travel token saw
  `open_ticket` alone; the canvas token saw the reads and `open_ticket`.
- **Refusals:** every call outside a token's scopes was refused at the gateway, "denied by
  default", before reaching the runtime.
- **Cost:** none measurable (A15).

Every claim reaches Cedar as a string, so scope names must not be prefixes of one another
(A15). The rules live in the HR stack beside the gateway, and the engine runs in ENFORCE
mode.

The HR tools server keeps a second, smaller check on `X-Hr-User-Token` (critique findings
3 and 15):

- it accepts this issuer's tokens only, with audience `api://hr-tools`, `client_id` on the
  list above, and a `uid`-shaped `sub`;
- the token must hold the tool's scope, so a caller cannot pair an `Authorization` token
  that Policy allowed with a different employee token;
- `commit_change` loads the proposal first and requires the write scope of its domain,
  which Policy cannot see (it knows only the proposal id);
- the `act` chain is written to the audit table with each change.

During the switch the server accepts Okta's tokens as well. That needs code, since the
verifier takes one issuer today. A later step removes Okta.

## Latency

Measured from a laptop in Virginia against us-east-1 (prototype, 3 October):

| Call | Time |
| --- | --- |
| Direct exchange, cold start, 256 MB | 1,504 ms (init 470 ms, first exchange 772 ms) |
| Direct exchange, warm (20 calls) | median 126 ms, of which the Lambda took 16 ms |
| AgentCore `GetWorkloadAccessTokenForJWT` (10 calls) | median 80 ms |
| AgentCore `GetResourceOauth2Token` (10 calls) | median 190 ms, no caching (one issuer call each) |

Where the cost lands:

- **The bridge's exchange runs before the contact starts** (critique finding 6), since
  the designer reads attributes only at start. The warm start fires on the first focus
  on the composer (D44), so the exchange overlaps the employee's typing. It delays the
  first answer only when the first message is sent within a few hundred milliseconds of
  focus, or when the issuer is cold.
- **A cold issuer costs about 1.5 s at 256 MB.** The fixes above should cut that; if
  they do not, provisioned concurrency of one instance costs about 3 dollars a month.
- **A turn adds no exchange** while T2 is cached. A sub-agent restarted by AgentCore
  re-exchanges once.
- **The first delegation to each sub-agent on `/p/hr-diy/`** pays for one exchange, since
  that page has no warm start.

The first build step measures time to greeting and to first answer, warm and with a cold
issuer, from inside the bridge runtime, with the latency harness. The results go in the
latency log.

## When the issuer fails

Every caller fails closed, with a plain message, and no caller falls back to T0
(critique finding 12):

- **The bridge cannot exchange.** It does not start the contact, and the run ends with
  "HR could not confirm the sign-in. Try again in a minute." The `boto3` call has a
  5-second read timeout and one retry.
- **A sub-agent cannot exchange.** It answers that turn with the error line the canvas
  already shows for a failed tool call, and tries again on the next turn.
- **The tools server gets no valid token.** It refuses the call, as today.
- **Testing:** set the issuer's reserved concurrency to 0 and run the harness.

## Token lifetime and the one-hour contact

T1 and T1p expire with T0, and the contact lasts up to 60 minutes. The page refreshes T0
just before it sends the warm start, so T0, T1 and the contact begin together and end
within a minute of each other (critique finding 14). The bridge's existing rule stays as
the fallback: when a contact's token is within 5 minutes of expiry and a fresher one
arrives, it starts a new contact (`turn.py:446-457`, D42).

## Prototype and spike results

`prototypes/obo-issuer/` holds the throwaway stack `GuppiOboPrototype`. `run.py` ran the
first three checks; `spike.py` ran the rest after the critique.

| Check | Result |
| --- | --- |
| Exchange T0 to T1 as the bridge client | 200; audience `api://hr-agents`, `act` the bridge, `sub` the Okta `uid` |
| Exchange T1 to T2 as the agent client | 200; `act` nested, agent acting for bridge |
| Wrong secret; a scope the client lacks; a tampered token | 401; 400; 400 |
| AgentCore Identity on-behalf-of provider against the issuer | issued T1 with the same claims |
| Gateway trusting the issuer: T1, Okta token, no token | 200, 403, 401 |
| Gateway, `scope` alone; `scp` alone | 200; 200 |
| Gateway, right audience and wrong scope; wrong audience | 403; 403 |
| Gateway `allowedScopes` with two scopes, token holding one | 200 (any-of) |
| Gateway `allowedClients`, other client with the same scope and audience | 403 |
| Runtime with `allowedClients` and `allowedScopes`: right token; wrong client; wrong scope; Okta token; none | past the authorizer; 401 each for the rest |
| Gateway-side exchange, HTTP targets (runtime, passthrough) | client credentials only, no employee (A13) |
| Gateway-side exchange, MCP server target | real exchange, employee and `act` present; new exchange and MCP session every call (A14) |
| Gateway-side exchange to a copy of the HR tools runtime, `get_profile` x8 | median 1.92 s, eight exchanges; today's tools gateway 1.49 s (A14) |
| Gateway Policy, Cedar rules on `scope`, four tokens | each token listed and called only its tools; the rest refused; no added time (A15) |
| `JWT_PASSTHROUGH` on an MCP server target | refused by the API (A14) |

## Options compared

| Option | Outcome |
| --- | --- |
| Okta token exchange | Not on the free plan (X8) |
| Okta, two authorization servers trusting each other | Not on the free plan (X8) |
| Keycloak on Fargate with a database | 20 to 40 dollars a month, and a server to patch |
| Cognito with AWS's token-exchange sample | An API Gateway and six Lambda functions around a provider without the grant |
| Gateway-side exchange on the agents gateway | Not possible: HTTP targets fall back to client credentials (A13) |
| Gateway-side exchange on the tools gateway | Works; adds about 430 ms per tool call until the gateway reuses tokens (A14) |
| Per-tool checks in the tools server's code | Replaced by Gateway Policy, which also filters `tools/list` (A15) |
| IAM actor token instead of client secrets | Needs an account-wide IAM setting; Sam's decision |
| The issuer here | About 3 dollars a month; standard RFC 8693, so callers depend only on a discovery URL |

## Cost

| Item | Monthly |
| --- | --- |
| KMS key | 1.00 dollar |
| Secrets Manager, four client secrets (referenced, not copied) | 1.60 dollars |
| Lambda, HTTP API, AgentCore Identity calls at POC volume | under 0.50 dollars |
| Policy in AgentCore, one authorization per tool call and per `tools/list` | not yet priced; to confirm on the pricing page before the switch |

About 3 dollars a month before Policy, or 6 with one provisioned instance.

## Steps

The authorizers each trust one issuer and are shared by `/p/hr/`, `/p/hr-diy/` and the
bridge's warm calls (critique finding 4), so the change cannot roll out hop by hop.
Everything that can be built ahead is built first, then one deploy switches it all:

1. **Issuer** in the guppi-gpt platform stack, with:
   - unit tests for every row of the subject policy;
   - clients, secrets and credential providers;
   - SSM `/guppi/obo/*`;
   - alarms.

   No caller uses it yet. Measure cold and warm exchanges from inside a runtime.
2. **Tools server and Policy.** The tools server accepts both issuers, checks scopes on
   exchanged tokens, and records `act`. The Policy engine and its rules are created in
   LOG_ONLY mode on today's tools gateway, so their decisions show in the logs without
   blocking. With Okta tokens unchanged, the HR path is unaffected.
3. **Callers' code** behind one setting, `OBO=off`:
   - the bridge's exchange, attributes, blanking and failure message;
   - the sub-agents' exchange and cache;
   - the orchestrator's exchange;
   - the page's refresh before the warm start.
4. **The switch**, one deploy plus a canvas publish:
   - `OBO=on`;
   - the authorizers on the agents gateway, the three sub-agent runtimes and the tools
     gateway;
   - the Policy engine to ENFORCE;
   - `hr.js` reading `hrAgentsToken` and `hrToolsToken`.

   Rollback is a script that reverts the commit, redeploys and republishes the previous
   canvas version. Then run harness rounds on both pages and a latency run.
5. **Negative tests:**
   - T0 at each HR gateway;
   - T1p at the agents gateway and at a runtime;
   - a Travel T2 calling a pay tool;
   - T1p calling a write tool;
   - a T2 exchanged a third time;
   - the issuer at concurrency 0.

   Also a Dynatrace query showing that no token appears in a span.
6. **Remove Okta from the tools server.**
7. **Clean up** the prototype stack, workload identity, credential provider, test
   runtime and test gateways. Also remove the Okta objects from the first attempt:
   - the `hr-agents` authorization server;
   - the `hr-bridge-obo` and `hr-agent-obo` apps;
   - the `hr.*` scopes on `guppi`;
   - the `okta-hr-bridge` and `okta-hr-agent` providers;
   - `/guppi/hr/obo/*`.

## Decisions for Sam

1. Approve the issuer as a Lambda in the request path. It runs about five times per chat,
   never per turn.
2. On the tools path, Gateway Policy decides each tool and `X-Hr-User-Token` carries the
   employee to the runtime (recommended), or the gateway exchanges on every call and the
   runtime verifies the token itself, at about 430 ms per tool call until AWS adds token
   reuse (A14).
3. A client per domain with secrets (recommended for now), or turn on outbound web
   identity federation for the account and use IAM actor tokens.
4. The issuer in the platform stack (recommended) or the HR stack.
5. One switch with a scripted rollback (recommended), or new gateways and runtimes side
   by side, which costs a second set of runtimes during the move.
