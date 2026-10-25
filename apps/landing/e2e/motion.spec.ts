import { statSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "@playwright/test";

test("reduced motion: the poster stays, no video element and no video download", async ({ browser }) => {
  const ctx = await browser.newContext({ reducedMotion: "reduce" });
  const page = await ctx.newPage();
  const asked: string[] = [];
  page.on("request", (r) => asked.push(r.url()));
  await page.goto("/", { waitUntil: "load" });
  await page.waitForTimeout(1500);
  await expect(page.locator("video")).toHaveCount(0);
  await expect(page.locator('img[src$="circuit-logo-poster.webp"]')).toBeVisible();
  expect(asked.filter((u) => u.endsWith(".mp4"))).toEqual([]);
  await ctx.close();
});

test("normal motion: a muted, looping, inline video is added after the page has loaded, with the poster", async ({ browser }) => {
  const ctx = await browser.newContext({ reducedMotion: "no-preference" });
  const page = await ctx.newPage();
  await page.goto("/", { waitUntil: "load" });
  const video = page.locator("video");
  await expect(video).toHaveCount(1);
  await expect(video).toHaveJSProperty("muted", true);
  await expect(video).toHaveJSProperty("loop", true);
  await expect(video).toHaveJSProperty("playsInline", true);
  await expect(video).toHaveAttribute("poster", "/brand/circuit-logo-poster.webp");
  await expect(video).toHaveAttribute("preload", "none");
  const startedBeforeLoad = await page.evaluate(() => {
    const nav = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming;
    const v = performance.getEntriesByType("resource").find((r) => r.name.endsWith(".mp4"));
    return v ? v.startTime < nav.loadEventStart : false;
  });
  expect(startedBeforeLoad, "the video must not be fetched before the load event").toBe(false);
  await ctx.close();
});

test("the video file is under 1 MB and the poster is plain HTML (visible without JavaScript)", async ({ browser }) => {
  expect(statSync(join(__dirname, "../public/brand/circuit-logo.mp4")).size).toBeLessThan(1_000_000);
  const ctx = await browser.newContext({ javaScriptEnabled: false });
  const page = await ctx.newPage();
  await page.goto("/");
  await expect(page.locator('img[src$="circuit-logo-poster.webp"]')).toBeVisible();
  await ctx.close();
});
