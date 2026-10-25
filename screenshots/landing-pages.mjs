// Usage: node landing-pages.mjs <outDir> <baseUrl> <slug...>   e.g. node landing-pages.mjs landing-pages http://localhost:3101 students
// Full-page screenshots of audience pages at 375 and 1280, dark and light, into screenshots/<outDir>/<slug>/<width>-<theme>.png.
// Serve a build first, e.g. `node scripts/serve-static.mjs apps/landing/.out-on 3101` (made by `make test-landing`).
import { chromium } from "/home/klk/circuit/apps/app/node_modules/@playwright/test/index.mjs";
import { mkdirSync } from "node:fs";

const [outDir, base, ...slugs] = process.argv.slice(2);
const b = await chromium.launch();
for (const slug of slugs) {
  const dir = `/home/klk/circuit/screenshots/${outDir}/${slug}`;
  mkdirSync(dir, { recursive: true });
  for (const [w, h] of [[375, 812], [1280, 800]]) {
    for (const scheme of ["dark", "light"]) {
      const ctx = await b.newContext({ viewport: { width: w, height: h }, colorScheme: scheme, reducedMotion: "reduce" });
      const p = await ctx.newPage();
      await p.goto(`${base}/${slug}/`, { waitUntil: "networkidle" });
      await p.evaluate(async () => { for (let y = 0; y < document.body.scrollHeight; y += 400) { scrollTo(0, y); await new Promise((r) => setTimeout(r, 60)); } scrollTo(0, 0); });
      await p.waitForTimeout(400);
      await p.screenshot({ path: `${dir}/${w}-${scheme}.png`, fullPage: true });
      await ctx.close();
    }
  }
}
await b.close();
console.log("done");
