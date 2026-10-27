import { expect, test } from "@playwright/test";
import { checkPage, inBothThemes, isPhone, shot, signInAs } from "./helpers";

test.beforeEach(async ({ context }) => { await signInAs(context, "ravi"); });

test("Home in the new shell", async ({ page }, info) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Today", level: 1 })).toBeAttached();
  // The wire is a list when there are updates in the last 24h, one quiet line when there are none (depends on the data).
  await expect(page.getByRole("list", { name: "Live wire" }).or(page.getByText("Quiet on the wire today"))).toBeVisible();
  await page.waitForLoadState("networkidle");
  await inBothThemes(page, async (theme) => {
    await page.waitForTimeout(300);
    await checkPage(page, `home ${theme}`);
    await shot(page, "shell", `home-${isPhone(info) ? 375 : 1280}-${theme}`);
  });
});

test("the bar shows only tabs that are built (Circuits is built, Investor and Partner are not)", async ({ page }, info) => {
  await page.goto("/");
  const nav = page.getByRole("navigation", { name: "Main" }).filter({ visible: true });
  await expect(nav.getByRole("link")).toHaveText(["Home", "Discover", "Circuits", "Inbox", "Profile"]);
  void info;
});

test("with pulse and daily_drop off, Home has no wire, drop or Pulse and the bar is unchanged", async ({ page }) => {
  await page.route("**/api/config", async (route) => {
    const res = await route.fetch();
    const body = await res.json();
    await route.fulfill({ response: res, json: { ...body, features: { ...body.features, pulse: false, daily_drop: false } } });
  });
  await page.goto("/");
  await expect(page.getByText("Nothing on Home right now.", { exact: false })).toBeVisible();
  await expect(page.getByRole("list", { name: "Live wire" })).toHaveCount(0);
  await expect(page.getByText("Quiet on the wire today")).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Daily Drop" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Pulse" })).toHaveCount(0);
  await checkPage(page, "home, flags off");
});

test("investor and partner features stay hidden even when the server flag is on", async ({ page }) => {
  await page.route("**/api/config", async (route) => {
    const res = await route.fetch();
    const body = await res.json();
    await route.fulfill({ response: res, json: { ...body, features: Object.fromEntries(Object.keys(body.features).map((k) => [k, true])) } });
  });
  await page.goto("/");
  const nav = page.getByRole("navigation", { name: "Main" }).filter({ visible: true });
  await expect(nav.getByRole("link")).toHaveText(["Home", "Discover", "Circuits", "Inbox", "Profile"]);
});
