import { expect, test, type Page } from "@playwright/test";
import { checkPage as axeCheck, inBothThemes } from "../e2e/helpers";

/**
 * F6 build logs on mock mode (no backend). The composer: media first (up to 4, cropped and shrunk on the phone, each uploading with its
 * own progress, Retry when it fails), text with a 500 counter, up to 3 capability chips, a link, who can see it (under-18 starts on My
 * organisation), discard. The post view: media pager, reactions with no public counts (the author sees totals privately), one-level
 * replies, report, delete your own. Both hidden with the `pulse` flag off. Mock rules: src/data/mocks/posts.ts and inbox.ts (uploads).
 */

const checkPage = (page: Page, label: string) => axeCheck(page, label, { exclude: ["nav.material", "header.material", "div.material"] });

const composer = async (page: Page, scenario = "default") => {
  await page.goto(`/compose?scenario=${scenario}`);
  await expect(page.getByRole("heading", { name: "New build log" })).toBeVisible();
};
const post = (page: Page) => page.getByRole("button", { name: "Post", exact: true });
const body = (page: Page) => page.getByRole("textbox", { name: "What did you build?" });

/** Makes a PNG of the given size in the page (so the test needs no image files) and hands it to the hidden file input. */
async function addPhotos(page: Page, sizes: Array<[number, number]>) {
  const files = await page.evaluate(async (sz) => {
    const out: Array<{ name: string; data: string }> = [];
    for (const [w, h] of sz) {
      const c = document.createElement("canvas");
      c.width = w; c.height = h;
      const g = c.getContext("2d")!;
      g.fillStyle = "#1e5a46"; g.fillRect(0, 0, w, h);
      g.fillStyle = "#c8b478"; g.fillRect(w / 8, h / 6, (w * 3) / 4, (h * 2) / 3);
      const blob: Blob = await new Promise((r) => c.toBlob((b) => r(b!), "image/png"));
      const buf = new Uint8Array(await blob.arrayBuffer());
      let bin = "";
      for (const b of buf) bin += String.fromCharCode(b);
      out.push({ name: `photo-${w}x${h}.png`, data: btoa(bin) });
    }
    return out;
  }, sizes);
  await page.getByTestId("photo-input").setInputFiles(files.map((f) => ({ name: f.name, mimeType: "image/png", buffer: Buffer.from(f.data, "base64") })));
}

async function describe(page: Page, n: number, total: number, text: string) {
  await page.getByRole("button", { name: new RegExp(`^Photo ${n} of ${total}`) }).click();
  const sheet = page.getByRole("dialog", { name: "Crop and describe" });
  await sheet.getByRole("textbox", { name: "Description" }).fill(text);
  await sheet.getByRole("button", { name: "Done" }).click();
  await expect(sheet).toHaveCount(0);
}

