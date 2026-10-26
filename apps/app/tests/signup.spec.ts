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
    await expect(heading(page, "What are you working on?")).toBeVisible();
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

const BIO = "Third-year B.Tech student in Madurai. I build React apps with maps and dashboards, mostly for small farms. Looking for an internship and someone to help me with backend.";

/** The screen with this title, once the one before it has finished leaving (both are in the page while a step slides). */
async function onScreen(page: import("@playwright/test").Page, title: string) {
  await expect(heading(page, title)).toBeVisible();
  await expect(page.getByRole("main")).toHaveCount(1);
}

/** Name → Role → Age → Where (Madurai): ends on the Work screen. */
async function toWork(page: import("@playwright/test").Page, opts: { role?: string; scenario?: string } = {}) {
  await intoOnboarding(page, "/", { scenario: opts.scenario });
  await page.getByLabel("First name").fill("Ravi");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: opts.role ?? "Find work and internships" }).click();
  await page.getByRole("button", { name: "Yes", exact: true }).click();
  await page.getByRole("button", { name: "Choose a city" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Madurai" }).click();
  await onScreen(page, "What are you working on?");
}

/** Skips Work, then picks one chip from each searchable list: ends on the screen after Needs. */
async function throughPickers(page: import("@playwright/test").Page) {
  await page.getByRole("button", { name: "Skip" }).click();
  await onScreen(page, "Here's what you can offer.");
  await page.getByRole("button", { name: "Sales", exact: true }).click();
  await page.getByRole("button", { name: "Continue" }).click();
  await onScreen(page, "And what you need right now.");
  await page.getByRole("button", { name: "Marketing", exact: true }).click();
  await page.getByRole("button", { name: "Continue" }).click();
}

test.describe("onboarding: work, offers, needs, organisation", () => {
  test("Work → Offers: the bio becomes chips, already chosen; remove, add back, save", async ({ page }, info) => {
    await toWork(page);
    await checkStep(page, info, "work");
    await page.getByLabel("About your work").fill(BIO);
    await page.getByRole("button", { name: "Continue" }).click();
    await onScreen(page, "Here's what you can offer.");
    const pressed = (name: string) => page.getByRole("button", { name, exact: true });
    for (const n of ["Frontend development", "Maps", "Dashboards"]) await expect(pressed(n)).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByText("3 of 5")).toBeVisible();
    await checkStep(page, info, "offers");
    await pressed("Maps").click();
    await expect(pressed("Maps")).toHaveAttribute("aria-pressed", "false");
    await expect(page.getByText("2 of 5")).toBeVisible();
    await pressed("Maps").click(); // a removed chip stays so it can be added back
    await expect(page.getByText("3 of 5")).toBeVisible();
    await pressed("Dashboards").click();
    await page.getByRole("button", { name: "Continue" }).click();
    await onScreen(page, "And what you need right now.");
    const s = await serverState(page);
    expect(s.offers.map((o) => o.capability).sort()).toEqual(["frontend-dev", "maps"]);
    expect(s.me.bio).toBe(BIO);
  });

  test("Work: Enter makes a new line, Ctrl+Enter continues", async ({ page }) => {
    await toWork(page);
    const field = page.getByLabel("About your work");
    await field.fill("I build maps.");
    await field.press("Enter");
    await expect(field).toHaveValue("I build maps.\n");
    await onScreen(page, "What are you working on?");
    await field.press("Control+Enter");
    await onScreen(page, "Here's what you can offer.");
  });

  test("Offers: + Add searches the rest, and the sixth chip is refused", async ({ page }, info) => {
    await toWork(page);
    await page.getByLabel("About your work").fill(BIO);
    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByRole("button", { name: "Add a skill" }).click();
    const sheet = page.getByRole("dialog");
    await expect(sheet).toBeVisible();
    await checkStep(page, info, "offers-add");
    await sheet.getByLabel("Search skills").fill("sal");
    await expect(sheet.getByRole("button")).toHaveCount(1);
    await sheet.getByRole("button", { name: "Sales" }).click();
    await expect(sheet).toBeHidden();
    await expect(page.getByRole("button", { name: "Sales", exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByText("4 of 5")).toBeVisible();
    await page.getByRole("button", { name: "Add a skill" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Pitching" }).click();
    await expect(page.getByText("5 of 5")).toBeVisible();
    await page.getByRole("button", { name: "Add a skill" }).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(page.getByText("Up to 5. Remove one to add another.")).toBeVisible();
  });

  test("Needs: starts from the bio, holds three, and wants at least one", async ({ page }) => {
    await toWork(page);
    await page.getByLabel("About your work").fill(BIO);
    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByRole("button", { name: "Continue" }).click();
    await onScreen(page, "And what you need right now.");
    const backend = page.getByRole("button", { name: "Backend development", exact: true });
    await expect(backend).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByText("1 of 3")).toBeVisible();
    await backend.click();
    await page.getByRole("button", { name: "Continue" }).click();
    await expect(page.getByText("Pick at least one.")).toBeVisible();
    await onScreen(page, "And what you need right now.");
    await backend.click();
    for (const n of ["Sales", "Marketing"]) {
      await page.getByRole("button", { name: "Add a need" }).click();
      await page.getByRole("dialog").getByRole("button", { name: n }).click();
    }
    await expect(page.getByText("3 of 3")).toBeVisible();
    await page.getByRole("button", { name: "Add a need" }).click();
    await expect(page.getByText("Up to 3. Remove one to add another.")).toBeVisible();
    await page.getByRole("button", { name: "Continue" }).click();
    await onScreen(page, "Where do you study?");
    expect((await serverState(page)).needs.map((n) => n.capability).sort()).toEqual(["backend-dev", "marketing", "sales"]);
  });

  test("Skip on Work gives the searchable list, with no error shown", async ({ page }, info) => {
    await toWork(page);
    await page.getByRole("button", { name: "Skip" }).click();
    await onScreen(page, "Here's what you can offer.");
    await expect(alertOf(page)).toHaveCount(0);
    await expect(page.getByLabel("Search skills")).toBeVisible();
    await checkStep(page, info, "offers-list");
    await page.getByLabel("Search skills").fill("sal");
    await expect(page.getByRole("button", { name: "Sales", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Marketing", exact: true })).toHaveCount(0);
    await page.getByRole("button", { name: "Sales", exact: true }).click();
    await page.getByRole("button", { name: "Continue" }).click();
    await onScreen(page, "And what you need right now.");
    expect((await serverState(page)).offers.map((o) => o.capability)).toEqual(["sales"]);
  });

  test("AI down: the same searchable list, no error, saving works", async ({ page }) => {
    await toWork(page, { scenario: "signup_ai_down" });
    await page.getByLabel("About your work").fill(BIO);
    await page.getByRole("button", { name: "Continue" }).click();
    await onScreen(page, "Here's what you can offer.");
    await expect(alertOf(page)).toHaveCount(0);
    await expect(page.getByLabel("Search skills")).toBeVisible();
    await page.getByRole("button", { name: "Frontend development", exact: true }).click();
    await page.getByRole("button", { name: "Continue" }).click();
    await onScreen(page, "And what you need right now.");
    expect((await serverState(page)).offers.map((o) => o.capability)).toEqual(["frontend-dev"]);
  });

  test("Organisation: a result saves the college and moves on", async ({ page }, info) => {
    await toWork(page);
    await throughPickers(page);
    await onScreen(page, "Where do you study?");
    await checkStep(page, info, "organisation", { primary: 0 });
    await page.getByLabel("Search colleges").fill("thia");
    await page.getByRole("button", { name: "Thiagarajar College of Engineering" }).click();
    await onScreen(page, "Almost there");
    expect((await serverState(page)).me.college).toBe("Thiagarajar College of Engineering");
  });

  test("Organisation: a college that isn't listed can be used as typed", async ({ page }) => {
    await toWork(page);
    await throughPickers(page);
    await page.getByLabel("Search colleges").fill("Kamaraj Engineering College");
    await page.getByRole("button", { name: "Use “Kamaraj Engineering College”" }).click();
    await onScreen(page, "Almost there");
    expect((await serverState(page)).me.college).toBe("Kamaraj Engineering College");
  });

  test("Organisation: Skip saves nothing", async ({ page }) => {
    await toWork(page);
    await throughPickers(page);
    await page.getByRole("button", { name: "Skip" }).click();
    await onScreen(page, "Almost there");
    const s = await serverState(page);
    expect(s.me.college).toBe("");
    expect(s.onboarding.answers.organisation).toEqual({ skipped: true });
  });

  test("a college email skips Organisation: the college is already set", async ({ page }) => {
    await openAsNewMember(page, "/");
    await signInByEmail(page, "ravi@svit.edu.in");
    await page.getByRole("button", { name: "I agree" }).click();
    const invite = page.getByLabel("Invite code");
    await invite.fill("CIRCUIT-0001");
    await invite.press("Enter");
    await page.getByLabel("First name").fill("Ravi");
    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByRole("button", { name: "Find work and internships" }).click();
    await page.getByRole("button", { name: "Yes", exact: true }).click();
    await page.getByRole("button", { name: "Choose a city" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Madurai" }).click();
    await throughPickers(page);
    await onScreen(page, "Almost there");
    expect((await serverState(page)).me.college).toBe("Sri Venkateswara Institute of Technology");
  });

  test("a founder is never asked where they study", async ({ page }) => {
    await toWork(page, { role: "Build a startup" });
    await throughPickers(page);
    await onScreen(page, "Almost there");
  });

  test("Back keeps what was chosen, and a reload resumes on Needs", async ({ page }) => {
    await toWork(page);
    await page.getByLabel("About your work").fill(BIO);
    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByRole("button", { name: "Maps", exact: true }).click(); // removes Maps
    await page.getByRole("button", { name: "Continue" }).click();
    await onScreen(page, "And what you need right now.");
    await page.getByRole("button", { name: "Back", exact: true }).click();
    await onScreen(page, "Here's what you can offer.");
    await expect(page.getByRole("button", { name: "Maps", exact: true })).toHaveAttribute("aria-pressed", "false");
    await expect(page.getByRole("button", { name: "Dashboards", exact: true })).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("button", { name: "Continue" }).click();
    await onScreen(page, "And what you need right now.");
    await page.reload();
    await onScreen(page, "And what you need right now.");
  });
});
