import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const manifest = JSON.parse(readFileSync(new URL("../manifest.json", import.meta.url)));

test("the manifest names the project, its agent path and its extension", () => {
  assert.equal(manifest.name, "hr-diy");
  assert.equal(manifest.agent, "/api/hr-diy/invocations");
  assert.equal(manifest.extension, "/projects/hr-diy/ext.js");
});

test("the platform's default palette applies: the manifest carries no theme", () => {
  assert.equal("theme" in manifest, false);
});

test("the product flags that have not launched ship off", () => {
  // history stays dark; logging and rum match the platform's defaults.
  assert.equal(manifest.features.history, false);
  assert.equal(manifest.features.feedback, false);
  assert.equal(manifest.features.logging, true);
});

test("the suggestions are the four scenarios' opening lines, as plain text", () => {
  assert.deepEqual(
    manifest.suggestions.map((s) => s.prompt),
    [
      "I need to update my information",
      "Change my home address to 419 Glendale Ave, Decatur GA 30030",
      "What about my emergency contact?",
      "How many buddy passes do I get?",
    ],
  );
  for (const suggestion of manifest.suggestions) {
    assert.equal(typeof suggestion.label, "string");
    assert.ok(suggestion.label.length > 0);
  }
});
