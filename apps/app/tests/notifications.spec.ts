import { expect, test, type Page } from "@playwright/test";
import { checkPage, inBothThemes, isPhone } from "../e2e/helpers";
import { drag } from "./touch";

/**
 * F3 Notifications on mock mode: the bell, the screen grouped by day (IST), unread dots, deep links, mark-read, back, empty state, axe.
 * The clock is fixed at Monday 26 Oct 2026, 12:00 IST so "Today", "Yesterday" and the weekday group never depend on when this runs.
 */
test.beforeEach(async ({ page }) => { await page.clock.setFixedTime(new Date("2026-10-26T06:30:00Z")); });

const home = async (page: Page, scenario = "default") => {
  await page.goto(`/?scenario=${scenario}`);
  await expect(page.getByRole("heading", { name: "Today", level: 1 })).toBeVisible();
};
const bell = (page: Page) => page.getByRole("link", { name: /^Notifications/ }).filter({ visible: true });
const screen = (page: Page) => page.getByRole("heading", { name: "Notifications", level: 1 });
const unreadDots = (page: Page) => page.getByRole("img", { name: "Unread" });
const openFromBell = async (page: Page) => { await bell(page).click(); await expect(screen(page)).toBeVisible(); };

test.describe("Notifications", () => {
  test("the bell says how many are unread and opens the screen", async ({ page }) => {
    await home(page);
    await expect(bell(page)).toHaveAccessibleName("Notifications, 2 unread");
    await openFromBell(page);
    await expect(page).toHaveURL(/\/notifications$/);
  });

  test("grouped by day with times in IST and an unread dot on the two new ones", async ({ page }) => {
    await page.goto("/notifications?scenario=default");
    await expect(screen(page)).toBeVisible();
    const headings = page.getByRole("heading", { level: 2 });
    await expect(headings).toHaveText(["Today", "Yesterday", "Friday"]);
    await expect(page.getByRole("link", { name: /accepted your introduction/ })).toContainText("11:52 am");
    await expect(page.getByRole("region", { name: "Today" }).getByRole("listitem")).toHaveCount(3);
    await expect(page.getByRole("region", { name: "Yesterday" }).getByRole("listitem")).toHaveCount(2);
    await expect(unreadDots(page)).toHaveCount(2);
  });

  test("every kind opens where the link map says (never a 404)", async ({ page }) => {
    await page.goto("/notifications?scenario=default");
    await expect(screen(page)).toBeVisible();
    const href = (name: RegExp) => page.getByRole("link", { name }).getAttribute("href");
    expect(await href(/accepted your introduction/)).toBe("/inbox");
    expect(await href(/application has a new status/)).toBe("/discover/applications");
    expect(await href(/new circuit is waiting/)).toBe("/inbox");
    expect(await href(/replied to your build log/)).toBe("/");
    expect(await href(/sent you a message/)).toBe("/inbox");
    expect(await href(/showed interest in your startup/)).toBe("/startups/41");
  });

  test("tapping an unread one marks it read, opens it, and the bell drops by one", async ({ page }, info) => {
    await page.goto("/notifications?scenario=default");
    await expect(unreadDots(page)).toHaveCount(2);
    await page.getByRole("link", { name: /accepted your introduction/ }).click();
    await expect(page).toHaveURL(/\/inbox$/);
    if (isPhone(info)) await page.getByRole("link", { name: "Home" }).filter({ visible: true }).first().click();
    else await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Home" }).click();
    await expect(page.getByRole("heading", { name: "Today", level: 1 })).toBeVisible();
    await expect(bell(page)).toHaveAccessibleName("Notifications, 1 unread");
    await openFromBell(page);
    await expect(unreadDots(page)).toHaveCount(1);
  });

  test("Back returns to Home", async ({ page }) => {
    await home(page);
    await openFromBell(page);
    await page.getByRole("button", { name: "Back to Today" }).click();
    await expect(page.getByRole("heading", { name: "Today", level: 1 })).toBeVisible();
    await expect(page).toHaveURL(/localhost:\d+\/(\?.*)?$/);
  });

  test.describe("by touch", () => {
    test.use({ reducedMotion: "no-preference", hasTouch: true });
    test("a swipe from the left edge goes back", async ({ page }, info) => {
      test.skip(!isPhone(info), "edge swipe is a phone gesture");
      await home(page);
      await openFromBell(page);
      await page.waitForTimeout(600);
      await drag(page, { x: 6, y: 400 }, { x: 300, y: 405 });
      await expect(page.getByRole("heading", { name: "Today", level: 1 })).toBeVisible();
    });
  });

  test("nothing yet: one sentence, no dots", async ({ page }) => {
    await page.goto("/notifications?scenario=empty");
    await expect(screen(page)).toBeVisible();
    await expect(page.getByText("Nothing new.")).toBeVisible();
    await expect(unreadDots(page)).toHaveCount(0);
  });

  test("axe is clean in both themes at both widths, with no sideways overflow", async ({ page }) => {
    await page.goto("/notifications?scenario=default");
    await expect(screen(page)).toBeVisible();
    await page.waitForTimeout(500);
    await inBothThemes(page, async (theme) => { await checkPage(page, `notifications ${theme}`); });
  });
});
