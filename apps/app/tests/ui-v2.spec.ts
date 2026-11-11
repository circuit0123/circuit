import { expect, test, type Page } from "@playwright/test";
import { checkPage as axeCheck } from "../e2e/helpers";

/**
 * ui_v2 (docs/ui-v2-plan.md §6) on mock mode with NEXT_PUBLIC_UI_V2=on: each rebuilt screen renders at 390px and 1440px, with axe.
 * Runs on playwright.v2.config.ts. The flag-off run (playwright.mock.config.ts) ignores this file and is the proof the old UI is unchanged.
 */
const checkPage = (page: Page, label: string) => axeCheck(page, label, { exclude: ["nav.material", "header.material", "div.material"] });

const open = async (page: Page, path: string) => {
  await page.goto(path.includes("?") ? path : `${path}?scenario=default`);
  await expect(page.locator("html")).toHaveAttribute("data-ui", "v2");
};
const phoneOnly = (info: { project: { name: string } }) => info.project.name === "phone";

test.describe("ui_v2", () => {
  test("Today: header, big headline, v2 bar on the phone", async ({ page }, info) => {
    await open(page, "/");
    await expect(page.getByRole("heading", { name: /Today/, level: 1 })).toBeVisible();
    await expect(page.getByRole("link", { name: "Settings" })).toBeVisible();
    await expect(page.getByRole("img", { name: "Circuit" }).first()).toBeVisible();
    if (phoneOnly(info)) {
      const bar = page.getByRole("navigation", { name: "Main" });
      await expect(bar).toBeVisible();
      await expect(bar.getByRole("button", { name: "New build log" })).toBeVisible();
      await expect(bar.getByRole("link", { name: /^Home/ })).toHaveAttribute("aria-current", "page");
    }
    await checkPage(page, "today");
  });

  test("the page stays dark whatever the system theme says", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "light" });
    await open(page, "/");
    expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor)).toBe("rgb(10, 10, 12)");
  });

  test("Composer: Post stays off until there is text", async ({ page }) => {
    await open(page, "/compose");
    await expect(page.getByRole("heading", { name: /Ship/, level: 1 })).toBeVisible();
    await expect(page.getByRole("button", { name: "Post" })).toBeDisabled();
    await page.getByRole("textbox", { name: /What did you build/i }).fill("Shipped a thing.");
    await expect(page.getByRole("button", { name: "Post" })).toBeEnabled();
    await checkPage(page, "composer");
  });

  test("Profile: own and someone else's", async ({ page }) => {
    await open(page, "/profile");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await checkPage(page, "profile");
    await open(page, "/members/2");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByRole("button", { name: /Connect|Request sent|Connected|Answer request/ })).toBeVisible();
    await checkPage(page, "person");
  });

  test("Inbox: Chats and Requests tabs, then a conversation", async ({ page }) => {
    await open(page, "/inbox");
    await expect(page.getByRole("heading", { name: "Inbox", level: 1 })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Chats" })).toHaveAttribute("aria-selected", "true");
    await page.getByRole("tab", { name: "Requests" }).click();
    await expect(page.getByRole("tab", { name: "Requests" })).toHaveAttribute("aria-selected", "true");
    await checkPage(page, "inbox");
    await open(page, "/inbox/501");
    await expect(page.getByRole("log", { name: "Messages" })).toBeVisible();
    await page.getByRole("textbox", { name: "Message" }).fill("Hello from v2");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await expect(page.locator("[data-bubble]", { hasText: "Hello from v2" })).toBeVisible();
    await checkPage(page, "chat");
  });

  test("Directory: Startups and Jobs tabs", async ({ page }) => {
    await open(page, "/discover?s=startups&scenario=default");
    await expect(page.getByRole("heading", { name: /Startups/, level: 1 })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Startups" })).toHaveAttribute("aria-selected", "true");
    await checkPage(page, "startups");
    await page.getByRole("tab", { name: "Jobs" }).click();
    await expect(page.getByRole("heading", { name: /Jobs/, level: 1 })).toBeVisible();
    await checkPage(page, "jobs");
  });

  test("Map: header and filters render", async ({ page }) => {
    await open(page, "/discover?s=map&scenario=default");
    await expect(page.getByRole("heading", { name: /Nearby/, level: 1 })).toBeVisible();
    await expect(page.getByRole("group", { name: "Map filters" }).getByRole("button", { name: "Hiring" })).toBeVisible();
  });

  test("No sample content is on screen", async ({ page }) => {
    await open(page, "/");
    const text = await page.locator("body").innerText();
    for (const bad of ["Tatvagrid", "[COMPANY", "No cold messages"]) expect(text).not.toContain(bad);
  });
});
