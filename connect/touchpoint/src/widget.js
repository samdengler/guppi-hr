// The /p/hr-widget/ extension (D62): AWS's Touchpoint chat widget on a stand-in HR portal
// page, over the /p/hr/ chat start, contact flow, canvas, sub-agents and tools. The platform
// page signs the employee in and hands this module the screen below its header
// (guppi.onSurface); Touchpoint's launcher, in the lower right corner, opens the chat panel
// over the page. Built into dist/widget/ext.js by vite.widget.config.js.

import { create } from "@amazon-connect-touchpoint/web";
import hr from "../../web/manifest.json";
import { chatStarter } from "./chat.js";
import { renderPortal } from "./portal.js";

const REGION = "us-east-1";
// The platform's CSP allows Connect's participant service on its amazonaws.com host only
// (guppi-gpt decision 22); Touchpoint's default is the api.aws host.
const PARTICIPANT_ENDPOINT = `https://participant.connect.${REGION}.amazonaws.com`;
// A variable, so the bundler leaves the URL to be resolved next to this module at run time.
const STYLESHEET = "./widget.css";

export default function install(guppi) {
  guppi.onSurface((surface) => mount(guppi, surface));
}

async function mount(guppi, surface) {
  const note = (text) => console.info(`[hr-widget] ${text}`);
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = new URL(STYLESHEET, import.meta.url).href;
  document.head.append(link);

  let touchpoint = null;
  const handler = () => touchpoint?.conversationHandler;
  renderPortal(surface, {
    suggestions: hr.suggestions ?? [],
    ask(prompt) {
      if (!touchpoint) return;
      touchpoint.expanded = true;
      handler().sendText(prompt);
    },
  });

  const starter = chatStarter({ bearer: () => guppi.token(), rules: hr.connectChat, handler, note });
  touchpoint = await create({
    config: {
      details: starter.details,
      region: REGION,
      globalConfig: {
        endpoint: PARTICIPANT_ENDPOINT,
        // Receipts stay off as on /p/hr/ (D57). Touchpoint's typing events cannot be turned off.
        features: { messageReceipts: { shouldSendMessageReceipts: false } },
      },
    },
    input: "text",
    colorMode: matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light",
    assistantName: guppi.project?.assistant ?? hr.assistant,
    userMessageBubble: true,
    agentMessageBubble: true,
  });
  handler().subscribe((all) => starter.track(all));
  note("Touchpoint mounted");
}
