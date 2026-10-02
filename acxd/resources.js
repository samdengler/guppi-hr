'use strict';

/**
 * Everything the spike creates in the ACXD workspace, as data. `deploy.js` upserts it.
 *
 * Experiment 1 (header probe): a context variable `hrToken`, set by the Connect contact
 * flow from a contact attribute, must reach a data request's Authorization header. The
 * HeaderProbe data request calls the spike's echo endpoint, which reports which headers
 * arrived; the flow speaks that report back into the chat transcript.
 */

const fs = require('fs');
const path = require('path');
const { FlowBuilder, statusIs } = require('./lib/nodes');

const outputs = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'cdk-outputs.json'), 'utf8'));
const MOCK_URL = outputs.GuppiConnect.MockUrl.replace(/\/$/, '');

const CONTEXT_VARIABLES = [
  { name: 'hrToken', schema: { type: 'string' }, disallowExternalModification: false },
  { name: 'employeeId', schema: { type: 'string' }, disallowExternalModification: false },
];

const env = (url, headers = []) => ({
  production: { url, headers },
  development: { url, headers },
});

const PROBE_SCHEMA = {
  type: 'object',
  properties: {
    summary: { type: 'string' },
    hrThreadId: { type: 'string' },
    body: { type: 'string' },
    bearerPrefix: { type: 'boolean' },
  },
};

const hdr = (key, value, extra = {}) => ({ key, value, ...extra });

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
    aiDescription: 'Runs the header probe diagnostic',
    utterances: [{ text: 'run the header probe' }, { text: 'header probe' }],
    nodes: f.nodes,
  };
}

const FLOWS = [headerProbeFlow()];

const APPLICATION = {
  name: 'hr-assistant',
  description: 'guppi-connect spike: the canvas as the HR super-agent over hr-super-agent sub-agents.',
  flows: FLOWS.map((f) => ({ flowId: f.flowId })),
  settings: {
    languageCode: 'en-US',
    languageCodes: ['en-US'],
    defaultFlows: { welcome: { flowId: 'HeaderProbe' } },
  },
};

module.exports = { MOCK_URL, CONTEXT_VARIABLES, DATA_REQUESTS, FLOWS, APPLICATION, AUTH_HEADERS, PROBE_PAYLOAD };
