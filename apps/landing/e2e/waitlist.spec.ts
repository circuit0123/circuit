import { expect, test } from "@playwright/test";
import { fillWaitlist, mockWaitlist } from "./support";

const submit = (page: import("@playwright/test").Page) => page.getByRole("button", { name: "Join the waitlist" });

test("success: sends exactly email, role, city and src, then confirms", async ({ page }) => {
  const bodies = await mockWaitlist(page, () => ({ status: 202 }));
  await page.goto("/");
  await fillWaitlist(page, { email: "asha@example.com", role: "founder", city: "Pune" });
  await submit(page).click();
  await expect(page.getByRole("status")).toContainText("You’re on the list");
  expect(bodies).toEqual([{ email: "asha@example.com", role: "founder", city: "Pune", src: "landing-home" }]);
  await expect(submit(page)).toHaveCount(0);
});

test("duplicate: the API answers 202 again, so the message is identical and never says 'already'", async ({ page }) => {
  await mockWaitlist(page, () => ({ status: 202 }));
  const messages: string[] = [];
  for (let i = 0; i < 2; i++) {
    await page.goto("/");
    await fillWaitlist(page, { email: "asha@example.com" });
    await submit(page).click();
    messages.push((await page.getByRole("status").textContent()) ?? "");
  }
  expect(messages[0]).toBe(messages[1]);
  expect(messages.join(" ")).not.toMatch(/already|exists|registered/i);
});

test("invalid email (422): one sentence, typed values are kept", async ({ page }) => {
  await mockWaitlist(page, () => ({ status: 422, body: { error: { code: "validation_error" } } }));
  await page.goto("/");
  await fillWaitlist(page, { email: "asha@example.com", city: "Pune" });
  await submit(page).click();
  await expect(page.locator("#waitlist-msg").filter({ hasText: "Check your email address" })).toBeVisible();
  await expect(page.getByLabel("Email")).toHaveValue("asha@example.com");
  await expect(page.getByLabel("City")).toHaveValue("Pune");
});

test("rate limit (429): says to try again in an hour and does not retry", async ({ page }) => {
  const bodies = await mockWaitlist(page, () => ({ status: 429, body: { error: { code: "rate_limited" } } }));
  await page.goto("/");
  await fillWaitlist(page, { email: "asha@example.com" });
  await submit(page).click();
  await expect(page.locator("#waitlist-msg")).toContainText("Too many tries from this connection. Try again in an hour.");
  expect(bodies).toHaveLength(1);
});

test("server error (500): retries once, then shows the connection message and keeps the values", async ({ page }) => {
  const bodies = await mockWaitlist(page, () => ({ status: 500 }));
  await page.goto("/");
  await fillWaitlist(page, { email: "asha@example.com" });
  await submit(page).click();
  await expect(page.locator("#waitlist-msg")).toContainText("Couldn’t reach Circuit. Check your connection and try again.");
  expect(bodies).toHaveLength(2);
  await expect(page.getByLabel("Email")).toHaveValue("asha@example.com");
});

test("network failure: one retry that can succeed", async ({ page }) => {
  const bodies = await mockWaitlist(page, (_b, n) => (n === 1 ? "abort" : { status: 202 }));
  await page.goto("/");
  await fillWaitlist(page, { email: "asha@example.com" });
  await submit(page).click();
  await expect(page.getByRole("status")).toContainText("You’re on the list");
  expect(bodies).toHaveLength(2);
});

test("missing role or email is stopped by the browser before any request", async ({ page }) => {
  const bodies = await mockWaitlist(page, () => ({ status: 202 }));
  await page.goto("/");
  await page.getByLabel("Email").fill("asha@example.com");
  await submit(page).click();
  await expect(page.getByLabel("I am a")).toBeFocused();
  expect(bodies).toHaveLength(0);
});

test("the form is switched off in the server HTML and on once the page runs (no half-working form without JavaScript)", async ({ browser }) => {
  const ctx = await browser.newContext({ javaScriptEnabled: false });
  const page = await ctx.newPage();
  await page.goto("/");
  await expect(page.locator("#waitlist fieldset")).toHaveAttribute("disabled", "");
  await expect(page.getByRole("region", { name: "Introduction" }).getByRole("link", { name: "Join the beta" })).toBeVisible();
  await ctx.close();
});
