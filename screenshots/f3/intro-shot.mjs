// Screenshots of the intro sheet in its states. Usage: node intro-shot.mjs <w> <h> <dark|light> <outPrefix>
import { chromium } from "/home/klk/circuit/apps/app/node_modules/@playwright/test/index.mjs";
const [w, h, scheme, out] = process.argv.slice(2);
const b = await chromium.launch();
async function run(scenario, skips, name, send = false) {
  const ctx = await b.newContext({ viewport: { width: +w, height: +h }, colorScheme: scheme, reducedMotion: "reduce" });
  const p = await ctx.newPage();
  await p.goto(`http://localhost:3000/?scenario=${scenario}`); await p.waitForLoadState("networkidle"); await p.waitForTimeout(1500);
  const drop = p.getByRole("region", { name: "Daily Drop" });
  for (let i = 0; i < skips; i++) { await drop.getByRole("button", { name: "Skip" }).click(); await p.waitForTimeout(300); }
  await drop.getByRole("button", { name: "Intro me" }).click();
  await p.waitForTimeout(1200);
  if (send) { await p.getByRole("dialog").getByRole("button", { name: "Send request" }).click(); await p.waitForTimeout(1000); }
  await p.screenshot({ path: `${out}-${name}.png` });
  await ctx.close();
}
await run("default", 0, "via");
await run("default", 1, "no-connection");
await run("default", 2, "full", true);
await run("intros_used", 0, "weekly-limit", true);
await b.close();
