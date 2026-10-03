'use strict';

/**
 * Endpoints and small helpers shared by the HR resource modules.
 *
 * The URLs come from SSM, where the stacks publish them, so a fresh clone deploys the
 * canvas without local state (critique finding 15): the HR stack writes
 * /guppi-hr/agents-gateway-url and /guppi-hr/tools-gateway-url, GuppiConnect writes
 * /guppi-hr/connect/mock-url. The AWS CLI reads them with the caller's credentials. The
 * local cdk-outputs.json files are the fallback for a machine without those parameters.
 */

const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const readJson = (p) => JSON.parse(fs.readFileSync(p, 'utf8'));

function parameter(name) {
  try {
    return execFileSync('aws', ['ssm', 'get-parameter', '--name', name, '--query', 'Parameter.Value', '--output', 'text'], {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
      env: { ...process.env, AWS_REGION: process.env.AWS_REGION || 'us-east-1' },
    }).trim();
  } catch {
    return null;
  }
}

function fromOutputs(file, pick) {
  try {
    return pick(readJson(file));
  } catch {
    return null;
  }
}

const trim = (url, name) => {
  if (!url) throw new Error(`no value for ${name}: deploy the stack that publishes it`);
  return url.replace(/\/$/, '');
};

const root = path.join(__dirname, '..', '..', '..');
const MOCK_URL = trim(
  parameter('/guppi-hr/connect/mock-url') ||
    fromOutputs(path.join(__dirname, '..', '..', 'cdk-outputs.json'), (o) => o.GuppiConnect.MockUrl),
  'the mock URL',
);
const AGENTS_GATEWAY_URL = trim(
  parameter('/guppi-hr/agents-gateway-url') ||
    fromOutputs(path.join(root, 'cdk-outputs.json'), (o) => Object.values(o)[0].AgentsGatewayUrl),
  'the agents gateway URL',
);
const TOOLS_GATEWAY_URL = trim(
  parameter('/guppi-hr/tools-gateway-url') ||
    fromOutputs(path.join(root, 'cdk-outputs.json'), (o) => Object.values(o)[0].ToolsGatewayUrl),
  'the tools gateway URL',
);

/** Webhook environments: `development` and `production` may point at different URLs. */
const env = (url, headers = [], productionUrl = url) => ({
  production: { url: productionUrl, headers },
  development: { url, headers },
});

const hdr = (key, value, extra = {}) => ({ key, value, ...extra });

module.exports = { MOCK_URL, AGENTS_GATEWAY_URL, TOOLS_GATEWAY_URL, env, hdr };
