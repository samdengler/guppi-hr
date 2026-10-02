'use strict';

/**
 * Create-or-update helpers for the resources the spike owns, so `deploy.js` can run
 * again after every change. A deployment cannot be updated in place reliably (the AICC
 * sample's live notes, 2026-09-27), so `deploy` replaces it and reports the new alias.
 */

const { sdk } = require('./client');

async function listAll(client, Command, input = {}) {
  const items = [];
  let nextToken;
  do {
    const page = await client.send(new Command({ ...input, ...(nextToken ? { nextToken } : {}) }));
    items.push(...(page.items ?? []));
    nextToken = page.nextToken;
  } while (nextToken);
  return items;
}

async function upsertContextVariable(client, variable) {
  const existing = await listAll(client, sdk.ListContextVariablesCommand);
  if (existing.some((v) => v.name === variable.name)) {
    const { name, ...rest } = variable;
    await client.send(new sdk.UpdateContextVariableCommand({ contextVariableIdentifier: name, ...rest }));
    return 'updated';
  }
  await client.send(new sdk.CreateContextVariableCommand(variable));
  return 'created';
}

async function upsertDataRequest(client, dataRequest) {
  const existing = await listAll(client, sdk.ListDataRequestsCommand);
  if (existing.some((d) => d.dataRequestId === dataRequest.dataRequestId)) {
    const { dataRequestId, ...rest } = dataRequest;
    await client.send(new sdk.UpdateDataRequestCommand({ dataRequestIdentifier: dataRequestId, ...rest }));
    return 'updated';
  }
  await client.send(new sdk.CreateDataRequestCommand(dataRequest));
  return 'created';
}

async function upsertFlow(client, flow) {
  const existing = await listAll(client, sdk.ListFlowsCommand);
  const body = {
    utterances: [],
    untrained: false,
    mainLanguageCode: 'en-US',
    languageCodes: ['en-US'],
    slotTypes: [],
    ...flow,
  };
  if (existing.some((f) => f.flowId === flow.flowId)) {
    const { flowId, ...rest } = body;
    await client.send(new sdk.UpdateFlowCommand({ flowIdentifier: flowId, ...rest }));
    return 'updated';
  }
  await client.send(new sdk.CreateFlowCommand(body));
  return 'created';
}

async function upsertApplication(client, application) {
  const existing = await listAll(client, sdk.ListApplicationsCommand);
  const match = existing.find((a) => a.name === application.name);
  if (match) {
    const { name, ...rest } = application;
    await client.send(
      new sdk.UpdateApplicationCommand({ applicationIdentifier: match.applicationId, name, ...rest }),
    );
    return { action: 'updated', applicationId: match.applicationId };
  }
  const created = await client.send(new sdk.CreateApplicationCommand(application));
  return { action: 'created', applicationId: created.applicationId };
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function build(client, applicationId, description) {
  const created = await client.send(
    new sdk.CreateApplicationBuildCommand({ applicationIdentifier: applicationId, description }),
  );
  const deadline = Date.now() + 10 * 60 * 1000;
  for (;;) {
    const b = await client.send(
      new sdk.GetApplicationBuildCommand({ applicationIdentifier: applicationId, buildIdentifier: created.buildId }),
    );
    if (b.status === 'BUILT') return b;
    if (!['PENDING', 'IN_PROGRESS', 'BUILDING'].includes(b.status)) {
      const err = new Error(`build ${created.buildId} ended ${b.status}`);
      err.build = b;
      throw err;
    }
    if (Date.now() > deadline) throw new Error(`build ${created.buildId} still ${b.status}`);
    await sleep(5000);
  }
}

/** Deploy a build to an environment, replacing any deployment already there. */
async function deploy(client, { applicationId, buildId, environment, languageCodes }) {
  const list = await client.send(
    new sdk.ListApplicationDeploymentsCommand({ applicationIdentifier: applicationId }),
  );
  const current = (list.items ?? []).find((d) => d.environment === environment);
  if (current) {
    try {
      await client.send(
        new sdk.UpdateApplicationDeploymentCommand({
          applicationIdentifier: applicationId,
          deploymentIdentifier: current.deploymentId,
          buildIdentifier: buildId,
          environment,
          languageCodes,
        }),
      );
      const d = await client.send(
        new sdk.GetApplicationDeploymentCommand({
          applicationIdentifier: applicationId,
          deploymentIdentifier: current.deploymentId,
        }),
      );
      return { action: 'updated', deployment: d, previousAlias: current.deploymentAlias };
    } catch (err) {
      await client.send(
        new sdk.DeleteApplicationDeploymentCommand({
          applicationIdentifier: applicationId,
          deploymentIdentifier: current.deploymentId,
        }),
      );
    }
  }
  const created = await client.send(
    new sdk.CreateApplicationDeploymentCommand({
      applicationIdentifier: applicationId,
      buildIdentifier: buildId,
      environment,
      languageCodes,
      description: 'guppi-connect spike deploy',
    }),
  );
  const d = await client.send(
    new sdk.GetApplicationDeploymentCommand({
      applicationIdentifier: applicationId,
      deploymentIdentifier: created.deploymentId,
    }),
  );
  return { action: current ? 'replaced' : 'created', deployment: d, previousAlias: current?.deploymentAlias };
}

module.exports = {
  listAll,
  upsertContextVariable,
  upsertDataRequest,
  upsertFlow,
  upsertApplication,
  build,
  deploy,
};
