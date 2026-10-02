'use strict';

/**
 * Diagnostic flows from the first experiments, kept so they can be re-run.
 *
 * Experiment 1 (header probe): a context variable `hrToken`, set by the Connect contact
 * flow from a contact attribute, must reach a data request's Authorization header. The
 * HeaderProbe data request calls the spike's echo endpoint, which reports which headers
 * arrived; the flow speaks that report back into the chat transcript.
 */

const { FlowBuilder, statusIs } = require('./lib/nodes');
const { MOCK_URL, env, hdr } = require('./lib/common');

const PROBE_SCHEMA = {
  type: 'object',
  properties: {
    summary: { type: 'string' },
    hrThreadId: { type: 'string' },
    body: { type: 'string' },
    bearerPrefix: { type: 'boolean' },
  },
};


// Three ways to put the token in a header, one data request each:
//   ProbeNode    - headers only on the flow node (experiment 1: not sent)
//   ProbeDynamic - headers declared on the data request with dynamic: true, values from the node
//   ProbeStatic  - headers declared on the data request with the placeholder as the value
const DATA_REQUESTS = [
  {
    dataRequestId: 'ProbeNode',
    type: 'object',
    description: 'Echo endpoint; headers set only on the flow node.',
    webhook: { implementation: 'external', method: 'POST', environments: env(`${MOCK_URL}/echo`) },
    responseSchema: PROBE_SCHEMA,
  },
  {
    dataRequestId: 'ProbeDynamic',
    type: 'object',
    description: 'Echo endpoint; headers declared dynamic, values supplied by the node.',
    webhook: {
      implementation: 'external',
      method: 'POST',
      environments: env(`${MOCK_URL}/echo`, [
        hdr('Authorization', 'Bearer {hrToken:NLX.Context}', { dynamic: true }),
        hdr('X-Hr-User-Token', '{hrToken:NLX.Context}', { dynamic: true }),
        hdr('X-Hr-Thread-Id', '{System.conversationId:NLX.System}', { dynamic: true }),
      ]),
    },
    responseSchema: PROBE_SCHEMA,
  },
  {
    dataRequestId: 'ProbeStatic',
    type: 'object',
    description: 'Echo endpoint; headers declared with context placeholders as values.',
    webhook: {
      implementation: 'external',
      method: 'POST',
      environments: env(`${MOCK_URL}/echo`, [
        hdr('Authorization', 'Bearer {hrToken:NLX.Context}', { sensitive: true }),
        hdr('X-Hr-User-Token', '{hrToken:NLX.Context}', { sensitive: true }),
        hdr('X-Hr-Thread-Id', '{System.conversationId:NLX.System}'),
      ]),
    },
    responseSchema: PROBE_SCHEMA,
  },
  {
    dataRequestId: 'ProbeRecursive',
    type: 'object',
    description: 'Echo endpoint; headers declared with context placeholders as values.',
    webhook: {
      implementation: 'external',
      method: 'POST',
      environments: env(`${MOCK_URL}/echo`, [
        hdr('Authorization', 'Bearer {hrToken:NLX.Context}', { sensitive: true }),
        hdr('X-Hr-User-Token', '{hrToken:NLX.Context}', { sensitive: true }),
        hdr('X-Hr-Thread-Id', '{System.conversationId:NLX.System}'),
      ]),
    },
    responseSchema: PROBE_SCHEMA,
  },
  {
    dataRequestId: 'ProbeString',
    type: 'object',
    description: 'Echo endpoint; headers declared with context placeholders as values.',
    webhook: {
      implementation: 'external',
      method: 'POST',
      environments: env(`${MOCK_URL}/echo`, [
        hdr('Authorization', 'Bearer {hrToken:NLX.Context}', { sensitive: true }),
        hdr('X-Hr-User-Token', '{hrToken:NLX.Context}', { sensitive: true }),
        hdr('X-Hr-Thread-Id', '{System.conversationId:NLX.System}'),
      ]),
    },
    responseSchema: PROBE_SCHEMA,
  },
  {
    dataRequestId: 'DelegateMockProbe',
    type: 'object',
    description: 'Mock Profile sub-agent; checks how a nested A2A reply is read.',
    webhook: {
      implementation: 'external',
      method: 'POST',
      environments: env(`${MOCK_URL}/a2a/profile/invocations`, [
        hdr('Authorization', 'Bearer {hrToken:NLX.Context}', { sensitive: true }),
        hdr('Content-Type', 'application/json'),
      ]),
    },
    responseSchema: {
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
    },
  },
];

