// Usage: node landing-compare.mjs  (needs the landing static export served on :3101, e.g. `make test-landing` once, then
//   python3 -m http.server 3101 -d apps/landing/out)
// Shots of the built landing home at 375 and 1280, dark and light, next to Landing.dc.html (dark only: the mock has no light version).
// The mock's template tags (<sc-for>) are expanded from its own sample data, and Geist is loaded from the landing build so both use the same font.
import { chromium } from "/home/klk/circuit/apps/app/node_modules/@playwright/test/index.mjs";
import { mkdirSync, readFileSync, readdirSync } from "node:fs";
import { execSync } from "node:child_process";

const OUT = "/home/klk/circuit/screenshots/landing-home";
const SITE = "http://localhost:3101/";
mkdirSync(OUT, { recursive: true });

// Expand the mock: evaluate its sample data, repeat each <sc-for> body per item, fill {{x.y}}.
const src = readFileSync("/home/klk/circuit/docs/design-reference/Landing.dc.html", "utf8");
const logic = /<script type="text\/x-dc"[^>]*>([\s\S]*?)<\/script>/.exec(src)[1];
const data = new Function("DCLogic", `${logic}; return new Component().renderVals();`)(class {});
let body = /<x-dc>([\s\S]*?)<\/x-dc>/.exec(src)[1].replace(/<helmet>[\s\S]*?<\/helmet>/, "");
body = body.replace(/<sc-for list="\{\{(\w+)\}\}" as="(\w+)"[^>]*>([\s\S]*?)<\/sc-for>/g, (_, list, as, inner) =>
  data[list].map((item) => inner.replace(new RegExp(`\\{\\{${as}\\.(\\w+)\\}\\}`, "g"), (_m, k) => item[k])).join(""));
const font = readdirSync("/home/klk/circuit/apps/landing/out/_next/static/media").find((f) => f.startsWith("Geist_Variable"));
const refHtml = `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>@font-face{font-family:Geist;src:url(file:///home/klk/circuit/apps/landing/out/_next/static/media/${font});font-weight:100 900}
body{margin:0;background:#000}a{color:#F3EEF5;text-decoration:none}summary{cursor:pointer;list-style:none}summary::-webkit-details-marker{display:none}</style>${body}`;
const refFile = "/tmp/claude-1000/-home-klk-circuit/fd801764-9c69-46a8-aaac-0b3a8e5c33bc/scratchpad/landing-ref.html";
(await import("node:fs")).writeFileSync(refFile, refHtml);

const b = await chromium.launch();
for (const [w, h] of [[375, 812], [1280, 800]]) {
  for (const scheme of ["dark", "light"]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, colorScheme: scheme, reducedMotion: "reduce", deviceScaleFactor: 1 });
    const p = await ctx.newPage();
    await p.goto(SITE, { waitUntil: "networkidle" });
    // lazy images: scroll through once so the screenshots below the fold are loaded
    await p.evaluate(async () => { for (let y = 0; y < document.body.scrollHeight; y += 400) { scrollTo(0, y); await new Promise((r) => setTimeout(r, 60)); } scrollTo(0, 0); });
    await p.waitForTimeout(500);
    await p.screenshot({ path: `${OUT}/home-${w}-${scheme}.png`, fullPage: true });
    await p.screenshot({ path: `${OUT}/home-${w}-${scheme}-fold.png` });
    await ctx.close();
  }
  const ctx = await b.newContext({ viewport: { width: w, height: h }, colorScheme: "dark", deviceScaleFactor: 1 });
  const p = await ctx.newPage();
  await p.goto("file://" + refFile, { waitUntil: "load" });
  await p.waitForTimeout(300);
  await p.screenshot({ path: `${OUT}/ref-${w}-dark.png`, fullPage: true });
  await p.screenshot({ path: `${OUT}/ref-${w}-dark-fold.png` });
  await ctx.close();
}
await b.close();
for (const w of [375, 1280]) {
  execSync(`magick ${OUT}/ref-${w}-dark.png -background '#444' -gravity north ${OUT}/home-${w}-dark.png +append ${OUT}/compare-${w}-dark.png`);
  execSync(`magick ${OUT}/ref-${w}-dark-fold.png -background '#444' ${OUT}/home-${w}-dark-fold.png ${OUT}/home-${w}-light-fold.png +append ${OUT}/compare-${w}-fold.png`);
}
console.log("done");
