import { expect, test } from "@playwright/test";
import { APP, OFF } from "./support";

test("flags on: the investor tile on the home page goes straight into the app", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("a#investors")).toHaveAttribute("href", `${APP}/join?role=investor&src=landing-home`);
});

test.describe("flags off (build with every feature off)", () => {
  test.use({ baseURL: OFF });

  test("the investor tile opens /investors/ instead of the app", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("a#investors")).toHaveAttribute("href", "/investors/");
    await expect(page.locator("a#students")).toHaveAttribute("href", `${APP}/join?role=student&src=landing-home`);
  });
});
