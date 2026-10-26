// Opens a Live wire node and screenshots the Update view. Usage: node update-shot.mjs <w> <h> <dark|light> <out.png> [nodeIndex]
import { chromium } from "/home/klk/circuit/apps/app/node_modules/@playwright/test/index.mjs";
const [w, h, scheme, out, idx = "0"] = process.argv.slice(2);
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: +w, height: +h }, colorScheme: scheme, reducedMotion: "reduce", hasTouch: +w < 600 });
const p = await ctx.newPage();
await p.goto("http://localhost:3000/?scenario=default"); await p.waitForLoadState("networkidle"); await p.waitForTimeout(1500);
await p.getByRole("list", { name: "Live wire" }).getByRole("button").nth(+idx).click();
await p.waitForTimeout(1500);
await p.screenshot({ path: out });
await b.close();
