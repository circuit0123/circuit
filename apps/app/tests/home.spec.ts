import { expect, test, type Page } from "@playwright/test";
import { checkPage as axeCheck, inBothThemes, isPhone } from "../e2e/helpers";
import { drag } from "./touch";

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

const wireNode = (page: Page, i: number) => page.getByRole("list", { name: "Live wire" }).getByRole("button").nth(i);
const update = (page: Page) => page.getByRole("dialog", { name: "Update" });

test.describe("Update view", () => {
  test("opens full screen with who, what, why and one action; the picture is 66% of the height", async ({ page }) => {
    await open(page);
    await wireNode(page, 0).click();
    const v = update(page);
    await expect(v).toBeVisible();
    await expect(v.getByText("1 of 5", { exact: true })).toBeVisible();
    await expect(v.getByRole("heading", { level: 2 })).toContainText("Arjun shipped");
    await expect(v.getByText("He builds with the same tools you do.")).toBeVisible();
    await expect(v.getByRole("button", { name: "Reply" })).toBeVisible();
    await expect(v.locator("button.bg-primary")).toHaveCount(1); // one action
    await expect(v.getByRole("button", { name: "Previous update" })).toBeDisabled();
    const vb = (await v.boundingBox())!;
    const pic = (await v.getByRole("button", { name: "Next update" }).boundingBox())!; // the tap zone sits on the picture
    expect(pic.y + pic.height).toBeLessThan(vb.height * 0.66);
  });

  test("the picture's edges, the arrow keys and Esc move and close", async ({ page }) => {
    await open(page);
    await wireNode(page, 0).click();
    const v = update(page);
    await v.getByRole("button", { name: "Next update" }).click();
    await expect(v.getByText("2 of 5", { exact: true })).toBeVisible();
    await page.keyboard.press("ArrowRight");
    await expect(v.getByText("3 of 5", { exact: true })).toBeVisible();
    await page.keyboard.press("ArrowLeft");
    await expect(v.getByText("2 of 5", { exact: true })).toBeVisible();
    await v.getByRole("button", { name: "Previous update" }).click();
    await expect(v.getByText("1 of 5", { exact: true })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(v).toHaveCount(0);
  });

  test("Next on the last update closes it", async ({ page }) => {
    await open(page);
    await wireNode(page, 4).click();
    await expect(update(page).getByText("5 of 5", { exact: true })).toBeVisible();
    await update(page).getByRole("button", { name: "Close" }).first().click();
    await expect(update(page)).toHaveCount(0);
  });

  test("an opened node is marked seen (no longer \"new\")", async ({ page }) => {
    await open(page);
    await expect(wireNode(page, 0)).toContainText(", new");
    await wireNode(page, 0).click();
    await page.keyboard.press("Escape");
    await expect(wireNode(page, 0)).not.toContainText(", new");
  });

  test("the action does what it says: Reply opens Inbox, View role opens Discover", async ({ page }) => {
    await open(page);
    await wireNode(page, 0).click();
    await update(page).getByRole("button", { name: "Reply" }).click();
    await expect(page).toHaveURL(/\/inbox$/);
    await open(page);
    await wireNode(page, 1).click();
    await update(page).getByRole("button", { name: "View role" }).click();
    await expect(page).toHaveURL(/\/discover$/);
  });

  test("under 18: an intro update has no action", async ({ page }) => {
    await open(page, "under18");
    await wireNode(page, 2).click();
    await expect(update(page).getByRole("heading", { level: 2 })).toContainText("Kavya needs");
    await expect(update(page).getByRole("button", { name: "Intro me" })).toHaveCount(0);
  });

  test.describe("by touch", () => {
    test.use({ reducedMotion: "no-preference", hasTouch: true });
    test("swipe left goes to the next update, swipe down closes", async ({ page }, info) => {
      test.skip(!isPhone(info), "swiping is a phone gesture");
      await open(page);
      await wireNode(page, 0).click();
      const v = update(page);
      await expect(v).toBeVisible();
      await page.waitForTimeout(600);
      const box = (await v.boundingBox())!;
      await drag(page, { x: box.width * 0.75, y: box.height * 0.45 }, { x: box.width * 0.1, y: box.height * 0.45 });
      await expect(v.getByText("2 of 5", { exact: true })).toBeVisible();
      await drag(page, { x: box.width * 0.5, y: box.height * 0.3 }, { x: box.width * 0.5, y: box.height * 0.8 });
      await expect(v).toHaveCount(0);
    });
  });

  test("axe is clean in both themes", async ({ page }) => {
    await open(page);
    await wireNode(page, 1).click();
    await expect(update(page)).toBeVisible();
    await page.waitForTimeout(500);
    await inBothThemes(page, async (theme) => { await checkPage(page, `update ${theme}`); });
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
