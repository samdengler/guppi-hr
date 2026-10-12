// Render docs/figures/diagrams.html to the PNGs beside it, at 2x.
// Needs playwright-core and a local Google Chrome (or CHROMIUM_PATH and PW_MODULE for another build):
//   npx -y -p playwright-core@1.47.2 node docs/figures/render.js
const { chromium } = require(process.env.PW_MODULE || 'playwright-core');
const path = require('path');
const FIGURES = {
  architecture: 'hr-architecture.png',
  tokens: 'hr-token-chain.png',
  connect: 'hr-connect-page.png',
};
(async () => {
  const opts = process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : { channel: 'chrome' };
  const b = await chromium.launch(opts);
  const p = await b.newPage({ viewport: { width: 1400, height: 1000 }, deviceScaleFactor: 2 });
  await p.goto('file://' + path.resolve(__dirname, 'diagrams.html'));
  await p.waitForTimeout(300);
  for (const [id, file] of Object.entries(FIGURES)) {
    const el = p.locator(`#${id}`);
    if (await el.count() === 0) continue;
    await el.screenshot({ path: path.join(__dirname, file) });
    console.log('wrote', file);
  }
  await b.close();
})().catch(e => { console.error('FAIL:', e.message); process.exit(1); });
