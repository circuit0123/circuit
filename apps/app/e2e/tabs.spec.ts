import { expect, test, type Page } from "@playwright/test";
import { API, personaToken, signInAs } from "./helpers";

/** One touch drag through Chrome's input pipeline, so the page sees real pointer events (and the browser can claim vertical pans). */
async function drag(page: Page, from: { x: number; y: number }, to: { x: number; y: number }, ms = 250, steps = 12) {
  const cdp = await page.context().newCDPSession(page);
  const at = (p: { x: number; y: number }) => [{ x: p.x, y: p.y, id: 1 }];
  await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: at(from) });
  for (let i = 1; i <= steps; i++) {
    await page.waitForTimeout(ms / steps);
    await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: at({ x: from.x + ((to.x - from.x) * i) / steps, y: from.y + ((to.y - from.y) * i) / steps }) });
  }
  await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
  await cdp.detach();
}

const current = (page: Page) => page.getByRole("navigation", { name: "Main" }).filter({ visible: true }).locator('[aria-current="page"]');

// Swiping is switched off for people who ask for reduced motion, so this spec runs with motion on.
test.use({ reducedMotion: "no-preference" });

test.beforeEach(async ({ context }, info) => {
  test.skip(info.project.name !== "phone", "swiping is a phone gesture");
  await signInAs(context, "ravi");
});

async function home(page: Page) {
  await page.goto("/");
  await expect(page.getByRole("list", { name: "Live wire" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Daily Drop" })).toBeVisible();
  await page.waitForTimeout(600);
}
/** A spot on the page that belongs to no swipeable widget: the "Today" title, scrolled into view. */
const spot = async (page: Page) => {
  const h = page.getByRole("heading", { name: "Today", level: 1 });
  await h.scrollIntoViewIfNeeded();
  await page.waitForTimeout(200);
  return (await h.boundingBox())!;
};

test("tapping a tab changes the screen and the bar", async ({ page }) => {
  await home(page);
  await page.getByRole("navigation", { name: "Main" }).filter({ visible: true }).getByRole("link", { name: "Discover" }).click();
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
  await page.getByRole("navigation", { name: "Main" }).filter({ visible: true }).getByRole("link", { name: "Profile" }).click();
  await expect(page).toHaveURL(/\/profile$/);
  await page.waitForTimeout(300);
  await page.getByRole("navigation", { name: "Main" }).filter({ visible: true }).getByRole("link", { name: "Home" }).click();
  await expect(page).toHaveURL(/\/$/);
  await page.waitForTimeout(600);
  expect(Math.abs((await page.evaluate(() => window.scrollY)) - y)).toBeLessThan(40);
});

test("the Settings toggle turns swiping off", async ({ page }) => {
  const token = await personaToken("ravi");
  const patch = (swipe_tabs: boolean) => fetch(`${API}/api/me/appearance`, { method: "PATCH", headers: { "content-type": "application/json", authorization: `Bearer ${token}` }, body: JSON.stringify({ swipe_tabs }) });
  await patch(false);
  try {
    await home(page);
    const b = await spot(page);
    await drag(page, { x: 330, y: b.y + 10 }, { x: 60, y: b.y + 14 }, 200);
    await page.waitForTimeout(500);
    await expect(page).toHaveURL(/\/$/);
  } finally {
    await patch(true);
  }
});
