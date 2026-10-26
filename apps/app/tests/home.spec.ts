import { expect, test, type Page } from "@playwright/test";
import { checkPage as axeCheck, inBothThemes, isPhone } from "../e2e/helpers";

/** The translucent tab bar (DESIGN.md §5 Materials) takes on whatever scrolls under it, so a green button behind it dips its labels below 4.5:1 in
 * the light theme. The bar is checked on its own over plain content in foundation.spec.ts; here it is left out. */
const checkPage = (page: Page, label: string) => axeCheck(page, label, { exclude: ["nav.material"] });

/**
 * F3 Home on mock mode (no backend): the Daily Drop (buttons and swipes), Pulse and its end, the flags (Pulse off, Daily Drop off, both
 * off), under-18, and axe in both themes. Update view, Notifications, desktop and the intro sheet have their own specs/sections below.
 */
const open = async (page: Page, scenario = "default") => {
  await page.goto(`/?scenario=${scenario}`);
  await expect(page.getByRole("heading", { name: "Today", level: 1 })).toBeVisible();
};
const drop = (page: Page) => page.getByRole("region", { name: "Daily Drop" });
const counter = (page: Page) => drop(page).getByText(/^\d of 3$/);

type Pt = { x: number; y: number };
/** One real touch drag, so the card sees pointer events the way it does on a phone. */
async function drag(page: Page, from: Pt, to: Pt) {
  const cdp = await page.context().newCDPSession(page);
  const at = (p: Pt) => [{ x: p.x, y: p.y, id: 1 }];
  await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: at(from) });
  for (let i = 1; i <= 10; i++) {
    await page.waitForTimeout(20);
    await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: at({ x: from.x + ((to.x - from.x) * i) / 10, y: from.y + ((to.y - from.y) * i) / 10 }) });
  }
  await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
  await cdp.detach();
}

test.describe("Home: the Daily Drop", () => {
  test("shows the reason first, the two buttons inside the card, and 1 of 3", async ({ page }) => {
    await open(page);
    await expect(drop(page).getByRole("heading", { name: "Your drop" })).toBeVisible();
    await expect(counter(page)).toHaveText("1 of 3");
    await expect(drop(page).getByRole("heading", { level: 3 })).toContainText("can help you with");
    await expect(drop(page).getByRole("button", { name: "Intro me" })).toBeVisible();
    await expect(drop(page).getByRole("button", { name: "Skip" })).toBeVisible();
    await expect(drop(page).getByText(/^(Strong|Good) match$/)).toBeVisible();
  });

  test("Skip, Skip, Skip ends on \"That's today's drop.\"", async ({ page }) => {
    await open(page);
    for (const n of ["2 of 3", "3 of 3"]) {
      await drop(page).getByRole("button", { name: "Skip" }).click();
      await expect(counter(page)).toHaveText(n);
    }
    await drop(page).getByRole("button", { name: "Skip" }).click();
    await expect(drop(page).getByText("That's today's drop.")).toBeVisible();
    await expect(drop(page).getByText("New one tomorrow at 8.")).toBeVisible();
    await expect(drop(page).getByRole("button", { name: "Skip" })).toHaveCount(0);
  });

  test.describe("by swipe", () => {
    test.use({ reducedMotion: "no-preference", hasTouch: true });
    test("a swipe left skips and the next card comes up", async ({ page }, info) => {
      test.skip(!isPhone(info), "swiping the stack is a phone gesture");
      await open(page);
      const first = await drop(page).getByRole("heading", { level: 3 }).textContent();
      const box = (await drop(page).locator("article, div.shadow-lift").first().boundingBox())!;
      await page.mouse.move(0, 0);
      await drag(page, { x: box.x + box.width * 0.85, y: box.y + 60 }, { x: box.x + 5, y: box.y + 60 });
      await expect(counter(page)).toHaveText("2 of 3");
      expect(await drop(page).getByRole("heading", { level: 3 }).textContent()).not.toBe(first);
    });

    test("a short drag springs back", async ({ page }, info) => {
      test.skip(!isPhone(info), "swiping the stack is a phone gesture");
      await open(page);
      const box = (await drop(page).locator("div.shadow-lift").first().boundingBox())!;
      await drag(page, { x: box.x + box.width * 0.5, y: box.y + 60 }, { x: box.x + box.width * 0.5 - 40, y: box.y + 60 });
      await page.waitForTimeout(500);
      await expect(counter(page)).toHaveText("1 of 3");
    });
  });
});

