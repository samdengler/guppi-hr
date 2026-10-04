'use strict';

/**
 * The HR super-agent as an Agentic CX designer application (shape D).
 *
 * The canvas replaces hr-super-agent's Strands orchestrator and nothing below it:
 *
 * - WelcomeFlow greets once and hands each turn to the flow the application recognizes
 *   ({System.capturedFlow}); anything unrecognized goes to PolicyFlow.
 * - ClarifyFlow answers the ambiguous "update my information" with one question.
 * - ProfileFlow, PayFlow and TravelFlow delegate every turn to their sub-agent with one
 *   A2A message/send (a JSON string template, so nested fields are filled), the
 *   sub-agent's own agents token in the Authorization header (guppi-hr D47: the bridge
 *   trades the employee's Okta token for one per sub-agent; the tools calls carry a
 *   read-only tools token). A follow-up stays in the flow; a turn
 *   the application recognizes as another domain redirects there (sticky context, D6).
 * - A reply that carries a pending change goes to a fixed confirmation step. Only its
 *   "yes" branch sends the pending change back, so nothing commits without it (D7).
 * - PolicyFlow searches the policy documents with one fixed data request (PolicySearch) and
 *   answers from those passages in a generative journey with no tools (guppi-hr D52); its
 *   exits hand reads, changes and requests for a person to the other flows.
 * - EscalationFlow opens an HR ticket through the tools gateway, gives the employee its
 *   id and ends the conversation; nobody staffs a Connect queue (D43).
 * - Every reply node that ends a turn ends its text with END_MARK, an invisible character
 *   the bridge ends the turn on instead of waiting for silence (D42); a node that ends
 *   the conversation uses CLOSED_MARK. Neither is a message of its own, since Connect
 *   bills chat by the message. A generative journey's
 *   own answers cannot be followed by a node, so those turns still end on silence, and
 *   the journey is told to write nothing before it hands off to a domain flow.
 *
 * Delegate data requests point at the spike's mock sub-agents in `development` and at
 * hr-super-agent's agents gateway in `production`.
 */

const { FlowBuilder, statusIs } = require('./lib/nodes');
const { MOCK_URL, AGENTS_GATEWAY_URL, TOOLS_GATEWAY_URL, env, hdr } = require('./lib/common');

// The policy journey runs on Haiku 4.5 with short answers: for the POC, speed comes before
// answer length (Sam, 3 Oct; docs/latency-log.md, L21).
const HAIKU = 'anthropic.claude-haiku-4-5';
const CONV = '{System.conversationId:NLX.System}';
const UTTERANCE = '{System.utterance:NLX.System}';
// End-of-turn and closed signals ride on the reply itself, as one invisible trailing
// character, because Connect bills chat by the message and a separate hidden line made
// every turn three messages instead of two (connect_bridge.turn, END_MARK and
// CLOSED_MARK). The bridge strips the character before the page sees the text.
const END_MARK = '\u2063'; // INVISIBLE SEPARATOR: the turn is over
const CLOSED_MARK = '\u2064'; // INVISIBLE PLUS: the conversation ends after this message
const endsTurn = (text) => `${text}${END_MARK}`;
const closes = (text) => `${text}${CLOSED_MARK}`;

// The domain names live in domains.json, which the bridge's stack also reads for the warm
// start's session names ("{conversationId}-{domain}"); the check below keeps the two from
// drifting apart (critique finding 15).
const DOMAIN_NAMES = require('./domains.json');

