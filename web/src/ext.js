// The HR extension for the chat.dengler.io platform page (guppi-gpt's
// docs/proposals/platform.md, "Page extension API"). The page imports this module from
// /projects/hr-diy/ext.js and calls the default export with its `guppi` object. It carries
// what phase 5 built into HR's own page:
//
// - a status line per tool call and per delegation ("Asking the Pay agent…"),
// - the reply's label tagged with the agent that answered ("HR Assistant · Pay"),
// - the AG-UI state round trip: the run's STATE_SNAPSHOT (activeDomain, pendingAction)
//   is sent back as `state` on the next run, so a "yes" can commit a proposed change
//   (D6, D23), and a new or switched thread starts without it.
//
// The page's history keeps reply text only, so a reopened thread shows the plain label;
// the agent tag lives for the page load (D33).

import { replyLabel, stepStatus, toolStatus } from "./copy.js";

/**
 * The extension's state for one page load: the last snapshot of the current thread and
 * the names of tool calls in flight (TOOL_CALL_END carries only the id).
 */
export function createThreadState() {
  let state = {};
  const toolNames = new Map();
  return {
    /** The state to send on the next run; a copy, so a hook downstream cannot change it. */
    current() {
      return { ...state };
    },
    /** Keeps a STATE_SNAPSHOT's snapshot as the thread's state; anything else is empty. */
    keep(snapshot) {
      state =
        snapshot && typeof snapshot === "object" && !Array.isArray(snapshot) ? { ...snapshot } : {};
    },
    startTool(toolCallId, toolCallName) {
      toolNames.set(toolCallId, toolCallName);
    },
    /** The name of a tool call that has ended, forgotten afterwards. */
    endTool(toolCallId) {
      const name = toolNames.get(toolCallId);
      toolNames.delete(toolCallId);
      return name;
    },
    reset() {
      state = {};
      toolNames.clear();
    },
  };
}

/** The run input with the thread's state in place of whatever state it carried. */
export function withThreadState(runInput, state) {
  return { ...runInput, state };
}

export default function install(guppi) {
  const thread = createThreadState();

  guppi.renderers.event("TOOL_CALL_START", (event) => {
    thread.startTool(event.toolCallId, event.toolCallName);
    guppi.status(toolStatus(event.toolCallName).running);
  });
  guppi.renderers.event("TOOL_CALL_END", (event) => {
    guppi.status(toolStatus(thread.endTool(event.toolCallId)).done);
  });
  guppi.renderers.event("STEP_STARTED", (event, _slot, ctx) => {
    ctx.setLabel(replyLabel(event.stepName));
    guppi.status(stepStatus(event.stepName).running);
  });
  guppi.renderers.event("STEP_FINISHED", (event) => {
    guppi.status(stepStatus(event.stepName).done);
  });
  guppi.renderers.event("STATE_SNAPSHOT", (event) => {
    thread.keep(event.snapshot);
  });
  guppi.onSend((runInput) => withThreadState(runInput, thread.current()));
  guppi.onThread(() => thread.reset());
}
