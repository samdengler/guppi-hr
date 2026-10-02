'use strict';

/** Endpoints and small helpers shared by the probe and HR resource modules. */

const fs = require('fs');
const path = require('path');

const readJson = (p) => JSON.parse(fs.readFileSync(p, 'utf8'));

const spike = readJson(path.join(__dirname, '..', '..', 'cdk-outputs.json'));
const MOCK_URL = spike.GuppiConnect.MockUrl.replace(/\/$/, '');

// The HR stack's deployed gateways (the repository root's cdk-outputs.json, read-only here).
const hr = readJson(path.join(__dirname, '..', '..', '..', 'cdk-outputs.json'));
const hrOutputs = Object.values(hr)[0];
const AGENTS_GATEWAY_URL = hrOutputs.AgentsGatewayUrl.replace(/\/$/, '');
const TOOLS_GATEWAY_URL = hrOutputs.ToolsGatewayUrl.replace(/\/$/, '');

/** Webhook environments: `development` and `production` may point at different URLs. */
const env = (url, headers = [], productionUrl = url) => ({
  production: { url: productionUrl, headers },
  development: { url, headers },
});

const hdr = (key, value, extra = {}) => ({ key, value, ...extra });

module.exports = { MOCK_URL, AGENTS_GATEWAY_URL, TOOLS_GATEWAY_URL, env, hdr };
