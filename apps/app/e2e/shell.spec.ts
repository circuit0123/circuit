import { expect, test } from "@playwright/test";
import { checkPage, inBothThemes, isPhone, shot, signInAs } from "./helpers";

test.beforeEach(async ({ context }) => { await signInAs(context, "ravi"); });

test("Home in the new shell", async ({ page }, info) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Today", level: 1 })).toBeAttached();
  await expect(page.getByRole("list", { name: "Live wire" })).toBeVisible();
  await page.waitForLoadState("networkidle");
  await inBothThemes(page, async (theme) => {
    await page.waitForTimeout(300);
    await checkPage(page, `home ${theme}`);
    await shot(page, "shell", `home-${isPhone(info) ? 375 : 1280}-${theme}`);
  });
});

test("the bar shows only tabs that are built", async ({ page }, info) => {
  await page.goto("/");
  const nav = page.getByRole("navigation", { name: "Main" }).filter({ visible: true });
  await expect(nav.getByRole("link")).toHaveText(["Home", "Discover", "Inbox", "Profile"]);
  void info;
});

test("with pulse and daily_drop off, Home is matches only and the bar is unchanged", async ({ page }) => {
  await page.route("**/api/config", async (route) => {
    const res = await route.fetch();
    const body = await res.json();
    await route.fulfill({ response: res, json: { ...body, features: { ...body.features, pulse: false, daily_drop: false } } });
  });
  await page.goto("/");
  await expect(page.getByRole("region", { name: "Worth meeting" })).toBeVisible();
  await expect(page.getByRole("list", { name: "Live wire" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Daily Drop" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Pulse" })).toHaveCount(0);
  await checkPage(page, "home, flags off");
});

test("circuits, investor and partner features stay hidden even when the server flag is on", async ({ page }) => {
  await page.route("**/api/config", async (route) => {
    const res = await route.fetch();
    const body = await res.json();
    await route.fulfill({ response: res, json: { ...body, features: Object.fromEntries(Object.keys(body.features).map((k) => [k, true])) } });
  });
  await page.goto("/");
  const nav = page.getByRole("navigation", { name: "Main" }).filter({ visible: true });
  await expect(nav.getByRole("link")).toHaveText(["Home", "Discover", "Inbox", "Profile"]);
});
