import { chromium } from "/home/klk/circuit/apps/app/node_modules/@playwright/test/index.mjs";
import AxeBuilder from "/home/klk/circuit/apps/app/node_modules/@axe-core/playwright/dist/index.mjs";
const out = process.argv[2];
const b = await chromium.launch();
for (const [name, url] of [["landing", "http://localhost:3001"], ["home", "http://localhost:3000"]]) {
  for (const [w, h] of [[375, 812], [1280, 800]]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, reducedMotion: "reduce" });
    const p = await ctx.newPage();
    await p.goto(url); await p.waitForLoadState("networkidle");
    await p.screenshot({ path: `${out}/shots/${name}-${w}.png`, fullPage: true });
    const r = await new AxeBuilder({ page: p }).analyze();
    console.log(name, w, "axe violations:", r.violations.map(v => `${v.id}(${v.impact}) x${v.nodes.length}`).join(", ") || "none");
    const overflow = await p.evaluate(() => document.documentElement.scrollWidth > innerWidth);
    console.log(name, w, "horizontal overflow:", overflow);
    await ctx.close();
  }
}
await b.close();
