'use strict';

/**
 * The ACXD SDK client and the spike's fixed identifiers.
 *
 * The API key is read at run time from ~/.config/guppi-connect/acxd_api_key (mode 600,
 * written by Sam with pbpaste) and is never logged or stored in the repository.
 */

const fs = require('fs');
const os = require('os');
const path = require('path');
const sdk = require('amazon-connect-acxd-sdk');

const REGION = 'us-east-1';
const WORKSPACE_ID = 'f77cf767-cecf-407a-9671-02b07d536b0f';
const CONNECT_INSTANCE_ID = '5665011a-f5fa-40e3-92d0-85ff625d10f6';
const KEY_FILE = path.join(os.homedir(), '.config', 'guppi-connect', 'acxd_api_key');

function makeClient() {
  const apiKey = fs.readFileSync(KEY_FILE, 'utf8').trim();
  return new sdk.AgenticCXDesignerClient({ region: REGION, apiKey, workspaceId: WORKSPACE_ID });
}

/** Mask anything that looks like an ACXD key before it reaches a log line. */
function mask(text) {
  return String(text).replace(/acxd_live_[A-Za-z0-9.]+/g, 'acxd_live_***');
}

module.exports = { sdk, makeClient, mask, REGION, WORKSPACE_ID, CONNECT_INSTANCE_ID };