test.describe("Composer", () => {
  test("text only: Post turns on, posting opens the new build log", async ({ page }) => {
    await composer(page);
    await expect(post(page)).toBeDisabled();
    await body(page).fill("Shipped offline mode for the farm map.");
    await expect(page.getByText("38 / 500")).toBeVisible();
    await post(page).click();
    await expect(page).toHaveURL(/\/posts\/9\d\d$/);
    await expect(page.getByText("Shipped offline mode for the farm map.")).toBeVisible();
    await expect(page.getByRole("status").filter({ hasText: "Posted." })).toBeVisible();
    // It shows up on your profile (reached in the app: a reload would start the mock afresh).
    await page.getByRole("article").getByRole("button", { name: /Ravi Kumar/ }).click();
    await expect(page.getByRole("list", { name: "Build logs" }).getByRole("link")).toHaveCount(3);
  });

  test("the counter stops at 500", async ({ page }) => {
    await composer(page);
    await body(page).fill("a".repeat(520));
    await expect(page.getByText("500 / 500")).toBeVisible();
  });

  test("photos upload with progress; Post waits for a description on each", async ({ page }) => {
    await composer(page, "slow3g");
    await addPhotos(page, [[1600, 1200], [900, 1600]]);
    await expect(page.getByRole("progressbar", { name: "Photo 1 of 2 upload" })).toBeVisible();
    await expect(page.getByRole("progressbar")).toHaveCount(0, { timeout: 20_000 });
    await expect(page.getByRole("radio", { name: "Square" })).toHaveAttribute("aria-checked", "true"); // the first photo is landscape
    await expect(page.getByText(/Add a description to each photo/)).toBeVisible();
    await expect(post(page)).toBeDisabled();
    await describe(page, 1, 2, "The farm map on a phone");
    await describe(page, 2, 2, "Plot details with soil moisture");
    await expect(post(page)).toBeEnabled();
    await post(page).click();
    await expect(page).toHaveURL(/\/posts\/9\d\d$/, { timeout: 15_000 });
    await expect(page.getByRole("img", { name: "The farm map on a phone" })).toBeVisible();
  });

  test("a failed upload says so on its tile, and Retry sends it again", async ({ page }) => {
    await composer(page, "upload_fails");
    await addPhotos(page, [[1200, 1500]]);
    await expect(page.getByRole("button", { name: "Retry Photo 1 of 1" })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("One photo didn't upload. Retry it or remove it.")).toBeVisible();
    await page.getByRole("button", { name: "Retry Photo 1 of 1" }).click();
    await expect(page.getByRole("button", { name: "Retry Photo 1 of 1" })).toHaveCount(0, { timeout: 10_000 });
    await expect(page.getByText(/Add a description to each photo/)).toBeVisible();
  });

  test("crop: the frame can be moved with the keyboard; up to 4 photos", async ({ page }) => {
    await composer(page);
    await addPhotos(page, [[1600, 1000], [1000, 1000], [1000, 1000], [1000, 1000], [1000, 1000]]);
    await expect(page.getByRole("status").filter({ hasText: "A build log takes up to 4 photos." })).toBeVisible();
    await expect(page.getByRole("button", { name: /^Remove Photo \d of 4$/ })).toHaveCount(4);
    await expect(page.getByRole("button", { name: "Add photo" })).toHaveCount(0);
    await page.getByRole("button", { name: /^Photo 1 of 4/ }).click();
    const crop = page.getByRole("slider", { name: /^Crop/ });
    await crop.focus();
    await page.keyboard.press("ArrowLeft");
    await expect(crop).toHaveAttribute("aria-valuenow", "45");
    await page.getByRole("dialog", { name: "Crop and describe" }).getByRole("button", { name: "Remove photo" }).click();
    await expect(page.getByRole("button", { name: /^Remove Photo \d of 3$/ })).toHaveCount(3);
  });

  test("up to 3 capability chips", async ({ page }) => {
    await composer(page);
    await page.getByRole("button", { name: "Add a skill" }).click();
    const sheet = page.getByRole("dialog", { name: "Tag up to 3 skills" });
    for (const name of ["Maps", "Dashboards", "Frontend development"]) await sheet.getByRole("button", { name, exact: true }).click();
    await expect(sheet.getByRole("button", { name: "Marketing", exact: true })).toBeDisabled();
    await sheet.getByRole("button", { name: "Done" }).click();
    await expect(page.getByRole("group", { name: "Capabilities" }).getByRole("button", { name: /^Remove/ })).toHaveCount(3);
    await expect(page.getByRole("button", { name: "Add a skill" })).toHaveCount(0);
  });

  test("link: a bad one blocks Post until fixed", async ({ page }) => {
    await composer(page);
    await body(page).fill("Demo is up.");
    await page.getByRole("button", { name: /^Add a link/ }).click();
    await page.getByRole("textbox", { name: "Link" }).fill("not a link");
    await page.getByRole("dialog", { name: "Add a link" }).getByRole("button", { name: "Done" }).click();
    await expect(post(page)).toBeDisabled();
    await expect(page.getByText("That link doesn't look right. Start it with https://")).toBeVisible();
    await page.getByRole("button", { name: /^Link/ }).click();
    await page.getByRole("textbox", { name: "Link" }).fill("https://github.com/ravikumar/farm-map");
    await page.getByRole("dialog", { name: "Add a link" }).getByRole("button", { name: "Done" }).click();
    await expect(page.getByRole("button", { name: /github\.com/ })).toBeVisible();
    await expect(post(page)).toBeEnabled();
  });

  test("who can see this: Everyone by default; under 18 starts on My organisation and can't pick Everyone", async ({ page }) => {
    await composer(page);
    await expect(page.getByRole("button", { name: /Who can see this\s*Everyone/ })).toBeVisible();
    await composer(page, "under18");
    await expect(page.getByRole("button", { name: /Who can see this\s*My organisation/ })).toBeVisible();
    await page.getByRole("button", { name: /Who can see this/ }).click();
    const sheet = page.getByRole("dialog", { name: "Who can see this" });
    await expect(sheet.getByRole("radio", { name: "Everyone" })).toBeDisabled();
    await expect(sheet.getByText("Posting to everyone opens once your age is verified.")).toBeVisible();
    await sheet.getByRole("radio", { name: "Connections" }).click();
    await expect(page.getByRole("button", { name: /Who can see this\s*Connections/ })).toBeVisible();
  });

  test("Cancel with something written asks before throwing it away", async ({ page }) => {
    await page.goto("/?scenario=default");
    await page.goto("/compose");
    await body(page).fill("Half a thought");
    await page.getByRole("button", { name: "Cancel" }).first().click();
    const sheet = page.getByRole("dialog", { name: "Discard this build log?" });
    await sheet.getByRole("button", { name: "Cancel" }).click();
    await expect(body(page)).toHaveValue("Half a thought");
    await page.getByRole("button", { name: "Cancel" }).first().click();
    await page.getByRole("dialog", { name: "Discard this build log?" }).getByRole("button", { name: "Discard" }).click();
    await expect(page).not.toHaveURL(/\/compose/);
  });

  test("the + on Home opens the composer", async ({ page }) => {
    await page.goto("/?scenario=default");
    await expect(page.getByRole("heading", { name: "Today", level: 1 })).toBeVisible();
    await page.getByRole("button", { name: "New build log" }).first().click();
    await expect(page).toHaveURL(/\/compose$/);
  });

  test("Pulse off: the composer is a 404", async ({ page }) => {
    await page.goto("/compose?scenario=pulse_off");
    await expect(page.getByRole("heading", { name: "We couldn't find that page" })).toBeVisible();
  });
});

