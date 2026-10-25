// Usage: node landing-motion.mjs rest <baseUrl> <outSubdir>      e.g. rest http://localhost:3111 before
//        node landing-motion.mjs frames <baseUrl>                  mid-animation frames (hero, arch, tile hover) into screenshots/landing-motion/frames/
//        node landing-motion.mjs video <baseUrl>                   screen recordings (home and /students, 375 and 1280) into screenshots/landing-motion/video/
// Serve a build first, e.g. `node scripts/serve-static.mjs apps/landing/.out-after 3112`.
import { chromium } from "/home/klk/circuit/apps/app/node_modules/@playwright/test/index.mjs";
import { mkdirSync, readdirSync, rmSync } from "node:fs";
import { execFileSync } from "node:child_process";

const ROOT = "/home/klk/circuit/screenshots/landing-motion";
const [mode, base, outSub] = process.argv.slice(2);
const PAGES = [["home", "/"], ["students", "/students/"]];
const SIZES = [[375, 812], [1280, 800]];
const b = await chromium.launch();

const scrollThrough = (p, step = 250, pause = 110) =>
  p.evaluate(async ([step, pause]) => { for (let y = 0; y < document.body.scrollHeight; y += step) { scrollTo(0, y); await new Promise((r) => setTimeout(r, pause)); } }, [step, pause]);

if (mode === "rest") {
  // The page at rest with motion ON, after scrolling through it: before and after the change must look the same (no layout shift).
  const dir = `${ROOT}/${outSub}`;
  mkdirSync(dir, { recursive: true });
  for (const [name, path] of PAGES) for (const [w, h] of SIZES) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, colorScheme: "dark", reducedMotion: "no-preference" });
    const p = await ctx.newPage();
    await p.goto(base + path, { waitUntil: "networkidle" });
    await scrollThrough(p);
    await p.waitForTimeout(1200);
    await p.evaluate(() => scrollTo(0, 0));
    await p.waitForTimeout(500);
    await p.screenshot({ path: `${dir}/${name}-${w}.png`, fullPage: true });
    await ctx.close();
  }
}

if (mode === "frames") {
  const dir = `${ROOT}/frames`;
  mkdirSync(dir, { recursive: true });
  for (const [w, h] of SIZES) {
    // Hero: freeze the CSS animation at 0.2s and 0.4s from its start.
    for (const t of [200, 400]) {
      const ctx = await b.newContext({ viewport: { width: w, height: h }, colorScheme: "dark", reducedMotion: "no-preference" });
      const p = await ctx.newPage();
      await p.addInitScript((t) => document.addEventListener("DOMContentLoaded", () => document.getAnimations().forEach((a) => { a.pause(); a.currentTime = t; })), t);
      await p.goto(base + "/", { waitUntil: "domcontentloaded" });
      await p.waitForTimeout(300);
      await p.screenshot({ path: `${dir}/hero-${w}-${t}ms.png` });
      await ctx.close();
    }
    // Bridge arch: freeze the first line half way through its 450ms draw.
    const ctx = await b.newContext({ viewport: { width: w, height: h }, colorScheme: "dark", reducedMotion: "no-preference" });
    const p = await ctx.newPage();
    await p.goto(base + "/", { waitUntil: "networkidle" });
    await p.waitForTimeout(800);
    await p.evaluate(() => {
      const bridge = document.querySelector("[data-bridge]");
      scrollTo(0, bridge.getBoundingClientRect().top + scrollY - (innerWidth < 600 ? 80 : 120));
    });
    await p.waitForTimeout(100);
    // Scroll in small steps until the first line starts drawing, then freeze it half way.
    await p.evaluate(() => new Promise((res) => {
      const t = setInterval(() => {
        const a = document.getAnimations().find((x) => x.effect?.target?.tagName?.toLowerCase() === "path");
        if (a) { clearInterval(t); a.pause(); a.currentTime = 225; res(); } else scrollBy(0, 12);
      }, 8);
    }));
    await p.waitForTimeout(150);
    await p.screenshot({ path: `${dir}/arch-${w}-half.png` });
    await ctx.close();
  }
  // Tile hover (desktop only: a phone has no hover).
  const ctx = await b.newContext({ viewport: { width: 1280, height: 800 }, colorScheme: "dark", reducedMotion: "no-preference" });
  const p = await ctx.newPage();
  await p.goto(base + "/", { waitUntil: "networkidle" });
  const tile = p.locator("[data-tile]").nth(1);
  await tile.scrollIntoViewIfNeeded();
  await p.waitForTimeout(900);
  await p.screenshot({ path: `${dir}/tiles-1280-rest.png`, clip: { x: 0, y: 0, width: 1280, height: 800 } });
  await tile.hover();
  await p.waitForTimeout(500);
  await p.screenshot({ path: `${dir}/tiles-1280-hover.png` });
  await ctx.close();
}

if (mode === "video") {
  const dir = `${ROOT}/video`;
  mkdirSync(dir, { recursive: true });
  for (const [w, h] of SIZES) for (const [name, path] of PAGES) {
    const tmp = `${dir}/tmp-${name}-${w}`;
    const ctx = await b.newContext({ viewport: { width: w, height: h }, colorScheme: "dark", reducedMotion: "no-preference", hasTouch: false, recordVideo: { dir: tmp, size: { width: w, height: h } } });
    const p = await ctx.newPage();
    await p.goto(base + path, { waitUntil: "load" });
    await p.waitForTimeout(1600); // the hero words and the video start
    await scrollThrough(p, 160, 120);
    await p.waitForTimeout(700);
    if (w > 600) {
      const tile = p.locator("[data-tile]").first();
      if (await tile.count()) { await p.evaluate(() => scrollTo({ top: 0 })); await p.waitForTimeout(500); await tile.scrollIntoViewIfNeeded(); await tile.hover(); await p.waitForTimeout(600); await p.mouse.move(2, 2); await p.waitForTimeout(500); }
    }
    const first = p.locator("details[data-faq] summary").first();
    await first.scrollIntoViewIfNeeded();
    await p.waitForTimeout(500);
    await first.click();
    await p.waitForTimeout(900);
    await first.click();
    await p.waitForTimeout(700);
    await ctx.close(); // writes the video
    const webm = readdirSync(tmp).find((f) => f.endsWith(".webm"));
    execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", `${tmp}/${webm}`, "-c:v", "libx264", "-crf", "30", "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", `${dir}/${name}-${w}.mp4`]);
    rmSync(tmp, { recursive: true, force: true });
  }
}

await b.close();
console.log("done", mode);