const AUTH_HEADERS = {
  Authorization: 'Bearer {hrToken:NLX.Context}',
  'X-Hr-User-Token': '{hrToken:NLX.Context}',
  'X-Hr-Thread-Id': '{System.conversationId:NLX.System}',
};

const PROBE_PAYLOAD = {
  text: '{System.utterance:NLX.System}',
  contextId: '{System.conversationId:NLX.System}',
  employeeId: '{employeeId:NLX.Context}',
  nested: { employeeId: '{employeeId:NLX.Context}', text: '{System.utterance:NLX.System}' },
};

const A2A_BODY = {
  jsonrpc: '2.0',
  id: '{System.conversationId:NLX.System}',
  method: 'message/send',
  params: {
    message: {
      role: 'user',
      messageId: '{System.conversationId:NLX.System}',
      contextId: '{System.conversationId:NLX.System}',
      parts: [{ kind: 'text', text: '{System.utterance:NLX.System}' }],
      metadata: { employeeId: '{employeeId:NLX.Context}' },
    },
  },
};

const probeCall = (id) => ({
  dataRequestId: id,
  name: id,
  headers: AUTH_HEADERS,
  payload: PROBE_PAYLOAD,
  alwaysRetrigger: true,
});

const after = (next) => [
  { to: next, when: [statusIs('success')] },
  { to: next, when: [statusIs('failure')] },
  { to: next, when: [statusIs('timeout')] },
];

function headerProbeFlow() {
  const f = new FlowBuilder('HeaderProbe');
  f.add('start', 'start', { children: ['listen'] })
    .add('listen', 'user_input', {
      children: [
        { to: 'probeNode', when: [{ left: { type: 'captured_flow' }, operator: 'exists' }] },
        { to: 'probeNode', when: [{ left: { type: 'captured_flow' }, operator: 'not_exists' }] },
      ],
      messages: ['Header probe ready. Send any message.'],
    })
    .add('probeNode', 'data_request', { children: after('probeDynamic'), dataRequests: [probeCall('ProbeNode')] })
    .add('probeDynamic', 'data_request', { children: after('probeStatic'), dataRequests: [probeCall('ProbeDynamic')] })
    .add('probeStatic', 'data_request', { children: after('probeRecursive'), dataRequests: [probeCall('ProbeStatic')] })
    .add('probeRecursive', 'data_request', {
      children: after('probeString'),
      dataRequests: [{ ...probeCall('ProbeRecursive'), payload: { type: 'recursive', value: A2A_BODY } }],
    })
    .add('probeString', 'data_request', {
      children: after('report'),
      dataRequests: [{ ...probeCall('ProbeString'), payload: JSON.stringify(A2A_BODY) }],
    })
    .add('report', 'basic', {
      children: ['end'],
      messages: [
        'ProbeNode: {ProbeNode.summary:NLX.Variable}; thread {ProbeNode.hrThreadId:NLX.Variable}',
        'ProbeDynamic: {ProbeDynamic.summary:NLX.Variable}; thread {ProbeDynamic.hrThreadId:NLX.Variable}',
        'ProbeStatic: {ProbeStatic.summary:NLX.Variable}; thread {ProbeStatic.hrThreadId:NLX.Variable}',
        'Body (static): {ProbeStatic.body:NLX.Variable}',
        'Body (recursive): {ProbeRecursive.body:NLX.Variable}',
        'Body (string): {ProbeString.body:NLX.Variable}',
      ],
    })
    .add('end', 'terminate');
  return {
    flowId: 'HeaderProbe',
    description: 'Spike experiment: does a context variable reach a data request header?',
    untrained: true,
    aiDescription: 'Diagnostic flow; not a routing target.',
    nodes: f.nodes,
  };
}

