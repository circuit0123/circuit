import { expect, test } from "@playwright/test";
import { alertOf, checkStep, edgeSwipe, intoOnboarding, isPhone, openAsNewMember, progressOf, serverState, signInByEmail } from "./signup-helpers";

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

const heading = (page: import("@playwright/test").Page, name: string) => page.getByRole("heading", { level: 1, name });

test.describe("onboarding: name, role, age, safety, where", () => {
  test("Name is prefilled from Google, asks for a first name, and Enter submits", async ({ page }, info) => {
    await intoOnboarding(page, "/", { google: true });
    await expect(heading(page, "What should we call you?")).toBeVisible();
    await expect(page.getByLabel("First name")).toHaveValue("Meera");
    await expect(page.getByLabel("Last name")).toHaveValue("Krishnan");
    await checkStep(page, info, "name");
    await page.getByLabel("First name").fill("");
    await page.getByLabel("First name").press("Enter");
    await expect(page.getByText("Add your first name.")).toBeVisible();
    await page.getByLabel("First name").fill("Meera");
    await page.getByLabel("Last name").press("Enter");
    await expect(heading(page, "What brings you here?")).toBeVisible();
    expect((await serverState(page)).me.name).toBe("Meera Krishnan");
  });

  test("Name by email starts empty", async ({ page }) => {
    await intoOnboarding(page);
    await expect(page.getByLabel("First name")).toHaveValue("");
    await expect(page.getByRole("button", { name: "Back" })).toHaveCount(0); // nothing to go back to inside sign-up
  });

  test("Role shows three rows, advances on tap, and saves the answer", async ({ page }, info) => {
    await intoOnboarding(page);
    await page.getByLabel("First name").fill("Ravi");
    await page.getByRole("button", { name: "Continue" }).click();
    await expect(heading(page, "What brings you here?")).toBeVisible();
    await expect(page.getByRole("button", { name: /^(Find work and internships|Build a startup|Mentor people)$/ })).toHaveCount(3);
    await expect(page.getByRole("button", { name: "Invest" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /Run a college/ })).toHaveCount(0);
    await checkStep(page, info, "role", { primary: 0 });
    await page.getByRole("button", { name: "Build a startup" }).click();
    await expect(heading(page, "Are you 18 or older?")).toBeVisible();
    const s = await serverState(page);
    expect(s.me.role).toBe("founder");
    expect(s.onboarding.answers.role).toEqual({ choice: "founder" });
  });

  test("a role link skips the Role screen and saves the role", async ({ page }) => {
    await intoOnboarding(page, "/join?role=founder&src=landing-founders");
    await page.getByLabel("First name").fill("Ravi");
    await page.getByRole("button", { name: "Continue" }).click();
    await expect(heading(page, "Are you 18 or older?")).toBeVisible();
    const s = await serverState(page);
    expect(s.me.role).toBe("founder");
    expect(s.onboarding.answers.role).toEqual({ choice: "founder" });
    expect(s.signup_source).toBe("landing-founders");
  });

  test("a link for a role that isn't built yet falls back to the Role screen", async ({ page }) => {
    await intoOnboarding(page, "/join?role=investor&src=landing-investors");
    await page.getByLabel("First name").fill("Ravi");
    await page.getByRole("button", { name: "Continue" }).click();
    await expect(heading(page, "What brings you here?")).toBeVisible();
  });

  test("Age: Yes goes straight to Where; Not yet shows the safety screen first", async ({ page }, info) => {
    await intoOnboarding(page);
    await page.getByLabel("First name").fill("Ravi");
    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByRole("button", { name: "Find work and internships" }).click();
    await expect(heading(page, "Are you 18 or older?")).toBeVisible();
    await checkStep(page, info, "age", { primary: 0 });
    await page.getByRole("button", { name: "Yes", exact: true }).click();
    await expect(heading(page, "Where are you based?")).toBeVisible();
    expect((await serverState(page)).me.profile_visibility).toBe("members");
  });

  test("under 18: Not yet → safety screen → private defaults saved → Where", async ({ page }, info) => {
    await intoOnboarding(page);
    await page.getByLabel("First name").fill("Ravi");
    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByRole("button", { name: "Find work and internships" }).click();
    await page.getByRole("button", { name: "Not yet" }).click();
    await expect(heading(page, "We've made a few things private.")).toBeVisible();
    await checkStep(page, info, "safety");
    await page.getByRole("button", { name: "Got it" }).click();
    await expect(heading(page, "Where are you based?")).toBeVisible();
    const s = await serverState(page);
    expect(s.me.profile_visibility).toBe("hidden");
    expect(s.me.allow_requests).toBe(false);
    expect(s.onboarding.answers.age).toEqual({ adult: false });
  });

  test("Where: Use my location saves a coarse point and the nearest city", async ({ page, context }, info) => {
    await context.grantPermissions(["geolocation"]);
    await context.setGeolocation({ latitude: 13.0827123, longitude: 80.2707456 });
    await intoOnboarding(page);
    await page.getByLabel("First name").fill("Ravi");
    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByRole("button", { name: "Find work and internships" }).click();
    await page.getByRole("button", { name: "Yes", exact: true }).click();
    await expect(heading(page, "Where are you based?")).toBeVisible();
    await checkStep(page, info, "where");
    await page.getByRole("button", { name: "Use my location" }).click();
    await expect.poll(async () => (await serverState(page)).me.city).toBe("Chennai");
    const s = await serverState(page);
    expect([s.me.lat, s.me.lng]).toEqual([13.08, 80.27]); // two decimals: about 1 km
  });

  test("Where: location off → one sentence, then Choose a city works", async ({ page }, info) => {
    await intoOnboarding(page);
    await page.getByLabel("First name").fill("Ravi");
    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByRole("button", { name: "Find work and internships" }).click();
    await page.getByRole("button", { name: "Yes", exact: true }).click();
    await page.getByRole("button", { name: "Use my location" }).click();
    await expect(alertOf(page)).toHaveText("Location is off. Choose a city instead.");
    await page.getByRole("button", { name: "Choose a city" }).click();
    const sheet = page.getByRole("dialog");
    await expect(sheet).toBeVisible();
    await checkStep(page, info, "where-cities");
    await sheet.getByLabel("Search cities").fill("mad");
    await expect(sheet.getByRole("button")).toHaveCount(1);
    await sheet.getByRole("button", { name: "Madurai" }).click();
    await expect.poll(async () => (await serverState(page)).me.city).toBe("Madurai");
    await expect(heading(page, "Almost there")).toBeVisible(); // the next screens arrive in F2 parts 3–4
  });

  test("reloading resumes on the screen you were on, with the progress kept", async ({ page }) => {
    await intoOnboarding(page);
    await page.getByLabel("First name").fill("Ravi");
    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByRole("button", { name: "Mentor people" }).click();
    await expect(heading(page, "Are you 18 or older?")).toBeVisible();
    const before = await progressOf(page);
    await page.reload();
    await expect(heading(page, "Are you 18 or older?")).toBeVisible();
    expect(await progressOf(page)).toBe(before);
  });

  test("progress grows with each screen and Back returns to the one before", async ({ page }) => {
    await intoOnboarding(page);
    const first = await progressOf(page);
    await page.getByLabel("First name").fill("Ravi");
    await page.getByRole("button", { name: "Continue" }).click();
    const second = await progressOf(page);
    expect(second).toBeGreaterThan(first);
    await page.getByRole("button", { name: "Back" }).click();
    await expect(heading(page, "What should we call you?")).toBeVisible();
    await expect(page.getByLabel("First name")).toHaveValue("Ravi"); // typed text is never lost
  });

  test("swiping from the left edge goes back (touch)", async ({ page }, info) => {
    test.skip(!isPhone(info), "a touch gesture");
    await page.emulateMedia({ reducedMotion: "no-preference" });
    await intoOnboarding(page);
    await page.getByLabel("First name").fill("Ravi");
    await page.getByRole("button", { name: "Continue" }).click();
    await expect(heading(page, "What brings you here?")).toBeVisible();
    await page.waitForTimeout(600);
    await edgeSwipe(page);
    await expect(heading(page, "What should we call you?")).toBeVisible();
  });

  test("a save that fails keeps the screen and says so in one sentence", async ({ page }) => {
    await intoOnboarding(page);
    await page.evaluate(() => localStorage.setItem("circuit.mock.fail", "onboarding")); // the mock drops the next save, like a lost connection
    await page.getByLabel("First name").fill("Ravi");
    await page.getByRole("button", { name: "Continue" }).click();
    await expect(alertOf(page)).toHaveText("Can't reach Circuit. Check your connection and try again.");
    await expect(page.getByLabel("First name")).toHaveValue("Ravi");
    await page.evaluate(() => localStorage.removeItem("circuit.mock.fail"));
    await page.getByRole("button", { name: "Continue" }).click(); // trying again works
    await expect(heading(page, "What brings you here?")).toBeVisible();
  });
});
