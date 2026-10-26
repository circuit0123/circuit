import { expect, test, type Page } from "@playwright/test";
import { checkPage as axeCheck, inBothThemes } from "../e2e/helpers";

/**
 * F6 Settings on mock mode (no backend): the hub with each screen's value on its row, Edit profile, Privacy (under-18 rows locked and
 * explained), Notifications per type × channel, Appearance (theme, six accents with live preview, swipe toggle; saved on the member, so
 * it survives a reload), Blocked people, Export my data (preparing, ready, the email link: download, expired, someone else's), Delete
 * account behind a typed word and a confirm sheet, Help (FAQ, contact support, grievance officer), legal pages and Sign out. Every screen
 * in loading, error and slow 3G. Axe at 375px and 1280px, dark and light. Mock rules: src/data/mocks/settings.ts.
 */

const checkPage = (page: Page, label: string) => axeCheck(page, label, { exclude: ["nav.material", "header.material", "div.material"] });

const open = async (page: Page, path = "", scenario = "default") => {
  await page.goto(`/settings${path}?scenario=${scenario}`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
};
const row = (page: Page, name: string | RegExp) => page.getByRole("button", { name });
const toggle = (page: Page, name: string) => page.getByRole("switch", { name });

test.describe("Settings: hub", () => {
  test("groups and the value each screen holds", async ({ page }) => {
    await open(page);
    await expect(page.getByRole("heading", { name: "Settings", level: 1 })).toBeVisible();
    for (const h of ["Account", "Appearance", "Your data", "Help"]) await expect(page.getByRole("heading", { name: h, level: 2 })).toBeVisible();
    await expect(row(page, /^Edit profile\s*Ravi Kumar · r•••@gmail\.com/)).toBeVisible();
    await expect(row(page, /^Privacy\s*Members/)).toBeVisible();
    await expect(row(page, /^Notifications\s*All on/)).toBeVisible();
    await expect(row(page, /^Appearance\s*System · Emerald/)).toBeVisible();
    await expect(page.getByText("Circuit beta · Version dev · Policy 2026-10")).toBeVisible();
    await expect(page.getByText(/Mint/)).toHaveCount(0); // the API's "mint" is Emerald on screen
  });

  test("the profile gear opens Settings, and Back returns", async ({ page }, info) => {
    await page.goto("/profile?scenario=default");
    await expect(page.getByRole("region", { name: "About you" })).toBeVisible();
    if (info.project.name === "phone") await page.getByRole("button", { name: "Settings" }).first().click();
    else await page.getByRole("region", { name: "About you" }).getByRole("button", { name: "Settings" }).click();
    await expect(page.getByRole("heading", { name: "Settings", level: 1 })).toBeVisible();
    await page.getByRole("button", { name: "Back to Profile" }).click();
    await expect(page).toHaveURL(/\/profile(\?|$)/);
  });

  test("loading, error and slow 3G", async ({ page }) => {
    await page.goto("/settings?scenario=you_loading");
    await expect(page.getByLabel("Loading settings")).toBeVisible();
    await page.goto("/settings?scenario=you_error");
    await expect(page.getByRole("alert").filter({ hasText: "Couldn't load your settings" })).toBeVisible();
    await page.goto("/settings?scenario=slow3g");
    await expect(row(page, /^Privacy\s*Members/)).toBeVisible({ timeout: 15_000 });
  });

  test("Sign out ends the session", async ({ page }) => {
    await open(page);
    await page.getByRole("button", { name: "Sign out" }).last().click();
    await expect(page.getByRole("heading", { name: "Build with people near you." })).toBeVisible();
  });
});

test.describe("Settings: Edit profile", () => {
  test("change the bio and needs, save, and the profile shows it", async ({ page }) => {
    await open(page);
    await row(page, /^Edit profile/).click();
    await expect(page.getByRole("heading", { name: "Edit profile", level: 1 })).toBeVisible();
    await expect(page.getByRole("button", { name: "Save" })).toBeDisabled();
    await page.getByRole("textbox", { name: "About you" }).fill("Building offline-first maps for farmers in Thiruvallur.");
    await page.getByRole("group", { name: "What I need" }).getByRole("button", { name: "Remove Mentoring" }).click();
    await page.getByRole("button", { name: "Save" }).click();
    await expect(page).toHaveURL(/\/profile$/);
    await expect(page.getByRole("status").filter({ hasText: "Profile saved." })).toBeVisible();
    await expect(page.getByText("Building offline-first maps for farmers in Thiruvallur.")).toBeVisible();
    await expect(page.getByRole("list", { name: "Needs" }).getByRole("listitem")).toHaveText(["Backend development"]);
  });

  test("an empty name and a bad proof link are caught", async ({ page }) => {
    await open(page, "/profile");
    await page.getByRole("textbox", { name: "Name" }).fill("");
    await expect(page.getByText("Your name can't be empty.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Save" })).toBeDisabled();
    await page.getByRole("textbox", { name: "Name" }).fill("Ravi Kumar");
    await page.getByRole("textbox", { name: "Proof of work for Maps" }).fill("my site");
    await expect(page.getByText("Start the link with https://")).toBeVisible();
    await expect(page.getByRole("button", { name: "Save" })).toBeDisabled();
  });

  test("add an offer from the list; Discard changes asks first", async ({ page }) => {
    await open(page, "/profile");
    await page.getByRole("button", { name: "Add to what i offer" }).click();
    await page.getByRole("dialog", { name: "What I offer" }).getByRole("button", { name: "UI design", exact: true }).click();
    await page.getByRole("dialog", { name: "What I offer" }).getByRole("button", { name: "Done" }).click();
    await expect(page.getByRole("group", { name: "What I offer" }).getByText("UI design")).toBeVisible();
    await page.getByRole("button", { name: "Discard changes" }).click();
    await expect(page.getByRole("dialog", { name: "Discard your changes?" })).toBeVisible();
  });
});

