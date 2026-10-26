import { expect, test } from "@playwright/test";
import { PAGES } from "../src/content/pages";
import { checkPage, FORM, PRELAUNCH, THEMES } from "./support";

/** NEXT_PUBLIC_LAUNCH_MODE=waitlist (build on :3104, with JOIN_LIVE on to prove it is overridden): the external form, no app, no on-page form. */
test.use({ baseURL: PRELAUNCH });

const url = (src: string, role?: string) => `${FORM}?ref=x${role ? `&role=${role}` : ""}&src=${src}`;
const TILES = [
  { id: "students", role: "student" },
  { id: "founders", role: "founder" },
  { id: "mentors", role: "mentor" },
  { id: "investors", role: "investor" },
  { id: "partners", role: "partner" },
];

test("home: hero and tiles open the form with src (and role)", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("region", { name: "Introduction" }).getByRole("link", { name: "Join the beta" })).toHaveAttribute("href", url("landing-home"));
  for (const t of TILES) await expect(page.locator(`a#${t.id}`)).toHaveAttribute("href", url("landing-home", t.role));
  await expect(page.locator("#waitlist").getByRole("link", { name: "Join the waitlist" })).toHaveAttribute("href", url("landing-home"));
});

for (const p of PAGES) {
  test(`/${p.slug}/: every call to action opens the form with role=${p.role}`, async ({ page }) => {
    await page.goto(`/${p.slug}/`);
    const links = page.getByRole("link", { name: new RegExp(p.cta.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")) });
    expect(await links.count()).toBeGreaterThan(0);
    for (const l of await links.all()) await expect(l).toHaveAttribute("href", url(`landing-${p.slug}`, p.role));
  });
}

test("a campaign ?src= is passed on, an invalid one is ignored", async ({ page }) => {
  await page.goto("/students/?src=campaign-1");
  await expect(page.getByRole("link", { name: "Join the waitlist" }).first()).toHaveAttribute("href", url("campaign-1", "student"));
  await page.goto("/students/?src=Bad%20Value!");
  await page.waitForLoadState("networkidle");
  await expect(page.getByRole("link", { name: "Join the waitlist" }).first()).toHaveAttribute("href", url("landing-students", "student"));
});

for (const path of ["/", ...PAGES.map((p) => `/${p.slug}/`)]) {
  test(`${path}: no form, no app link, no sign-in link; accessible`, async ({ page }) => {
    const requests: string[] = [];
    page.on("request", (r) => requests.push(r.url()));
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    await expect(page.locator("form, input[type=email]")).toHaveCount(0);
    expect(await page.getByRole("link", { name: /sign in|log in/i }).count() + (await page.getByRole("button", { name: /sign in|log in/i }).count())).toBe(0);
    const hrefs = await page.locator("a[href]").evaluateAll((as) => as.map((a) => (a as HTMLAnchorElement).href));
    expect(hrefs.filter((h) => h.includes("app.test") || h.includes("/join"))).toEqual([]);
    expect(requests.filter((u) => !u.startsWith(PRELAUNCH) && !u.startsWith("data:"))).toEqual([]);
    for (const theme of THEMES) {
      await page.emulateMedia({ colorScheme: theme });
      await checkPage(page, `${path} ${theme}`);
    }
  });
}
