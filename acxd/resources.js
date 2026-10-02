'use strict';

/**
 * Everything the spike creates in the ACXD workspace, as data. `deploy.js` upserts it.
 *
 * hr.js is the HR super-agent canvas; probes.js keeps the experiments that settled how
 * headers, payloads and A2A replies work. Both live in one application, `hr-assistant`,
 * whose welcome flow is WelcomeFlow; the probes are reachable by saying their names.
 */

const hr = require('./hr');
const probes = require('./probes');

const CONTEXT_VARIABLES = [
  { name: 'hrToken', schema: { type: 'string' }, disallowExternalModification: false },
  { name: 'employeeId', schema: { type: 'string' }, disallowExternalModification: false },
  ...hr.CONTEXT_VARIABLES,
];

const DATA_REQUESTS = [...hr.DATA_REQUESTS, ...probes.DATA_REQUESTS];
const FLOWS = [...hr.FLOWS, ...probes.FLOWS];

const APPLICATION = {
  name: 'hr-assistant',
  description: 'guppi-connect spike: the canvas as the HR super-agent over hr-super-agent sub-agents.',
  flows: FLOWS.map((f) => ({ flowId: f.flowId })),
  settings: {
    languageCode: 'en-US',
    languageCodes: ['en-US'],
    defaultFlows: { welcome: { flowId: 'WelcomeFlow' }, unknown: { flowId: 'PolicyFlow' } },
  },
};

module.exports = { CONTEXT_VARIABLES, DATA_REQUESTS, FLOWS, APPLICATION };
