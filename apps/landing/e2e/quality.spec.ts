import { expect, test } from "@playwright/test";
import { checkPage, THEMES } from "./support";

for (const theme of THEMES) {
  test.describe(`${theme} theme`, () => {
    test.use({ colorScheme: theme, reducedMotion: "reduce" });

    test("axe clean, no horizontal scroll, one logo visible", async ({ page }, info) => {
      await page.goto("/");
      await page.getByRole("heading", { name: "Questions" }).scrollIntoViewIfNeeded();
      await checkPage(page, `home ${info.project.name} ${theme}`);
      await expect(page.locator("header svg[aria-label=Circuit]:visible")).toHaveCount(1);
      for (const path of ["/privacy/", "/terms/"]) {
        await page.goto(path);
        await checkPage(page, `${path} ${info.project.name} ${theme}`);
      }
    });

    test("app screenshot follows the theme", async ({ page }) => {
      await page.goto("/");
      const img = page.getByRole("img", { name: /Daily Drop in the Circuit app/ });
      await img.scrollIntoViewIfNeeded();
      await expect(img).toBeVisible();
      await expect.poll(() => img.evaluate((el: HTMLImageElement) => el.currentSrc)).toMatch(new RegExp(`daily-drop-${theme}\\.(avif|webp)$`));
    });
  });
}

test("makes no request outside the landing origin, and shows no placeholder text or fake numbers", async ({ page }) => {
  const origins = new Set<string>();
  page.on("request", (r) => origins.add(new URL(r.url()).origin));
  await page.goto("/", { waitUntil: "networkidle" });
  expect([...origins]).toEqual(["http://localhost:3101"]);
  const text = await page.locator("body").innerText();
  expect(text).not.toMatch(/\[[^\]]+\]/);
  expect(text).not.toMatch(/lorem|john doe/i);
  // The only digits on the page are the step numbers and "under 18": no counts, no stats (DESIGN.md §12).
  expect(text.replace(/\b0[123]\b|\b18\b/g, "").match(/\d+/g)).toBeNull();
  await expect(page.getByRole("region", { name: /Live in/ })).toHaveCount(0);
});

test("the two screens that don't exist yet are labelled placeholders", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("img", { name: "App screenshot coming: You offer screen" })).toBeVisible();
  await expect(page.getByRole("img", { name: "App screenshot coming: Circuit ring screen" })).toBeVisible();
});

test("SEO: title, description, canonical, Open Graph, Twitter, icons, robots and sitemap", async ({ page, request }) => {
  await page.goto("/");
  const meta = (sel: string) => page.locator(sel).getAttribute("content");
  await expect(page).toHaveTitle("Circuit — build with people near you");
  expect(await meta('meta[name="description"]')).toMatch(/needs and can offer/);
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", "http://localhost:3101/");
  expect(await meta('meta[property="og:image"]')).toBe("http://localhost:3101/og.png");
  expect(await meta('meta[property="og:title"]')).toBe("Circuit — build with people near you");
  expect(await meta('meta[name="twitter:card"]')).toBe("summary_large_image");
  expect(await meta('meta[name="twitter:image"]')).toBe("http://localhost:3101/og.png");
  expect(await meta('meta[name="robots"]')).not.toMatch(/noindex/);
  await expect(page.locator('link[rel="icon"]')).toHaveAttribute("href", /favicon\.ico/);
  await expect(page.locator('link[rel="apple-touch-icon"]')).toHaveAttribute("href", /apple-touch-icon\.png/);
  await expect(page.locator("html")).toHaveAttribute("lang", "en-IN");
  const robots = await (await request.get("/robots.txt")).text();
  expect(robots).toMatch(/Allow: \//);
  expect(robots).toContain("Sitemap: http://localhost:3101/sitemap.xml");
  expect(await (await request.get("/sitemap.xml")).text()).toContain("<loc>http://localhost:3101/</loc>");
  for (const asset of ["/og.png", "/favicon.ico", "/apple-touch-icon.png"]) expect((await request.get(asset)).status(), asset).toBe(200);
});

test("the legal holding pages are not indexed", async ({ page }) => {
  await page.goto("/privacy/");
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /noindex/);
});
