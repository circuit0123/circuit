import { expect, test, type Page } from "@playwright/test";

/**
 * TabPager touch tests (DESIGN.md §3 "Swipe between tabs", LAUNCH.md Stage 4). Real touch input through Chrome's pipeline, so the page
 * sees real pointer events and the browser can claim vertical pans, like on a phone. Two places:
 *   - the app shell on mock mode (five tabs; four with features off), and
 *   - /design/pager, the five-tab pager on its own, with a sideways chips row, a Map-like lock, a text field and a sheet.
 */
type Pt = { x: number; y: number };

/** One touch drag. With `hold`, the finger stays down and the call returns a function that lifts it. */
async function drag(page: Page, from: Pt, to: Pt, ms = 250, steps = 12, hold = false) {
  const cdp = await page.context().newCDPSession(page);
  const at = (p: Pt) => [{ x: p.x, y: p.y, id: 1 }];
  await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: at(from) });
  for (let i = 1; i <= steps; i++) {
    await page.waitForTimeout(ms / steps);
    await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: at({ x: from.x + ((to.x - from.x) * i) / steps, y: from.y + ((to.y - from.y) * i) / steps }) });
  }
  const lift = async () => { await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] }); await cdp.detach(); };
  if (hold) return lift;
  await lift();
  return lift;
}

const bar = (page: Page) => page.getByRole("navigation", { name: "Main" }).filter({ visible: true });
const current = (page: Page) => bar(page).locator('[aria-current="page"]');
const shownPane = (page: Page) => page.locator("[data-pane]:not([hidden])");
const tab = (page: Page, name: string) => bar(page).getByRole("link", { name });

// Swiping is switched off for people who ask for reduced motion, so this spec runs with motion on.
test.use({ reducedMotion: "no-preference" });
test.beforeEach(async ({}, info) => { test.skip(info.project.name !== "phone", "swiping is a phone gesture"); });

/** A spot on the screen that belongs to no swipeable widget: the Large title, scrolled into view. */
async function spot(page: Page): Promise<{ x: number; y: number; width: number; height: number }> {
  const h = shownPane(page).getByRole("heading", { level: 1 });
  await h.scrollIntoViewIfNeeded();
  await page.waitForTimeout(200);
  return (await h.boundingBox())!;
}

