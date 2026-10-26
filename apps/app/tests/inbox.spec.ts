import { expect, test, type Page } from "@playwright/test";
import { checkPage as axeCheck, inBothThemes, isPhone } from "../e2e/helpers";

/**
 * F5 Inbox and Conversation on mock mode (no backend): Chats and Requests (none for under-18s), unread states and the tab dot, a live
 * message through the mock Realtime bus, New message, the conversation (bubbles, optimistic send with retry, image share, live reply,
 * no read receipts), requests (Accept, Decline), and Report and Block behind confirm sheets. Every scenario: empty, loading, error,
 * slow 3G, under-18. Axe at 375px and 1280px, dark and light. Mock rules are at the top of src/data/mocks/inbox.ts.
 */

/** The translucent bars take on what scrolls under them (see home.spec.ts); they are checked over plain content in foundation.spec.ts. */
const checkPage = (page: Page, label: string) => axeCheck(page, label, { exclude: ["nav.material", "header.material", "div.material"] });

const inbox = async (page: Page, scenario = "default") => {
  await page.goto(`/inbox?scenario=${scenario}`);
  await expect(page.getByRole("heading", { name: "Inbox", level: 1 })).toBeVisible();
};
const chat = async (page: Page, id: number, scenario = "default") => {
  await page.goto(`/inbox/${id}?scenario=${scenario}`);
  await expect(page.getByRole("log", { name: "Messages" })).toBeVisible();
};
const rows = (page: Page, name = "Chats") => page.getByRole("list", { name, exact: true }).getByRole("link");
const row = (page: Page, who: string) => page.getByRole("link", { name: new RegExp(`^${who}`) });
const messageBox = (page: Page) => page.getByRole("textbox", { name: "Message" });
const send = async (page: Page, text: string) => {
  await messageBox(page).fill(text);
  await page.getByRole("button", { name: "Send", exact: true }).click();
};
const bubble = (page: Page, text: string) => page.locator("[data-bubble]", { hasText: text });

/** A 4×3 PNG, enough for the upload path and a real <img>. */
const PNG = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAQAAAADCAIAAAA7ljmRAAAAEElEQVR4nGPQ398FRww4OQBTohGhQEda6QAAAABJRU5ErkJggg==", "base64");

test.describe("Inbox: folders and unread", () => {
  test("Chats: newest first, unread ones in semibold with a dot", async ({ page }) => {
    await inbox(page);
    await expect(page.getByRole("radio", { name: "Chats" })).toHaveAttribute("aria-checked", "true");
    await expect(rows(page)).toHaveCount(5);
    await expect(rows(page).first()).toContainText("Meera Krishnan");
    await expect(rows(page).first()).toContainText("Happy to intro you to Sakthi this week.");
    await expect(page.getByRole("list", { name: "Chats" }).getByRole("img", { name: "Unread" })).toHaveCount(2);
    const weight = (who: string) => row(page, who).getByText(who, { exact: true }).evaluate((e) => getComputedStyle(e).fontWeight);
    expect(await weight("Meera Krishnan")).toBe("600");
    expect(await weight("Divya Subramanian")).toBe("400");
    await expect(rows(page).nth(2)).toContainText("Yesterday");
  });

  test("the Inbox tab has a dot while something is unread", async ({ page }, info) => {
    await page.goto("/?scenario=default");
    await expect(page.getByRole("heading", { name: "Today", level: 1 })).toBeVisible();
    if (isPhone(info)) await expect(page.locator('nav.material a[href="/inbox"] .bg-live')).toHaveCount(1);
    else await expect(page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: /^Inbox\s*,\s*unread messages$/ })).toBeVisible();
  });

  test("Requests: first messages from people you're not connected to", async ({ page }) => {
    await inbox(page);
    await page.getByRole("radio", { name: "Requests" }).click();
    await expect(rows(page, "Requests")).toHaveCount(2);
    await expect(rows(page, "Requests").first()).toContainText("Rohan Gupta");
    await expect(rows(page, "Requests").nth(1)).toContainText("Sneha Pillai");
  });

  test("live: a new message arrives without a reload and the row turns unread", async ({ page }) => {
    await inbox(page);
    const farhan = row(page, "Farhan Ali");
    await expect(farhan).toContainText("Can you share the map prototype?");
    await expect(farhan).toContainText("Also, is the repo public?", { timeout: 10_000 });
    await expect(farhan.getByRole("img", { name: "Unread" })).toBeVisible();
    await expect(rows(page).first()).toContainText("Farhan Ali"); // newest first
  });

  test("under 18: no Requests folder at all", async ({ page }) => {
    await inbox(page, "under18");
    await expect(page.getByRole("radiogroup", { name: "Inbox folders" })).toHaveCount(0);
    await expect(rows(page)).toHaveCount(5);
    await expect(page.getByText("Rohan Gupta")).toHaveCount(0);
  });

  test("empty: one sentence per folder", async ({ page }) => {
    await inbox(page, "empty");
    await expect(page.getByText("No chats yet. When you connect with someone, your conversation shows up here.")).toBeVisible();
    await page.getByRole("radio", { name: "Requests" }).click();
    await expect(page.getByText("When someone you're not connected to writes to you, it waits here until you accept.")).toBeVisible();
  });

  test("loading, error and slow 3G", async ({ page }) => {
    await inbox(page, "connect_loading");
    await page.waitForTimeout(500);
    await expect(rows(page)).toHaveCount(0);
    await inbox(page, "connect_error");
    await expect(page.getByRole("alert").filter({ hasText: "Couldn" })).toContainText("Couldn't load your messages. Check your connection and pull to refresh.");
    await page.goto("/inbox?scenario=slow3g");
    await expect(rows(page)).toHaveCount(5, { timeout: 20_000 });
  });
});

