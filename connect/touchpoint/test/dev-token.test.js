import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { tokenSource } from "../dev-token.mjs";

const okta = { tokenUrl: "https://okta.test/oauth2/guppi/v1/token", client: "harness-client" };

function session(refreshToken = "refresh-1") {
  const file = join(mkdtempSync(join(tmpdir(), "hr-touchpoint-")), "test-session.json");
  writeFileSync(file, JSON.stringify({ refreshToken }), { mode: 0o600 });
  return file;
}

function fakeOkta(answers) {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({ url, body: Object.fromEntries(new URLSearchParams(init.body)) });
    const { status = 200, json } = answers.shift();
    return { ok: status < 400, status, json: async () => json };
  };
  return { calls, fetchImpl };
}

test("a refresh grant with the harness client answers the access token and stores the rotated refresh token", async () => {
  const file = session();
  let clock = 1_000_000;
  const { calls, fetchImpl } = fakeOkta([{ json: { access_token: "access-1", expires_in: 3600, refresh_token: "refresh-2" } }]);
  const accessToken = tokenSource({ file, okta, fetchImpl, now: () => clock });

  assert.deepEqual(await accessToken(), { token: "access-1", expiresAt: 1_000_000 + 3_600_000 });
  assert.deepEqual(calls, [
    { url: okta.tokenUrl, body: { grant_type: "refresh_token", client_id: "harness-client", refresh_token: "refresh-1" } },
  ]);
  assert.deepEqual(JSON.parse(readFileSync(file, "utf8")), { refreshToken: "refresh-2" });
  assert.equal(statSync(file).mode & 0o777, 0o600);
});

test("the access token is reused until a minute before it expires", async () => {
  const file = session();
  let clock = 0;
  const { calls, fetchImpl } = fakeOkta([
    { json: { access_token: "access-1", expires_in: 3600, refresh_token: "refresh-2" } },
    { json: { access_token: "access-2", expires_in: 3600, refresh_token: "refresh-3" } },
  ]);
  const accessToken = tokenSource({ file, okta, fetchImpl, now: () => clock });

  await accessToken();
  clock = 3_600_000 - 61_000;
  assert.equal((await accessToken()).token, "access-1");
  clock = 3_600_000 - 59_000;
  assert.equal((await accessToken()).token, "access-2");
  assert.equal(calls.length, 2);
  assert.equal(calls[1].body.refresh_token, "refresh-2");
});

test("a missing session file is named before Okta or SSM is asked", async () => {
  const file = join(mkdtempSync(join(tmpdir(), "hr-touchpoint-")), "test-session.json");
  const accessToken = tokenSource({
    file,
    okta: () => assert.fail("SSM read"),
    fetchImpl: () => assert.fail("Okta call"),
  });

  await assert.rejects(accessToken(), { message: `no Okta test session at ${file}` });
});

test("a refused refresh names Okta's error and leaves the session file alone", async () => {
  const file = session("refresh-1");
  const { fetchImpl } = fakeOkta([{ status: 400, json: { error: "invalid_grant" } }]);
  const accessToken = tokenSource({ file, okta, fetchImpl });

  await assert.rejects(accessToken(), { message: "refresh refused: invalid_grant" });
  assert.deepEqual(JSON.parse(readFileSync(file, "utf8")), { refreshToken: "refresh-1" });
});
