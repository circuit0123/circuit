import { expect, test } from "@playwright/test";
import { PAGES } from "../src/content/pages";
import { APP, ON } from "./support";

/** What each proof section must say it is (DESIGN.md §12: never fake numbers or people). Students has real placeholders instead. */
const PROOF_LABEL: Record<string, string | null> = { students: null, founders: "Example", mentors: "Example", investors: "Example", partners: "Demo data" };

for (const p of PAGES) {
  test.describe(`/${p.slug}/`, () => {
    test.beforeEach(async ({ page }) => { await page.goto(`/${p.slug}/`); });

    test("headline, title, current page in the header, one primary button", async ({ page }) => {
      await expect(page.getByRole("heading", { level: 1 })).toHaveText(p.headline);
      await expect(page).toHaveTitle(`${p.title} — Circuit`);
      await expect(page.getByRole("navigation", { name: "Audiences" }).locator("[aria-current=page]")).toHaveText(p.who);
      const primaries = await page.evaluate(() => {
        const probe = document.createElement("i");
        probe.style.color = "var(--primary)";
        document.body.append(probe);
        const primary = getComputedStyle(probe).color;
        probe.remove();
        return Array.from(document.querySelectorAll("a, button")).filter((el) => getComputedStyle(el).backgroundColor === primary).map((el) => el.textContent?.trim());
      });
      expect(primaries).toEqual([p.cta]);
    });

    test("three steps, a proof section, 4 to 6 FAQ answers", async ({ page }) => {
      await expect(page.locator("#how-h ~ ol > li, section[aria-labelledby=how-h] ol > li")).toHaveCount(3);
      await expect(page.locator("section[aria-labelledby=proof-h]")).toHaveCount(1);
      const faq = await page.locator("section[aria-labelledby=faq-h] details").count();
      expect(faq).toBeGreaterThanOrEqual(4);
      expect(faq).toBeLessThanOrEqual(6);
    });

    test("the proof section says what it is", async ({ page }) => {
      const proof = page.locator("section[aria-labelledby=proof-h]");
      const label = PROOF_LABEL[p.slug];
      if (label) await expect(proof.getByText(label, { exact: true })).toHaveCount(1);
      else await expect(proof.getByRole("img", { name: /App screenshot coming/ }).first()).toBeVisible();
    });

    test("the call to action carries this page's role and src, in the hero and after the FAQ", async ({ page }) => {
      const href = `${APP}/join?role=${p.role}&src=landing-${p.slug}`;
      await expect(page.getByRole("region", { name: "Introduction" }).getByRole("link", { name: p.cta })).toHaveAttribute("href", href);
      await expect(page.getByRole("region", { name: "Next step" }).getByRole("link")).toHaveAttribute("href", href);
    });

    test("a campaign ?src= replaces the page's own src everywhere; a bad one is ignored", async ({ page }) => {
      await page.goto(`/${p.slug}/?src=campaign-9`);
      const want = `${APP}/join?role=${p.role}&src=campaign-9`;
      await expect(page.getByRole("region", { name: "Introduction" }).getByRole("link", { name: p.cta })).toHaveAttribute("href", want);
      await expect(page.getByRole("region", { name: "Next step" }).getByRole("link")).toHaveAttribute("href", want);
      await page.goto(`/${p.slug}/?src=NOT%20OK`);
      await page.waitForLoadState("networkidle");
      await expect(page.getByRole("region", { name: "Introduction" }).getByRole("link", { name: p.cta })).toHaveAttribute("href", `${APP}/join?role=${p.role}&src=landing-${p.slug}`);
    });

    test("SEO: own title and description, canonical, Open Graph image, Twitter card, in the sitemap", async ({ page, request }) => {
      const meta = (sel: string) => page.locator(sel).getAttribute("content");
      expect(await meta('meta[name="description"]')).toBe(p.description);
      await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", `${ON}/${p.slug}/`);
      expect(await meta('meta[property="og:title"]')).toBe(p.title);
      expect(await meta('meta[property="og:description"]')).toBe(p.description);
      expect(await meta('meta[property="og:url"]')).toBe(`${ON}/${p.slug}/`);
      expect(await meta('meta[property="og:image"]')).toBe(`${ON}/og.png`);
      expect(await meta('meta[name="twitter:card"]')).toBe("summary_large_image");
      expect(await meta('meta[name="twitter:image"]')).toBe(`${ON}/og.png`);
      expect(await meta('meta[name="robots"]')).not.toMatch(/noindex/);
      expect(await (await request.get("/sitemap.xml")).text()).toContain(`<loc>${ON}/${p.slug}/</loc>`);
    });
  });
}

test("each audience page has its own title and description", () => {
  expect(new Set(PAGES.map((p) => p.title)).size).toBe(PAGES.length);
  expect(new Set(PAGES.map((p) => p.description)).size).toBe(PAGES.length);
});