const DOMAINS = [
  {
    name: 'profile',
    flowId: 'ProfileFlow',
    title: 'Profile',
    // Routing text taken from hr-super-agent's own domain descriptions (agents/domains.py).
    aiDescription:
      "The employee's own personal record: name, job, home address and emergency contact. Show or change the home address or emergency contact, and tax effects of a move.",
    utterances: [
      'Change my home address',
      'I moved and need to update my address',
      'Update my emergency contact',
      'What address do you have on file for me',
      'Who is my emergency contact',
      'What name and job do you have for me',
      'Will moving change anything on my record',
      'profile',
      'my profile',
    ],
  },
  {
    name: 'pay',
    flowId: 'PayFlow',
    title: 'Pay',
    aiDescription:
      'Where and when the employee is paid: show or change the direct deposit account, list recent pay statements, pay schedule and payroll correction questions.',
    utterances: [
      'Change my direct deposit',
      'Update my bank account for direct deposit',
      'Show my last pay statements',
      'When is my next paycheck',
      'Where does my pay go',
      'pay',
      'my pay details',
    ],
  },
  {
    name: 'travel',
    flowId: 'TravelFlow',
    title: 'Travel',
    aiDescription:
      'The employee travel benefit: pass travel eligibility, buddy passes and their service charges, boarding priority and embargo dates.',
    utterances: [
      'How many buddy passes do I get',
      'Can my parents fly on my pass travel',
      'What are my flight benefits',
      'How does nonrev travel work',
      'Who is eligible for pass travel',
    ],
  },
];

if (JSON.stringify(DOMAINS.map((d) => d.name)) !== JSON.stringify(DOMAIN_NAMES)) {
  throw new Error(`hr.js domains ${DOMAINS.map((d) => d.name)} differ from domains.json ${DOMAIN_NAMES}`);
}

const CONTEXT_VARIABLES = [
  { name: 'welcomeGreeted', schema: { type: 'number' }, disallowExternalModification: false },
  { name: 'activeDomain', schema: { type: 'string' }, disallowExternalModification: false },
  ...DOMAINS.flatMap((d) => [
    { name: `lastUserText${d.title}`, schema: { type: 'string' }, disallowExternalModification: false },
    { name: `lastReply${d.title}`, schema: { type: 'string' }, disallowExternalModification: false },
  ]),
];

// Each sub-agent takes only its own agents token (guppi-hr D47; critique of the build,
// finding 3), which the bridge puts on the contact as hrProfileToken, hrPayToken and
// hrTravelToken.
const agentsTokenName = (domain) => `hr${domain[0].toUpperCase()}${domain.slice(1)}Token`;

const authHeaders = (sessionSuffix) => [
  hdr('Authorization', `Bearer {${agentsTokenName(sessionSuffix)}:NLX.Context}`, { sensitive: true }),
  hdr('Content-Type', 'application/json'),
  hdr('X-Amzn-Bedrock-AgentCore-Runtime-Session-Id', `${CONV}-${sessionSuffix}`),
];

const A2A_REPLY_SCHEMA = {
  type: 'object',
  properties: {
    jsonrpc: { type: 'string' },
    result: {
      type: 'object',
      properties: {
        contextId: { type: 'string' },
        parts: {
          type: 'array',
          items: {
            type: 'object',
            properties: { kind: { type: 'string' }, text: { type: 'string' }, data: { type: 'object' } },
          },
        },
      },
    },
  },
};

const delegateId = (d, confirm) => `Delegate${d.title}${confirm ? 'Confirm' : ''}`;

function delegateDataRequest(d, confirm) {
  return {
    dataRequestId: delegateId(d, confirm),
    type: 'object',
    description: `${d.title} sub-agent over A2A${confirm ? ', confirming a pending change' : ''}.`,
    webhook: {
      implementation: 'external',
      method: 'POST',
      environments: env(
        `${MOCK_URL}/a2a/${d.name}/invocations`,
        authHeaders(d.name),
        `${AGENTS_GATEWAY_URL}/${d.name}/invocations`,
      ),
    },
    responseSchema: A2A_REPLY_SCHEMA,
  };
}

/** The A2A body as a JSON string template: the runtime fills and escapes each placeholder. */
function delegateBody(d, confirm) {
  const last = `{${delegateId(d, false)}.result.parts`;
  const pending = (field) => `${last}.1.data.pendingAction.${field}:NLX.Variable}`;
  return JSON.stringify({
    jsonrpc: '2.0',
    id: CONV,
    method: 'message/send',
    params: {
      message: {
        role: 'user',
        messageId: CONV,
        contextId: CONV,
        parts: [{ kind: 'text', text: UTTERANCE }],
        metadata: {
          employeeId: '{employeeId:NLX.Context}',
          history: [
            { role: 'user', content: `{lastUserText${d.title}:NLX.Context}` },
            { role: 'assistant', content: `{lastReply${d.title}:NLX.Context}` },
          ],
          pendingAction: confirm
            ? {
                proposalId: pending('proposalId'),
                field: pending('field'),
                before: pending('before'),
                after: pending('after'),
              }
            : null,
        },
      },
    },
  });
}

