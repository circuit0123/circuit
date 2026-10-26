import { expect, test, type Page } from "@playwright/test";
import { checkPage as axeCheck, inBothThemes } from "../e2e/helpers";

/**
 * F5 Circuits on mock mode (no backend): the proposal card with its ring, who helps whom and time left; Accept and Decline; the live
 * segment update (Arjun answers about 4 seconds after the list loads, through the mock Realtime bus); the closing moment (DESIGN.md §7)
 * and its reduced-motion fade; mark done and rating; completed history; empty, under-18, loading, error, slow 3G and features off.
 * Axe at 375px and 1280px, dark and light. Mock rules are at the top of src/data/mocks/circuits.ts.
 */

/** The translucent tab bar takes on what scrolls under it (see home.spec.ts); it is checked over plain content in foundation.spec.ts. */
const checkPage = (page: Page, label: string) => axeCheck(page, label, { exclude: ["nav.material"] });

const open = async (page: Page, scenario = "default") => {
  await page.goto(`/circuits?scenario=${scenario}`);
  await expect(page.getByRole("heading", { name: "Circuits", level: 1 })).toBeVisible();
};
const proposal = (page: Page) => page.locator('[data-circuit-id="11"]');
const lastWeek = (page: Page) => page.locator('[data-circuit-id="10"]');
const ring = (page: Page) => proposal(page).getByRole("img").first();
/** Arjun says yes on his own a few seconds after the list loads. */
const arjunAnswers = (page: Page) => expect(ring(page)).toHaveAccessibleName("Priya and Arjun accepted, waiting for you", { timeout: 10_000 });

test.describe("Circuits: the proposal", () => {
  test("a proposed circuit: ring, three who-helps-whom lines, time left, Accept and Decline", async ({ page }) => {
    await open(page);
    const card = proposal(page);
    await expect(card.getByRole("heading", { name: "Proposed for you" })).toBeVisible();
    await expect(card).toContainText("2d 14h left");
    await expect(ring(page)).toHaveAccessibleName("Priya accepted, waiting for you and Arjun");
    await expect(card).toContainText("1 of 3 in");
    const lines = card.getByRole("list", { name: "Who helps whom" }).getByRole("listitem");
    await expect(lines).toHaveText(["You help Priya with fundraising", "Priya helps Arjun with hiring · accepted", "Arjun helps you with marketing"]);
    await expect(card.getByRole("button", { name: "Accept" })).toBeVisible();
    await expect(card.getByRole("button", { name: "Decline" })).toBeVisible();
    // Never a raw score or percentage on the card.
    await expect(card).not.toContainText("%");
  });

  test("live: Arjun's segment lights up without a reload", async ({ page }) => {
    await open(page);
    await page.evaluate(() => { (window as unknown as { marker: number }).marker = 1; });
    await arjunAnswers(page);
    await expect(proposal(page)).toContainText("2 of 3 in");
    await expect(proposal(page).getByRole("listitem").nth(2)).toHaveText("Arjun helps you with marketing · accepted");
    expect(await page.evaluate(() => (window as unknown as { marker?: number }).marker)).toBe(1); // same page, no reload
  });

  test("Accept when both others are in: the ring closes and says who you help", async ({ page }) => {
    await open(page);
    await arjunAnswers(page);
    await proposal(page).getByRole("button", { name: "Accept" }).click();
    await expect(proposal(page).getByRole("status")).toHaveText("Circuit closed. You help Priya with fundraising. We'll check in next week.");
    await expect(ring(page)).toHaveAccessibleName(/^Circuit closed/);
    await expect(proposal(page)).toContainText("3 of 3 in");
    // Reduced motion (the test default): a static closed ring with a checkmark, no drawing.
    await expect(proposal(page).locator("[data-check]")).toBeVisible();
    await expect(proposal(page).getByRole("button", { name: "Accept" })).toHaveCount(0);
  });

  test("Accept first: you wait, then the ring closes live when the last person says yes", async ({ page }) => {
    await open(page);
    await proposal(page).getByRole("button", { name: "Accept" }).click();
    await expect(proposal(page).getByRole("status")).toHaveText("You said yes. Waiting for Arjun.");
    await expect(proposal(page).getByRole("status")).toHaveText(/^Circuit closed\. You help Priya with fundraising\./, { timeout: 10_000 });
  });

  test("Decline asks first, then the circuit is gone", async ({ page }) => {
    await open(page);
    await proposal(page).getByRole("button", { name: "Decline" }).click();
    const sheet = page.getByRole("dialog", { name: "Decline this circuit?" });
    await expect(sheet).toContainText("One no ends it for all three of you");
    await sheet.getByRole("button", { name: "Keep it" }).click();
    await expect(sheet).toHaveCount(0);
    await expect(proposal(page)).toBeVisible();
    await proposal(page).getByRole("button", { name: "Decline" }).click();
    await page.getByRole("dialog", { name: "Decline this circuit?" }).getByRole("button", { name: "Decline" }).click();
    await expect(page.getByText("Declined. This circuit won't go ahead.")).toBeVisible();
    await expect(proposal(page)).toHaveCount(0);
  });

  test("one primary button on the screen: only the proposal's Accept", async ({ page }) => {
    await open(page);
    const primaries = await page.locator("main button:visible").evaluateAll((els) => els.filter((e) => getComputedStyle(e).backgroundColor === "rgb(0, 86, 63)").length);
    expect(primaries).toBe(1);
  });
});

