// Usage: node shots-v2.mjs <outDir> [persona] — Home at 375 (dark, light) and 1280, plus Update view, axe + overflow checks.
import { chromium } from "/home/klk/circuit/apps/app/node_modules/@playwright/test/index.mjs";
import AxeBuilder from "/home/klk/circuit/apps/app/node_modules/@axe-core/playwright/dist/index.mjs";
import { mkdirSync } from "node:fs";

const out = process.argv[2];
const persona = process.argv[3] ?? "ravi";
const API = "http://localhost:8000", APP = "http://localhost:3000";
mkdirSync(out, { recursive: true });
const { access_token } = await (await fetch(`${API}/api/demo/token`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ persona }) })).json();

const b = await chromium.launch();
const runs = [
  ["375-dark", 375, 812, "dark"], ["375-light", 375, 812, "light"],
  ["1280-dark", 1280, 800, "dark"], ["1280-light", 1280, 800, "light"],
];
for (const [name, w, h, scheme] of runs) {
  for (const full of [false, true]) {
    const ctx = await b.newContext({ viewport: { width: w, height: full ? 3000 : h }, colorScheme: scheme, reducedMotion: "reduce" });
    await ctx.addInitScript((t) => localStorage.setItem("circuit.token", t), access_token);
    const p = await ctx.newPage();
    p.on("console", (m) => m.type() === "error" && console.log("console error:", m.text().slice(0, 200)));
    await p.goto(APP); await p.waitForSelector('section[aria-label="Pulse"] article', { timeout: 15000 }).catch(() => {});
    await p.waitForLoadState("networkidle"); await p.waitForTimeout(500);
    const more = p.getByRole("button", { name: "See earlier this week" });
    if (await more.count()) { await more.click(); await p.waitForSelector('section[aria-label="Pulse"] article'); await p.waitForTimeout(800); }
    await p.evaluate(() => window.scrollTo(0, 0)); await p.waitForTimeout(300);
    await p.screenshot({ path: `${out}/home-${name}${full ? "-full" : ""}.png` });
    if (!full) {
      const r = await new AxeBuilder({ page: p }).analyze();
      console.log(name, "axe:", r.violations.map((v) => `${v.id}(${v.impact}) x${v.nodes.length}`).join(", ") || "none");
      console.log(name, "overflow:", await p.evaluate(() => document.documentElement.scrollWidth > innerWidth));
    }
    await ctx.close();
  }
}

// Update view and the finished drop (375). These change server state, so reset the demo afterwards.
for (const scheme of ["dark", "light"]) {
  const ctx = await b.newContext({ viewport: { width: 375, height: 812 }, colorScheme: scheme, reducedMotion: "reduce" });
  await ctx.addInitScript((t) => localStorage.setItem("circuit.token", t), access_token);
  const p = await ctx.newPage();
  await p.goto(APP); await p.waitForSelector('ul[aria-label="Live wire"] button');
  await p.locator('ul[aria-label="Live wire"] button').first().click(); await p.waitForTimeout(600);
  await p.screenshot({ path: `${out}/update-375-${scheme}.png` });
  await p.keyboard.press("Escape"); await p.waitForTimeout(400);
  await p.screenshot({ path: `${out}/home-after-update-375-${scheme}.png` });
  if (scheme === "dark") {
    for (let i = 0; i < 3; i++) { const skip = p.getByRole("button", { name: "Skip" }); if (!(await skip.count())) break; await skip.click(); await p.waitForTimeout(500); }
    await p.waitForTimeout(500);
    await p.screenshot({ path: `${out}/drop-done-375-dark.png` });
  }
  await ctx.close();
}
await b.close();