const capturedOther = (selfId) => [
  { left: { type: 'captured_flow' }, operator: 'exists' },
  { left: { type: 'captured_flow' }, operator: 'neq', right: { type: 'constant', value: selfId } },
  { left: { type: 'captured_flow' }, operator: 'neq', right: { type: 'constant', value: 'PolicyFlow' } },
];
/**
 * The edges a listen node takes when the turn stays in this flow. A user_input node
 * with an unconditional edge does not wait for input (AICC sample live notes), so the
 * "anything else" case is spelled out: no flow recognized, this flow, or the unknown
 * default (PolicyFlow), which an unmatched utterance still captures.
 */
const stayEdges = (selfId, to, name) => [
  { to, name: `${name}None`, when: [{ left: { type: 'captured_flow' }, operator: 'not_exists' }] },
  { to, name: `${name}Self`, when: [{ left: { type: 'captured_flow' }, operator: 'eq', right: { type: 'constant', value: selfId } }] },
  { to, name: `${name}Unknown`, when: [{ left: { type: 'captured_flow' }, operator: 'eq', right: { type: 'constant', value: 'PolicyFlow' } }] },
];
/**
 * A question the application recognizes as a policy question (PolicyFlow with an intent),
 * as opposed to input it does not recognize, which it also files under PolicyFlow but with
 * the intent NLX.Unknown. Only the first leaves a domain flow (seen 3 Oct: "How much PTO
 * do I earn per year?" after a profile question went to the Profile agent, which declined).
 */
const recognizedPolicy = [
  { left: { type: 'captured_flow' }, operator: 'eq', right: { type: 'constant', value: 'PolicyFlow' } },
  { left: { type: 'system', name: 'System.capturedIntent' }, operator: 'neq', right: { type: 'constant', value: 'NLX.Unknown' } },
];
const utteranceMatches = (regex) => [
  { left: { type: 'system', name: 'System.utterance' }, operator: 'matches_regex', right: { type: 'constant', value: regex } },
];
// A bare confirmation only, like NO: "yes, but make it Apt 4B" or "ok, what's the tax
// effect?" goes back to the sub-agent without the pending change, which re-proposes.
const YES = '^\\s*([Yy]es|[Yy]eah|[Yy]ep|[Cc]onfirm|[Oo][Kk]|[Oo]kay|[Ss]ure|[Gg]o ahead|[Pp]lease do|[Dd]o it)( please)?[\\s.!]*$';
// A bare refusal only: "no, make it 421 instead" goes back to the sub-agent to re-propose.
const NO = '^\\s*([Nn]o|[Nn]ope|[Cc]ancel|[Nn]ever ?mind|[Dd]on.t do it|[Ss]top)[\\s.!]*$';
const setContext = (name, value) => ({ type: 'context', name, modification: 'set', value });
/** The turn's utterance and the reply just given, kept as the next call's history. */
const remember = (d, confirm) => [
  setContext(`lastUserText${d.title}`, { type: 'system', name: 'System.utterance' }),
  setContext(`lastReply${d.title}`, { type: 'variable', name: `${delegateId(d, confirm)}.result.parts.0.text` }),
];

