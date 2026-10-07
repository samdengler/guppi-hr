// The experiment page's dev server. It serves the page on 127.0.0.1 only, forwards the chat
// start to chat.dengler.io so the page calls it on its own origin (the chat start sends no
// CORS headers, E11), and answers the page's token request from the harness session.

import { defineConfig } from "vite";
import { tokenSource } from "./dev-token.mjs";

const SITE = process.env.GUPPI_SITE_URL || "https://chat.dengler.io";

function devToken() {
  const accessToken = tokenSource();
  return {
    name: "hr-dev-token",
    configureServer(server) {
      server.middlewares.use("/dev/token", async (req, res) => {
        res.setHeader("cache-control", "no-store");
        res.setHeader("content-type", "application/json");
        // Only this page may ask: a same-origin POST from the browser.
        if (req.method !== "POST" || req.headers["sec-fetch-site"] !== "same-origin") {
          res.statusCode = 403;
          res.end(JSON.stringify({ error: "forbidden" }));
          return;
        }
        try {
          const { token, expiresAt } = await accessToken();
          res.end(JSON.stringify({ token, expiresAt }));
        } catch (error) {
          res.statusCode = 503;
          res.end(JSON.stringify({ error: String(error?.message ?? error) }));
        }
      });
    },
  };
}

export default defineConfig({
  plugins: [devToken()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    // The /p/hr/ manifest is read from ../web, so the rules stay in one place.
    fs: { allow: [".", "../web"] },
    proxy: {
      "/api/hr/chat": { target: SITE, changeOrigin: true, secure: true },
    },
  },
});
