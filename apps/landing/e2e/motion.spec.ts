import { statSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { PATHS } from "./support";

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

/**
 * Landing motion (DESIGN.md §7): hero words, section reveals, tiles, buttons and the FAQ, on every page.
 * Rules under test: only transform and opacity; plays once; no layout shift; visible without JavaScript; reduced motion = static.
 */
const ALLOWED = new Set(["opacity", "transform"]);

/** Scrolls the whole page slowly enough for every reveal to trigger. */
async function scrollThrough(page: Page) {
  await page.evaluate(async () => {
    for (let y = 0; y < document.body.scrollHeight; y += 250) {
      scrollTo(0, y);
      await new Promise((r) => setTimeout(r, 100));
    }
  });
}

/** Everything a section reveals: its direct children (and list items). */
const REVEALABLE = "main > section:not(:first-child) > div > *, main > section:not(:first-child) [data-stagger] > *";

test.describe("reduced motion: everything is static", () => {
  test.use({ reducedMotion: "reduce" });
  for (const path of PATHS) {
    test(`${path}: nothing animates, nothing is hidden`, async ({ page }, info) => {
      await page.goto(path);
      await page.waitForTimeout(800);
      await scrollThrough(page);
      expect(await page.evaluate(() => document.getAnimations().length), "animations running").toBe(0);
      expect(await page.evaluate(() => document.documentElement.hasAttribute("data-motion"))).toBe(false);
      const words = await page.locator(".hero-word").evaluateAll((els) => els.map((el) => [getComputedStyle(el).animationName, getComputedStyle(el).opacity, getComputedStyle(el).transform]));
      expect(words.length).toBeGreaterThan(1);
      for (const w of words) expect(w).toEqual(["none", "1", "none"]);
      const hidden = await page.locator(REVEALABLE).evaluateAll((els) => els.filter((el) => getComputedStyle(el).opacity !== "1" || getComputedStyle(el).transform !== "none").length);
      expect(hidden, "revealable items not at rest").toBe(0);
      // The FAQ opens at once, with no animation; the tiles do not move on hover.
      await page.locator("summary").first().click();
      await expect(page.locator("details[open]")).toHaveCount(1);
      expect(await page.evaluate(() => document.getAnimations().length)).toBe(0);
      if (path === "/" && info.project.name === "desktop") {
        await page.locator("[data-tile]").first().hover();
        await page.waitForTimeout(400);
        await expect(page.locator("[data-tile]").first()).toHaveCSS("transform", "none");
      }
    });
  }
});

test.describe("normal motion", () => {
  test.use({ reducedMotion: "no-preference" });

  for (const path of PATHS) {
    test(`${path}: hero words rise once and end at rest; reveals and FAQ play once`, async ({ page }) => {
      // Record every property any animation touches (script-driven ones here; the CSS keyframes are read from the stylesheet below).
      await page.addInitScript(() => {
        const w = window as unknown as { __props: Set<string>; __easings: Set<string>; __calls: number };
        w.__props = new Set();
        w.__easings = new Set();
        w.__calls = 0;
        const original = Element.prototype.animate;
        Element.prototype.animate = function (keyframes, options) {
          w.__calls++;
          if (options && typeof options === "object" && typeof options.easing === "string") w.__easings.add(options.easing);
          const list = Array.isArray(keyframes) ? keyframes : [keyframes ?? {}];
          for (const k of list) for (const key of Object.keys(k)) if (key !== "offset" && key !== "easing" && key !== "composite") w.__props.add(key);
          return original.call(this, keyframes, options);
        };
      });
      await page.goto(path);
      await expect(page.locator("html")).toHaveAttribute("data-motion", "");

      // Hero: a CSS animation on every word, finished and at rest well inside a second.
      const words = page.locator(".hero-word");
      expect(await words.evaluateAll((els) => els.every((el) => getComputedStyle(el).animationName === "hero-rise"))).toBe(true);
      await page.waitForTimeout(1200);
      expect(await words.evaluateAll((els) => els.map((el) => [getComputedStyle(el).opacity, getComputedStyle(el).transform]))).toEqual(
        Array.from({ length: await words.count() }, () => ["1", "none"]),
      );

      // Below the fold: hidden until it comes into view, then it reveals and the inline styles are cleared.
      const faqTitle = page.locator("#faq-h");
      await expect(faqTitle).toHaveCSS("opacity", "0");
      await faqTitle.scrollIntoViewIfNeeded();
      await expect(faqTitle).toHaveCSS("opacity", "1");
      await expect.poll(() => faqTitle.evaluate((el) => el.getAttribute("style") ?? "")).toBe("");

      // Every other reveal plays during one slow pass down the page.
      await scrollThrough(page);

      // FAQ: opens with the answer fading in, closes again.
      const first = page.locator("details[data-faq]").first();
      await first.scrollIntoViewIfNeeded();
      await first.locator("summary").click();
      await expect(first).toHaveJSProperty("open", true);
      await expect(first.locator("[data-faq-answer]")).toHaveCSS("opacity", "1");
      await first.locator("summary").click();
      await expect(first).toHaveJSProperty("open", false);

      // Plays once: going up and down the page again starts no new animation and hides nothing.
      await page.waitForTimeout(600);
      const before = await page.evaluate(() => (window as unknown as { __calls: number }).__calls);
      // (The pointer is parked in the page margin: a tile scrolling under a still pointer would, correctly, react to hover.)
      await page.mouse.move(0, 0);
      await page.evaluate(() => scrollTo(0, 0));
      await scrollThrough(page);
      await page.waitForTimeout(600);
      expect(await page.evaluate(() => (window as unknown as { __calls: number }).__calls), "animations started on the second pass").toBe(before);
      expect(await page.locator(REVEALABLE).evaluateAll((els) => els.filter((el) => getComputedStyle(el).opacity !== "1").length)).toBe(0);

      // The default spring is really applied (a CSS linear() curve), not silently replaced by a plain ease-out.
      const easings = await page.evaluate(() => [...(window as unknown as { __easings: Set<string> }).__easings]);
      expect(easings.some((e) => e.startsWith("linear(")), `easings seen: ${easings.join(" | ")}`).toBe(true);

      // Only transform and opacity, in script-driven animations and in the CSS keyframes.
      const props = await page.evaluate(() => [...(window as unknown as { __props: Set<string> }).__props]);
      expect(props.length).toBeGreaterThan(0);
      for (const prop of props) expect(ALLOWED.has(prop), `animated property ${prop}`).toBe(true);
      const cssProps = await page.evaluate(() =>
        [...document.styleSheets].flatMap((sheet) => [...sheet.cssRules]).flatMap((rule) => (rule instanceof CSSKeyframesRule ? [...rule.cssRules].flatMap((k) => [...(k as CSSKeyframeRule).style]) : [])),
      );
      expect(cssProps.length).toBeGreaterThan(0);
      for (const prop of new Set(cssProps)) expect(ALLOWED.has(prop), `keyframe property ${prop}`).toBe(true);
    });

    test(`${path}: no layout shift while loading and scrolling`, async ({ page }) => {
      await page.addInitScript(() => {
        const w = window as unknown as { __cls: number };
        w.__cls = 0;
        new PerformanceObserver((list) => {
          for (const e of list.getEntries() as unknown as Array<{ value: number; hadRecentInput: boolean }>) if (!e.hadRecentInput) w.__cls += e.value;
        }).observe({ type: "layout-shift", buffered: true });
      });
      await page.goto(path, { waitUntil: "networkidle" });
      await page.waitForTimeout(1000);
      await scrollThrough(page);
      await page.waitForTimeout(1000);
      expect(await page.evaluate(() => (window as unknown as { __cls: number }).__cls)).toBe(0);
    });
  }

  test("tiles lift 2px and nudge the arrow 4px on hover and focus, and settle back", async ({ page }, info) => {
    test.skip(info.project.name === "phone", "hover needs a pointer");
    await page.goto("/");
    await expect(page.locator("html")).toHaveAttribute("data-motion", "");
    const tile = page.locator("[data-tile]").first();
    const arrow = tile.locator("[data-arrow]");
    await tile.scrollIntoViewIfNeeded();
    await tile.hover();
    await expect(tile).toHaveCSS("transform", "matrix(1, 0, 0, 1, 0, -2)");
    await expect(arrow).toHaveCSS("transform", "matrix(1, 0, 0, 1, 4, 0)");
    await page.mouse.move(0, 0);
    await expect(tile).toHaveCSS("transform", "matrix(1, 0, 0, 1, 0, 0)");
    await expect(arrow).toHaveCSS("transform", "matrix(1, 0, 0, 1, 0, 0)");
    await page.keyboard.press("Tab"); // keyboard focus gets the same lift
    await tile.focus();
    await page.keyboard.press("Shift+Tab");
    await page.keyboard.press("Tab");
    await expect(tile).toHaveCSS("transform", "matrix(1, 0, 0, 1, 0, -2)");
  });

  test("buttons scale to 0.97 while pressed and tiles to 0.98, with no second CSS scale on top", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("html")).toHaveAttribute("data-motion", "");
    const button = page.getByRole("link", { name: "Join the beta" });
    const box = (await button.boundingBox())!;
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    await expect(button).toHaveCSS("transform", "matrix(0.97, 0, 0, 0.97, 0, 0)");
    await expect(button).toHaveCSS("scale", "none");
    await page.mouse.move(2, 2); // release away from the link so nothing navigates
    await page.mouse.up();
    await expect(button).toHaveCSS("transform", "matrix(1, 0, 0, 1, 0, 0)");

    const tile = page.locator("[data-tile]").first();
    await tile.scrollIntoViewIfNeeded();
    const t = (await tile.boundingBox())!;
    await page.mouse.move(t.x + t.width / 2, t.y + t.height / 2);
    await page.mouse.down();
    await expect.poll(() => tile.evaluate((el) => new DOMMatrix(getComputedStyle(el).transform).a)).toBeCloseTo(0.98, 2);
    await page.mouse.move(2, 2);
    await page.mouse.up();
  });
});

test.describe("without JavaScript", () => {
  test.use({ javaScriptEnabled: false });
  for (const path of PATHS) {
    test(`${path}: the headline and every section are fully visible`, async ({ page }) => {
      await page.goto(path);
      await page.waitForTimeout(1200); // the hero keyframes are pure CSS: they finish by themselves
      const h1 = await page.locator("h1").innerText();
      expect(h1.trim().split(/\s+/).length).toBeGreaterThan(2);
      expect(await page.locator(".hero-word").evaluateAll((els) => els.every((el) => getComputedStyle(el).opacity === "1"))).toBe(true);
      expect(await page.locator(REVEALABLE).evaluateAll((els) => els.filter((el) => getComputedStyle(el).opacity !== "1").length)).toBe(0);
      // The FAQ still opens natively.
      await page.locator("summary").first().click();
      await expect(page.locator("details[open]")).toHaveCount(1);
    });
  }
});
