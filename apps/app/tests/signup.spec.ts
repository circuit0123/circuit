import { expect, test } from "@playwright/test";
import { alertOf, checkStep, openAsNewMember, serverState, signInByEmail } from "./signup-helpers";

/**
 * F2: sign-up and access, on mock mode (the "New member" scenario: a stateful fake of the API and of Supabase sign-in).
 * This file grows with each part of F2: sign-in, consent, invite and waitlist first; the onboarding steps after.
 */

test.describe("sign-in and access", () => {
  test("Welcome → email code → consent → invite code → in", async ({ page }, info) => {
    await openAsNewMember(page);
    await expect(page.getByRole("heading", { level: 1, name: "Build with people near you." })).toBeVisible();
    await checkStep(page, info, "welcome", { primary: 1 });

    await page.getByRole("button", { name: "Use email instead" }).click();
    await expect(page.getByRole("heading", { name: "What's your email?" })).toBeVisible();
    await page.getByLabel("Email").fill("ravi.new@example.com");
    await checkStep(page, info, "email");
    await page.getByRole("button", { name: "Send code" }).click();
    await expect(page.getByRole("heading", { name: "Check your inbox." })).toBeVisible();
    await expect(page.getByRole("button", { name: /Resend in \d+s/ })).toBeDisabled();
    await checkStep(page, info, "code");
    await page.getByLabel("Digit 1 of 6").fill("123456"); // a paste fills every box

    await expect(page.getByRole("heading", { name: "Before you start." })).toBeVisible();
    await checkStep(page, info, "consent");
    await page.getByRole("button", { name: "I agree" }).click();

    await expect(page.getByRole("heading", { name: "Got an invite code?" })).toBeVisible();
    const go = page.getByRole("button", { name: "Continue" });
    await expect(go).toBeDisabled();
    await checkStep(page, info, "invite");

    const field = page.getByLabel("Invite code");
    await field.fill("wrong-1");
    await expect(field).toHaveValue("WRONG-1");
    await go.click();
    await expect(alertOf(page)).toHaveText("That code didn't work. Check it, or ask whoever invited you for a new one.");
    await expect(field).toHaveValue("WRONG-1"); // what was typed is never cleared
    await checkStep(page, info, "invite-error");

    await field.fill("circuit-0001");
    await field.press("Enter");
    await expect(page.getByRole("heading", { name: "Got an invite code?" })).toHaveCount(0);
    expect((await serverState(page)).beta).toBe(true);
  });

  test("a wrong 6-digit code keeps the boxes and says why", async ({ page }) => {
    await openAsNewMember(page);
    await signInByEmail(page, "ravi.new@example.com", "000000");
    await expect(alertOf(page)).toContainText("didn't work");
    await expect(page.getByRole("heading", { name: "Check your inbox." })).toBeVisible();
  });

  test("Google goes to Supabase and comes back signed in", async ({ page }) => {
    await openAsNewMember(page);
    await page.getByRole("button", { name: "Continue with Google" }).click();
    await expect(page.getByRole("heading", { name: "Before you start." })).toBeVisible();
  });

  test("the resend button counts down and then offers a new code", async ({ page }) => {
    await page.clock.install();
    await openAsNewMember(page);
    await page.getByRole("button", { name: "Use email instead" }).click();
    await page.getByLabel("Email").fill("ravi.new@example.com");
    await page.getByRole("button", { name: "Send code" }).click();
    await expect(page.getByRole("button", { name: "Resend in 30s" })).toBeDisabled();
    for (let i = 0; i < 31; i++) { await page.clock.runFor(1000); await page.waitForTimeout(10); } // React schedules each second after it renders the last
    await expect(page.getByRole("button", { name: "Resend code" })).toBeEnabled();
  });

  test("an invite link signs in, then skips the invite screen", async ({ page }) => {
    await openAsNewMember(page, "/join?code=CIRCUIT-0001&src=invite");
    await expect(page.getByRole("heading", { level: 1, name: "Build with people near you." })).toBeVisible();
    await signInByEmail(page);
    await page.getByRole("button", { name: "I agree" }).click();
    await expect(page.getByRole("heading", { name: "Got an invite code?" })).toHaveCount(0);
    await expect.poll(async () => (await serverState(page)).beta).toBe(true);
  });

  test("a link with a bad code lands on the invite screen with the code filled in", async ({ page }) => {
    await openAsNewMember(page, "/join?code=NOPE-1234&src=invite");
    await signInByEmail(page);
    await page.getByRole("button", { name: "I agree" }).click();
    await expect(page.getByRole("heading", { name: "Got an invite code?" })).toBeVisible();
    await expect(page.getByLabel("Invite code")).toHaveValue("NOPE-1234");
    await expect(alertOf(page)).toContainText("didn't work");
  });

  test("an organisation invite joins the college", async ({ page }) => {
    await openAsNewMember(page, "/join?code=SVIT-2026&org=7&role=student&src=partner-invite");
    await signInByEmail(page);
    await page.getByRole("button", { name: "I agree" }).click();
    await expect.poll(async () => (await serverState(page)).me.organisation_id).toBe(7);
  });

  test("waitlist: role link → confirmation, same wording every time", async ({ page }, info) => {
    await openAsNewMember(page, "/join?role=founder&src=landing-founders");
    await signInByEmail(page, "founder.new@example.com");
    await page.getByRole("button", { name: "I agree" }).click();
    await page.getByRole("button", { name: "Join the waitlist" }).click();
    await expect(page.getByRole("heading", { name: "Join the waitlist." })).toBeVisible();
    await expect(page.getByText("founder.new@example.com")).toBeVisible();
    await checkStep(page, info, "waitlist");
    await page.getByRole("button", { name: "Join the waitlist" }).click();
    await expect(page.getByRole("heading", { name: "You're on the list." })).toBeVisible();
    await checkStep(page, info, "waitlist-done");
    const s = await serverState(page);
    expect(s.waitlist).toEqual([{ email: "founder.new@example.com", role: "founder", src: "landing-founders" }]);
  });

  test("waitlist without a role link asks for the role first", async ({ page }) => {
    await openAsNewMember(page);
    await signInByEmail(page);
    await page.getByRole("button", { name: "I agree" }).click();
    await page.getByRole("button", { name: "Join the waitlist" }).click();
    await expect(page.getByRole("heading", { name: "What brings you here?" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Invest" })).toHaveCount(0); // hidden while investor mode is off for this build
    await page.getByRole("button", { name: "Mentor people" }).click();
    await page.getByRole("button", { name: "Join the waitlist" }).click();
    await expect(page.getByRole("heading", { name: "You're on the list." })).toBeVisible();
    expect((await serverState(page)).waitlist[0].role).toBe("mentor");
  });
});
