// Axe on the running mock app. Usage: node axe.mjs <path> <w> <dark|light> [scenario]
import { chromium } from "/home/klk/circuit/apps/app/node_modules/@playwright/test/index.mjs";
import AxeBuilder from "/home/klk/circuit/apps/app/node_modules/@axe-core/playwright/dist/index.mjs";
const [path, w, scheme, scenario = "default"] = process.argv.slice(2);
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: +w, height: 812 }, colorScheme: scheme, reducedMotion: "reduce" });
const p = await ctx.newPage();
await p.goto(`http://localhost:3000${path}?scenario=${scenario}`);
await p.waitForLoadState("networkidle"); await p.waitForTimeout(1000);
const r = await new AxeBuilder({ page: p }).analyze();
for (const v of r.violations) for (const n of v.nodes) console.log(v.id, "|", n.target.join(" "), "|", n.html.slice(0, 140), "|", (n.any[0]?.message ?? "").slice(0, 160));
console.log("violations:", r.violations.length);
await b.close();
