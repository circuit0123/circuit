import { chromium } from "/home/klk/circuit/apps/app/node_modules/@playwright/test/index.mjs";
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 375, height: 812 }, colorScheme: "light", reducedMotion: "reduce" });
const p = await ctx.newPage();
await p.goto("http://localhost:3000/?scenario=default"); await p.waitForLoadState("networkidle"); await p.waitForTimeout(1000);
console.log(await p.evaluate(() => { const a = [...document.querySelectorAll('a[href$="discover"]')].find((x) => x.getBoundingClientRect().y > 500); const r = a.getBoundingClientRect(); return document.elementsFromPoint(r.x + r.width / 2, r.y + 10).slice(0, 8).map((e) => e.tagName + "." + String(e.className.baseVal ?? e.className).slice(0, 50) + " bg=" + getComputedStyle(e).backgroundColor); }));
await b.close();
