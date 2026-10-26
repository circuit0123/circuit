// Screenshot of the running mock app. Usage: node screenshots/f3/app-shot.mjs <path> <w> <h> <dark|light> <out.png> [scenario] [fullPage]
import { chromium } from "/home/klk/circuit/apps/app/node_modules/@playwright/test/index.mjs";
const [path, w, h, scheme, out, scenario = "default", full] = process.argv.slice(2);
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: +w, height: +h }, colorScheme: scheme, reducedMotion: "reduce", deviceScaleFactor: 1, hasTouch: +w < 600 });
const p = await ctx.newPage();
await p.goto(`http://localhost:3000${path}${path.includes("?") ? "&" : "?"}scenario=${scenario}`);
await p.waitForLoadState("networkidle");
await p.waitForTimeout(2500);
// hide the dev banner so the frame matches the reference
await p.addStyleTag({ content: "[data-env-banner], #env-banner { display: none !important }" });
await p.screenshot({ path: out, fullPage: full === "full" });
await b.close();
