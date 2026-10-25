// Usage: node landing-app-shots.mjs <persona>  (needs `make api` and `make app` running)
// Captures the Daily Drop on app Home as a 390x640 CSS px (780x1280 px) crop, dark and light, for the landing "How it works" step 2.
// Output: apps/landing/public/shots/daily-drop-{dark,light}.png (convert to AVIF/WebP afterwards).
import { chromium } from "/home/klk/circuit/apps/app/node_modules/@playwright/test/index.mjs";

const persona = process.argv[2] ?? "ravi";
const API = "http://localhost:8000", APP = "http://localhost:3000";
const out = "/home/klk/circuit/apps/landing/public/shots";
const { access_token } = await (await fetch(`${API}/api/demo/token`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ persona }) })).json();

const b = await chromium.launch();
for (const scheme of ["dark", "light"]) {
  const ctx = await b.newContext({ viewport: { width: 390, height: 1000 }, deviceScaleFactor: 2, colorScheme: scheme, reducedMotion: "reduce" });
  await ctx.addInitScript((t) => localStorage.setItem("circuit.token", t), access_token);
  const p = await ctx.newPage();
  await p.goto(APP);
  const drop = p.locator('section[aria-label="Daily Drop"]');
  await drop.waitFor({ timeout: 20000 });
  await p.waitForLoadState("networkidle"); await p.waitForTimeout(800);
  await drop.scrollIntoViewIfNeeded();
  await p.evaluate(() => window.scrollTo(0, 0));
  const top = (await drop.boundingBox()).y;
  await p.screenshot({ path: `${out}/daily-drop-${scheme}.png`, clip: { x: 0, y: Math.round(top) - 8, width: 390, height: 640 } });
  await ctx.close();
}
await b.close();