test.describe("Inbox: new message", () => {
  test("New message lists your connections; an existing chat opens, someone new gets a draft", async ({ page }) => {
    await inbox(page);
    await page.getByRole("button", { name: "New message" }).click();
    const sheet = page.getByRole("dialog", { name: "New message" });
    await expect(sheet.getByRole("list", { name: "Your connections" }).getByRole("button")).toHaveCount(6);
    await sheet.getByRole("button", { name: /^Meera Krishnan/ }).click();
    await expect(page).toHaveURL(/\/inbox\/501$/);
    await page.getByRole("button", { name: "Back to Inbox" }).click();
    await expect(page).toHaveURL(/\/inbox(\?scenario=default)?$/);
    await page.getByRole("button", { name: "New message" }).click();
    await page.getByRole("dialog", { name: "New message" }).getByRole("button", { name: /^Dr\. Lakshmi Narayanan/ }).click();
    await expect(page).toHaveURL(/\/inbox\/new\?to=7$/);
    await expect(page.getByText("Your first message starts the conversation.", { exact: false })).toBeVisible();
    await send(page, "Hello Lakshmi, thank you for the intro to Asha.");
    await expect(page).toHaveURL(/\/inbox\/\d+$/);
    await expect(bubble(page, "thank you for the intro to Asha")).toBeVisible();
  });
});

