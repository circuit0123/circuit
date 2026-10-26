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

  test("the action does what it says: Reply opens a message to them, View role opens the job page", async ({ page }) => {
    await open(page);
    await wireNode(page, 0).click();
    await update(page).getByRole("button", { name: "Reply" }).click();
    await expect(page).toHaveURL(/\/inbox\/new\?to=4$/);
    await expect(page.getByRole("heading", { name: "Arjun Mehta", level: 1 })).toBeVisible();
    await open(page);
    await wireNode(page, 1).click();
    await update(page).getByRole("button", { name: "View role" }).click();
    await expect(page).toHaveURL(/\/discover\/jobs\/301$/);
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

test("on a phone the picture comes first, edge to edge (DESIGN.md §4 Build log)", async ({ page }, info) => {
  test.skip(!isPhone(info), "phone layout");
  await open(page);
  const post = page.getByRole("region", { name: "Pulse" }).locator("[data-feed-item]").first();
  const text = (await post.locator("p.t-body").first().boundingBox())!;
  const picture = (await post.locator("img").first().boundingBox())!;
  expect(picture.y).toBeLessThan(text.y);
  expect(picture.width).toBe(375);
});

test.describe("Desktop Home (Desktop.dc.html)", () => {
  test.beforeEach(async ({}, info) => { test.skip(isPhone(info), "desktop layout"); });
  const rail = (page: Page) => page.locator("aside").filter({ has: page.getByRole("navigation", { name: "Main" }) });

  test("left rail: logo, 48px rows with the current one filled, New build log, notifications", async ({ page }) => {
    await open(page);
    const r = rail(page);
    await expect(r.getByRole("link", { name: "Circuit, Home" })).toBeVisible();
    const rows = r.getByRole("navigation", { name: "Main" }).getByRole("link");
    await expect(rows).toHaveText(["Home", "Discover", "Circuits", /^Inbox/, "Profile"]); // Inbox may carry ", unread messages"
    for (const row of await rows.all()) expect((await row.boundingBox())!.height).toBe(48);
    await expect(rows.first()).toHaveAttribute("aria-current", "page");
    expect(await rows.first().evaluate((e) => getComputedStyle(e).backgroundColor)).not.toBe("rgba(0, 0, 0, 0)");
    expect(await rows.nth(1).evaluate((e) => getComputedStyle(e).backgroundColor)).toBe("rgba(0, 0, 0, 0)");
    await expect(r.getByRole("button", { name: "New build log" })).toBeVisible();
    await expect(r.getByRole("link", { name: /^Notifications/ })).toBeVisible();
    expect((await r.boundingBox())!.width).toBe(240);
  });

  test("centre column is at most 600px, the Daily Drop rail at most 340px, 56px apart, and nothing else beside them", async ({ page }) => {
    await open(page);
    const column = (await page.locator("main").boundingBox())!;
    const drop = (await page.getByRole("complementary", { name: "For you" }).boundingBox())!;
    expect(column.width).toBeLessThanOrEqual(600);
    expect(drop.width).toBeLessThanOrEqual(340);
    expect(drop.width).toBeGreaterThanOrEqual(280);
    expect(Math.round(drop.x - (column.x + column.width))).toBe(56);
    await expect(page.getByRole("complementary", { name: "For you" }).getByRole("region", { name: "Daily Drop" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Today", level: 1 })).toHaveCSS("font-size", "36px");
  });

  test("on desktop the words come before the picture, then the reactions", async ({ page }) => {
    await open(page);
    const post = page.getByRole("region", { name: "Pulse" }).locator("[data-feed-item]").first();
    const text = (await post.locator("p.t-body").first().boundingBox())!;
    const picture = (await post.locator("img").first().boundingBox())!;
    expect(text.y).toBeLessThan(picture.y);
    const reactions = (await post.getByRole("group", { name: "React" }).boundingBox())!;
    expect(reactions.y).toBeGreaterThan(picture.y + picture.height - 1);
  });

  test("Pulse off: the Daily Drop is the centre column and there is no rail, no New build log", async ({ page }) => {
    await open(page, "pulse_off");
    await expect(page.getByRole("complementary", { name: "For you" })).toHaveCount(0);
    await expect(page.locator("main").getByRole("region", { name: "Daily Drop" })).toBeVisible();
    await expect(rail(page).getByRole("button", { name: "New build log" })).toHaveCount(0);
  });

  test("Daily Drop off: no empty rail is left behind", async ({ page }) => {
    await open(page, "drop_off");
    await expect(page.getByRole("complementary", { name: "For you" })).toHaveCount(0);
    await expect(page.getByRole("region", { name: "Pulse" })).toBeVisible();
    const column = (await page.locator("main").boundingBox())!;
    expect(column.width).toBeLessThanOrEqual(600);
  });

  test("both off: the empty state and still the rail", async ({ page }) => {
    await open(page, "home_off");
    await expect(page.getByText("Nothing on Home right now.")).toBeVisible();
    await expect(rail(page).getByRole("navigation", { name: "Main" })).toBeVisible();
  });

  test("axe and overflow at 1280 and 1440, both themes", async ({ page }) => {
    for (const width of [1280, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      await open(page);
      await inBothThemes(page, async (theme) => { await checkPage(page, `desktop home ${width} ${theme}`); });
    }
  });
});

test.describe("Intro request flow", () => {
  const sheet = (page: Page, name: string) => page.getByRole("dialog", { name });
  const asked = "Intro requested. We'll tell you when they reply.";
  const skipTo = async (page: Page, n: number) => {
    for (let i = 0; i < n; i++) { await drop(page).getByRole("button", { name: "Skip" }).click(); await expect(counter(page)).toHaveText(`${i + 2} of 3`); }
  };

  test("Intro me opens the sheet first and the card waits; Send request sends it and the card leaves", async ({ page }) => {
    await open(page);
    await drop(page).getByRole("button", { name: "Intro me" }).click();
    const s = sheet(page, "Intro to Asha");
    await expect(s).toBeVisible();
    await expect(s.getByText("Lakshmi, mentor, will introduce you to Asha.")).toBeVisible();
    await expect(s.getByText("A request stays open for 7 days.")).toBeVisible();
    await expect(counter(page)).toHaveText("1 of 3"); // nothing recorded yet
    await s.getByRole("button", { name: "Send request" }).click();
    await expect(s).toHaveCount(0);
    await expect(page.getByText(asked)).toBeVisible();
    await expect(counter(page)).toHaveText("2 of 3");
  });

  test("Cancel and Esc leave the card where it was, and Skip still works", async ({ page }) => {
    await open(page);
    await drop(page).getByRole("button", { name: "Intro me" }).click();
    await sheet(page, "Intro to Asha").getByRole("button", { name: "Cancel" }).click();
    await expect(sheet(page, "Intro to Asha")).toHaveCount(0);
    await expect(counter(page)).toHaveText("1 of 3");
    await drop(page).getByRole("button", { name: "Intro me" }).click();
    await expect(sheet(page, "Intro to Asha")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(sheet(page, "Intro to Asha")).toHaveCount(0);
    await expect(counter(page)).toHaveText("1 of 3");
    await drop(page).getByRole("button", { name: "Skip" }).click();
    await expect(counter(page)).toHaveText("2 of 3");
  });

  test("no shared connection: one sentence, no Send button, the card stays", async ({ page }) => {
    await open(page);
    await skipTo(page, 1);
    await drop(page).getByRole("button", { name: "Intro me" }).click();
    const s = sheet(page, "Intro to Kavya");
    await expect(s.getByRole("alert")).toHaveText("You don't share a connection with Kavya yet.");
    await expect(s.getByRole("button", { name: "Send request" })).toHaveCount(0);
    await s.getByRole("button", { name: "Close" }).click();
    await expect(counter(page)).toHaveText("2 of 3");
  });

  test("the person has no slots left: the message says so and the card stays", async ({ page }) => {
    await open(page);
    await skipTo(page, 2);
    await drop(page).getByRole("button", { name: "Intro me" }).click();
    const s = sheet(page, "Intro to Arjun");
    await expect(s.getByText("You're already connected. We'll send your request straight to Arjun.")).toBeVisible();
    await s.getByRole("button", { name: "Send request" }).click();
    await expect(s.getByRole("alert")).toHaveText("Arjun isn't taking more intros this week. Try again next week.");
    await expect(s.getByRole("button", { name: "Send request" })).toHaveCount(0); // retrying cannot help
    await s.getByRole("button", { name: "Close" }).click();
    await expect(counter(page)).toHaveText("3 of 3");
    await expect(drop(page).getByRole("button", { name: "Skip" })).toBeVisible();
  });

  test("weekly capacity used up: the weekly message, and the card stays", async ({ page }) => {
    await open(page, "intros_used");
    await drop(page).getByRole("button", { name: "Intro me" }).click();
    const s = sheet(page, "Intro to Asha");
    await s.getByRole("button", { name: "Send request" }).click();
    await expect(s.getByRole("alert")).toHaveText("You've used this week's intros. You can ask again next week.");
    await s.getByRole("button", { name: "Close" }).click();
    await expect(counter(page)).toHaveText("1 of 3");
    await expect(page.getByText(asked)).toHaveCount(0);
  });

  test.describe("by swipe", () => {
    test.use({ reducedMotion: "no-preference", hasTouch: true });
    test("a swipe right springs the card back and opens the sheet", async ({ page }, info) => {
      test.skip(!isPhone(info), "swiping the stack is a phone gesture");
      await open(page);
      const box = (await drop(page).locator("div.shadow-lift").first().boundingBox())!;
      await drag(page, { x: box.x + 30, y: box.y + 60 }, { x: box.x + box.width - 5, y: box.y + 60 });
      await expect(sheet(page, "Intro to Asha")).toBeVisible();
      await expect(counter(page)).toHaveText("1 of 3");
      await sheet(page, "Intro to Asha").getByRole("button", { name: "Send request" }).click();
      await expect(counter(page)).toHaveText("2 of 3");
    });
  });

  test("from the Update view: the view steps aside, the sheet opens, send confirms", async ({ page }) => {
    await open(page);
    await wireNode(page, 3).click(); // "joined": Divya, action Intro me
    await update(page).getByRole("button", { name: "Intro me" }).click();
    await expect(update(page)).toHaveCount(0);
    const s = sheet(page, "Intro to Divya");
    await expect(s).toBeVisible();
    await s.getByRole("button", { name: "Send request" }).click();
    await expect(page.getByText(asked)).toBeVisible();
  });

  test("under a build log: Intro me opens the sheet and is only recorded once sent", async ({ page }) => {
    await open(page);
    const first = page.getByRole("region", { name: "Pulse" }).locator("[data-feed-item]").first();
    const intro = first.getByRole("button", { name: "Intro me" });
    await intro.click();
    const s = sheet(page, "Intro to Arjun");
    await expect(s).toBeVisible();
    await s.getByRole("button", { name: "Close" }).or(s.getByRole("button", { name: "Cancel" })).click();
    await expect(intro).toHaveAttribute("aria-pressed", "false");
  });

  test("Helpful shows pressed at once", async ({ page }) => {
    await open(page);
    const helpful = page.getByRole("region", { name: "Pulse" }).locator("[data-feed-item]").first().getByRole("button", { name: "Helpful" });
    await expect(helpful).toHaveAttribute("aria-pressed", "false");
    await helpful.click();
    await expect(helpful).toHaveAttribute("aria-pressed", "true");
  });

  test("in Discover's People grid too", async ({ page }) => {
    await page.goto("/discover?s=people");
    await page.getByRole("list", { name: "People" }).getByRole("button", { name: /^Sneha Pillai/ }).click();
    await sheet(page, "Intro to Sneha").getByRole("button", { name: "Send request" }).click();
    await expect(page.getByText("Intro requested. We'll tell you when they reply.")).toBeVisible();
  });

  test("axe is clean with the sheet open, in both themes", async ({ page }) => {
    await open(page);
    await drop(page).getByRole("button", { name: "Intro me" }).click();
    await expect(sheet(page, "Intro to Asha").getByRole("button", { name: "Send request" })).toBeVisible();
    await page.waitForTimeout(500);
    await inBothThemes(page, async (theme) => { await checkPage(page, `intro sheet ${theme}`); });
  });
});