function domainFlow(d) {
  const f = new FlowBuilder(d.flowId);
  const call = (id, confirm) => ({
    dataRequestId: delegateId(d, confirm),
    name: delegateId(d, confirm),
    headers: {},
    payload: delegateBody(d, confirm),
    alwaysRetrigger: true,
  });
  const reply = (confirm) => `{${delegateId(d, confirm)}.result.parts.0.text:NLX.Variable}`;
  const pendingExists = [
    {
      left: { type: 'variable', name: `${delegateId(d, false)}.result.parts.1.data.pendingAction.proposalId` },
      operator: 'exists',
    },
  ];

  f.add('start', 'start', {
    children: ['call'],
    metadata: { stateModifications: [setContext('activeDomain', { type: 'constant', value: d.name })] },
  })
    .add('call', 'data_request', {
      children: [
        { to: 'route', when: [statusIs('success')] },
        { to: 'unreachable', when: [statusIs('failure')] },
        { to: 'unreachable', when: [statusIs('timeout')] },
      ],
      dataRequests: [call('call', false)],
      metadata: { timeout: 30000 },
    })
    .add('route', 'choice', { children: [{ to: 'replyPending', when: pendingExists }, 'reply'] })
    .add('reply', 'basic', {
      children: ['toListen'],
      messages: [endsTurn(reply(false))],
      metadata: { stateModifications: remember(d, false) },
    })
    .add('replyPending', 'basic', {
      children: ['confirm'],
      messages: [endsTurn(reply(false))],
      metadata: { stateModifications: remember(d, false) },
    })
    .add('confirm', 'user_input', {
      children: [
        { to: 'commit', when: utteranceMatches(YES), name: 'confirmed' },
        { to: 'declined', when: utteranceMatches(NO), name: 'declined' },
        // Any other reply to a pending change stays with this sub-agent (hr-super-agent
        // D28): "no, make it 421 instead" re-proposes. It goes without the pending
        // change, so it cannot commit. captured_flow exists covers every other flow.
        ...stayEdges(d.flowId, 'call', 'otherReply'),
        { to: 'call', when: [{ left: { type: 'captured_flow' }, operator: 'exists' }], name: 'otherReplyAny' },
      ],
    })
    .add('commit', 'data_request', {
      children: [
        { to: 'replyCommit', when: [statusIs('success')] },
        { to: 'unreachable', when: [statusIs('failure')] },
        { to: 'unreachable', when: [statusIs('timeout')] },
      ],
      dataRequests: [call('commit', true)],
      metadata: { timeout: 30000 },
    })
    .add('replyCommit', 'basic', {
      children: ['toListen'],
      messages: [endsTurn(reply(true))],
      metadata: { stateModifications: remember(d, true) },
    })
    .add('declined', 'basic', { children: ['toListen'], messages: [endsTurn("Okay, I won't make that change.")] })
    .add('unreachable', 'basic', {
      children: ['toListen'],
      messages: [endsTurn(`Sorry, the ${d.title} agent could not be reached just now.`)],
    })
    // A second user_input reached in the same turn re-reads that turn's utterance
    // (AICC sample live notes), so a reply ends the turn with a redirect to this flow's
    // listen node instead of an edge.
    .add('toListen', 'redirect', {
      children: ['end'],
      metadata: { redirect: { type: 'flow', flowId: d.flowId, nodeId: f.id('listen') } },
    })
    .add('listen', 'user_input', {
      children: [
        { to: 'shift', when: capturedOther(d.flowId), name: 'topicShift' },
        { to: 'shift', when: recognizedPolicy, name: 'policyShift' },
        ...stayEdges(d.flowId, 'call', 'followUp'),
      ],
    })
    .add('shift', 'redirect', {
      children: ['end'],
      metadata: { redirect: { type: 'flow', flowId: '{System.capturedFlow:NLX.System}' } },
    })
    .add('end', 'end');

  return {
    flowId: d.flowId,
    description: `Delegates each turn to the ${d.title} sub-agent over A2A and confirms writes.`,
    aiDescription: d.aiDescription,
    utterances: d.utterances.map((text) => ({ text })),
    contextVariables: [
      { name: 'activeDomain', type: 'text' },
      { name: `lastUserText${d.title}`, type: 'text' },
      { name: `lastReply${d.title}`, type: 'text' },
      { name: agentsTokenName(d.name), type: 'text' },
      { name: 'hrToolsToken', type: 'text' },
      { name: 'employeeId', type: 'text' },
    ],
    nodes: f.nodes,
  };
}

