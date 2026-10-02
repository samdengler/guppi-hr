'use strict';

/**
 * Upsert every resource in resources.js, build the application, deploy it to
 * `development`, and write the deployment (with its alias) to ../.deploy/acxd.json for
 * the contact flow script.
 *
 *   node deploy.js            # everything
 *   node deploy.js --no-build # resources only
 */

const fs = require('fs');
const path = require('path');
const { makeClient, mask, sdk } = require('./lib/client');
const u = require('./lib/upsert');
const R = require('./resources');

const STATE = path.join(__dirname, '..', '.deploy', 'acxd.json');

(async () => {
  const client = makeClient();
  const noBuild = process.argv.includes('--no-build');
  try {
    for (const v of R.CONTEXT_VARIABLES) console.log(`context variable ${v.name}: ${await u.upsertContextVariable(client, v)}`);
    for (const d of R.DATA_REQUESTS) console.log(`data request ${d.dataRequestId}: ${await u.upsertDataRequest(client, d)}`);
    for (const f of R.FLOWS) console.log(`flow ${f.flowId}: ${await u.upsertFlow(client, f)}`);
    const app = await u.upsertApplication(client, R.APPLICATION);
    console.log(`application ${R.APPLICATION.name}: ${app.action} ${app.applicationId}`);
    if (noBuild) return;

    console.log('building ...');
    const b = await u.build(client, app.applicationId, 'guppi-connect spike build');
    console.log(`build ${b.buildId}: ${b.status}`);
    const d = await u.deploy(client, {
      applicationId: app.applicationId,
      buildId: b.buildId,
      environment: 'development',
      languageCodes: ['en-US'],
    });
    console.log(`deployment ${d.action}: ${d.deployment.deploymentId} status=${d.deployment.deploymentStatus} alias=${d.deployment.deploymentAlias}`);
    fs.mkdirSync(path.dirname(STATE), { recursive: true });
    const prior = fs.existsSync(STATE) ? JSON.parse(fs.readFileSync(STATE, 'utf8')) : {};
    if (prior.alias_bound && prior.alias_bound !== d.deployment.deploymentAlias) {
      console.log(`ALIAS CHANGED: contact flow is bound to ${prior.alias_bound}; run scripts/contact_flow.py`);
    }
    fs.writeFileSync(
      STATE,
      JSON.stringify(
        {
          ...prior,
          applicationId: app.applicationId,
          buildId: b.buildId,
          deploymentId: d.deployment.deploymentId,
          deploymentAlias: d.deployment.deploymentAlias,
          previousAlias: d.previousAlias ?? null,
          deployedAt: new Date().toISOString(),
        },
        null,
        2,
      ),
    );
  } catch (e) {
    console.error('deploy failed:', e.name, mask(e.message));
    if (e.fieldList) console.error(JSON.stringify(e.fieldList, null, 2));
    if (e.build) console.error(JSON.stringify(e.build, null, 2).slice(0, 4000));
    if (e.$metadata) console.error('HTTP', e.$metadata.httpStatusCode);
    process.exitCode = 1;
  }
})();
