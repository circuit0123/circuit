import { chromium } from "/home/klk/circuit/apps/app/node_modules/@playwright/test/index.mjs";
import AxeBuilder from "/home/klk/circuit/apps/app/node_modules/@axe-core/playwright/dist/index.mjs";
const { access_token } = await (await fetch("http://localhost:8000/api/demo/token", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ persona: "ravi" }) })).json();
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 375, height: 812 }, reducedMotion: "reduce" });
await ctx.addInitScript((t) => localStorage.setItem("circuit.token", t), access_token);
const p = await ctx.newPage();
await p.goto("http://localhost:3000"); await p.waitForLoadState("networkidle"); await p.waitForTimeout(800);
const more = p.getByRole("button", { name: "See earlier this week" });
if (await more.count()) { await more.click(); await p.waitForSelector("article"); await p.waitForTimeout(800); }
const wide = await p.evaluate(() => [...document.querySelectorAll("body *")].filter((e) => !e.closest("ul[aria-label=Today]") && e.getBoundingClientRect().right > innerWidth + 1).slice(0, 8).map((e) => e.tagName + "." + String(e.className).slice(0, 60) + " " + Math.round(e.getBoundingClientRect().right)));
console.log("wide:", wide);
console.log("sw", await p.evaluate(() => [document.documentElement.scrollWidth, document.body.scrollWidth, innerWidth]));
const r = await new AxeBuilder({ page: p }).analyze();
for (const v of r.violations) for (const n of v.nodes.slice(0, 3)) console.log(v.id, "|", n.target.join(" "), "|", n.html.slice(0, 120));
await b.close();
