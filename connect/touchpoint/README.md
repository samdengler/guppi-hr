# touchpoint: AWS's Touchpoint widget in front of the HR assistant

AWS's Touchpoint chat widget (`@amazon-connect-touchpoint/web` 1.0.2) over the `/p/hr/`
backend: the same chat start, HR contact flow, Agentic CX canvas, sub-agents and tools that
`https://chat.dengler.io/p/hr/` uses. Two pages are built from this folder
([`../docs/touchpoint-experiment.md`](../docs/touchpoint-experiment.md)):

- `https://chat.dengler.io/p/hr-widget/` (T4, D62): the project `hr-widget` on the platform.
  The platform page signs the employee in and hands the screen below its header to this
  project's extension, which draws a stand-in HR portal and mounts the widget; its launcher,
  in the lower right corner, opens the chat panel over the page.
- A local experiment page (T1) on `127.0.0.1:5173`, with a run log of timings beside the
  widget.

## Before running locally

- `~/.config/guppi/test-session.json`, the harness's Okta session, written by guppi-gpt
  `scripts/okta-harness-signin.py` or `scripts/test-token.sh` (or set
  `GUPPI_TEST_SESSION_FILE`). The dev server refreshes it with the harness client and stores
  the rotated refresh token, as the A/B bench does.
- AWS credentials for account 009080466601, us-east-1: the dev server reads the Okta token
  URL and the harness client from `/guppi/okta/*` in SSM.
- Node 20.19 or later.

## Commands

```sh
npm ci
npm test         # node:test for src/hr.js, src/chat.js and dev-token.mjs; no network
npm run dev      # http://127.0.0.1:5173/ (the experiment page), /widget.html (the preview)
npm run build    # the /p/hr-widget/ extension into dist/widget/
```

`../scripts/deploy.sh --site-only` runs the tests and the build and publishes `dist/widget/`
to `/projects/hr-widget/` on the platform's site bucket. `widget.html` loads the built
bundle under the CSP guppi-gpt serves on `/p/hr-widget/*`, with the dev server's token in
place of the platform's sign-in, so a change can be checked before it is published.
`GUPPI_SITE_URL` points the dev server's chat start proxy at another site (default
`https://chat.dengler.io`).

## What the widget does

- Touchpoint's `config.details` calls `POST /api/hr/chat/start` with the employee's bearer
  token (`guppi.token()` on the platform, the dev server's `/dev/token` locally) and the
  previous contact, so the chat start ends it.
- The canvas's greeting reaches Connect before the widget connects (the chat start waits for
  it), so it is read from the transcript and added to the widget after every start,
  Touchpoint's own restart button included.
- Receipts are off, as on `/p/hr/` (D57). Touchpoint's typing events stay on.
- On the platform the participant service is `participant.connect.us-east-1.amazonaws.com`,
  the host the platform's CSP allows; the experiment page keeps Touchpoint's default.
- Touchpoint renders replies as Markdown through DOMPurify, the one exception to the
  plain-text rule (D62). The portal and the run log are plain text.

Every page load starts a real contact on the signed-in employee, and every message is a
billed Connect message.

## Files

```
src/widget.js         the /p/hr-widget/ extension: the portal, Touchpoint, the chat start
src/portal.js         the stand-in HR portal, plain text
src/chat.js           Touchpoint's details option and the greeting replay (tested)
src/hr.js             the chat start's answer, greeting lines, turn times (tested)
widget/               the hr-widget manifest and the portal's stylesheet, published as they are
vite.widget.config.js the extension build into dist/widget/
index.html, src/main.js, src/page.css   the experiment page and its run log
widget.html, src/widget-preview.js, src/preview.css   the extension under the platform's CSP
dev-token.mjs         the Okta access token from the harness session (tested)
vite.config.js        127.0.0.1 only, the chat start proxy, POST /dev/token for same-origin calls
test/                 node:test
```

The token never leaves the dev server except in the answer to `/dev/token` and the page's
`Authorization` header; neither is logged. `npm audit` reports `braces` through
`jest-environment-jsdom`, which chatjs 5.2.0 lists as a dependency; it does not reach the
browser bundle.