function a2aProbeFlow() {
  const f = new FlowBuilder('ReplyProbe');
  const D = 'DelegateMockProbe';
  f.add('start', 'start', { children: ['listen'] })
    .add('listen', 'user_input', {
      children: [
        { to: 'call', when: [{ left: { type: 'captured_flow' }, operator: 'exists' }] },
        { to: 'call', when: [{ left: { type: 'captured_flow' }, operator: 'not_exists' }] },
      ],
      messages: ['A2A probe ready. Send a message for the mock Profile agent.'],
    })
    .add('call', 'data_request', {
      children: [
        { to: 'report', when: [statusIs('success')] },
        { to: 'failed', when: [statusIs('failure')] },
        { to: 'failed', when: [statusIs('timeout')] },
      ],
      dataRequests: [{ dataRequestId: D, name: D, headers: {}, payload: JSON.stringify(A2A_BODY), alwaysRetrigger: true }],
    })
    .add('report', 'basic', {
      children: ['end'],
      messages: [
        `dot0: {${D}.result.parts.0.text:NLX.Variable}`,
        `bracket0: {${D}.result.parts[0].text:NLX.Variable}`,
        `contextId: {${D}.result.contextId:NLX.Variable}`,
        `jsonrpc: {${D}.jsonrpc:NLX.Variable}`,
        `pendingId dot: {${D}.result.parts.1.data.pendingAction.proposalId:NLX.Variable}`,
        `pendingId bracket: {${D}.result.parts[1].data.pendingAction.proposalId:NLX.Variable}`,
      ],
    })
    .add('failed', 'basic', { children: ['end'], messages: ['A2A probe call failed.'] })
    .add('end', 'terminate');
  return {
    flowId: 'ReplyProbe',
    description: 'Spike experiment: read fields from a nested A2A message/send reply.',
    untrained: true,
    aiDescription: 'Diagnostic flow; not a routing target.',
    nodes: f.nodes,
  };
}

function mcpProbeFlow() {
  const f = new FlowBuilder('McpProbe');
  const call = (name, payload) => ({ dataRequestId: 'HrTools', name, action: name, headers: {}, payload, alwaysRetrigger: true });
  f.add('start', 'start', { children: ['listen'] })
    .add('listen', 'user_input', {
      children: [
        { to: 'retrieve', when: [{ left: { type: 'captured_flow' }, operator: 'exists' }] },
        { to: 'retrieve', when: [{ left: { type: 'captured_flow' }, operator: 'not_exists' }] },
      ],
      messages: ['MCP probe ready. Send a policy question.'],
    })
    .add('retrieve', 'data_request', {
      children: [
        { to: 'ok', when: [statusIs('success')] },
        { to: 'failed', when: [statusIs('failure')] },
        { to: 'timedOut', when: [statusIs('timeout')] },
      ],
      dataRequests: [call('docs___Retrieve', { retrievalQuery: { text: '{System.utterance:NLX.System}' } })],
    })
    .add('ok', 'basic', { children: ['end'], messages: ['MCP probe: success. {HrTools.content.0.text:NLX.Variable}'] })
    .add('failed', 'basic', { children: ['end'], messages: ['MCP probe: failure.'] })
    .add('timedOut', 'basic', { children: ['end'], messages: ['MCP probe: timeout.'] })
    .add('end', 'terminate');
  return {
    flowId: 'McpProbe',
    untrained: true,
    description: 'Spike experiment: call the HrTools MCP data request from a fixed data_request node.',
    aiDescription: 'Diagnostic flow; not a routing target.',
    nodes: f.nodes,
  };
}

const FLOWS = [headerProbeFlow(), a2aProbeFlow(), mcpProbeFlow()];


module.exports = { DATA_REQUESTS, FLOWS, A2A_BODY };
