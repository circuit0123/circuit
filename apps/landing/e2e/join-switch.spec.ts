import { expect, test, type Page } from "@playwright/test";
import { PAGES } from "../src/content/pages";
import { APP, checkPage, digitsIn, mockWaitlist, OFF, ON, PATHS, THEMES, WAIT } from "./support";

/**
 * NEXT_PUBLIC_JOIN_LIVE. Off (the default; the app has no /join yet): every call to action keeps its label and opens the waitlist form on the
 * same page, with the role from that button, and nothing links to APP_URL/join. On: call to action buttons link to APP_URL/join?role=…&src=….
 * The test builds: :3101 and :3102 have it on, :3103 has it off.
 */

const TILES = [
  { id: "students", role: "student" },
  { id: "founders", role: "founder" },
  { id: "mentors", role: "mentor" },
  { id: "investors", role: "investor" },
  { id: "partners", role: "partner" },
];
const heroLink = (page: Page, name: string) => page.getByRole("region", { name: "Introduction" }).getByRole("link", { name });
const submit = (page: Page) => page.getByRole("button", { name: "Join the waitlist" });

/** Every link on the page leads somewhere that exists: pages answer 200, #targets are on the page, and the app is only linked when the switch is on. */
async function checkNoDeadLinks(page: Page, base: string, path: string, live: boolean) {
  await page.goto(base + path);
  const hrefs = await page.$$eval("a[href]", (as) => [...new Set(as.map((a) => a.getAttribute("href") ?? ""))]);
  const appLinks = hrefs.filter((h) => h.startsWith(APP));
  if (live) for (const h of appLinks) expect(h, `${path}: ${h}`).toMatch(/^http:\/\/app\.test\/join\?(role=[a-z]+&)?src=[a-z0-9_-]+$/);
  else expect(appLinks, `${path}: no link to the app while the join screen doesn't exist`).toEqual([]);
  for (const h of hrefs) {
    if (h.startsWith("mailto:") || h.startsWith(APP)) continue;
    if (h.startsWith("#")) {
      expect(await page.locator(`[id="${h.slice(1)}"]`).count(), `${path}: ${h} has no target`).toBeGreaterThan(0);
    } else {
      expect((await page.request.get(new URL(h, base + path).toString())).status(), `${path}: ${h}`).toBe(200);
    }
  }
  return appLinks;
}

test.describe("no call to action leads to a 404, in either mode", () => {
  for (const path of PATHS) {
    test(`switch on, flags on: ${path}`, async ({ page }) => { await checkNoDeadLinks(page, ON, path, true); });
    test(`switch on, flags off: ${path}`, async ({ page }) => { await checkNoDeadLinks(page, OFF, path, true); });
    test(`switch off: ${path}`, async ({ page }) => { await checkNoDeadLinks(page, WAIT, path, false); });
  }
  test("switch on: the home page and every audience page really do link into the app", async ({ page }) => {
    expect((await checkNoDeadLinks(page, ON, "/", true)).length).toBeGreaterThanOrEqual(6);
    // the hero button and the closing link share one address, so a page has at least one distinct app link
    for (const p of PAGES) expect((await checkNoDeadLinks(page, ON, `/${p.slug}/`, true)).length, p.slug).toBeGreaterThanOrEqual(1);
  });
});

test.describe("switch off: the home page", () => {
  test.use({ baseURL: WAIT });

  test("'Join the beta' keeps its label, scrolls to the form and puts the cursor in it", async ({ page }) => {
    await page.goto("/");
    const hero = heroLink(page, "Join the beta");
    await expect(hero).toHaveAttribute("href", "#waitlist");
    await hero.click();
    await expect(page.getByRole("heading", { name: "Circuit is invite-only right now" })).toBeInViewport();
    await expect(page.getByText("Join the waitlist and we’ll send you an invite.")).toBeVisible();
    await expect(page.getByLabel("Email")).toBeFocused();
    await expect(page.getByLabel("I am a")).toHaveValue("");
  });

  for (const t of TILES) {
    test(`the ${t.id} tile opens the form with ${t.role} preselected and sends role and src`, async ({ page }) => {
      await page.goto("/");
      const bodies = await mockWaitlist(page, () => ({ status: 202 }));
      await page.locator(`a#${t.id}`).click();
      await expect(page.getByLabel("I am a")).toHaveValue(t.role);
      await expect(page.getByLabel("Email")).toBeFocused();
      await page.getByLabel("Email").fill("asha@example.com");
      await submit(page).click();
      await expect(page.getByRole("status")).toContainText("You’re on the list");
      expect(bodies).toEqual([{ email: "asha@example.com", role: t.role, city: "", src: "landing-home" }]);
    });
  }

  test("the preselected role can be changed before sending", async ({ page }) => {
    await page.goto("/");
    const bodies = await mockWaitlist(page, () => ({ status: 202 }));
    await page.locator("a#students").click();
    await page.getByLabel("I am a").selectOption("mentor");
    await page.getByLabel("Email").fill("asha@example.com");
    await submit(page).click();
    await expect(page.getByRole("status")).toBeVisible();
    expect(bodies[0]).toMatchObject({ role: "mentor", src: "landing-home" });
  });

  test("a campaign ?src= is what gets recorded", async ({ page }) => {
    await page.goto("/?src=campus-poster");
    const bodies = await mockWaitlist(page, () => ({ status: 202 }));
    await page.locator("a#founders").click();
    await page.getByLabel("Email").fill("asha@example.com");
    await submit(page).click();
    await expect(page.getByRole("status")).toBeVisible();
    expect(bodies[0]).toMatchObject({ role: "founder", src: "campus-poster" });
  });
});