test.describe("Conversation", () => {
  test("opens from the list, marks it read, own messages in primary and theirs on a surface", async ({ page }) => {
    await inbox(page);
    await row(page, "Meera Krishnan").click();
    await expect(page).toHaveURL(/\/inbox\/501$/);
    await expect(page.getByRole("log", { name: "Messages" })).toBeVisible();
    await expect(page.getByText("Mentor · Chennai")).toBeVisible();
    const bg = (text: string) => bubble(page, text).evaluate((e) => getComputedStyle(e).backgroundColor);
    expect(await bg("stuck on the backend")).toBe("rgb(0, 86, 63)");
    expect(await bg("Nicely done")).not.toBe("rgb(0, 86, 63)");
    // Read receipts are off: nothing says seen or read.
    await expect(page.getByText(/\b(Seen|Read)\b/)).toHaveCount(0);
    await page.getByRole("button", { name: "Back to Inbox" }).click();
    await expect(row(page, "Meera Krishnan").getByRole("img", { name: "Unread" })).toHaveCount(0);
  });

  test("sending is optimistic, and the reply arrives live", async ({ page }) => {
    await chat(page, 501);
    await send(page, "Yes please, that would be great.");
    await expect(bubble(page, "Yes please, that would be great.")).toBeVisible();
    await expect(messageBox(page)).toHaveValue("");
    await expect(page.locator('[data-state="sent"]', { hasText: "Yes please" })).toBeVisible();
    await expect(bubble(page, "Good. I'll write to Sakthi tonight.")).toBeVisible({ timeout: 10_000 });
  });

  test("a message that fails says so and sends on Retry", async ({ page }) => {
    await chat(page, 502, "send_fails");
    await send(page, "Sharing it tonight.");
    const failed = page.locator('[data-state="failed"]', { hasText: "Sharing it tonight." });
    await expect(failed).toBeVisible();
    await failed.getByRole("button", { name: "Not sent. Retry" }).click();
    await expect(page.locator('[data-state="sent"]', { hasText: "Sharing it tonight." })).toBeVisible();
    await expect(page.getByRole("button", { name: "Not sent. Retry" })).toHaveCount(0);
  });

  test("share an image", async ({ page }) => {
    await chat(page, 503);
    await expect(page.getByRole("button", { name: "Share an image" })).toBeVisible();
    await page.locator('input[type="file"]').setInputFiles({ name: "screen.png", mimeType: "image/png", buffer: PNG });
    await expect(page.locator('[data-state="sent"]').getByRole("img", { name: "Photo you sent" })).toBeVisible();
  });

  test("a file that isn't an image is refused before anything is sent", async ({ page }) => {
    await chat(page, 503);
    await page.locator('input[type="file"]').setInputFiles({ name: "notes.gif", mimeType: "image/gif", buffer: Buffer.from("GIF89a") });
    await expect(page.getByText("Send a JPEG, PNG or WebP image.")).toBeVisible();
  });

  test("a request waits for Accept before you can reply", async ({ page }) => {
    await chat(page, 506);
    await expect(messageBox(page)).toHaveCount(0);
    await expect(page.getByText("Rohan isn't one of your connections. Accept to reply.")).toBeVisible();
    await page.getByRole("button", { name: "Accept" }).click();
    await expect(messageBox(page)).toBeVisible();
    await send(page, "Sure, ask away.");
    await expect(bubble(page, "Sure, ask away.")).toBeVisible();
  });

  test("Decline a request (mock stand-in) takes you back to Inbox", async ({ page }) => {
    await chat(page, 507);
    await page.getByRole("button", { name: "Decline" }).click();
    await expect(page).toHaveURL(/\/inbox$/);
    await expect(page.getByText("Request declined.")).toBeVisible();
  });

  test("Report, behind a confirm sheet with a reason", async ({ page }) => {
    await chat(page, 501);
    await page.getByRole("button", { name: "Report or block" }).click();
    await page.getByRole("dialog", { name: "Meera" }).getByRole("button", { name: "Report Meera" }).click();
    const sheet = page.getByRole("dialog", { name: "Report Meera?" });
    await expect(sheet.getByRole("button", { name: "Send report" })).toBeDisabled();
    await sheet.getByRole("radio", { name: "Spam or a scam" }).click();
    await sheet.getByRole("button", { name: "Send report" }).click();
    await expect(page.getByText("Thanks. We'll look at this within a day.")).toBeVisible();
    await expect(sheet).toHaveCount(0);
  });

  test("Block, behind a confirm sheet, closes the conversation", async ({ page }) => {
    await inbox(page);
    await row(page, "Meera Krishnan").click();
    await page.getByRole("button", { name: "Report or block" }).click();
    await page.getByRole("dialog", { name: "Meera" }).getByRole("button", { name: "Block Meera" }).click();
    const sheet = page.getByRole("dialog", { name: "Block Meera?" });
    await expect(sheet).toContainText("you won't see each other's messages, posts or intro requests any more");
    await sheet.getByRole("button", { name: "Block Meera" }).click();
    await expect(page).toHaveURL(/\/inbox$/);
    await expect(page.getByText("Blocked Meera.")).toBeVisible();
    await expect(row(page, "Meera Krishnan")).toHaveCount(0);
  });

  test("a conversation that isn't yours is the 404 screen", async ({ page }) => {
    await page.goto("/inbox/999?scenario=default");
    await expect(page.getByRole("heading", { name: "We couldn't find that page" })).toBeVisible();
  });
});

test.describe("Inbox: accessibility", () => {
  test("axe is clean in both themes on every new screen and sheet", async ({ page }) => {
    await inbox(page);
    await expect(rows(page)).toHaveCount(5);
    await inBothThemes(page, (t) => checkPage(page, `inbox chats ${t}`));
    await page.getByRole("radio", { name: "Requests" }).click();
    await expect(rows(page, "Requests")).toHaveCount(2);
    await inBothThemes(page, (t) => checkPage(page, `inbox requests ${t}`));
    await page.getByRole("button", { name: "New message" }).click();
    await expect(page.getByRole("dialog", { name: "New message" }).getByRole("button").first()).toBeVisible();
    await inBothThemes(page, (t) => checkPage(page, `new message ${t}`));

    await chat(page, 501);
    await inBothThemes(page, (t) => checkPage(page, `conversation ${t}`));
    await page.getByRole("button", { name: "Report or block" }).click();
    await inBothThemes(page, (t) => checkPage(page, `conversation menu ${t}`));
    await page.getByRole("dialog", { name: "Meera" }).getByRole("button", { name: "Report Meera" }).click();
    await expect(page.getByRole("dialog", { name: "Report Meera?" })).toBeVisible();
    await inBothThemes(page, (t) => checkPage(page, `report sheet ${t}`));

    await chat(page, 506);
    await inBothThemes(page, (t) => checkPage(page, `request ${t}`));
    await chat(page, 502, "send_fails");
    await send(page, "Sharing it tonight.");
    await expect(page.getByRole("button", { name: "Not sent. Retry" })).toBeVisible();
    await inBothThemes(page, (t) => checkPage(page, `failed message ${t}`));

    await inbox(page, "under18");
    await inBothThemes(page, (t) => checkPage(page, `inbox under-18 ${t}`));
    await inbox(page, "empty");
    await inBothThemes(page, (t) => checkPage(page, `inbox empty ${t}`));
  });
});
