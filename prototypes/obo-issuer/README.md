# Token-exchange issuer prototype (throwaway)

Proves, before building D20 for real, that a self-hosted RFC 8693 issuer works with Okta
sign-in and with AgentCore, since Okta's free plan cannot exchange tokens (aws-feedback X8).
`issuer/handler.py` is one Lambda behind an HTTP API, with a KMS signing key and no
dependencies; `run.py` deploys `GuppiOboPrototype` and runs three checks.

Results on 3 October 2026:

1. Direct exchange: the harness's Okta token became an `hr.agents` token (audience
   `api://hr-agents`, `act` the bridge client), and that became an `hr.tools.profile`
   token (audience `api://hr-tools`, `act` the agent client acting for the bridge). A
   wrong secret got 401, a scope the client lacks 400, a tampered token 400.
2. AgentCore Identity: `GetWorkloadAccessTokenForJWT` accepted the Okta token, and
   `GetResourceOauth2Token` with `ON_BEHALF_OF_TOKEN_EXCHANGE` returned this issuer's token
   through an on-behalf-of credential provider.
3. AgentCore Gateway: an MCP gateway trusting this issuer (audience `api://hr-agents`,
   `allowedScopes` `hr.agents`) answered 200 to the exchanged token, 403 to the Okta token
   and 401 to none. A custom claim on `scp` is refused (aws-feedback A12).

Left in place for review: the stack, the workload identity `obo-prototype`, the credential
provider `obo-prototype-bridge` and the gateway `obo-prototype-gw`.
