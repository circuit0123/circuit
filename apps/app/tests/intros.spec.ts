import { expect, test, type Page } from "@playwright/test";
import { checkPage as axeCheck, inBothThemes } from "../e2e/helpers";

/**
 * H4: answering intros and connection requests on mock mode. The "Waiting for you" section in the Inbox (connection requests, intros
 * through you, intros for you), "Your intros" with the 1–5 rating, Remove connection on a profile, and nothing for members with nothing
 * waiting or under 18. Mock rules are at the top of src/data/mocks/requests.ts (scenario `requests`).
 */

const checkPage = (page: Page, label: string) => axeCheck(page, label, { exclude: ["nav.material", "header.material", "div.material"] });

const inbox = async (page: Page, scenario = "requests") => {
  await page.goto(`/inbox?scenario=${scenario}`);
  await expect(page.getByRole("heading", { name: "Inbox", level: 1 })).toBeVisible();
};
const waiting = (page: Page) => page.getByRole("region", { name: "Waiting for you" });

test.describe("Inbox: waiting for you", () => {
  test("lists connection requests and the intros that need you", async ({ page }) => {
    await inbox(page);
    await expect(waiting(page)).toBeVisible();
    await expect(waiting(page).getByTestId("connection-request")).toHaveCount(2);
    await expect(waiting(page).getByTestId("intro-request")).toHaveCount(2);
    await expect(waiting(page).getByText("Loved your farm map build log.", { exact: false })).toBeVisible();
    await expect(waiting(page).getByText("Intro through you")).toBeVisible();
    await expect(waiting(page).getByText("Intro for you")).toBeVisible();
  });

  test("accepting a connection request removes it and says so", async ({ page }) => {
    await inbox(page);
    await waiting(page).getByRole("button", { name: "Accept connection request from Divya Menon" }).click();
    await expect(page.getByText("You're now connected with Divya.")).toBeVisible();
    await expect(waiting(page).getByTestId("connection-request")).toHaveCount(1);
  });

  test("declining a connection request removes it", async ({ page }) => {
    await inbox(page);
    await waiting(page).getByRole("button", { name: "Decline connection request from Rohan Gupta" }).click();
    await expect(page.getByText("Request declined.")).toBeVisible();
    await expect(waiting(page).getByTestId("connection-request")).toHaveCount(1);
  });

  test("the mutual connection passes an intro on, the person accepts theirs", async ({ page }) => {
    await inbox(page);
    await waiting(page).getByRole("button", { name: "Pass it on intro from Asha Raman" }).click();
    await expect(page.getByText("Passed it on.")).toBeVisible();
    await expect(waiting(page).getByTestId("intro-request")).toHaveCount(1);
    await waiting(page).getByRole("button", { name: "Accept intro from Sneha Pillai" }).click();
    await expect(page.getByText("Intro accepted.")).toBeVisible();
    await expect(waiting(page).getByTestId("intro-request")).toHaveCount(0);
  });

  test("declining an intro removes it", async ({ page }) => {
    await inbox(page);
    await waiting(page).getByRole("button", { name: "Decline intro from Sneha Pillai" }).click();
    await expect(page.getByText("Intro declined.")).toBeVisible();
    await expect(waiting(page).getByTestId("intro-request")).toHaveCount(1);
  });

  test("answering everything leaves no section", async ({ page }) => {
    await inbox(page);
    for (const name of ["Decline connection request from Divya Menon", "Decline connection request from Rohan Gupta", "Decline intro from Asha Raman", "Decline intro from Sneha Pillai"]) {
      await waiting(page).getByRole("button", { name }).click();
    }
    await expect(page.getByRole("heading", { name: "Waiting for you" })).toHaveCount(0);
  });

  test("nothing waiting: no section", async ({ page }) => {
    await inbox(page, "default");
    await expect(page.getByRole("heading", { name: "Waiting for you" })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Your intros" })).toHaveCount(0);
  });

  test("under 18: no intro calls are made", async ({ page }) => {
    const asked: string[] = [];
    page.on("request", (r) => { if (new URL(r.url()).pathname.endsWith("/api/intros")) asked.push(r.url()); });
    await inbox(page, "under18");
    await expect(page.getByRole("heading", { name: "Waiting for you" })).toHaveCount(0);
    expect(asked).toEqual([]);
  });
});

test.describe("Inbox: your intros", () => {
  test("each says where it stands; an accepted one can be rated once", async ({ page }) => {
    await inbox(page);
    const mine = page.getByRole("region", { name: "Your intros" });
    await expect(mine.getByTestId("sent-intro")).toHaveCount(2);
    await expect(mine.getByText("Waiting for Dr. Lakshmi Narayanan to pass it on")).toBeVisible();
    const arjun = mine.getByTestId("sent-intro").filter({ hasText: "Arjun Mehta" });
    await expect(arjun.getByText("Accepted")).toBeVisible();
    await arjun.getByRole("radio", { name: "4 out of 5" }).click();
    await expect(page.getByText("Thanks for rating.")).toBeVisible();
    await expect(arjun.getByText("You rated this intro.")).toBeVisible();
    await expect(arjun.getByRole("radio", { name: "4 out of 5" })).toBeChecked();
    await expect(arjun.getByRole("radio", { name: "2 out of 5" })).toBeDisabled();
  });
});

test.describe("Profile: remove a connection", () => {
  test("Remove connection is behind a confirm and turns the button back into Connect", async ({ page }) => {
    await page.goto("/members/7?scenario=default");
    await expect(page.getByRole("button", { name: "Connected" })).toBeVisible();
    await page.getByRole("button", { name: /^More/ }).click();
    await page.getByRole("button", { name: "Remove connection" }).click();
    await expect(page.getByText("You'll stop being connected.", { exact: false })).toBeVisible();
    await page.getByRole("button", { name: "Remove connection" }).last().click();
    await expect(page.getByText("Removed Lakshmi.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Connect", exact: true })).toBeVisible();
  });

  test("a stranger has no Remove connection", async ({ page }) => {
    await page.goto("/members/5?scenario=default");
    await page.getByRole("button", { name: /^More/ }).click();
    await expect(page.getByRole("button", { name: /^Report/ })).toBeVisible();
    await expect(page.getByRole("button", { name: "Remove connection" })).toHaveCount(0);
  });
});

test.describe("Inbox: waiting for you, accessibility", () => {
  test("axe is clean in both themes with intros and requests", async ({ page }) => {
    await inbox(page);
    await inBothThemes(page, async (theme) => {
      await checkPage(page, `inbox waiting ${theme}`);
    });
  });
});
