import { expect, test, type Page } from "@playwright/test";
import { checkPage as axeCheck, inBothThemes, isPhone } from "../e2e/helpers";

/**
 * F6 profiles on mock mode (no backend): your own profile (strength meter for you only, offers and needs, highlights, Build logs ·
 * Circuits · About, no public counts) and someone else's (Connect, Message, Intro via a mutual, Report and Block), an under-18 profile
 * that is private to strangers, and every scenario: empty, loading, error, slow 3G, under-18, features off, Pulse off. Axe at 375px and
 * 1280px, dark and light. Mock rules are at the top of src/data/mocks/profile.ts and posts.ts.
 */

const checkPage = (page: Page, label: string) => axeCheck(page, label, { exclude: ["nav.material", "header.material", "div.material"] });

const own = async (page: Page, scenario = "default") => {
  await page.goto(`/profile?scenario=${scenario}`);
  await expect(page.getByRole("region", { name: "About you" })).toBeVisible();
};
const person = async (page: Page, id: number, scenario = "default") => {
  await page.goto(`/members/${id}?scenario=${scenario}`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
};
const tab = (page: Page, name: string) => page.getByRole("radiogroup", { name: "Profile sections" }).getByRole("radio", { name });
const noPublicCounts = async (page: Page) => {
  await expect(page.getByText(/followers?|following|views|likes/i)).toHaveCount(0);
};

test.describe("Profile: your own", () => {
  test("who you are, what you offer and need, highlights and build logs", async ({ page }) => {
    await own(page);
    await expect(page.getByRole("heading", { name: "Ravi Kumar", level: 1 })).toBeVisible();
    await expect(page.getByText("Frontend developer · Chennai")).toBeVisible();
    await expect(page.getByRole("button", { name: "Edit profile" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Share" })).toBeVisible();
    await expect(page.getByRole("list", { name: "Offers" }).getByRole("listitem")).toHaveText(["Frontend development", "Maps", "Dashboards"]);
    await expect(page.getByRole("list", { name: "Needs" }).getByRole("listitem")).toHaveText(["Mentoring", "Backend development"]);
    await expect(page.getByRole("list", { name: "Highlights" }).getByRole("listitem")).toHaveCount(2);
    await expect(tab(page, "Build logs")).toHaveAttribute("aria-checked", "true");
    await expect(page.getByRole("list", { name: "Build logs" }).getByRole("link")).toHaveCount(2);
    await noPublicCounts(page);
  });

  test("a complete profile has no strength meter; Settings is one tap away", async ({ page }, info) => {
    await own(page);
    await expect(page.getByRole("progressbar", { name: "Profile strength" })).toHaveCount(0);
    if (isPhone(info)) await page.getByRole("button", { name: "Settings" }).first().click();
    else await page.getByRole("region", { name: "About you" }).getByRole("button", { name: "Settings" }).click();
    await expect(page).toHaveURL(/\/settings$/);
  });

  test("profile to fill in: the strength meter shows one next step, only to you", async ({ page }) => {
    await own(page, "profile_empty");
    const meter = page.getByRole("progressbar", { name: "Profile strength" });
    await expect(meter).toBeVisible();
    expect(Number(await meter.getAttribute("aria-valuenow"))).toBeLessThan(50);
    await expect(page.getByText("Only you see this.")).toBeVisible();
    await page.getByRole("link", { name: /^Next: Write two lines/ }).click();
    await expect(page).toHaveURL(/\/settings\/profile#bio$/);
    await expect(page.getByRole("textbox", { name: "About you" })).toBeVisible();
  });

  test("tabs: About lists skills with proof links; Circuits lists yours", async ({ page }) => {
    await own(page);
    await tab(page, "About").click();
    await expect(page.getByRole("link", { name: "Proof of work for Frontend development" })).toHaveAttribute("href", "https://github.com/ravikumar/farm-map");
    await tab(page, "Circuits").click();
    await expect(page.getByRole("region", { name: "Your work" }).getByRole("listitem").first()).toContainText(/circuit/i);
  });

  test("a build log tile opens the post", async ({ page }) => {
    await own(page);
    await page.getByRole("list", { name: "Build logs" }).getByRole("link").first().click();
    await expect(page).toHaveURL(/\/posts\/201$/);
    await expect(page.getByText(/Only you see this: 4 found it helpful/)).toBeVisible();
  });

  test("empty: offers and build logs each say what to do", async ({ page }) => {
    await own(page, "empty");
    await expect(page.getByText("Add what you can offer and what you need, so we can find your people.")).toBeVisible();
    await expect(page.getByText("Your build logs show here. Share what you're working on.")).toBeVisible();
    await page.getByRole("button", { name: "New build log" }).last().click();
    await expect(page).toHaveURL(/\/compose$/);
  });

  test("under 18: a Private badge and what it means", async ({ page }) => {
    await own(page, "under18");
    await expect(page.getByText("Private", { exact: true })).toBeVisible();
    await expect(page.getByText("Your profile is private. Only your connections and people in your organisation can see it.")).toBeVisible();
  });

  test("features off: no Build logs or Circuits tab, About only", async ({ page }) => {
    await own(page, "features_off");
    await expect(page.getByRole("radiogroup", { name: "Profile sections" })).toHaveCount(0);
    await expect(page.getByText("No skills added yet.").or(page.getByRole("link", { name: /Proof of work/ }))).toBeVisible();
  });

  test("Pulse off: no Build logs tab", async ({ page }) => {
    await own(page, "pulse_off");
    await expect(tab(page, "Build logs")).toHaveCount(0);
    await expect(tab(page, "Circuits")).toBeVisible();
  });

  test("loading, error and slow 3G", async ({ page }) => {
    await page.goto("/profile?scenario=you_loading");
    await expect(page.getByRole("region", { name: "Loading your profile" })).toBeVisible();
    await page.goto("/profile?scenario=you_error");
    await expect(page.getByRole("alert").filter({ hasText: "Couldn't load your profile" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
    await page.goto("/profile?scenario=slow3g");
    await expect(page.getByRole("region", { name: "Loading your profile" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Ravi Kumar", level: 1 })).toBeVisible({ timeout: 15_000 });
  });
});

test.describe("Profile: someone else", () => {
  test("Connect is the one primary action; then Request sent", async ({ page }) => {
    await person(page, 2);
    await expect(page.getByRole("heading", { name: /Asha Raman/, level: 1 })).toBeVisible();
    await expect(page.getByText("Building a Kannada voice assistant · Chennai · 4 mutual connections")).toBeVisible();
    await page.getByRole("button", { name: "Connect" }).click();
    await expect(page.getByRole("button", { name: "Request sent" })).toBeDisabled();
    await expect(page.getByRole("status").filter({ hasText: "Request sent to Asha." })).toBeVisible();
    await noPublicCounts(page);
  });

  test("offers, needs, highlights and build logs; About shows the bio", async ({ page }) => {
    await person(page, 2);
    await expect(page.getByRole("list", { name: "Offers" })).toContainText("Product management");
    await expect(page.getByRole("list", { name: "Needs" })).toContainText("Marketing");
    await expect(page.getByRole("list", { name: "Highlights" }).getByRole("listitem")).toHaveCount(1);
    await expect(page.getByRole("list", { name: "Build logs" }).getByRole("link")).toHaveCount(1);
    await tab(page, "About").click();
    await expect(page.getByText(/farmers who don't read English/)).toBeVisible();
  });

  test("Intro via a mutual opens the intro sheet", async ({ page }) => {
    await person(page, 2);
    await page.getByRole("button", { name: "Intro via Dr. Lakshmi Narayanan, mentor" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
  });

  test("Message starts a conversation", async ({ page }) => {
    await person(page, 2);
    await page.getByRole("button", { name: "Message" }).click();
    await expect(page).toHaveURL(/\/inbox\/new\?to=2$/);
  });

  test("already asked, already connected, no mutual connection", async ({ page }) => {
    await person(page, 3);
    await expect(page.getByRole("button", { name: "Request sent" })).toBeDisabled();
    await person(page, 4);
    await expect(page.getByRole("button", { name: "Connected" })).toBeDisabled();
    await expect(page.getByRole("button", { name: /^Intro via/ })).toHaveCount(0);
    await person(page, 5);
    await expect(page.getByRole("button", { name: "Connect" })).toBeVisible();
    await expect(page.getByRole("button", { name: /^Intro via/ })).toHaveCount(0);
  });

  test("under 18 and not connected: private, and no way to message", async ({ page }) => {
    await person(page, 11);
    await expect(page.getByText("This profile is private.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Message" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Connect" })).toHaveCount(0);
    await expect(page.getByRole("list", { name: "Offers" })).toHaveCount(0);
    await expect(page.locator("main").getByText(/under 18/i)).toHaveCount(0); // a stranger isn't told the person's age
  });

  test("Report and Block are two taps away, behind confirm sheets", async ({ page }) => {
    await person(page, 2);
    await page.getByRole("button", { name: "More: share, report, block" }).click();
    await page.getByRole("button", { name: "Report Asha" }).click();
    await page.getByRole("radio", { name: "Spam or a scam" }).click();
    await page.getByRole("button", { name: "Send report" }).click();
    await expect(page.getByRole("status").filter({ hasText: "Thanks. We'll look at this within a day." })).toBeVisible();
    await page.getByRole("button", { name: "More: share, report, block" }).click();
    await page.getByRole("button", { name: "Block Asha" }).click();
    await expect(page.getByRole("dialog", { name: "Block Asha?" })).toBeVisible();
    await page.getByRole("dialog", { name: "Block Asha?" }).getByRole("button", { name: "Block Asha" }).click();
    await expect(page.getByRole("status").filter({ hasText: "Blocked Asha." })).toBeVisible();
  });

  test("your own id goes to your profile; an unknown one is a 404", async ({ page }) => {
    await page.goto("/members/1");
    await expect(page).toHaveURL(/\/profile$/);
    await page.goto("/members/999");
    await expect(page.getByRole("heading", { name: "We couldn't find that page" })).toBeVisible();
  });

  test("Pulse names open profiles", async ({ page }) => {
    await page.goto("/?scenario=default");
    const post = page.getByRole("article").filter({ hasText: "Shipped the stock-alert screen today" });
    await post.getByRole("button", { name: /Arjun Mehta/ }).click();
    await expect(page).toHaveURL(/\/members\/4$/);
  });

  test("loading and error", async ({ page }) => {
    await page.goto("/members/2?scenario=you_loading");
    await expect(page.getByLabel("Loading profile")).toBeVisible();
    await page.goto("/members/2?scenario=you_error");
    await expect(page.getByRole("alert").filter({ hasText: "Couldn't load this profile" })).toBeVisible();
  });

  test("features off: About only", async ({ page }) => {
    await person(page, 2, "features_off");
    await expect(page.getByRole("radiogroup", { name: "Profile sections" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Connect" })).toBeVisible();
  });
});

test.describe("Profile: accessibility", () => {
  for (const [label, path] of [["own", "/profile"], ["own, to fill in", "/profile?scenario=profile_empty"], ["person", "/members/2"], ["private", "/members/11"]] as const) {
    test(`${label}: no axe violations, no sideways scroll`, async ({ page }) => {
      await page.goto(path.includes("?") ? path : `${path}?scenario=default`);
      await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
      await page.waitForTimeout(300);
      await inBothThemes(page, async (theme) => checkPage(page, `${label} ${theme}`));
    });
  }
});
