import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { emptyStateText, hintText } from "../src/copy.js";

const flags = JSON.parse(readFileSync(new URL("../features.json", import.meta.url)));
const KEYS = "Enter to send, Shift+Enter for a new line.";

test("the product flags that have not launched ship off", () => {
  // history stays dark; logging, rum, and feedback were turned on 5 Sep 2026.
  assert.equal(flags.history, false);
});

test("with both switches off the page says nothing is saved", () => {
  assert.equal(hintText(false, false), `${KEYS} Nothing is saved.`);
  assert.equal(emptyStateText(false, false), "Ask anything. This conversation is not saved.");
});

test("logging on names the logging", () => {
  assert.equal(hintText(false, true), `${KEYS} Conversations are logged for troubleshooting.`);
  assert.equal(
    emptyStateText(false, true),
    "Ask anything. Conversations are logged for troubleshooting.",
  );
});

test("history on names the device", () => {
  assert.equal(hintText(true, false), `${KEYS} Chats are saved on this device only.`);
  assert.equal(emptyStateText(true, false), "Ask anything. Chats are saved on this device only.");
});

test("both switches on name both", () => {
  assert.equal(
    hintText(true, true),
    `${KEYS} Chats are saved on this device and logged for troubleshooting.`,
  );
  assert.equal(
    emptyStateText(true, true),
    "Ask anything. Chats are saved on this device and logged for troubleshooting.",
  );
});

test("the status line names what each tool is doing", async () => {
  const { toolStatus } = await import("../src/copy.js");
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
