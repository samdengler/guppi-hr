import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { BRAND, agentName, replyLabel, stepStatus, toolStatus } from "../src/copy.js";

const manifest = JSON.parse(readFileSync(new URL("../manifest.json", import.meta.url)));

test("the status line names what each tool is doing", () => {
  assert.deepEqual(toolStatus("docs___Retrieve"), {
    running: "Searching the HR policies…",
    done: "Searched the HR policies",
  });
  assert.equal(toolStatus("hr___propose_address_change").running, "Preparing the change…");
  assert.equal(toolStatus("hr___commit_change").done, "Saved the change");
  assert.equal(toolStatus("hr___open_ticket").done, "Opened a ticket");
  assert.equal(toolStatus("hr___get_profile").running, "Checking your HR records…");
  assert.equal(toolStatus(undefined).running, "Working…");
});

test("each delegation gets its own status line and reply tag", () => {
  assert.equal(agentName("profile"), "Profile");
  assert.equal(agentName("general"), null);
  assert.deepEqual(stepStatus("pay"), { running: "Asking the Pay agent…", done: "Pay agent answered" });
  assert.equal(stepStatus("unknown").running, "Working…");
  assert.equal(replyLabel("pay"), "HR Assistant · Pay");
  assert.equal(replyLabel("travel"), `${BRAND} · Travel`);
  assert.equal(replyLabel(undefined), BRAND);
});

test("the manifest's assistant name is the brand constant the reply label starts with", () => {
  // The header says "HR Assistant (DIY)" (label); replies say "HR Assistant · Pay" (assistant).
  assert.equal(manifest.assistant, BRAND);
});