test.describe("Circuits: the closing moment with motion", () => {
  test.use({ reducedMotion: "no-preference" });

  test("plays once, in 1.6 seconds, and doesn't replay after a reload", async ({ page }) => {
    await open(page);
    await arjunAnswers(page);
    await proposal(page).getByRole("button", { name: "Accept" }).click();
    const closing = proposal(page).locator("[data-closing]");
    await expect(closing).toHaveCount(1);
    const t0 = Date.now();
    await expect(closing).toHaveCount(0, { timeout: 4000 });
    const took = Date.now() - t0;
    expect(took).toBeGreaterThan(1000);
    expect(took).toBeLessThan(2600);
    await expect(proposal(page).locator("[data-check]")).toHaveCount(0); // the checkmark is the reduced-motion version only
    await expect(proposal(page).locator("[data-closed]")).toHaveCount(1);
    // The mock forgets answers on reload; the ring is open again, and nothing plays by itself.
    await page.reload();
    await expect(proposal(page)).toBeVisible();
    await page.waitForTimeout(500);
    await expect(proposal(page).locator("[data-closing]")).toHaveCount(0);
  });
});

test.describe("Circuits: doing your part", () => {
  test("mark your handover done, behind a confirm sheet", async ({ page }) => {
    await open(page);
    const card = lastWeek(page);
    await expect(card.getByRole("heading", { name: "Circuit closed" })).toBeVisible();
    await card.getByRole("button", { name: "Mark my part done" }).click();
    const sheet = page.getByRole("dialog", { name: "Done helping Divya?" });
    await expect(sheet).toContainText("Divya will be asked how your help with frontend development went.");
    await sheet.getByRole("button", { name: "Yes, it's done" }).click();
    await expect(page.getByText("Marked done. Thank you.")).toBeVisible();
    await expect(card.getByRole("button", { name: "Mark my part done" })).toHaveCount(0);
    await expect(card.getByRole("listitem").first()).toHaveText("You help Divya with frontend development · done");
  });

  test("rate what you received, 1 to 5", async ({ page }) => {
    await open(page);
    const stars = lastWeek(page).getByRole("radiogroup", { name: "How was Rohan's help with pitch deck?" });
    await expect(stars.getByRole("radio")).toHaveCount(5);
    await stars.getByRole("radio", { name: "4 out of 5" }).click();
    await expect(page.getByText("Thanks for rating.")).toBeVisible();
    await expect(stars).toHaveCount(0);
  });

  test("completed circuits are a row of small rings", async ({ page }) => {
    await open(page);
    const done = page.getByRole("region", { name: "Completed" });
    await expect(done.getByRole("img")).toHaveCount(2);
    await expect(done.getByRole("img", { name: "Completed circuit, September" })).toBeVisible();
    await expect(done.getByRole("img", { name: "Completed circuit, August" })).toBeVisible();
    await expect(done).toContainText("2 circuits closed");
  });
});

test.describe("Circuits: every scenario", () => {
  test("empty: the empty ring and one sentence", async ({ page }) => {
    await open(page, "empty");
    await expect(page.getByText("Add what you need and what you can offer to join this week's round.")).toBeVisible();
    await expect(page.locator("[data-circuit-id]")).toHaveCount(0);
  });

  test("under 18: no circuits, and it says why", async ({ page }) => {
    await open(page, "under18");
    await expect(page.getByText("Exchange circuits are for members 18 and over.", { exact: false })).toBeVisible();
    await expect(page.locator("[data-circuit-id]")).toHaveCount(0);
  });

  test("loading: a skeleton card, no content yet", async ({ page }) => {
    await open(page, "connect_loading");
    await expect(page.getByRole("region", { name: "Loading circuits" })).toBeVisible();
    await expect(page.locator("[data-circuit-id]")).toHaveCount(0);
  });

  test("error: what happened and Try again", async ({ page }) => {
    await open(page, "connect_error");
    await expect(page.getByRole("alert").filter({ hasText: "Couldn" })).toContainText("Couldn't load circuits. Check your connection and pull to refresh.");
    await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
  });

  test("slow 3G: the card arrives late, not never", async ({ page }) => {
    await page.goto("/circuits?scenario=slow3g");
    await expect(proposal(page)).toBeVisible({ timeout: 20_000 });
  });

  test("features off: no Circuits tab, and /circuits is the 404 screen", async ({ page }) => {
    await page.goto("/?scenario=features_off");
    await expect(page.getByRole("heading", { name: "Today", level: 1 })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Main" }).first()).toBeVisible();
    for (const nav of await page.getByRole("navigation", { name: "Main" }).all()) await expect(nav.getByRole("link", { name: "Circuits" })).toHaveCount(0);
    await page.goto("/circuits");
    await expect(page.getByRole("heading", { name: "We couldn't find that page" })).toBeVisible();
  });

  test("features on: Circuits sits in the middle of the bar", async ({ page }) => {
    await page.goto("/?scenario=default");
    const nav = page.getByRole("navigation", { name: "Main" }).locator("visible=true").first();
    await expect(nav.getByRole("link")).toHaveText(["Home", "Discover", "Circuits", "Inbox", "Profile"].map((t) => new RegExp(t)));
  });
});

test.describe("Circuits: accessibility", () => {
  test("axe is clean in both themes: the proposal, the closed ring and the empty state", async ({ page }) => {
    await open(page);
    await expect(proposal(page)).toBeVisible();
    await inBothThemes(page, (t) => checkPage(page, `circuits ${t}`));
    await arjunAnswers(page);
    await proposal(page).getByRole("button", { name: "Accept" }).click();
    await expect(proposal(page).getByRole("status")).toContainText("Circuit closed");
    await inBothThemes(page, (t) => checkPage(page, `circuits closed ${t}`));
    await lastWeek(page).getByRole("button", { name: "Mark my part done" }).click();
    await inBothThemes(page, (t) => checkPage(page, `mark done sheet ${t}`));
    await open(page, "empty");
    await inBothThemes(page, (t) => checkPage(page, `circuits empty ${t}`));
  });
});
