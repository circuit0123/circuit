import { expect, test } from "@playwright/test";
import { APP, checkPage, fillWaitlist, mockWaitlist, OFF, THEMES } from "./support";

const submit = (page: import("@playwright/test").Page) => page.getByRole("button", { name: "Join the waitlist" });

test("flags on: the investor tile on the home page goes straight into the app", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("a#investors")).toHaveAttribute("href", `${APP}/join?role=investor&src=landing-home`);
});

test("flags on: /investors/ has the app button and no waitlist form", async ({ page }) => {
  await page.goto("/investors/");
  await expect(page.getByRole("region", { name: "Introduction" }).getByRole("link", { name: "Set your focus" })).toHaveAttribute("href", `${APP}/join?role=investor&src=landing-investors`);
  await expect(page.locator("#waitlist")).toHaveCount(0);
  await expect(page.getByText("Investor access opens soon.")).toHaveCount(0);
});

test("flags on: /partners/ has the app button and no contact form", async ({ page }) => {
  await page.goto("/partners/");
  await expect(page.getByRole("region", { name: "Introduction" }).getByRole("link", { name: "Bring Circuit to your campus" })).toHaveAttribute("href", `${APP}/join?role=partner&src=landing-partners`);
  await expect(page.locator("#partner-form")).toHaveCount(0);
});

