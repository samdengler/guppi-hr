'use strict';

/**
 * Everything the spike creates in the ACXD workspace, as data. `deploy.js` upserts it.
 *
 * hr.js is the HR super-agent canvas, in one application, `hr-assistant`, whose welcome
 * flow is WelcomeFlow. probes.js keeps the experiments that settled how headers, payloads
 * and A2A replies work; they are no longer deployed, since flows are shared by the
 * development and production applications and a probe sent the employee's token to the
 * spike's public mock (critique finding 19).
 */

const hr = require('./hr');

const CONTEXT_VARIABLES = [
  { name: 'hrProfileToken', schema: { type: 'string' }, disallowExternalModification: false },
  { name: 'hrPayToken', schema: { type: 'string' }, disallowExternalModification: false },
  { name: 'hrTravelToken', schema: { type: 'string' }, disallowExternalModification: false },
  { name: 'hrToolsToken', schema: { type: 'string' }, disallowExternalModification: false },
  { name: 'employeeId', schema: { type: 'string' }, disallowExternalModification: false },
  ...hr.CONTEXT_VARIABLES,
];

const DATA_REQUESTS = hr.DATA_REQUESTS;
const FLOWS = hr.FLOWS;

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
