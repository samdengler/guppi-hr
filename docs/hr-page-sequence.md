# Sign-in to first answer on /p/hr/

How an employee gets from the sign-in screen to an answer on `chat.dengler.io/p/hr/`, the
Connect project (D39 to D50). Three stages: sign-in and page load, the warm start the page
sends for each new chat, and a question. Times are from the harness and the logs of
4 October 2026 (L23, L24); the decisions are in [decision-log.md](decision-log.md).

Who is who in the diagrams:

| Name | What it is |
| --- | --- |
| Page | guppi-gpt's page with this project's manifest (`connect/web/manifest.json`), `web/src/app.js` |
| Okta | The Okta org: the app `chat.dengler.io`, its sign-in policy (D49), the authorization server `guppi` (audience `api://guppi`, members of `chat-users` only) |
| Edge | CloudFront and the platform's edge gateway (AWS WAF, per-user limits, JWT check) |
| Bridge | AgentCore Runtime `guppi_connect_bridge`: one AG-UI run as one Connect chat turn (`connect/agent/src/connect_bridge/turn.py`) |
| Identity | AgentCore Identity: holds each client's secret and makes the RFC 8693 exchange (D47) |
| Issuer | guppi-gpt's token issuer: API Gateway and the Lambda `guppi-gpt-obo-issuer` |
| Connect | The chat contact, its contact flow and the Agentic CX canvas (`connect/acxd/hr.js`) |
| Agents GW | AgentCore Gateway `hr-super-agent-agents`, one target per sub-agent |
| Sub-agent | AgentCore Runtime `hr_super_agent_{profile,pay,travel}`, Haiku 4.5, A2A |
| Tools GW | AgentCore Gateway `hr-super-agent-tools` with its Cedar policy engine |
| Tools | AgentCore Runtime `hr_super_agent_tools` (MCP) over the DynamoDB tables |

## Sign-in and page load

The page keeps a session (refresh token) in the browser. With one, a load refreshes it
silently and shows the chat; without one, the employee signs in through Okta.

```mermaid
sequenceDiagram
    autonumber
    actor Employee
    participant Page
    participant Okta

    Employee->>Page: open chat.dengler.io/p/hr/
    Page->>Page: config.json, the project manifest (warm-start, suggestions)
    alt a stored session
        Page->>Okta: refresh token grant (refresh tokens rotate)
        Okta-->>Page: new access token (1 hour), id token, refresh token
    else no session, or it was refused
        Page-->>Employee: sign-in screen
        Employee->>Page: Sign in
        Page->>Okta: /authorize with PKCE
        Okta->>Employee: password, then Okta Verify push or code (D49)
        Employee-->>Okta: both factors
        Okta->>Okta: in chat-users? (otherwise "not assigned to the application")
        Okta-->>Page: redirect with a code
        Page->>Okta: code and PKCE verifier for tokens
        Okta-->>Page: access token (aud api://guppi), id token, refresh token
    end
    Page-->>Employee: the chat: empty state and the four suggestions
    Note over Page: the page is signed in and in view, so it sends the warm start now (D50)
```

## Warm start

For each new chat the page posts a run with no messages and `forwardedProps.warm`. It goes
out as soon as the signed-in page is in view: at load, at sign-in, on New chat, or when a
hidden tab comes into view; a chat still empty 50 minutes later is warmed again when the
employee comes back (D50, guppi-gpt `warmDue`). It takes 6.4 to 8.4 s, all of it before
the employee asks anything.

```mermaid
sequenceDiagram
    autonumber
    participant Page
    participant Edge
    participant Bridge
    participant Identity
    participant Issuer
    participant Connect
    participant AgentsGW as Agents GW
    participant Sub as Sub-agent (x3)
    participant ToolsGW as Tools GW
    participant Tools

    Page->>Edge: POST /api/hr/invocations, no messages, warm, Okta token
    Edge->>Bridge: token checked, passed through
    opt the page left a chat
        Bridge->>Connect: end the old chat's contact
    end
    par four exchanges at once
        Bridge->>Identity: Okta token for 3 agents tokens and the canvas tools token
        Identity->>Issuer: RFC 8693 token exchange, client hr-bridge
        Issuer-->>Identity: hop tokens, each naming the employee
        Identity-->>Bridge: hop tokens
    end
    Note over Bridge,Issuer: about 0.4 s, 2.3 s when the issuer is cold (L25)
    Bridge->>Connect: StartChatContact, hop tokens as attributes, 60 minutes
    Bridge->>Connect: CreateParticipantConnection and open the WebSocket
    par the canvas starts
        Connect->>Connect: the flow runs, the canvas reads the tokens and greets
        Connect-->>Bridge: greeting (not shown), the bridge blanks the token attributes
    and each sub-agent warms
        Bridge->>AgentsGW: A2A warm message, the sub-agent's agents token
        AgentsGW->>Sub: on the canvas's runtime session and thread
        Sub->>Identity: agents token for its domain's tools token
        Identity->>Issuer: exchange, client hr-agent-(name)
        Issuer-->>Sub: tools token (via Identity)
        Sub->>ToolsGW: read the employee's record (Profile, Pay) or search the travel policy (Travel)
        ToolsGW->>Identity: exchange for a runtime token, client hr-tools-gateway
        Identity->>Issuer: exchange
        ToolsGW->>ToolsGW: Cedar policy on the tool and scopes
        ToolsGW->>Tools: MCP tools/call with the runtime token
        Tools-->>Sub: the record or passages, cached for the conversation
    end
    Note over Bridge,Connect: starting the contact is 2.6 to 3.2 s of this
    Bridge-->>Page: RUN_FINISHED
```

## A question

A suggestion press or a typed question after the warm start finds the contact, the
sub-agent sessions and the record ready. First words in 1.3 to 5.0 s, depending on the
question (L24). A question sent while the warm start is still running waits for its end;
under D44 a suggestion press always did, at 8.5 s median.

```mermaid
sequenceDiagram
    autonumber
    actor Employee
    participant Page
    participant Edge
    participant Bridge
    participant Connect
    participant AgentsGW as Agents GW
    participant Sub as Sub-agent
    participant ToolsGW as Tools GW

    Employee->>Page: press "Change my address", or type and send
    Page->>Edge: POST /api/hr/invocations with the thread
    Edge->>Bridge: token checked
    Bridge->>Connect: SendMessage on the stored contact
    Bridge->>Connect: a fresh WebSocket for the replies
    Connect->>Connect: the canvas routes (Haiku 4.5, about 0.45 s)
    alt a domain question
        Connect->>AgentsGW: A2A message, Bearer (that sub-agent's agents token)
        AgentsGW->>Sub: the warm session
        opt a write, or a read not cached at the warm start
            Sub->>ToolsGW: MCP tool call (the gateway exchanges as above)
            ToolsGW-->>Sub: result
        end
        Sub-->>Connect: answer, at most two short sentences
    else a policy question
        Connect->>ToolsGW: PolicyFlow: docs___Retrieve with the canvas tools token
        ToolsGW-->>Connect: passages, the journey answers (Haiku 4.5)
    end
    Connect-->>Bridge: reply pushed over the WebSocket, ending in the turn mark (D42)
    Bridge-->>Page: TEXT_MESSAGE events, RUN_FINISHED
    Page-->>Employee: the answer
```
