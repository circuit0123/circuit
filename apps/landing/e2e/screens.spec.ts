import { expect, test } from "@playwright/test";
import { SCREENS, type ScreenId } from "../src/content/screens";

/** Which app screens each page shows (public/screens, rendered by `make landing-screens`). */
const SHOWN: Record<string, ScreenId[]> = {
  "/": ["home-main", "discover-jobs", "map", "circuits"],
  "/students/": ["discover-jobs", "map", "job"],
  "/founders/": ["home-match", "people", "inbox"],
  "/mentors/": ["people", "circuits", "chat"],
  "/investors/": ["investor-picks"],
  "/partners/": ["partner-home"],
};

/** Steps with a screen of their own ("How it works", step 03), besides the strip. */
const STEP_SCREENS: Record<string, ScreenId[]> = { "/": ["circuits"], "/students/": ["job"], "/mentors/": ["circuits"] };

test.use({ reducedMotion: "reduce" });

for (const [path, ids] of Object.entries(SHOWN)) {
  test(`${path}: shows its app screens, as AVIF, WebP and PNG, with size, alt text and lazy loading`, async ({ page }) => {
    await page.goto(path);
    const pictures = page.getByRole("region", { name: "App screens" }).locator("picture");
    await expect(pictures).toHaveCount(ids.length);
    for (const [i, id] of ids.entries()) {
      const pic = pictures.nth(i);
      await expect(pic.locator("source")).toHaveCount(2);
      await expect(pic.locator("source").nth(0)).toHaveAttribute("type", "image/avif");
      await expect(pic.locator("source").nth(1)).toHaveAttribute("type", "image/webp");
      const img = pic.locator("img");
      await expect(img).toHaveAttribute("alt", SCREENS[id].alt);
      await expect(img).toHaveAttribute("width", "780");
      await expect(img).toHaveAttribute("height", "1688");
      await expect(img).toHaveAttribute("loading", "lazy");
      await img.scrollIntoViewIfNeeded();
      await expect.poll(() => img.evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth)).toBe(780);
      await expect.poll(() => img.evaluate((el: HTMLImageElement) => el.currentSrc)).toMatch(new RegExp(`/screens/${id}\\.avif$`));
    }
    await expect(page.locator("main img[src^='/screens/']")).toHaveCount(ids.length + (STEP_SCREENS[path]?.length ?? 0));
    for (const id of STEP_SCREENS[path] ?? []) await expect(page.locator(`li img[src="/screens/${id}.png"]`).first()).toHaveAttribute("alt", SCREENS[id].alt);
    await expect(page.getByText("The screens show sample data, not real people or startups.")).toHaveCount(1);
  });
}

test("the phone strip can be reached with the keyboard on a phone and never widens the page", async ({ page }, info) => {
  await page.goto("/");
  const strip = page.getByRole("region", { name: "App screens" });
  await expect(strip).toHaveAttribute("tabindex", "0");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  if (info.project.name === "phone") expect(await strip.evaluate((el) => el.scrollWidth > el.clientWidth)).toBe(true);
  else expect(await strip.evaluate((el) => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
});