function welcomeFlow() {
  const f = new FlowBuilder('WelcomeFlow');
  f.add('start', 'start', { children: ['guard'] })
    .add('guard', 'choice', {
      children: [
        {
          to: 'listen',
          when: [{ left: { type: 'context', name: 'welcomeGreeted' }, operator: 'gte', right: { type: 'constant', value: 1 } }],
        },
        'greet',
      ],
    })
    .add('greet', 'basic', {
      children: ['listen'],
      messages: [
        "Hi, I'm the HR assistant. I can help with your home address and emergency contact, your pay and direct deposit, your travel benefits, and HR policy questions.",
      ],
      metadata: { stateModifications: [setContext('welcomeGreeted', { type: 'constant', value: 1 })] },
    })
    .add('listen', 'user_input', {
      children: [
        {
          to: 'help',
          when: [{ left: { type: 'captured_flow' }, operator: 'eq', right: { type: 'constant', value: 'WelcomeFlow' } }],
          name: 'smallTalk',
        },
        { to: 'toCaptured', when: [{ left: { type: 'captured_flow' }, operator: 'exists' }], name: 'recognized' },
        { to: 'toPolicy', when: [{ left: { type: 'captured_flow' }, operator: 'not_exists' }], name: 'unrecognized' },
      ],
    })
    // "Hi there" is captured as WelcomeFlow itself; a redirect to it would land on a
    // silent listen node and fail the turn with NoMessages (live, 2026-10-02).
    .add('help', 'basic', {
      children: ['toListen'],
      messages: [
        endsTurn(
          'I can help with your home address and emergency contact, your pay and direct deposit, your travel benefits, or an HR policy question. What do you need?',
        ),
      ],
    })
    .add('toListen', 'redirect', {
      children: ['end'],
      metadata: { redirect: { type: 'flow', flowId: 'WelcomeFlow', nodeId: f.id('listen') } },
    })
    .add('toCaptured', 'redirect', {
      children: ['end'],
      metadata: { redirect: { type: 'flow', flowId: '{System.capturedFlow:NLX.System}' } },
    })
    .add('toPolicy', 'redirect', { children: ['end'], metadata: { redirect: { type: 'flow', flowId: 'PolicyFlow' } } })
    .add('end', 'end');
  return {
    flowId: 'WelcomeFlow',
    untrained: true,
    description: 'Greets once, then hands each turn to the recognized flow; unrecognized goes to PolicyFlow.',
    aiDescription: 'System flow; not a routing target.',
    contextVariables: [{ name: 'welcomeGreeted', type: 'number' }],
    nodes: f.nodes,
  };
}

function clarifyFlow() {
  const f = new FlowBuilder('ClarifyFlow');
  f.add('start', 'start', { children: ['ask'] })
    .add('ask', 'user_input', {
      messages: [
        endsTurn(
          'Do you want to update your profile (home address or emergency contact) or your pay details (direct deposit)?',
        ),
      ],
      children: [
        {
          to: 'toCaptured',
          when: [
            { left: { type: 'captured_flow' }, operator: 'exists' },
            { left: { type: 'captured_flow' }, operator: 'neq', right: { type: 'constant', value: 'ClarifyFlow' } },
            { left: { type: 'captured_flow' }, operator: 'neq', right: { type: 'constant', value: 'PolicyFlow' } },
          ],
          name: 'chosen',
        },
        ...stayEdges('ClarifyFlow', 'again', 'unclear'),
      ],
    })
    .add('again', 'basic', { children: ['ask'], messages: ['Please say "profile" or "pay".'] })
    .add('toCaptured', 'redirect', {
      children: ['end'],
      metadata: { redirect: { type: 'flow', flowId: '{System.capturedFlow:NLX.System}' } },
    })
    .add('end', 'end');
  return {
    flowId: 'ClarifyFlow',
    description: 'Asks one clarifying question when the employee wants to update information without saying which.',
    aiDescription:
      'A vague request to change, update, fix or check the employee information, details, records or account without saying whether it is the address, the emergency contact or pay.',
    utterances: [
      'I need to update my information',
      'Update my details',
      'I want to change my info',
      'I need to change some of my information',
    ].map((text) => ({ text })),
    nodes: f.nodes,
  };
}