test.describe("Post view", () => {
  const open = async (page: Page, id: number, scenario = "default") => {
    await page.goto(`/posts/${id}?scenario=${scenario}`);
    await expect(page.getByRole("article").first()).toBeVisible();
  };

  test("someone else's: media, reactions with no counts, threaded replies", async ({ page }) => {
    await open(page, 101);
    await expect(page.getByRole("img", { name: /Dashboard listing four medicines/ })).toBeVisible();
    const react = page.getByRole("group", { name: "React" });
    await expect(react.getByRole("button")).toHaveText(["Helpful", "Intro me", "Let's talk"]);
    await react.getByRole("button", { name: "Helpful" }).click();
    await expect(react.getByRole("button", { name: "Helpful" })).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByText(/\d+ (found it helpful|reactions?|likes?)/)).toHaveCount(0);
    const thread = page.getByRole("list", { name: "Replies", exact: true });
    await expect(thread.getByRole("article", { name: /^Dr\. Lakshmi Narayanan/ })).toBeVisible();
    await expect(page.getByRole("list", { name: "Replies to Dr. Lakshmi Narayanan" }).getByRole("article")).toHaveCount(1);
  });

  test("reply, and reply to a reply (one level only)", async ({ page }) => {
    await open(page, 101);
    const box = page.getByRole("textbox", { name: "Add a reply" });
    await box.fill("Does it work offline?");
    await page.getByRole("button", { name: "Send reply" }).click();
    await expect(page.getByRole("article", { name: /^Ravi Kumar/ })).toContainText("Does it work offline?");
    await page.getByRole("button", { name: "Reply to Dr. Lakshmi Narayanan" }).click();
    await expect(page.getByText("Replying to Dr. Lakshmi Narayanan")).toBeVisible();
    await box.fill("A week ahead sounds right.");
    await page.getByRole("button", { name: "Send reply" }).click();
    await expect(page.getByRole("list", { name: "Replies to Dr. Lakshmi Narayanan" }).getByRole("article")).toHaveCount(2);
    // Replies to replies have no Reply button of their own.
    await expect(page.getByRole("list", { name: "Replies to Dr. Lakshmi Narayanan" }).getByRole("button", { name: /^Reply to/ })).toHaveCount(0);
  });

  test("report the post or a reply", async ({ page }) => {
    await open(page, 101);
    await page.getByRole("button", { name: "More options", exact: true }).first().click();
    await page.getByRole("button", { name: "Report this build log" }).click();
    await page.getByRole("radio", { name: "Something else" }).click();
    await page.getByRole("button", { name: "Send report" }).click();
    await expect(page.getByRole("status").filter({ hasText: "Thanks. We'll look at this within a day." })).toBeVisible();
    await page.getByRole("button", { name: "More options for Dr. Lakshmi Narayanan's reply" }).click();
    await page.getByRole("button", { name: "Report this reply" }).click();
    await expect(page.getByRole("dialog", { name: "Report this reply?" })).toBeVisible();
  });

  test("Let's talk opens a message; Intro me opens the intro sheet", async ({ page }) => {
    await open(page, 101);
    await page.getByRole("button", { name: "Intro me" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await page.getByRole("button", { name: "Let's talk" }).click();
    await expect(page).toHaveURL(/\/inbox\/new\?to=4$/);
  });

  test("your own: private totals, no reactions, and Delete", async ({ page }) => {
    await open(page, 201);
    await expect(page.getByText("Only you see this: 4 found it helpful, 1 asked for an intro, 1 reply.")).toBeVisible();
    await expect(page.getByRole("group", { name: "React" })).toHaveCount(0);
    await page.getByRole("button", { name: "More options", exact: true }).first().click();
    const sheet = page.getByRole("dialog", { name: "Delete this build log?" });
    await sheet.getByRole("button", { name: "Delete build log" }).click();
    await expect(page).toHaveURL(/\/profile$/);
    await expect(page.getByRole("list", { name: "Build logs" }).getByRole("link")).toHaveCount(1);
  });

  test("the media pager keeps its own swipe and shows one dot per picture", async ({ page }) => {
    await open(page, 201);
    const pager = page.getByRole("group", { name: "Images, 2" });
    await expect(pager).toBeVisible();
    await expect(page.locator("[data-no-swipe]").filter({ has: pager })).toHaveCount(1);
  });

  test("under 18: no Intro me", async ({ page }) => {
    await open(page, 101, "under18");
    await expect(page.getByRole("button", { name: "Intro me" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Helpful" })).toBeVisible();
  });

  test("empty replies, loading, error and not found", async ({ page }) => {
    await open(page, 301);
    await expect(page.getByText("No replies yet. Ask Asha something about it.")).toBeVisible();
    await page.goto("/posts/101?scenario=you_loading");
    await expect(page.getByLabel("Loading build log")).toBeVisible();
    await page.goto("/posts/101?scenario=you_error");
    await expect(page.getByRole("alert").filter({ hasText: "Couldn't load this build log" })).toBeVisible();
    await page.goto("/posts/12345?scenario=default");
    await expect(page.getByRole("heading", { name: "We couldn't find that page" })).toBeVisible();
  });

  test("Pulse off: a post is a 404", async ({ page }) => {
    await page.goto("/posts/101?scenario=pulse_off");
    await expect(page.getByRole("heading", { name: "We couldn't find that page" })).toBeVisible();
  });
});

test.describe("Composer and post view: accessibility", () => {
  test("composer, empty and with a photo", async ({ page }) => {
    await composer(page);
    await inBothThemes(page, async (theme) => checkPage(page, `composer ${theme}`));
    await addPhotos(page, [[1200, 1500]]);
    await expect(page.getByRole("progressbar")).toHaveCount(0, { timeout: 10_000 });
    await inBothThemes(page, async (theme) => checkPage(page, `composer with photo ${theme}`));
  });

  test("post view, someone else's and your own", async ({ page }) => {
    await page.goto("/posts/101?scenario=default");
    await expect(page.getByRole("list", { name: "Replies", exact: true })).toBeVisible();
    await inBothThemes(page, async (theme) => checkPage(page, `post ${theme}`));
    await page.goto("/posts/201");
    await expect(page.getByText(/Only you see this/)).toBeVisible();
    await inBothThemes(page, async (theme) => checkPage(page, `own post ${theme}`));
  });
});