test.describe("switch off: the audience pages", () => {
  test.use({ baseURL: WAIT });

  for (const p of PAGES) {
    const partner = p.slug === "partners";
    const target = partner ? "#partner-form" : "#waitlist";

    test(`/${p.slug}/: "${p.cta}" keeps its label and opens the form`, async ({ page }) => {
      await page.goto(`/${p.slug}/`);
      const bodies = await mockWaitlist(page, () => ({ status: 202 }));
      const hero = heroLink(page, p.cta);
      await expect(hero).toHaveAttribute("href", target);
      await expect(page.getByRole("region", { name: "Next step" }).getByRole("link")).toHaveAttribute("href", target);
      await hero.click();
      if (partner) {
        await expect(page.getByRole("heading", { name: "Bring Circuit to your campus" })).toBeInViewport();
        await expect(page.getByText("Circuit is invite-only right now.")).toBeVisible();
        await expect(page.getByLabel("Your name")).toBeFocused();
        await page.getByLabel("Your name").fill("Kavya Rao");
        await page.getByLabel("Organisation", { exact: true }).fill("Example Institute of Technology");
        await page.getByLabel("City").fill("Pune");
        await page.getByLabel("Email").fill("kavya@example.com");
        await page.getByRole("button", { name: "Send to Circuit" }).click();
        await expect(page.getByRole("status")).toContainText("Thanks");
        expect(bodies).toEqual([{ email: "kavya@example.com", role: "partner", city: "Pune", college: "Example Institute of Technology", note: "Name: Kavya Rao", src: "landing-partners" }]);
      } else {
        await expect(page.getByRole("heading", { name: "Circuit is invite-only right now" })).toBeInViewport();
        await expect(page.getByText("Join the waitlist and we’ll send you an invite.")).toBeVisible();
        await expect(page.getByLabel("I am a")).toHaveCount(0);
        await expect(page.getByLabel("Email")).toBeFocused();
      }
    });
  }

  for (const p of PAGES.filter((x) => x.slug !== "partners")) {
    test(`/${p.slug}/: the form sends the page's role and src, or a carried ?src=`, async ({ page }) => {
      for (const src of [`landing-${p.slug}`, "campaign-3"]) {
        await page.goto(src === "campaign-3" ? `/${p.slug}/?src=${src}` : `/${p.slug}/`);
        const bodies = await mockWaitlist(page, () => ({ status: 202 }));
        await page.getByLabel("Email").fill("asha@example.com");
        await page.getByLabel("City").fill("Pune");
        await submit(page).click();
        await expect(page.getByRole("status")).toContainText("You’re on the list");
        expect(bodies, p.slug).toEqual([{ email: "asha@example.com", role: p.role, city: "Pune", src }]);
      }
    });
  }

  test("/investors/ with the investor flag on: a normal waitlist section, not the 'opens soon' fallback", async ({ page }) => {
    await page.goto("/investors/");
    await expect(page.getByText("Investor access opens soon.")).toHaveCount(0);
    await expect(page.locator("#waitlist")).toHaveCount(1);
  });

  test("errors on the form: 429 and 500 show one sentence and keep what was typed", async ({ page }) => {
    for (const c of [{ status: 429, text: "Try again in an hour", calls: 1 }, { status: 500, text: "Couldn’t reach Circuit", calls: 2 }]) {
      await page.goto("/students/");
      await page.unroute("**/api/waitlist");
      const bodies = await mockWaitlist(page, () => ({ status: c.status }));
      await page.getByLabel("Email").fill("asha@example.com");
      await submit(page).click();
      await expect(page.locator("#waitlist-msg")).toContainText(c.text);
      expect(bodies).toHaveLength(c.calls);
      await expect(page.getByLabel("Email")).toHaveValue("asha@example.com");
    }
  });

  test("without JavaScript the buttons still point at the form", async ({ browser }) => {
    const ctx = await browser.newContext({ javaScriptEnabled: false, baseURL: WAIT });
    const page = await ctx.newPage();
    await page.goto("/");
    await expect(heroLink(page, "Join the beta")).toHaveAttribute("href", "#waitlist");
    await expect(page.locator("a#students")).toHaveAttribute("href", "#waitlist");
    await page.goto("/students/");
    await expect(heroLink(page, "Find work near you")).toHaveAttribute("href", "#waitlist");
    await ctx.close();
  });

  test("every page: no placeholder text, no fake numbers, nothing requested from another origin", async ({ page }) => {
    for (const path of PATHS) {
      const origins = new Set<string>();
      const onRequest = (r: import("@playwright/test").Request) => origins.add(new URL(r.url()).origin);
      page.on("request", onRequest);
      await page.goto(path, { waitUntil: "networkidle" });
      page.off("request", onRequest);
      expect([...origins], path).toEqual([WAIT]);
      const text = await page.locator("body").innerText();
      expect(text, path).not.toMatch(/\[[^\]]+\]/);
      expect(digitsIn(text), `${path}: digits`).toBeNull();
    }
  });

  for (const theme of THEMES) {
    test(`axe clean and no horizontal scroll on every page (${theme})`, async ({ page }, info) => {
      await page.emulateMedia({ colorScheme: theme, reducedMotion: "reduce" });
      for (const path of PATHS) {
        await page.goto(path);
        await checkPage(page, `${path} join switch off ${info.project.name} ${theme}`);
      }
    });
  }
});