test.describe("Settings: Privacy", () => {
  test("choose who can see your profile; toggles save at once", async ({ page }) => {
    await open(page);
    await row(page, /^Privacy\s*Members/).click();
    await page.getByRole("radio", { name: "Hidden" }).click();
    await expect(page.getByRole("radio", { name: "Hidden" })).toHaveAttribute("aria-checked", "true");
    await expect(page.getByText("Only your connections see your profile.")).toBeVisible();
    await toggle(page, "Visible to my organisation").click();
    await expect(toggle(page, "Visible to my organisation")).toHaveAttribute("aria-checked", "true");
    await page.getByRole("button", { name: "Back to Settings" }).click();
    await expect(row(page, /^Privacy\s*Hidden/)).toBeVisible();
  });

  test("circuits need a verified work email once turned off", async ({ page }) => {
    await open(page, "/privacy");
    await toggle(page, "Show me in circuits").click();
    await expect(toggle(page, "Show me in circuits")).toHaveAttribute("aria-checked", "false");
    await expect(toggle(page, "Show me in circuits")).toBeDisabled();
    await expect(page.getByText("Circuits need a verified work email (level 2).")).toBeVisible();
  });

  test("under 18: no public profile and no requests from strangers, and it says why", async ({ page }) => {
    await open(page, "/privacy", "under18");
    await expect(page.getByRole("radio", { name: /^Everyone/ })).toBeDisabled();
    await expect(page.getByRole("radio", { name: "Hidden" })).toHaveAttribute("aria-checked", "true");
    await expect(toggle(page, "Message requests from people you aren't connected to")).toBeDisabled();
    await expect(page.getByText(/Because you're under 18, your profile can't be public/)).toBeVisible();
    await expect(page.getByText("Under 18, only your connections can message you.")).toBeVisible();
    await page.getByRole("radio", { name: "Members" }).click();
    await expect(page.getByRole("radio", { name: "Members" })).toHaveAttribute("aria-checked", "true");
  });

  test("blocked people: Unblock", async ({ page }) => {
    await open(page, "/privacy");
    await row(page, /^Blocked people\s*1/).click();
    await expect(page.getByRole("heading", { name: "Blocked people", level: 1 })).toBeVisible();
    await page.getByRole("button", { name: "Unblock Karthik Selvam" }).click();
    await expect(page.getByText("You haven't blocked anyone.")).toBeVisible();
  });
});