test.describe("flags off (build with every feature off)", () => {
  test.use({ baseURL: OFF });

  test("the investor tile opens /investors/ instead of the app", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("a#investors")).toHaveAttribute("href", "/investors/");
    await expect(page.locator("a#students")).toHaveAttribute("href", `${APP}/join?role=student&src=landing-home`);
  });

  test.describe("/investors/: the waitlist replaces the app button", () => {
    test.beforeEach(async ({ page }) => { await page.goto("/investors/"); });

    test("says access opens soon, has a form without a role choice, and links nowhere into the app", async ({ page }) => {
      await expect(page.getByRole("heading", { level: 1 })).toHaveText("Three startups a day that fit your thesis. No noise.");
      await expect(page.getByText("Investor access opens soon.")).toBeVisible();
      await expect(page.getByLabel("Email")).toBeVisible();
      await expect(page.getByLabel("I am a")).toHaveCount(0);
      await expect(page.locator(`main a[href^="${APP}"]`)).toHaveCount(0);
      await expect(page.getByRole("region", { name: "Next step" }).getByRole("link")).toHaveAttribute("href", "#waitlist");
    });

    test("success: sends role=investor and src=landing-investors", async ({ page }) => {
      const bodies = await mockWaitlist(page, () => ({ status: 202 }));
      await page.getByLabel("Email").fill("meera@example.com");
      await page.getByLabel("City").fill("Mumbai");
      await submit(page).click();
      await expect(page.getByRole("status")).toContainText("You’re on the list");
      expect(bodies).toEqual([{ email: "meera@example.com", role: "investor", city: "Mumbai", src: "landing-investors" }]);
    });

    test("a campaign ?src= is sent instead", async ({ page }) => {
      await page.goto("/investors/?src=fund-event");
      const bodies = await mockWaitlist(page, () => ({ status: 202 }));
      await page.getByLabel("Email").fill("meera@example.com");
      await submit(page).click();
      await expect(page.getByRole("status")).toBeVisible();
      expect(bodies[0]?.src).toBe("fund-event");
    });

    test("duplicate: the same message, never 'already'", async ({ page }) => {
      await mockWaitlist(page, () => ({ status: 202 }));
      const messages: string[] = [];
      for (let i = 0; i < 2; i++) {
        await page.goto("/investors/");
        await page.getByLabel("Email").fill("meera@example.com");
        await submit(page).click();
        messages.push((await page.getByRole("status").textContent()) ?? "");
      }
      expect(messages[0]).toBe(messages[1]);
      expect(messages.join(" ")).not.toMatch(/already|exists|registered/i);
    });

    test("errors: 422, 429 and 500 each show one sentence and keep what was typed", async ({ page }) => {
      const cases = [
        { status: 422, text: "Check your email address", calls: 1 },
        { status: 429, text: "Try again in an hour", calls: 1 },
        { status: 500, text: "Couldn’t reach Circuit", calls: 2 },
      ];
      for (const c of cases) {
        await page.goto("/investors/");
        await page.unroute("**/api/waitlist");
        const bodies = await mockWaitlist(page, () => ({ status: c.status }));
        await page.getByLabel("Email").fill("meera@example.com");
        await submit(page).click();
        await expect(page.locator("#waitlist-msg")).toContainText(c.text);
        expect(bodies, String(c.status)).toHaveLength(c.calls);
        await expect(page.getByLabel("Email")).toHaveValue("meera@example.com");
      }
    });

    for (const theme of THEMES) {
      test(`axe clean, no horizontal scroll (${theme})`, async ({ page }, info) => {
        await page.emulateMedia({ colorScheme: theme, reducedMotion: "reduce" });
        await checkPage(page, `/investors/ flag off ${info.project.name} ${theme}`);
      });
    }
  });

  test.describe("/partners/: the same button opens a short contact form", () => {
    const ask = (page: import("@playwright/test").Page) => page.getByRole("button", { name: "Send to Circuit" });
    const fill = async (page: import("@playwright/test").Page, note = "") => {
      await page.getByLabel("Your name").fill("Kavya Rao");
      await page.getByLabel("Organisation", { exact: true }).fill("Example Institute of Technology");
      await page.getByLabel("City").fill("Pune");
      await page.getByLabel("Email").fill("kavya@example.com");
      if (note) await page.getByLabel("Note (optional)").fill(note);
    };
    test.beforeEach(async ({ page }) => { await page.goto("/partners/"); });

    test("the hero button keeps its text but jumps to the form; nothing links into the app", async ({ page }) => {
      const hero = page.getByRole("region", { name: "Introduction" }).getByRole("link", { name: "Bring Circuit to your campus" });
      await expect(hero).toHaveAttribute("href", "#partner-form");
      await expect(page.locator(`main a[href^="${APP}"]`)).toHaveCount(0);
      await expect(page.getByRole("region", { name: "Next step" }).getByRole("link")).toHaveAttribute("href", "#partner-form");
      await hero.click();
      await expect(page.getByRole("heading", { name: "Bring Circuit to your campus" })).toBeInViewport();
    });

    test("success: role=partner, organisation in college, name first in note, src=landing-partners", async ({ page }) => {
      const bodies = await mockWaitlist(page, () => ({ status: 202 }));
      await fill(page, "We run an incubator.");
      await ask(page).click();
      await expect(page.getByRole("status")).toContainText("Thanks");
      expect(bodies).toEqual([{ email: "kavya@example.com", role: "partner", city: "Pune", college: "Example Institute of Technology", note: "Name: Kavya Rao\nWe run an incubator.", src: "landing-partners" }]);
    });

    test("without a note the name alone is sent; a campaign ?src= replaces the src", async ({ page }) => {
      await page.goto("/partners/?src=college-fair");
      const bodies = await mockWaitlist(page, () => ({ status: 202 }));
      await fill(page);
      await ask(page).click();
      await expect(page.getByRole("status")).toBeVisible();
      expect(bodies[0]).toMatchObject({ note: "Name: Kavya Rao", src: "college-fair" });
    });

    test("duplicate: the same message, never 'already'", async ({ page }) => {
      await mockWaitlist(page, () => ({ status: 202 }));
      const messages: string[] = [];
      for (let i = 0; i < 2; i++) {
        await page.goto("/partners/");
        await fill(page);
        await ask(page).click();
        messages.push((await page.getByRole("status").textContent()) ?? "");
      }
      expect(messages[0]).toBe(messages[1]);
      expect(messages.join(" ")).not.toMatch(/already|exists|registered/i);
    });

    test("errors: 422, 429 and 500 each show one sentence and keep what was typed", async ({ page }) => {
      const cases = [
        { status: 422, text: "Check your email address", calls: 1 },
        { status: 429, text: "Try again in an hour", calls: 1 },
        { status: 500, text: "Couldn\u2019t reach Circuit", calls: 2 },
      ];
      for (const c of cases) {
        await page.goto("/partners/");
        await page.unroute("**/api/waitlist");
        const bodies = await mockWaitlist(page, () => ({ status: c.status }));
        await fill(page);
        await ask(page).click();
        await expect(page.locator("#partner-msg")).toContainText(c.text);
        expect(bodies, String(c.status)).toHaveLength(c.calls);
        await expect(page.getByLabel("Organisation", { exact: true })).toHaveValue("Example Institute of Technology");
      }
    });

    test("only the public waitlist endpoint is called", async ({ page }) => {
      const urls: string[] = [];
      page.on("request", (r) => { if (!r.url().startsWith(OFF)) urls.push(r.url()); });
      await mockWaitlist(page, () => ({ status: 202 }));
      await fill(page);
      await ask(page).click();
      await expect(page.getByRole("status")).toBeVisible();
      expect(urls.every((u) => u.endsWith("/api/waitlist"))).toBe(true);
    });

    for (const theme of THEMES) {
      test(`axe clean, no horizontal scroll (${theme})`, async ({ page }, info) => {
        await page.emulateMedia({ colorScheme: theme, reducedMotion: "reduce" });
        await checkPage(page, `/partners/ flag off ${info.project.name} ${theme}`);
      });
    }
  });
});