test.describe("app shell on mock mode", () => {
  async function home(page: Page, query = "") {
    await page.goto(`/${query}`);
    await expect(page.getByRole("list", { name: "Live wire" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Daily Drop" })).toBeVisible();
    await page.waitForTimeout(600);
  }

  test("tapping a tab changes the screen and the bar", async ({ page }) => {
    await home(page);
    await tab(page, "Discover").click();
    await expect(page).toHaveURL(/\/discover$/);
    await expect(current(page)).toHaveText("Discover");
    await expect(page.getByRole("heading", { name: "Discover", level: 1 })).toBeVisible();
  });

  test("a fast swipe left goes to the next tab; swiping right comes back", async ({ page }) => {
    await home(page);
    const b = await spot(page);
    await drag(page, { x: 330, y: b.y + 10 }, { x: 60, y: b.y + 14 }, 200);
    await expect(page).toHaveURL(/\/discover$/);
    await expect(current(page)).toHaveText("Discover");
    await page.waitForTimeout(300);
    await drag(page, { x: 60, y: 400 }, { x: 330, y: 404 }, 200);
    await expect(page).toHaveURL(/\/$/);
    await expect(current(page)).toHaveText("Home");
  });

  test("a short, slow drag snaps back", async ({ page }) => {
    await home(page);
    const b = await spot(page);
    await drag(page, { x: 200, y: b.y + 10 }, { x: 130, y: b.y + 12 }, 900);
    await page.waitForTimeout(500);
    await expect(page).toHaveURL(/\/$/);
    await expect(current(page)).toHaveText("Home");
    expect(await page.evaluate(() => document.querySelector<HTMLElement>('[data-pane="home"]')!.style.transform)).toBe("");
  });

  test("vertical scrolling wins over a slightly diagonal drag", async ({ page }) => {
    await home(page);
    const b = await spot(page);
    await drag(page, { x: 200, y: b.y + 200 }, { x: 160, y: b.y - 40 }, 200);
    await page.waitForTimeout(400);
    await expect(page).toHaveURL(/\/$/);
    expect(await page.evaluate(() => window.scrollY)).toBeGreaterThan(50);
  });

  test("swipes that start in the Live wire belong to it; the Daily Drop opts out of tab swiping", async ({ page }) => {
    await home(page);
    const wire = (await page.getByRole("list", { name: "Live wire" }).boundingBox())!;
    await drag(page, { x: 330, y: wire.y + 30 }, { x: 60, y: wire.y + 32 }, 200);
    await page.waitForTimeout(400);
    await expect(page).toHaveURL(/\/$/);
    // A swipe on a Drop card means Intro or Skip (it changes the person's data), so this only checks the opt-out.
    await expect(page.locator('section[aria-label="Daily Drop"][data-no-swipe]')).toHaveCount(1);
  });

  test("each tab keeps its scroll position", async ({ page }) => {
    await home(page);
    await page.evaluate(() => window.scrollTo(0, 600));
    await page.waitForTimeout(200);
    const y = await page.evaluate(() => window.scrollY);
    expect(y).toBeGreaterThan(300);
    await tab(page, "Profile").click();
    await expect(page).toHaveURL(/\/profile$/);
    await page.waitForTimeout(300);
    await tab(page, "Home").click();
    await expect(page).toHaveURL(/\/$/);
    await page.waitForTimeout(600);
    expect(Math.abs((await page.evaluate(() => window.scrollY)) - y)).toBeLessThan(40);
  });

  test("tapping the current tab scrolls to the top", async ({ page }) => {
    await home(page);
    await page.evaluate(() => window.scrollTo(0, 600));
    await page.waitForTimeout(200);
    await tab(page, "Home").click();
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBeLessThan(5);
  });

  test("the Settings toggle turns swiping off", async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem("circuit.mock.appearance", JSON.stringify({ swipe_tabs: false })));
    await home(page);
    const b = await spot(page);
    await drag(page, { x: 330, y: b.y + 10 }, { x: 60, y: b.y + 14 }, 200);
    await page.waitForTimeout(500);
    await expect(page).toHaveURL(/\/$/);
  });

  test("with features off the bar has four tabs and swiping follows them", async ({ page }) => {
    await page.goto("/?scenario=features_off");
    await expect(page.getByRole("heading", { name: "Today", level: 1 })).toBeVisible();
    await expect(bar(page).getByRole("link")).toHaveText(["Home", "Discover", "Inbox", "Profile"]);
    const b = await spot(page);
    await drag(page, { x: 330, y: b.y + 10 }, { x: 60, y: b.y + 14 }, 200);
    await expect(page).toHaveURL(/\/discover$/);
    await page.waitForTimeout(300);
    await drag(page, { x: 330, y: 400 }, { x: 60, y: 404 }, 200);
    await expect(page).toHaveURL(/\/inbox$/);
  });
});

test.describe("five-tab pager (/design/pager)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/design/pager");
    await expect(shownPane(page).getByRole("heading", { level: 1 })).toHaveText("Today");
    await page.waitForTimeout(400);
  });

  const swipeLeft = async (page: Page, ms = 200) => { const b = await spot(page); await drag(page, { x: 330, y: b.y + 10 }, { x: 60, y: b.y + 14 }, ms); };
  const swipeRight = async (page: Page, ms = 200) => { const b = await spot(page); await drag(page, { x: 60, y: b.y + 10 }, { x: 330, y: b.y + 14 }, ms); };

  /** Swipes left one tab at a time, checking each lands before the next starts (a swipe made mid-settle is ignored, as it should be). */
  const swipeTo = async (page: Page, ...names: string[]) => {
    for (const name of names) {
      await swipeLeft(page);
      await expect(current(page)).toHaveText(name);
      await page.waitForTimeout(400);
    }
  };

  test("swipes through all five tabs in bar order and back", async ({ page }) => {
    for (const name of ["Discover", "Circuits", "Inbox", "Profile"]) {
      await swipeLeft(page);
      await expect(current(page)).toHaveText(name);
      await page.waitForTimeout(300);
    }
    for (const name of ["Inbox", "Circuits", "Discover", "Home"]) {
      await swipeRight(page);
      await expect(current(page)).toHaveText(name);
      await page.waitForTimeout(300);
    }
  });

  test("there is nothing past the first or last tab", async ({ page }) => {
    await swipeRight(page);
    await page.waitForTimeout(500);
    await expect(current(page)).toHaveText("Home");
    expect(await page.evaluate(() => document.querySelector<HTMLElement>('[data-pane="home"]')!.style.transform)).toBe("");
  });

  test("a slow drag past 35% of the width commits; one short of it snaps back", async ({ page }) => {
    const b = await spot(page);
    await drag(page, { x: 300, y: b.y + 10 }, { x: 190, y: b.y + 12 }, 1200); // 110px = 29% at 375px
    await page.waitForTimeout(500);
    await expect(current(page)).toHaveText("Home");
    await drag(page, { x: 330, y: b.y + 10 }, { x: 180, y: b.y + 12 }, 1200); // 150px = 40%
    await expect(current(page)).toHaveText("Discover");
  });

  test("the screen follows the finger and the bar indicator slides with it", async ({ page }) => {
    const b = await spot(page);
    const indicator = page.locator('nav[aria-label="Main"] span[aria-hidden]').first();
    const x0 = (await indicator.boundingBox())!.x;
    const lift = await drag(page, { x: 330, y: b.y + 10 }, { x: 130, y: b.y + 12 }, 600, 12, true);
    await page.waitForTimeout(100);
    const during = await page.evaluate(() => document.querySelector<HTMLElement>('[data-pane="home"]')!.style.transform);
    expect(during).toMatch(/translate3d\(-(1[89]\d|200)(\.\d+)?px/);
    expect((await indicator.boundingBox())!.x).toBeGreaterThan(x0 + 20);
    await lift();
    await page.waitForTimeout(600);
  });

  test("a sideways chips row keeps its own swipe", async ({ page }) => {
    await swipeLeft(page);
    await expect(current(page)).toHaveText("Discover");
    await page.waitForTimeout(400);
    const row = (await page.getByTestId("chips-row").boundingBox())!;
    const before = await page.getByTestId("chips-row").evaluate((el) => el.scrollLeft);
    await drag(page, { x: 330, y: row.y + 20 }, { x: 60, y: row.y + 24 }, 200);
    await page.waitForTimeout(400);
    await expect(current(page)).toHaveText("Discover");
    expect(await page.getByTestId("chips-row").evaluate((el) => el.scrollLeft)).toBeGreaterThan(before);
  });

  test("a segmented control keeps its own swipe, and a screen can lock swiping (the Map)", async ({ page }) => {
    await swipeLeft(page);
    await expect(current(page)).toHaveText("Discover");
    await page.waitForTimeout(400);
    const seg = (await page.getByRole("radiogroup", { name: "Discover" }).boundingBox())!;
    await drag(page, { x: seg.x + seg.width - 10, y: seg.y + 15 }, { x: 40, y: seg.y + 17 }, 200);
    await page.waitForTimeout(400);
    await expect(current(page)).toHaveText("Discover");

    await page.getByRole("radio", { name: "Map" }).click();
    await expect(page.getByTestId("map-area")).toBeVisible();
    const b = await spot(page);
    await drag(page, { x: 330, y: b.y + 10 }, { x: 60, y: b.y + 14 }, 200);
    await page.waitForTimeout(500);
    await expect(current(page)).toHaveText("Discover");

    await page.getByRole("radio", { name: "People" }).click();
    await expect(page.getByTestId("map-area")).toHaveCount(0);
    await drag(page, { x: 330, y: b.y + 10 }, { x: 60, y: b.y + 14 }, 200);
    await expect(current(page)).toHaveText("Circuits");
  });

  test("no tab swipe while a sheet is open or a text field has focus", async ({ page }) => {
    await swipeTo(page, "Discover", "Circuits", "Inbox");
    await page.getByRole("textbox", { name: "Search messages" }).tap();
    const b = await spot(page);
    await drag(page, { x: 330, y: b.y + 10 }, { x: 60, y: b.y + 14 }, 200);
    await page.waitForTimeout(500);
    await expect(current(page)).toHaveText("Inbox");
    await page.getByRole("textbox", { name: "Search messages" }).blur();

    await page.getByRole("button", { name: "Open sheet" }).tap();
    await expect(page.getByRole("dialog", { name: "A sheet" })).toBeVisible();
    await drag(page, { x: 330, y: 150 }, { x: 60, y: 154 }, 200);
    await page.waitForTimeout(500);
    await expect(current(page)).toHaveText("Inbox");
  });

  test("each tab keeps its scroll position across swipes", async ({ page }) => {
    await page.evaluate(() => window.scrollTo(0, 500));
    await page.waitForTimeout(300);
    const y = await page.evaluate(() => window.scrollY);
    expect(y).toBeGreaterThan(300);
    // Start on a list item well below the title, so nothing scrolls the page back.
    await drag(page, { x: 330, y: 300 }, { x: 60, y: 304 }, 200);
    await expect(current(page)).toHaveText("Discover");
    await page.waitForTimeout(500);
    await drag(page, { x: 60, y: 300 }, { x: 330, y: 304 }, 200);
    await expect(current(page)).toHaveText("Home");
    await page.waitForTimeout(500);
    expect(Math.abs((await page.evaluate(() => window.scrollY)) - y)).toBeLessThan(40);
  });

  test("the toggle turns swiping off", async ({ page }) => {
    await swipeTo(page, "Discover", "Circuits", "Inbox", "Profile");
    await page.getByRole("button", { name: "Turn swiping off" }).tap();
    await swipeRight(page);
    await page.waitForTimeout(500);
    await expect(current(page)).toHaveText("Profile");
  });
});