test.describe("Settings: Notifications", () => {
  test("every type × channel is its own switch", async ({ page }) => {
    await open(page);
    await row(page, /^Notifications/).click();
    await expect(page.getByRole("switch")).toHaveCount(12);
    await expect(toggle(page, "Intros by email")).toHaveAttribute("aria-checked", "true");
    await expect(toggle(page, "Circuits by email")).toHaveAttribute("aria-checked", "false");
    await toggle(page, "Intros by email").click();
    await expect(toggle(page, "Intros by email")).toHaveAttribute("aria-checked", "false");
    for (const t of ["Intros", "Messages", "Applications", "Circuits", "Replies", "Announcements"]) await toggle(page, `${t} in the app`).click();
    await page.getByRole("button", { name: "Back to Settings" }).click();
    await expect(row(page, /^Notifications\s*Messages/)).toBeVisible(); // only Messages by email is left on
  });
});

test.describe("Settings: Appearance", () => {
  test("theme, accent and swipe apply at once and follow the member after a reload", async ({ page }) => {
    await open(page, "/appearance");
    await page.getByRole("radiogroup", { name: "Theme" }).getByRole("radio", { name: "Light" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await page.getByRole("radiogroup", { name: "Accent colour" }).getByRole("radio", { name: "Rose" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-accent", "rose");
    await expect(page.getByRole("group", { name: "Preview" })).toContainText("Divya shipped offline sync");
    await toggle(page, "Swipe between tabs").click();
    await expect(toggle(page, "Swipe between tabs")).toHaveAttribute("aria-checked", "false");
    await page.reload();
    await expect(page.getByRole("radiogroup", { name: "Accent colour" }).getByRole("radio", { name: "Rose" })).toHaveAttribute("aria-checked", "true");
    await expect(page.getByRole("radiogroup", { name: "Theme" }).getByRole("radio", { name: "Light" })).toHaveAttribute("aria-checked", "true");
    await expect(toggle(page, "Swipe between tabs")).toHaveAttribute("aria-checked", "false");
    await expect(page.locator("html")).toHaveAttribute("data-accent", "rose");
    // Put it back for the next tests (the mock keeps it in this browser's storage).
    await page.getByRole("radiogroup", { name: "Theme" }).getByRole("radio", { name: "System" }).click();
    await page.getByRole("radiogroup", { name: "Accent colour" }).getByRole("radio", { name: "Emerald" }).click();
    await toggle(page, "Swipe between tabs").click();
  });

  test("arrow keys move through the six accents", async ({ page }) => {
    await open(page, "/appearance");
    const group = page.getByRole("radiogroup", { name: "Accent colour" });
    await expect(group.getByRole("radio")).toHaveText(["Emerald", "Sky", "Indigo", "Rose", "Lime", "Mono"]);
    await group.getByRole("radio", { name: "Emerald" }).focus();
    await page.keyboard.press("ArrowRight");
    await expect(group.getByRole("radio", { name: "Sky" })).toHaveAttribute("aria-checked", "true");
    await page.keyboard.press("ArrowLeft");
    await expect(group.getByRole("radio", { name: "Emerald" })).toHaveAttribute("aria-checked", "true");
  });
});

test.describe("Settings: your data", () => {
  test("export: ask, then preparing", async ({ page }) => {
    await open(page, "/export");
    await page.getByRole("button", { name: "Ask for my data" }).click();
    await expect(page.getByText(/We're preparing your file/)).toBeVisible();
  });

  test("export ready: open the email link", async ({ page }) => {
    await open(page, "/export", "export_ready");
    await expect(page.getByText(/Your file is ready. Open the link we emailed you/)).toBeVisible();
    await page.goto("/settings/export?token=mock-ok");
    await expect(page.getByRole("link", { name: /^Download \(48 KB\)$/ })).toBeVisible();
    await page.goto("/settings/export?token=old");
    await expect(page.getByText("This link has expired. Ask for your data again to get a new one.")).toBeVisible();
    await page.goto("/settings/export?token=someone-else");
    await expect(page.getByText(/This link belongs to a different account/)).toBeVisible();
  });

  test("delete: type DELETE, confirm, and you're signed out", async ({ page }) => {
    await open(page);
    await row(page, "Delete account").click();
    const go = page.getByRole("button", { name: "Delete my account" });
    await expect(go).toBeDisabled();
    await page.getByRole("textbox", { name: "Type DELETE to confirm" }).fill("delete");
    await expect(go).toBeDisabled();
    await page.getByRole("textbox", { name: "Type DELETE to confirm" }).fill("DELETE");
    await go.click();
    const sheet = page.getByRole("dialog", { name: "Delete your account?" });
    await sheet.getByRole("button", { name: "Cancel" }).click();
    await expect(sheet).toHaveCount(0);
    await go.click();
    await page.getByRole("dialog", { name: "Delete your account?" }).getByRole("button", { name: "Delete account" }).click();
    await expect(page.getByRole("heading", { name: "Build with people near you." })).toBeVisible();
  });
});

test.describe("Settings: help and legal", () => {
  test("FAQ opens one answer at a time", async ({ page }) => {
    await open(page, "/help");
    const q = page.getByRole("button", { name: "What is a circuit?" });
    await expect(q).toHaveAttribute("aria-expanded", "false");
    await q.click();
    await expect(q).toHaveAttribute("aria-expanded", "true");
    await expect(page.getByText(/Three people who each help the next/)).toBeVisible();
  });

  test("contact support gives a reference; the grievance officer is listed", async ({ page }) => {
    await open(page);
    await row(page, "Contact support").click();
    await expect(page).toHaveURL(/\/settings\/help#contact$/);
    await page.getByRole("radiogroup", { name: "What is it about?" }).getByRole("radio", { name: "My data" }).click();
    await page.getByRole("textbox", { name: "How can we help?" }).fill("Please correct my college name.");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await expect(page.getByText(/Your reference is CIR-2026-0042/)).toBeVisible();
    await expect(page.getByRole("heading", { name: "Grievance Officer" })).toBeVisible();
  });

  test("legal pages say they're with the lawyer; an unknown one is a 404", async ({ page }) => {
    await open(page);
    await row(page, "Terms").click();
    await expect(page.getByRole("heading", { name: "Terms", level: 1 })).toBeVisible();
    await expect(page.getByText(/We're finishing this document with our lawyer/)).toBeVisible();
    await expect(page.getByText("You accepted policy version 2026-10.")).toBeVisible();
    await page.goto("/settings/legal/nope");
    await expect(page.getByRole("heading", { name: "We couldn't find that page" })).toBeVisible();
  });
});

test.describe("Settings: accessibility", () => {
  const SCREENS = [
    ["settings", ""], ["edit profile", "/profile"], ["privacy", "/privacy"], ["privacy under 18", "/privacy?scenario=under18"],
    ["notifications", "/notifications"], ["appearance", "/appearance"], ["blocked", "/blocked"], ["export", "/export"],
    ["delete", "/delete"], ["help", "/help"], ["terms", "/legal/terms"],
  ] as const;
  for (const [label, path] of SCREENS) {
    test(`${label}: no axe violations, no sideways scroll`, async ({ page }) => {
      await page.goto(`/settings${path}${path.includes("?") ? "" : "?scenario=default"}`);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await page.waitForTimeout(400);
      await inBothThemes(page, async (theme) => checkPage(page, `${label} ${theme}`));
    });
  }
});