// The tools on the HrTools MCP data request. The policy journey uses none of them (D52):
// the designer fails every call to this data request with "data request could not be
// prepared" before any HTTP request (spike fact 11, last seen 2 Oct), so a tool call only
// cost the journey a model step. The data request stays defined for when it can be prepared.
const HR_TOOLS = [
  {
    name: 'docs___Retrieve',
    enabled: true,
    // As the tools gateway lists it (guppi-mcp-app .deploy/phase4-gateway-probe.txt).
    requestSchema: {
      type: 'object',
      properties: { retrievalQuery: { type: 'object', properties: { text: { type: 'string' } } } },
      required: ['retrievalQuery'],
    },
  },
  { name: 'hr___get_profile', enabled: true, requestSchema: { type: 'object', properties: {} } },
  { name: 'hr___list_pay_statements', enabled: true, requestSchema: { type: 'object', properties: { count: { type: 'integer' } } } },
  {
    name: 'hr___open_ticket',
    enabled: true,
    requestSchema: {
      type: 'object',
      properties: { summary: { type: 'string' }, domain: { type: 'string' } },
      required: ['summary'],
    },
  },
  // Writes stay with the sub-agents: listed so the choice is visible, never enabled.
  { name: 'hr___propose_address_change', enabled: false },
  { name: 'hr___propose_emergency_contact_change', enabled: false },
  { name: 'hr___propose_direct_deposit_change', enabled: false },
  { name: 'hr___commit_change', enabled: false },
];

function hrToolsDataRequest() {
  const headers = [
    hdr('Authorization', 'Bearer {hrToolsToken:NLX.Context}', { sensitive: true }),
    hdr('X-Hr-Thread-Id', CONV),
  ];
  return {
    dataRequestId: 'HrTools',
    type: 'object',
    description: 'hr-super-agent tools gateway over MCP: policy search, profile, pay statements, tickets.',
    webhook: {
      implementation: 'mcp',
      mcp: {
        method: 'POST',
        // Top-level url and headers as well as per environment: with environments alone
        // every call failed "data request could not be prepared" (live, 2026-10-02).
        url: TOOLS_GATEWAY_URL,
        headers,
        environments: env(TOOLS_GATEWAY_URL, headers),
        tools: HR_TOOLS,
      },
    },
  };
}

/**
 * MCP over a plain HTTP data request: one JSON-RPC tools/call to the tools gateway, the
 * same headers as the sub-agents send (D19). The canvas decides to search, so this is a
 * fixed step, not a model's tool call.
 */
function policySearchDataRequest() {
  return {
    dataRequestId: 'PolicySearch',
    type: 'object',
    description: 'tools/call docs___Retrieve on the hr-super-agent tools gateway over HTTP.',
    webhook: {
      implementation: 'external',
      method: 'POST',
      environments: env(TOOLS_GATEWAY_URL, [
        hdr('Authorization', 'Bearer {hrToolsToken:NLX.Context}', { sensitive: true }),
        hdr('X-Hr-Thread-Id', CONV),
        hdr('Content-Type', 'application/json'),
        hdr('Accept', 'application/json'),
      ]),
    },
    responseSchema: {
      type: 'object',
      properties: {
        result: {
          type: 'object',
          properties: {
            content: { type: 'array', items: { type: 'object', properties: { type: { type: 'string' }, text: { type: 'string' } } } },
            isError: { type: 'boolean' },
          },
        },
      },
    },
  };
}

const POLICY_SEARCH_BODY = JSON.stringify({
  jsonrpc: '2.0',
  id: CONV,
  method: 'tools/call',
  params: { name: 'docs___Retrieve', arguments: { retrievalQuery: { text: UTTERANCE } } },
});

