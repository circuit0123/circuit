import { expect, test } from "@playwright/test";
import { checkPage, inBothThemes, isPhone, personaToken, shot, signInAs, STAGING, stubBackends } from "./helpers";

const size = (info: Parameters<typeof isPhone>[0]) => (isPhone(info) ? 375 : 1280);

test.describe("staging-like (Supabase stubbed)", () => {
  test.use({ baseURL: STAGING });
  test.afterEach(async ({ page }) => { await page.unrouteAll({ behavior: "ignoreErrors" }); });

  test("Welcome has one job: Continue with Google", async ({ page }, info) => {
    await stubBackends(page);
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Build with people near you.", level: 1 })).toBeVisible();
    await expect(page.getByText("Find work, collaborators and mentors who need what you're good at.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Continue with Google" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Use email instead" })).toBeVisible();
    await expect(page.getByText(/By continuing you agree to the Terms and Privacy Policy\./)).toBeVisible();
    await expect(page.getByRole("region", { name: "Demo people" })).toHaveCount(0);
    // Exactly one primary button on the screen.
    await inBothThemes(page, async (theme) => {
      await page.waitForTimeout(300);
      await checkPage(page, `welcome ${theme}`);
      await shot(page, "signin", `welcome-${size(info)}-${theme}`);
    });
  });

  test("Google sends the person to Supabase and back to /auth/callback", async ({ page }) => {
    const seen = await stubBackends(page);
    await page.goto("/");
    await page.getByRole("button", { name: "Continue with Google" }).click();
    await expect.poll(() => seen.authorize.length).toBeGreaterThan(0);
    const url = new URL(seen.authorize[0]);
    expect(url.searchParams.get("provider")).toBe("google");
    expect(url.searchParams.get("redirect_to")).toBe(`${STAGING}/auth/callback`);
  });

  test("email: address, then a 6-digit code that verifies on the last digit", async ({ page }, info) => {
    const token = await personaToken("ravi");
    const seen = await stubBackends(page, { personaToken: token });
    await page.goto("/");
    await page.getByRole("button", { name: "Use email instead" }).click();
    await expect(page.getByRole("heading", { name: "What's your email?" })).toBeVisible();

    // A bad address is an inline sentence, and what was typed stays.
    await page.getByLabel("Email").fill("not-an-email");
    await page.getByRole("button", { name: "Send code" }).click();
    await expect(page.locator("p[role=alert]")).toHaveText("Enter your email address, like name@example.com.");
    await expect(page.getByLabel("Email")).toHaveValue("not-an-email");
    await inBothThemes(page, async (theme) => { await page.waitForTimeout(200); await shot(page, "signin", `email-error-${size(info)}-${theme}`); });

    await page.getByLabel("Email").fill("someone@example.com");
    await page.keyboard.press("Enter");
    await expect(page.getByRole("heading", { name: "Check your inbox." })).toBeVisible();
    expect(seen.otp).toHaveLength(1);
    expect((seen.otp[0] as { email: string }).email).toBe("someone@example.com");
    await expect(page.getByText("We sent a 6-digit code to someone@example.com.")).toBeVisible();
    await expect(page.getByRole("button", { name: /Resend in \d+s/ })).toBeDisabled();
    await inBothThemes(page, async (theme) => {
      await page.waitForTimeout(200);
      await checkPage(page, `code ${theme}`);
      await shot(page, "signin", `code-${size(info)}-${theme}`);
    });

    // Typing digit by digit advances; the sixth verifies.
    const first = page.getByLabel("Digit 1 of 6");
    await first.click();
    await page.keyboard.type("123456");
    await expect.poll(() => seen.verify.length).toBe(1);
    expect(seen.verify[0]).toMatchObject({ email: "someone@example.com", token: "123456", type: "email" });
    // The session arrives, the sign-in screen is gone.
    await expect(page.getByRole("heading", { name: "Check your inbox." })).toHaveCount(0);
  });

  test("a wrong code is one inline sentence and the digits stay", async ({ page }) => {
    await stubBackends(page, { verify: "bad" });
    await page.goto("/");
    await page.getByRole("button", { name: "Use email instead" }).click();
    await page.getByLabel("Email").fill("someone@example.com");
    await page.getByRole("button", { name: "Send code" }).click();
    await page.getByLabel("Digit 1 of 6").fill("999999"); // a paste or autofill fills every box
    await expect(page.locator("p[role=alert]")).toHaveText("That code didn't work. Check it, or ask for a new one.");
    for (let i = 1; i <= 6; i++) await expect(page.getByLabel(`Digit ${i} of 6`)).toHaveValue("9");
  });

  test("back goes one screen at a time", async ({ page }) => {
    await stubBackends(page);
    await page.goto("/");
    await page.getByRole("button", { name: "Use email instead" }).click();
    await page.getByLabel("Email").fill("someone@example.com");
    await page.getByRole("button", { name: "Send code" }).click();
    await expect(page.getByRole("heading", { name: "Check your inbox." })).toBeVisible();
    await expect(page.getByRole("button", { name: "Back" })).toHaveCount(1); // the screen that is leaving is gone
    await page.getByRole("button", { name: "Back" }).click();
    await expect(page.getByLabel("Email")).toHaveValue("someone@example.com");
    await expect(page.getByRole("button", { name: "Back" })).toHaveCount(1);
    await page.getByRole("button", { name: "Back" }).click();
    await expect(page.getByRole("button", { name: "Continue with Google" })).toBeVisible();
  });

  test("/auth/callback says so when Google reports a problem", async ({ page }, info) => {
    await stubBackends(page);
    await page.goto("/auth/callback?error=access_denied&error_description=denied");
    await expect(page.getByRole("heading", { name: "Couldn't sign you in" })).toBeVisible();
    await checkPage(page, "callback error");
    await shot(page, "signin", `callback-error-${size(info)}-dark`);
    await page.getByRole("button", { name: "Back to sign-in" }).click();
    await expect(page.getByRole("button", { name: "Continue with Google" })).toBeVisible();
  });
});

test.describe("local dev (demo people)", () => {
  test("a demo person signs in and lands on Home", async ({ page }, info) => {
    await page.goto("/");
    const people = page.getByRole("region", { name: "Demo people" });
    await expect(people).toBeVisible();
    await page.waitForLoadState("networkidle");
    await inBothThemes(page, async (theme) => { await page.waitForTimeout(200); await shot(page, "signin", `welcome-dev-${size(info)}-${theme}`); });
    await people.getByRole("button", { name: /Ravi Kumar/ }).click();
    await expect(page.getByRole("heading", { name: "Home", level: 1 })).toBeAttached();
  });

  test("a signed-in person goes straight to Home", async ({ page, context }) => {
    await signInAs(context, "ravi");
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Home", level: 1 })).toBeAttached();
  });
});