test.describe("reduced motion", () => {
  test.use({ reducedMotion: "reduce" });

  test("a swipe does nothing and a tap switches tabs with a fade", async ({ page }) => {
    await page.goto("/design/pager");
    await expect(shownPane(page).getByRole("heading", { level: 1 })).toHaveText("Today");
    const b = await spot(page);
    await drag(page, { x: 330, y: b.y + 10 }, { x: 60, y: b.y + 14 }, 200);
    await page.waitForTimeout(500);
    await expect(current(page)).toHaveText("Home");
    await tab(page, "Inbox").tap();
    await expect(current(page)).toHaveText("Inbox");
    await expect(shownPane(page).getByRole("heading", { level: 1 })).toHaveText("Inbox");
  });
});

test.describe("sheet detents (/design)", () => {
  test("medium opens at half the screen, a drag up goes large, a flick down closes, and the page behind steps back", async ({ page }) => {
    await page.goto("/design");
    const dark = page.getByRole("region", { name: "dark theme" });
    await dark.getByRole("button", { name: "Medium detent" }).scrollIntoViewIfNeeded();
    await dark.getByRole("button", { name: "Medium detent" }).click();
    const dialog = page.getByRole("dialog", { name: "Report this post" });
    await expect(dialog).toBeVisible();
    await page.waitForTimeout(700);
    const vh = 812;
    expect(await page.evaluate(() => document.documentElement.hasAttribute("data-sheet-open"))).toBe(true);
    const medium = (await dialog.boundingBox())!;
    expect(medium.y).toBeGreaterThan(vh * 0.5 - 40);
    expect(medium.y).toBeLessThan(vh * 0.5 + 40);

    await drag(page, { x: 187, y: medium.y + 20 }, { x: 187, y: 120 }, 300);
    await page.waitForTimeout(700);
    const large = (await dialog.boundingBox())!;
    expect(large.y).toBeLessThan(vh * 0.08 + 40);

    await drag(page, { x: 187, y: large.y + 20 }, { x: 187, y: large.y + 400 }, 120);
    await expect(dialog).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.hasAttribute("data-sheet-open"))).toBe(false);
  });
});