function policyFlow() {
  const f = new FlowBuilder('PolicyFlow');
  const gj = (i) => [{ left: { type: 'system', name: 'System.gjConditionIndex' }, operator: 'eq', right: { type: 'constant', value: i } }];
  f.add('start', 'start', { children: ['search'] })
    .add('search', 'data_request', {
      children: [
        { to: 'journey', when: [statusIs('success')] },
        { to: 'journey', when: [statusIs('failure')] },
        { to: 'journey', when: [statusIs('timeout')] },
      ],
      dataRequests: [
        { dataRequestId: 'PolicySearch', name: 'PolicySearch', headers: {}, payload: POLICY_SEARCH_BODY, alwaysRetrigger: true },
      ],
      metadata: { timeout: 20000 },
    })
    .add('journey', 'generative_journey', {
      children: [
        { to: 'toProfile', when: gj(0), name: 'switchToProfile' },
        { to: 'toPay', when: gj(1), name: 'switchToPay' },
        { to: 'toTravel', when: gj(2), name: 'switchToTravel' },
        { to: 'toEscalation', when: gj(3), name: 'human' },
        { to: 'failed', when: [statusIs('failure')] },
        { to: 'failed', when: [statusIs('timeout')] },
      ],
      metadata: {
        generativeJourney: {
          modelType: HAIKU,
          maxSteps: 8,
          maxTokens: 300,
          temperature: 0.2,
          prompt: [
            "You answer an airline employee's HR policy questions for the HR assistant.",
            'Policy search results for the question, retrieved before you started (empty if the search failed): <results>{PolicySearch.result.content.0.text:NLX.Variable}</results>.',
            'Answer only from those results, naming the policy you used. If they do not have the answer, say so and offer a ticket for a person on the HR team.',
            'You have no tools and never look up or change records. If the employee wants to see or change their home address or emergency contact, use the switchToProfile exit; direct deposit or pay statements, switchToPay; pass travel or buddy passes, switchToTravel; a person, or the ticket you offered, human.',
            'When you take an exit, write nothing before it: the flow you hand to answers the employee.',
            'Answer in at most two short sentences.',
          ].join(' '),
          // No tools (D52): the passages are in the prompt, and every call to the HrTools
          // MCP data request failed before reaching the gateway (spike fact 11).
          tools: [],
          exitConditions: [
            { name: 'switchToProfile', prompt: 'The employee wants to change or see their home address or emergency contact.' },
            { name: 'switchToPay', prompt: 'The employee wants to change direct deposit or see pay statements.' },
            { name: 'switchToTravel', prompt: 'The employee asks about pass travel, buddy passes or flight benefits.' },
            // EscalationFlow opens the ticket and ends the conversation (D43).
            { name: 'human', prompt: 'The employee asks to talk to a person, or agrees to the ticket you offered.' },
          ],
        },
      },
    })
    .add('toProfile', 'redirect', { children: ['end'], metadata: { redirect: { type: 'flow', flowId: 'ProfileFlow' } } })
    .add('toPay', 'redirect', { children: ['end'], metadata: { redirect: { type: 'flow', flowId: 'PayFlow' } } })
    .add('toTravel', 'redirect', { children: ['end'], metadata: { redirect: { type: 'flow', flowId: 'TravelFlow' } } })
    .add('toEscalation', 'redirect', { children: ['end'], metadata: { redirect: { type: 'flow', flowId: 'EscalationFlow' } } })
    .add('failed', 'basic', {
      children: ['toWelcome'],
      messages: [endsTurn("I couldn't look that up just now. You can ask again, or ask for a person.")],
    })
    .add('toWelcome', 'redirect', { children: ['end'], metadata: { redirect: { type: 'flow', flowId: 'WelcomeFlow' } } })
    .add('end', 'end');
  return {
    flowId: 'PolicyFlow',
    description: 'Answers HR policy questions from a policy search made before the journey, which has no tools.',
    aiDescription: 'The employee asks a general HR policy question, such as leave, holidays, benefits enrollment or workplace rules.',
    utterances: [
      'How much vacation do I get',
      'What is the bereavement leave policy',
      'When is open enrollment',
      'What holidays do we get off',
    ].map((text) => ({ text })),
    nodes: f.nodes,
  };
}

function goodbyeFlow() {
  const f = new FlowBuilder('GoodbyeFlow');
  f.add('start', 'start', { children: ['bye'] })
    .add('bye', 'basic', { children: ['end'], messages: [closes("You're welcome. Have a good day.")] })
    .add('end', 'terminate');
  return {
    flowId: 'GoodbyeFlow',
    description: 'Closes the conversation when the employee is done.',
    aiDescription: 'The employee is finished: thanks the assistant, says goodbye or says they need nothing else.',
    utterances: ["That's everything, thank you", 'Goodbye', 'No, nothing else', 'All set, thanks'].map((text) => ({ text })),
    nodes: f.nodes,
  };
}

