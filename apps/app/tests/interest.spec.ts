import { expect, test, type Page } from "@playwright/test";
import { checkPage, inBothThemes } from "../e2e/helpers";

/** H5: "I'm interested" on the Startup page and in the map popup (students only), in mock mode. Startup 42 starts interested; 44 does not. */

test.beforeEach(async ({ context }) => {
  await context.route(/tile\.openstreetmap\.org/, (r) => r.abort());
});

const interestedButton = (page: Page) => page.getByRole("button", { name: /^(I'm interested|Interested)/ });

test.describe("Startup page: I'm interested", () => {
  test("tap to say so, tap again to withdraw", async ({ page }) => {
    await page.goto("/startups/44?scenario=default");
    await expect(page.getByRole("heading", { name: "Medisetu", level: 1 })).toBeVisible();
    await expect(interestedButton(page)).toHaveText("I'm interested");
    await interestedButton(page).click();
    await expect(interestedButton(page)).toHaveText("Interested · tap to withdraw");
    await expect(interestedButton(page)).toHaveAttribute("aria-pressed", "true");
    await interestedButton(page).click();
    await expect(interestedButton(page)).toHaveText("I'm interested");
  });

  test("a startup I already tapped starts as interested", async ({ page }) => {
    await page.goto("/startups/42?scenario=default");
    await expect(interestedButton(page)).toHaveText("Interested · tap to withdraw");
  });

  test("a founder has no such button", async ({ page }) => {
    await page.goto("/startups/44?scenario=founder");
    await expect(page.getByRole("heading", { name: "Medisetu", level: 1 })).toBeVisible();
    await expect(interestedButton(page)).toHaveCount(0);
  });

  test("axe is clean in both themes", async ({ page }) => {
    await page.goto("/startups/44?scenario=default");
    await expect(interestedButton(page)).toBeVisible();
    await inBothThemes(page, async (theme) => checkPage(page, `startup interested ${theme}`));
  });
});

test.describe("Map popup: I'm interested", () => {
  test("a student can say so from the popup; a founder cannot", async ({ page }) => {
    await page.goto("/discover?scenario=default&s=map");
    await expect(page.getByRole("region", { name: "Map of startups near you" })).toBeVisible();
    await page.getByRole("button", { name: "Kalam Labs, not hiring" }).dispatchEvent("click");
    const sheet = page.getByRole("region", { name: "Selected startup" });
    await sheet.getByRole("button", { name: "I'm interested" }).click();
    await expect(sheet.getByRole("button", { name: "Interested · tap to withdraw" })).toBeVisible();
  });

  test("a founder sees no such button in the popup", async ({ page }) => {
    await page.goto("/discover?scenario=founder&s=map");
    await expect(page.getByRole("region", { name: "Map of startups near you" })).toBeVisible();
    await page.getByRole("button", { name: "Kalam Labs, not hiring" }).dispatchEvent("click");
    const sheet = page.getByRole("region", { name: "Selected startup" });
    await expect(sheet.getByRole("button", { name: "View startup" })).toBeVisible();
    await expect(sheet.getByRole("button", { name: /^(I'm interested|Interested)/ })).toHaveCount(0);
  });
});
