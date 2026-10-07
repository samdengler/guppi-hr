// The employee's Okta access token for the experiment page, from the harness session that
// guppi-gpt's scripts/test-token.sh writes (~/.config/guppi/test-session.json). It stands in
// for the platform page's own sign-in, which this local page does not have. Each refresh
// grant rotates the refresh token, so the new one is stored at once under the same lock
// directory the A/B bench and browser-check use. The access token is kept in memory until a
// minute before it expires and is never printed or written anywhere.

import { execFileSync } from "node:child_process";
import { chmodSync, existsSync, mkdirSync, readFileSync, renameSync, rmdirSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

export const SESSION_FILE =
  process.env.GUPPI_TEST_SESSION_FILE || join(homedir(), ".config", "guppi", "test-session.json");

const MARGIN_MS = 60_000;

function ssm(name) {
  try {
    return execFileSync(
      "aws",
      ["ssm", "get-parameter", "--name", name, "--query", "Parameter.Value", "--output", "text", "--region", "us-east-1"],
      { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] },
    ).trim();
  } catch {
    throw new Error(`could not read ${name} from SSM; check the AWS credentials for account 009080466601`);
  }
}

/** The Okta token URL and the harness client, which the chat start accepts (OKTA_CLIENTS). */
export function oktaFromSsm() {
  return { tokenUrl: ssm("/guppi/okta/token-url"), client: ssm("/guppi/okta/harness-client-id") };
}

async function withLock(file, fn) {
  const lock = `${file}.lock`;
  for (let i = 0; i < 100; i += 1) {
    try {
      mkdirSync(lock);
    } catch (error) {
      if (error.code !== "EEXIST") throw error;
      await new Promise((r) => setTimeout(r, 100));
      continue;
    }
    try {
      return await fn();
    } finally {
      rmdirSync(lock);
    }
  }
  throw new Error(`could not take ${lock}`);
}

function readRefreshToken(file) {
  const token = JSON.parse(readFileSync(file, "utf8")).refreshToken;
  if (typeof token !== "string" || !token) throw new Error(`${file} has no refreshToken`);
  return token;
}

function writeRefreshToken(file, token) {
  const tmp = `${file}.${process.pid}`;
  writeFileSync(tmp, JSON.stringify({ refreshToken: token }), { mode: 0o600 });
  chmodSync(tmp, 0o600);
  renameSync(tmp, file);
}

/**
 * A function that answers `{token, expiresAt}` (epoch ms), refreshing from the session file
 * when the cached token is within a minute of expiry. `okta`, `fetchImpl` and `now` are seams
 * for the tests.
 */
export function tokenSource({ file = SESSION_FILE, okta = oktaFromSsm, fetchImpl = fetch, now = Date.now } = {}) {
  let cached = null;
  let settings = null;
  return async function accessToken() {
    if (cached && cached.expiresAt - MARGIN_MS > now()) return cached;
    if (!existsSync(file)) throw new Error(`no Okta test session at ${file}`);
    settings ??= typeof okta === "function" ? okta() : okta;
    cached = await withLock(file, async () => {
      const body = new URLSearchParams({
        grant_type: "refresh_token",
        client_id: settings.client,
        refresh_token: readRefreshToken(file),
      });
      const response = await fetchImpl(settings.tokenUrl, {
        method: "POST",
        headers: { "content-type": "application/x-www-form-urlencoded" },
        body,
      });
      const json = await response.json().catch(() => ({}));
      if (!response.ok || typeof json.access_token !== "string") {
        throw new Error(`refresh refused: ${json.error || response.status}`);
      }
      if (json.refresh_token) writeRefreshToken(file, json.refresh_token);
      return { token: json.access_token, expiresAt: now() + Number(json.expires_in ?? 0) * 1000 };
    });
    return cached;
  };
}