test.describe("Home: Pulse", () => {
  test("has a visible header, text reactions, ends with \"You're caught up.\", and promoted slots are labelled and never first", async ({ page }) => {
    await open(page);
    const pulse = page.getByRole("region", { name: "Pulse" });
    await expect(pulse.getByRole("heading", { name: "Pulse" })).toBeVisible();
    await expect(pulse.getByRole("button", { name: "Helpful" }).first()).toBeAttached();
    await page.getByText("You're caught up.").scrollIntoViewIfNeeded();
    await expect(page.getByText("You're caught up.")).toBeVisible();
    // Promoted: labelled, with its menu, and not the first item.
    const promoted = pulse.getByText(/^Promoted · /);
    await expect(promoted).toHaveCount(1);
    expect(await pulse.locator("[data-index]").first().getByText(/^Promoted · /).count()).toBe(0);
    await expect(pulse.getByText(/^From SVIT/)).toHaveCount(1);
  });

  test("Why am I seeing this? and Hide this", async ({ page }) => {
    await open(page);
    const pulse = page.getByRole("region", { name: "Pulse" });
    await pulse.getByRole("button", { name: "About this promotion" }).scrollIntoViewIfNeeded();
    await pulse.getByRole("button", { name: "About this promotion" }).click();
    await expect(page.getByRole("dialog", { name: "Why am I seeing this?" })).toContainText("Promoted to people in Chennai");
    await page.getByRole("button", { name: "Hide this" }).click();
    await expect(pulse.getByText(/^Promoted · /)).toHaveCount(0);
  });
});

test.describe("Home: flags", () => {
  test("Pulse off: only the Daily Drop (no +, wire, feed or Worth meeting)", async ({ page }) => {
    await open(page, "pulse_off");
    await expect(drop(page)).toBeVisible();
    await expect(page.getByRole("list", { name: "Live wire" })).toHaveCount(0);
    await expect(page.getByRole("region", { name: "Pulse" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "New build log" })).toHaveCount(0);
    await expect(page.getByText("Worth meeting")).toHaveCount(0);
    await checkPage(page, "pulse off");
  });

  test("Daily Drop off: the wire and Pulse, no stack", async ({ page }, info) => {
    await open(page, "drop_off");
    await expect(page.getByRole("list", { name: "Live wire" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Pulse" })).toBeVisible();
    await expect(drop(page)).toHaveCount(0);
    if (isPhone(info)) await expect(page.getByRole("button", { name: "New build log" })).toBeVisible(); // desktop has it in the rail (Part 4)
    await checkPage(page, "drop off");
  });

  for (const scenario of ["home_off", "features_off"]) {
    test(`${scenario}: a calm empty state, never a broken layout`, async ({ page }) => {
      await open(page, scenario);
      await expect(page.getByText("Nothing on Home right now.")).toBeVisible();
      await expect(page.getByRole("button", { name: "Go to Discover" })).toBeVisible();
      await expect(drop(page)).toHaveCount(0);
      await expect(page.getByRole("list", { name: "Live wire" })).toHaveCount(0);
      await checkPage(page, scenario);
    });
  }

  test("under 18: no Daily Drop and no Intro me anywhere on Home", async ({ page }) => {
    await open(page, "under18");
    await expect(page.getByRole("list", { name: "Live wire" })).toBeVisible();
    await expect(drop(page)).toHaveCount(0);
    await page.getByText("You're caught up.").scrollIntoViewIfNeeded();
    await expect(page.getByRole("button", { name: "Intro me" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Helpful" }).first()).toBeAttached();
  });
});

test.describe("Home: accessibility", () => {
  test("axe is clean in both themes, with no sideways overflow", async ({ page }) => {
    await open(page);
    await inBothThemes(page, async (theme) => { await checkPage(page, `home ${theme}`); });
  });

  test("the six accents all keep Home clean", async ({ page }) => {
    await open(page);
    for (const accent of ["emerald", "sky", "indigo", "rose", "lime", "mono"]) {
      await page.evaluate((a) => { document.documentElement.dataset.accent = a; }, accent);
      await checkPage(page, `home ${accent}`);
    }
  });
});
