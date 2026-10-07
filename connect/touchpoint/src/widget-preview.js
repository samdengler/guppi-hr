// widget.html: the built /p/hr-widget/ extension as the platform page runs it, under the
// platform's widget CSP, with the dev server's token in place of the platform's sign-in and
// a stand-in for the page's `guppi` object. Run `npm run build` first.

import manifest from "../widget/manifest.json";

const BUNDLE = "/dist/widget/ext.js";

const res = await fetch("/dev/token", { method: "POST" });
const { token, error } = await res.json();
if (!token) throw new Error(`no Okta test session: ${error}`);

const surfaceHooks = [];
const guppi = Object.freeze({
  project: manifest,
  token: () => token,
  onSurface: (fn) => surfaceHooks.push(fn),
});
const { default: install } = await import(/* @vite-ignore */ BUNDLE);
install(guppi);
for (const hook of surfaceHooks) hook(document.getElementById("surface-screen"));