/**
 * hr___open_ticket over a plain HTTP data request, like PolicySearch: one JSON-RPC
 * tools/call to the tools gateway with the employee's token. The tools server takes the
 * employee from the token, so the summary is all the canvas sends.
 */
function openTicketDataRequest() {
  return {
    dataRequestId: 'OpenTicket',
    type: 'object',
    description: 'tools/call hr___open_ticket on the hr-super-agent tools gateway over HTTP.',
    webhook: {
      implementation: 'external',
      method: 'POST',
      environments: env(TOOLS_GATEWAY_URL, [
        hdr('Authorization', 'Bearer {hrToolsToken:NLX.Context}', { sensitive: true }),
        hdr('X-Hr-Thread-Id', CONV),
        hdr('Content-Type', 'application/json'),
        hdr('Accept', 'application/json'),
      ]),
    },
    responseSchema: {
      type: 'object',
      properties: {
        result: {
          type: 'object',
          properties: {
            structuredContent: { type: 'object', properties: { ticket_id: { type: 'string' } } },
            isError: { type: 'boolean' },
          },
        },
      },
    },
  };
}

const OPEN_TICKET_BODY = JSON.stringify({
  jsonrpc: '2.0',
  id: CONV,
  method: 'tools/call',
  params: {
    name: 'hr___open_ticket',
    arguments: { summary: `The employee asked for a person: ${UTTERANCE}`, domain: 'general' },
  },
});

function escalationFlow() {
  const f = new FlowBuilder('EscalationFlow');
  const ticketId = [
    { left: { type: 'variable', name: 'OpenTicket.result.structuredContent.ticket_id' }, operator: 'exists' },
  ];
  f.add('start', 'start', { children: ['ticket'] })
    .add('ticket', 'data_request', {
      children: [
        { to: 'route', when: [statusIs('success')] },
        { to: 'noTicket', when: [statusIs('failure')] },
        { to: 'noTicket', when: [statusIs('timeout')] },
      ],
      dataRequests: [
        { dataRequestId: 'OpenTicket', name: 'OpenTicket', headers: {}, payload: OPEN_TICKET_BODY, alwaysRetrigger: true },
      ],
      metadata: { timeout: 20000 },
    })
    .add('route', 'choice', { children: [{ to: 'opened', when: ticketId }, 'noTicket'] })
    // The conversation ends after either line: the contact flow says goodbye and
    // disconnects, and the bridge ends the thread on Connect's end event.
    .add('opened', 'basic', {
      children: ['end'],
      messages: [
        closes(
          'I opened HR ticket {OpenTicket.result.structuredContent.ticket_id:NLX.Variable} for you. A person on the HR team will follow up within two business days. This conversation is now closed; a new message starts a new one.',
        ),
      ],
    })
    .add('noTicket', 'basic', {
      children: ['end'],
      messages: [
        closes(
          "I couldn't open a ticket just now. Please contact the HR service desk directly. This conversation is now closed; a new message starts a new one.",
        ),
      ],
    })
    .add('end', 'terminate');
  return {
    flowId: 'EscalationFlow',
    description: 'Opens an HR ticket for a person to follow up, gives its id, and ends the conversation.',
    aiDescription: 'The employee asks to talk to a person, a human, an agent or the HR service desk.',
    utterances: [
      'I need to talk to someone',
      'Let me talk to a person',
      'Connect me to an agent',
      'I want a human',
      'Transfer me to the HR service desk',
    ].map((text) => ({ text })),
    nodes: f.nodes,
  };
}

const DATA_REQUESTS = [
  ...DOMAINS.flatMap((d) => [delegateDataRequest(d, false), delegateDataRequest(d, true)]),
  hrToolsDataRequest(),
  policySearchDataRequest(),
  openTicketDataRequest(),
];

const FLOWS = [welcomeFlow(), clarifyFlow(), ...DOMAINS.map(domainFlow), policyFlow(), goodbyeFlow(), escalationFlow()];

module.exports = {
  agentsTokenName, HR_TOOLS, DOMAINS, CONTEXT_VARIABLES, DATA_REQUESTS, FLOWS, END_MARK, CLOSED_MARK };
