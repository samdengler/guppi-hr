import assert from "node:assert/strict";
import test from "node:test";

import install, { createThreadState, withThreadState } from "../src/ext.js";

// A stand-in for the platform's `guppi` object: it records what the extension registers
// and what it writes to the status line, so each renderer can be driven by hand.
function fakeGuppi() {
  const events = new Map();
  const sendHooks = [];
  const threadHooks = [];
  const statuses = [];
  const guppi = {
    project: { name: "hr-diy" },
    renderers: {
      tool() {},
      event(type, fn) {
        events.set(type, fn);
      },
    },
    onSend(fn) {
      sendHooks.push(fn);
    },
    onThread(fn) {
      threadHooks.push(fn);
    },
    status(text) {
      statuses.push(text);
    },
    token: () => "",
    mcp: null,
  };
  const labels = [];
  const ctx = { setLabel: (text) => labels.push(text) };
  return {
    guppi,
    statuses,
    labels,
    emit(event) {
      const fn = events.get(event.type);
      assert.ok(fn, `no renderer for ${event.type}`);
      fn(event, null, ctx);
    },
    send(runInput) {
      return sendHooks.reduce((input, hook) => hook(input), runInput);
    },
    switchThread(threadId) {
      for (const hook of threadHooks) hook({ threadId });
    },
    registered: () => [...events.keys()].sort(),
  };
}

const RUN = { threadId: "t1", runId: "r1", messages: [], forwardedProps: {}, state: {} };

test("the extension takes the tool, step and state events", () => {
  const page = fakeGuppi();
  install(page.guppi);
  assert.deepEqual(page.registered(), [
    "STATE_SNAPSHOT",
    "STEP_FINISHED",
    "STEP_STARTED",
    "TOOL_CALL_END",
    "TOOL_CALL_START",
  ]);
});

test("a tool call's status line names the tool while it runs and once it ends", () => {
  const page = fakeGuppi();
  install(page.guppi);
  page.emit({ type: "TOOL_CALL_START", toolCallId: "c1", toolCallName: "hr___open_ticket" });
  page.emit({ type: "TOOL_CALL_END", toolCallId: "c1" });
  assert.deepEqual(page.statuses, ["Opening a ticket…", "Opened a ticket"]);
});

test("a delegation tags the reply and sets the step status lines", () => {
  const page = fakeGuppi();
  install(page.guppi);
  page.emit({ type: "STEP_STARTED", stepName: "pay" });
  page.emit({ type: "STEP_FINISHED", stepName: "pay" });
  assert.deepEqual(page.labels, ["HR Assistant · Pay"]);
  assert.deepEqual(page.statuses, ["Asking the Pay agent…", "Pay agent answered"]);
});

test("the snapshot goes back as the next run's state", () => {
  const page = fakeGuppi();
  install(page.guppi);
  assert.deepEqual(page.send(RUN).state, {});
  const snapshot = {
    activeDomain: "profile",
    pendingAction: { proposalId: "p1", field: "home_address", to: "419 Glendale Ave" },
  };
  page.emit({ type: "STATE_SNAPSHOT", snapshot });
  const next = page.send(RUN);
  assert.deepEqual(next.state, snapshot);
  assert.equal(next.threadId, "t1");
  assert.equal(next.runId, "r1");
});

test("a new or switched thread starts without state", () => {
  const page = fakeGuppi();
  install(page.guppi);
  page.emit({ type: "STATE_SNAPSHOT", snapshot: { activeDomain: "travel" } });
  page.switchThread("t2");
  assert.deepEqual(page.send(RUN).state, {});
});

test("thread state keeps only an object snapshot and hands out copies", () => {
  const thread = createThreadState();
  thread.keep(["not", "an", "object"]);
  assert.deepEqual(thread.current(), {});
  thread.keep(null);
  assert.deepEqual(thread.current(), {});
  thread.keep({ activeDomain: "pay" });
  const copy = thread.current();
  copy.activeDomain = "travel";
  assert.deepEqual(thread.current(), { activeDomain: "pay" });
  thread.startTool("c1", "docs___Retrieve");
  assert.equal(thread.endTool("c1"), "docs___Retrieve");
  assert.equal(thread.endTool("c1"), undefined);
});

test("withThreadState replaces the run's state and keeps the rest", () => {
  const run = { ...RUN, forwardedProps: { project: "hr-diy" }, state: { stale: true } };
  assert.deepEqual(withThreadState(run, { activeDomain: "pay" }), {
    ...run,
    state: { activeDomain: "pay" },
  });
});
