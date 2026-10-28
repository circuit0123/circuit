import { expect, test, type Page } from "@playwright/test";
import { checkPage as axeCheck, inBothThemes, isPhone } from "../e2e/helpers";
import { drag } from "./touch";

/**
 * F4 Discover on mock mode (no backend): the four segments, search, filters, the promoted slot, the job page with one-click apply,
 * "Your applications", the founder's applicant view, the map (pins, sheet, Back restores pin and zoom) and the Startup page with Follow,
 * founders and the claim flow. Every scenario the brief names: empty, loading, error, under-18, features off. Axe at 375px and 1280px,
 * dark and light, on every new screen. Mock data rules are at the top of src/data/mocks/discover.ts.
 */

/** The translucent tab bar takes on what scrolls under it (see home.spec.ts); it is checked over plain content in foundation.spec.ts. */
const checkPage = (page: Page, label: string) => axeCheck(page, label, { exclude: ["nav.material"] });

// Map tiles come from the network; tests never use it, so tiles fail quietly and the map shows its plain background.
test.beforeEach(async ({ context }) => {
  await context.route(/tile\.openstreetmap\.org/, (r) => r.abort());
});

const discover = async (page: Page, segment: "people" | "startups" | "jobs" | "map" | null = null, scenario = "default") => {
  await page.goto(`/discover?scenario=${scenario}${segment ? `&s=${segment}` : ""}`);
  await expect(page.getByRole("radiogroup", { name: "Discover sections" }).first()).toBeVisible();
};
const segment = (page: Page, name: string) => page.getByRole("radio", { name }).first();
const roles = (page: Page) => page.getByRole("list", { name: "Roles", exact: true });

test.describe("Discover: segments, search and filters", () => {
  test("a student starts on Jobs: skills in demand on top, then roles that fit, in words not numbers", async ({ page }) => {
    await discover(page);
    await expect(segment(page, "Jobs")).toHaveAttribute("aria-checked", "true");
    const skills = page.getByRole("region", { name: "Skills in demand" });
    await expect(skills.getByRole("heading", { name: "Skills in demand near you" })).toBeVisible();
    await expect(skills).toContainText("have the most open roles within 10 km.");
    await expect(roles(page).getByRole("link")).toHaveCount(5); // the promoted role also has its own slot above
    await expect(roles(page).getByRole("link").first()).toContainText("Frontend intern");
    await expect(roles(page).getByRole("link").first()).toContainText("Strong skill match");
    await expect(roles(page)).not.toContainText("%");
    // Skills in demand comes before the roles.
    const [a, b] = [await skills.boundingBox(), await page.getByRole("region", { name: "Roles near you" }).boundingBox()];
    expect(a!.y).toBeLessThan(b!.y);
  });

  test("People and Startups are photo-first grids; arrow keys move between segments", async ({ page }) => {
    await discover(page, "people");
    const people = page.getByRole("list", { name: "People" });
    await expect(people.getByRole("listitem")).toHaveCount(5);
    await expect(people).toContainText("Bridge match");
    await expect(people.getByRole("link", { name: /^Rohan Gupta.*Founder, logistics.*Good match/ })).toHaveAttribute("href", "/members/6");
    await segment(page, "People").focus();
    await page.keyboard.press("ArrowRight");
    await expect(segment(page, "Startups")).toHaveAttribute("aria-checked", "true");
    const startups = page.getByRole("list", { name: "Startups" });
    await expect(startups.getByRole("link").first()).toContainText("Kalam Labs"); // closest first
    await expect(startups).toContainText("Hiring · 2 roles");
  });

  test("a person's tile opens their profile, where the intro is one tap away (F6)", async ({ page }) => {
    await discover(page, "people");
    await page.getByRole("link", { name: /^Rohan Gupta/ }).click();
    await expect(page).toHaveURL(/\/members\/6$/);
    await page.getByRole("button", { name: /^Intro via/ }).click();
    await expect(page.getByRole("dialog")).toContainText("Rohan");
    await expect(page.getByRole("dialog").getByRole("button", { name: "Send request" })).toBeVisible();
  });

  test("filters live in a bottom sheet and only change things on Show results", async ({ page }) => {
    await discover(page, "jobs");
    await page.getByRole("button", { name: "Filters", exact: true }).click();
    const sheet = page.getByRole("dialog", { name: "Filters" });
    await expect(sheet.getByRole("group", { name: "Type" })).toBeVisible();
    await expect(sheet.getByRole("group", { name: "Who" })).toHaveCount(0); // a People filter
    await sheet.getByRole("button", { name: "Within 10 km" }).click();
    await expect(roles(page).getByRole("link")).toHaveCount(5); // not applied yet
    await sheet.getByRole("button", { name: "Show results" }).click();
    await expect(page.getByRole("button", { name: "Filters · 1" })).toBeVisible();
    await expect(roles(page).getByRole("link")).toHaveCount(1); // only Aravind Pathology is within 10 km
    await page.getByRole("button", { name: "Filters · 1" }).click();
    await sheet.getByRole("button", { name: "Clear filters" }).click();
    await sheet.getByRole("button", { name: "Show results" }).click();
    await expect(roles(page).getByRole("link")).toHaveCount(5);
  });

  test("People filters by role and verified", async ({ page }) => {
    await discover(page, "people");
    await page.getByRole("button", { name: "Filters", exact: true }).click();
    const sheet = page.getByRole("dialog", { name: "Filters" });
    await sheet.getByRole("button", { name: "Mentors" }).click();
    await sheet.getByRole("button", { name: "Show results" }).click();
    await expect(page.getByRole("list", { name: "People" }).getByRole("listitem")).toHaveCount(1);
    await expect(page.getByRole("list", { name: "People" })).toContainText("Lakshmi");
  });

  test("one search looks through people, startups and roles", async ({ page }) => {
    await discover(page, "people");
    await page.getByRole("searchbox", { name: "Search people, startups and roles" }).fill("tatva");
    await expect(page.getByRole("region", { name: "Startups found" })).toContainText("Tatvagrid");
    await expect(page.getByRole("region", { name: "Roles found" })).toContainText("Mobile app intern");
    await expect(page.getByRole("region", { name: "People found" })).toHaveCount(0);
    await page.getByRole("searchbox").fill("kavya");
    await expect(page.getByRole("region", { name: "People found" })).toContainText("Kavya");
    await expect(page.getByRole("region", { name: "People found" }).getByRole("link", { name: /Kavya/ })).toHaveAttribute("href", "/members/5");
    await page.getByRole("searchbox").fill("zzzz");
    await expect(page.getByText("Nothing matches “zzzz”. Try a skill, a startup or a role.")).toBeVisible();
    await page.getByRole("searchbox").fill("");
    await expect(page.getByRole("list", { name: "People" })).toBeVisible();
  });

  test("the promoted slot is labelled, explains itself and can be hidden", async ({ page }) => {
    await discover(page, "jobs");
    const promo = page.getByRole("group", { name: "Promoted" });
    await expect(promo).toContainText("Promoted · Sutragrid");
    await promo.getByRole("button", { name: "About this promotion" }).click();
    const why = page.getByRole("dialog", { name: "Why am I seeing this?" });
    await expect(why).toContainText("Promoted to people in Chennai interested in frontend development.");
    await why.getByRole("button", { name: "Hide this" }).click();
    await expect(promo).toHaveCount(0);
    await segment(page, "Startups").click();
    await expect(page.getByRole("group", { name: "Promoted" })).toContainText("Promoted · Tatvagrid");
  });
});

test.describe("Discover: scenarios", () => {
  test("features off: no promoted slots, Discover itself still works", async ({ page }) => {
    await discover(page, "jobs", "features_off");
    await expect(roles(page).getByRole("link").first()).toBeVisible();
    await expect(page.getByRole("group", { name: "Promoted" })).toHaveCount(0);
    await segment(page, "Startups").click();
    await expect(page.getByRole("list", { name: "Startups" })).toBeVisible();
    await expect(page.getByRole("group", { name: "Promoted" })).toHaveCount(0);
  });

  test("under 18: only roles and promotions from verified startups, and no intro from a person's tile", async ({ page }) => {
    await discover(page, "jobs", "under18");
    await expect(roles(page).getByRole("link").first()).toBeVisible();
    await expect(page.getByText("Backend engineer intern")).toHaveCount(0); // Sutragrid is unclaimed, so its role and its promotion are hidden
    await expect(page.getByRole("group", { name: "Promoted" })).toHaveCount(0);
    await segment(page, "Startups").click();
    await expect(page.getByRole("group", { name: "Promoted" })).toContainText("Tatvagrid"); // verified
    await segment(page, "People").click();
    await expect(page.getByRole("list", { name: "People" }).getByRole("listitem").first()).toBeVisible();
    await expect(page.getByRole("list", { name: "People" }).getByRole("button")).toHaveCount(0);
  });

  test("under 18: a role from an unverified startup is not found", async ({ page }) => {
    await page.goto("/discover/jobs/304?scenario=under18");
    await expect(page.getByRole("heading", { name: "We couldn't find that page" })).toBeVisible();
  });

  test("empty: each segment says what to do next in one sentence", async ({ page }) => {
    await discover(page, "jobs", "empty");
    await expect(page.getByText("No open roles near you right now. Follow startups to hear when they hire.")).toBeVisible();
    await expect(page.getByRole("region", { name: "Skills in demand" })).toHaveCount(0);
    await segment(page, "People").click();
    await expect(page.getByText(/^No matches here yet\./)).toBeVisible();
    await segment(page, "Startups").click();
    await expect(page.getByText("No startups match these filters nearby. Try a wider distance.")).toBeVisible();
  });

  test("error: what happened and Try again, in every segment and on the pages", async ({ page }) => {
    await discover(page, "jobs", "discover_error");
    await expect(page.getByRole("alert").filter({ hasText: "Couldn't load jobs. Check your connection and pull to refresh." })).toBeVisible();
    await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
    await segment(page, "People").click();
    await expect(page.getByRole("alert").filter({ hasText: "Couldn't load people." })).toBeVisible();
    await segment(page, "Startups").click();
    await expect(page.getByRole("alert").filter({ hasText: "Couldn't load startups." })).toBeVisible();
    await segment(page, "Map").click();
    await expect(page.getByRole("alert").filter({ hasText: "Couldn't load startups on the map." })).toBeVisible();
    await page.goto("/discover/jobs/301");
    await expect(page.getByRole("alert").filter({ hasText: "Couldn't load this role." })).toBeVisible();
    await page.goto("/startups/42");
    await expect(page.getByRole("alert").filter({ hasText: "Couldn't load this startup." })).toBeVisible();
  });

  test("loading: skeletons in the segment, no spinner", async ({ page }) => {
    await discover(page, "jobs", "discover_loading");
    await expect(page.getByRole("region", { name: "Roles near you" }).locator(".skeleton").first()).toBeVisible();
    await segment(page, "People").click();
    await expect(page.getByRole("region", { name: "People" }).locator(".skeleton").first()).toBeVisible();
  });
});

test.describe("Job page and applying", () => {
  test("skill match, sticky Apply, one click, then it shows in Your applications", async ({ page }) => {
    await discover(page, "jobs");
    await expect(page.getByRole("link", { name: /Your applications/ })).toContainText("1");
    await roles(page).getByRole("link", { name: /Frontend intern/ }).click();
    await expect(page).toHaveURL(/\/discover\/jobs\/301$/);
    await expect(page.getByRole("heading", { name: "Frontend intern", level: 1 })).toBeVisible();
    await expect(page.getByRole("heading", { name: "You match 3 of 4 skills" })).toBeVisible();
    await expect(page.getByText("Backend development, not one of your skills yet")).toHaveCount(1);
    const apply = page.getByRole("button", { name: "Apply with your profile" });
    await expect(apply).toBeInViewport(); // sticky at the bottom
    await apply.click();
    await expect(page.getByRole("status").filter({ hasText: "Applied" })).toContainText("We'll tell you when Aravind Pathology replies.");
    await page.getByRole("button", { name: "Back to Discover" }).click();
    await expect(page.getByRole("link", { name: /Your applications/ })).toContainText("2");
    await page.getByRole("link", { name: /Your applications/ }).click();
    const list = page.getByRole("list", { name: "Applications" });
    await expect(list.getByRole("link")).toHaveCount(2);
    await expect(list.getByRole("link").first()).toContainText("Frontend intern");
    await expect(list.getByRole("link").first()).toContainText("Sent");
    await expect(list).toContainText("Shortlisted");
  });

  test("the job page links to its startup", async ({ page }) => {
    await page.goto("/discover/jobs/302");
    await page.getByRole("link", { name: /Tatvagrid · Agritech/ }).click();
    await expect(page.getByRole("heading", { name: "Tatvagrid", level: 1 })).toBeVisible();
  });

  test("an unknown role is the 404 screen", async ({ page }) => {
    await page.goto("/discover/jobs/999");
    await expect(page.getByRole("heading", { name: "We couldn't find that page" })).toBeVisible();
  });
});

test.describe("Founder applicant view", () => {
  test("founders see applicants ranked by skill match and can decide", async ({ page }) => {
    await page.goto("/discover/jobs/301?scenario=founder");
    await expect(page.getByRole("button", { name: "Apply with your profile" })).toHaveCount(0);
    await page.getByRole("button", { name: "See applicants" }).click();
    await expect(page).toHaveURL(/\/discover\/jobs\/301\/applicants$/);
    const list = page.getByRole("list", { name: "Applicants, best skill match first" });
    const items = list.getByRole("article");
    await expect(items).toHaveCount(4);
    await expect(items.nth(0)).toHaveAccessibleName("1. Karthik Selvam");
    await expect(items.nth(3)).toHaveAccessibleName("4. Deepika Rao");
    await expect(items.nth(0)).toContainText("Strong skill match");
    await expect(items.nth(0)).toContainText("New");
    await expect(items.nth(0).getByRole("link", { name: /github\.com\/karthik-selvam/ })).toHaveAttribute("target", "_blank");
    await expect(list).not.toContainText("college");
    const shortlist = items.nth(0).getByRole("button", { name: "Shortlist" });
    await shortlist.click();
    await expect(shortlist).toHaveAttribute("aria-pressed", "true");
    await expect(items.nth(0).getByRole("status")).toHaveText("Shortlisted");
  });

  test("anyone else gets the 404 screen", async ({ page }) => {
    await page.goto("/discover/jobs/301/applicants");
    await expect(page.getByRole("heading", { name: "We couldn't find that page" })).toBeVisible();
  });
});

const pin = (page: Page, name: RegExp | string) => page.getByRole("button", { name });
const mapView = (page: Page) => page.evaluate(() => JSON.parse(sessionStorage.getItem("circuit.discover.map") ?? "null"));

test.describe("Map", () => {
  test("zoomed out past a city, the map asks to zoom in instead of showing an error", async ({ page }) => {
    await page.addInitScript(() => sessionStorage.setItem("circuit.discover.map", JSON.stringify({ lat: 13.08, lng: 80.27, zoom: 6, selected: null })));
    await discover(page, "map");
    await expect(page.getByText("Zoom in to see startups.")).toBeVisible();
    await expect(page.getByRole("alert").filter({ hasText: "Couldn't load startups on the map." })).toHaveCount(0);
  });

  test("pins by hiring status; a tap opens the sheet and never navigates", async ({ page }) => {
    await discover(page, "map");
    await expect(page.getByRole("region", { name: "Map of startups near you" })).toBeVisible();
    await expect(pin(page, "Aravind Pathology, hiring")).toBeAttached();
    await expect(pin(page, "Kalam Labs, not hiring")).toBeAttached();
    await pin(page, "Aravind Pathology, hiring").dispatchEvent("click");
    await expect(page).toHaveURL(/\/discover/);
    const sheet = page.getByRole("region", { name: "Selected startup" });
    await expect(sheet.getByRole("heading", { name: "Aravind Pathology" })).toBeVisible();
    await expect(sheet).toContainText("Healthtech · 8.6 km");
    await expect(sheet).toContainText("Hiring · Frontend intern · Strong skill match");
    await expect(pin(page, "Aravind Pathology, hiring")).toHaveAttribute("aria-pressed", "true");
    await page.keyboard.press("Escape");
    await expect(sheet).toHaveCount(0);
  });

  test("one open role: See open roles opens the job; Back returns to the same pin and zoom", async ({ page }) => {
    await discover(page, "map");
    await pin(page, "Aravind Pathology, hiring").dispatchEvent("click");
    await expect(page.getByRole("button", { name: "See open roles" })).toBeEnabled();
    await page.waitForTimeout(600); // the pin glides above the sheet; the view is saved when it stops
    const before = await mapView(page);
    await page.getByRole("button", { name: "See open roles" }).click();
    await expect(page).toHaveURL(/\/discover\/jobs\/301$/);
    await expect(page.getByRole("region", { name: "Map of startups near you" })).toBeHidden();
    await page.getByRole("button", { name: "Back to Discover" }).click();
    await expect(page.getByRole("region", { name: "Map of startups near you" })).toBeVisible();
    await expect(pin(page, "Aravind Pathology, hiring")).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByRole("region", { name: "Selected startup" })).toContainText("Aravind Pathology");
    const after = await mapView(page);
    expect(after.zoom).toBeCloseTo(before.zoom, 3);
    expect(after.lat).toBeCloseTo(before.lat, 4);
    expect(after.selected).toBe(41);
  });

  test("more than one role: See open roles opens the Startup page at Hiring", async ({ page }) => {
    await discover(page, "map");
    await pin(page, "Tatvagrid, hiring").dispatchEvent("click");
    await expect(page.getByRole("region", { name: "Selected startup" })).toContainText("2 open roles");
    await page.getByRole("button", { name: "See open roles" }).click();
    await expect(page).toHaveURL(/\/startups\/42#hiring$/);
    await expect(page.getByRole("region", { name: "Hiring" }).getByRole("heading", { name: "Hiring" })).toBeInViewport();
  });

  test("a startup that isn't hiring offers Follow", async ({ page }) => {
    await discover(page, "map");
    await pin(page, "Medisetu, not hiring").dispatchEvent("click");
    const sheet = page.getByRole("region", { name: "Selected startup" });
    await expect(sheet).toContainText("Not hiring right now · Follow for updates");
    await expect(sheet.getByRole("button", { name: "See open roles" })).toHaveCount(0);
    await sheet.getByRole("button", { name: "Follow" }).click();
    await expect(sheet.getByRole("button", { name: "Following" })).toHaveAttribute("aria-pressed", "true");
  });

  test("hiring with no roles on Circuit: the sheet links to their careers page", async ({ page }) => {
    await discover(page, "map");
    await pin(page, "Ledgerly, hiring").dispatchEvent("click");
    const sheet = page.getByRole("region", { name: "Selected startup" });
    const link = sheet.getByRole("link", { name: /Hiring · see their careers page/ });
    await expect(link).toHaveAttribute("href", "https://ledgerly.in/careers");
    await expect(link).toHaveAttribute("target", "_blank");
    await expect(sheet).not.toContainText("Not hiring");
    await expect(sheet.getByRole("button", { name: "See open roles" })).toHaveCount(0);
    await inBothThemes(page, () => checkPage(page, "map sheet, careers page"));
  });

  test.describe("by touch", () => {
    test.use({ reducedMotion: "no-preference", hasTouch: true });
    test("a sideways swipe on the map pans the map and never changes tab (DESIGN.md §3)", async ({ page }, info) => {
      test.skip(!isPhone(info), "tab swiping is a phone gesture");
      await discover(page, "map");
      await expect(pin(page, "Aravind Pathology, hiring")).toBeAttached();
      const before = await mapView(page);
      await drag(page, { x: 320, y: 420 }, { x: 40, y: 430 });
      await page.waitForTimeout(800);
      await expect(page).toHaveURL(/\/discover/);
      await expect(page.getByRole("region", { name: "Map of startups near you" })).toBeVisible();
      expect((await mapView(page)).lng).toBeGreaterThan(before.lng); // dragged left: the map moved east
    });
  });

  test("the Hiring chip filters pins", async ({ page }) => {
    await discover(page, "map");
    await expect(pin(page, "Kalam Labs, not hiring")).toBeAttached();
    await page.getByRole("group", { name: "Map filters" }).getByRole("button", { name: "Hiring" }).click();
    await expect(pin(page, "Kalam Labs, not hiring")).toHaveCount(0);
    await expect(pin(page, "Aravind Pathology, hiring")).toBeAttached();
  });
});

test.describe("Startup page", () => {
  test("header, Follow, Hiring first, About, build logs and founders with an intro via a mutual", async ({ page }) => {
    await page.goto("/startups/42");
    await expect(page.getByRole("heading", { name: "Tatvagrid", level: 1 })).toBeVisible();
    await expect(page.getByText("Agritech · Pre-seed · 4 people")).toBeVisible();
    await expect(page.getByText("Claimed by its team")).toBeVisible();
    const follow = page.getByRole("button", { name: "Follow", exact: true });
    await follow.click();
    await expect(page.getByRole("button", { name: "Following" })).toHaveAttribute("aria-pressed", "true");
    const order = await page.locator("main section[aria-label]").evaluateAll((els) => els.map((e) => e.getAttribute("aria-label")));
    expect(order).toEqual(["Hiring", "About", "Build logs", "Founders"]);
    await expect(page.getByRole("list", { name: "Open roles" }).getByRole("link")).toHaveCount(2);
    await expect(page.getByRole("list", { name: "Open roles" })).toContainText("₹15k/mo");
    await expect(page.getByRole("region", { name: "Build logs" }).getByRole("img")).toHaveCount(1);
    await expect(page.getByRole("region", { name: "About" })).not.toContainText("views");
    await page.getByRole("button", { name: "Intro via Lakshmi" }).click();
    await expect(page.getByRole("dialog")).toContainText("Lakshmi");
  });

  test("no public counts; the team sees its own views privately", async ({ page }) => {
    await page.goto("/startups/41");
    await expect(page.getByRole("heading", { name: "Aravind Pathology", level: 1 })).toBeVisible();
    await expect(page.getByText(/Only your team sees this/)).toHaveCount(0);
    await page.goto("/startups/41?scenario=founder");
    await expect(page.getByText(/Only your team sees this: 214 views/)).toBeVisible();
  });

  test("hiring with no roles on Circuit: Hiring, with a link to their careers page", async ({ page }) => {
    await page.goto("/startups/48");
    await expect(page.getByRole("heading", { name: "Hiring", exact: true })).toBeVisible();
    const link = page.getByRole("link", { name: /Hiring · see their careers page/ });
    await expect(link).toHaveAttribute("href", "https://ledgerly.in/careers");
    await expect(link).toHaveAttribute("target", "_blank");
    await expect(page.getByText("Not hiring")).toHaveCount(0);
    await inBothThemes(page, () => checkPage(page, "startup page, careers page"));
  });

  test("Startups grid says Hiring, not 0 roles, for a startup with only a careers page", async ({ page }) => {
    await discover(page, "startups");
    const tile = page.getByRole("list", { name: "Startups" }).getByRole("link", { name: /Ledgerly/ });
    await expect(tile).toContainText("Hiring");
    await expect(tile).not.toContainText("0 roles");
    await expect(tile).not.toContainText("Not hiring");
  });

  test("not hiring: says so, with Follow for updates", async ({ page }) => {
    await page.goto("/startups/47");
    await expect(page.getByRole("heading", { name: "Not hiring right now" })).toBeVisible();
    await page.getByRole("button", { name: "Follow for updates" }).click();
    await expect(page.getByText("You're following. We'll tell you when they post a role.")).toBeVisible();
  });

  test("unclaimed: from public sources; students get no claim button", async ({ page }) => {
    await page.goto("/startups/44");
    await expect(page.getByText("Unclaimed · from public sources")).toBeVisible();
    await expect(page.getByRole("button", { name: "Claim this startup" })).toHaveCount(0);
  });

  test("a founder claims an unclaimed startup with a work email on its domain", async ({ page }) => {
    await page.goto("/startups/44?scenario=founder");
    await expect(page.getByRole("region", { name: "Claim this startup" })).toContainText("23 students looked at this page and 6 are interested.");
    await page.getByRole("button", { name: "Claim this startup" }).click();
    const sheet = page.getByRole("dialog", { name: "Claim Medisetu" });
    await sheet.getByLabel("Work email at medisetu.in").fill("priya@gmail.com");
    await sheet.getByRole("button", { name: "Send code" }).click();
    await expect(sheet.getByRole("alert")).toHaveText("Use an email address at medisetu.in.");
    await sheet.getByLabel("Work email at medisetu.in").fill("priya@medisetu.in");
    await sheet.getByRole("button", { name: "Send code" }).click();
    await expect(sheet).toContainText("Enter the 8-character code we sent to priya@medisetu.in.");
    await sheet.getByLabel("Character 1 of 8").fill("K7M2P9QX"); // a paste fills every box
    await expect(sheet).toHaveCount(0);
    await expect(page.getByText("Claimed by its team")).toBeVisible();
    await expect(page.getByRole("region", { name: "Claim this startup" })).toHaveCount(0);
  });

  test("under 18: no intros to founders", async ({ page }) => {
    await page.goto("/startups/42?scenario=under18");
    await expect(page.getByRole("region", { name: "Founders" })).toContainText("Divya Menon");
    await expect(page.getByRole("button", { name: /Intro via/ })).toHaveCount(0);
  });

  test("under 18: an unverified startup shows as not hiring", async ({ page }) => {
    await page.goto("/startups/43?scenario=under18");
    await expect(page.getByRole("heading", { name: "Sutragrid", level: 1 })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Not hiring right now" })).toBeVisible();
    await expect(page.getByText("Backend engineer intern")).toHaveCount(0);
  });

  test("features off: no build logs", async ({ page }) => {
    await page.goto("/startups/42?scenario=features_off");
    await expect(page.getByRole("region", { name: "Hiring" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Build logs" })).toHaveCount(0);
  });

  test("Report is two taps away", async ({ page }) => {
    await page.goto("/startups/43");
    await page.getByRole("button", { name: "More" }).click();
    await page.getByRole("button", { name: "Report this startup" }).click();
    await expect(page.getByText("Thanks. We'll look at this page.")).toBeVisible();
  });
});

test.describe("axe and layout", () => {
  const screens: Array<{ label: string; go: (page: Page) => Promise<void> }> = [
    { label: "discover jobs", go: (p) => discover(p, "jobs") },
    { label: "discover people", go: (p) => discover(p, "people") },
    { label: "discover startups", go: (p) => discover(p, "startups") },
    { label: "discover map with sheet", go: async (p) => { await discover(p, "map"); await pin(p, "Aravind Pathology, hiring").dispatchEvent("click"); await expect(p.getByRole("region", { name: "Selected startup" })).toBeVisible(); } },
    { label: "discover search", go: async (p) => { await discover(p, "people"); await p.getByRole("searchbox").fill("ta"); await expect(p.getByRole("region", { name: "Roles found" })).toBeVisible(); } },
    { label: "filters sheet", go: async (p) => { await discover(p, "startups"); await p.getByRole("button", { name: "Filters", exact: true }).click(); await expect(p.getByRole("dialog", { name: "Filters" })).toBeVisible(); } },
    { label: "job page", go: async (p) => { await p.goto("/discover/jobs/301"); await expect(p.getByRole("heading", { level: 1, name: "Frontend intern" })).toBeVisible(); } },
    { label: "applications", go: async (p) => { await p.goto("/discover/applications"); await expect(p.getByRole("list", { name: "Applications" })).toBeVisible(); } },
    { label: "applicants", go: async (p) => { await p.goto("/discover/jobs/301/applicants?scenario=founder"); await expect(p.getByRole("article").first()).toBeVisible(); } },
    { label: "startup page", go: async (p) => { await p.goto("/startups/42"); await expect(p.getByRole("region", { name: "Founders" })).toBeVisible(); } },
    { label: "unclaimed startup, founder", go: async (p) => { await p.goto("/startups/44?scenario=founder"); await expect(p.getByRole("region", { name: "Claim this startup" })).toBeVisible(); } },
  ];
  for (const s of screens) {
    test(`axe: ${s.label}`, async ({ page }) => {
      await s.go(page);
      await page.waitForTimeout(300);
      await inBothThemes(page, async (theme) => {
        await page.waitForTimeout(200);
        await checkPage(page, `${s.label} ${theme}`);
      });
    });
  }

  test("pushed screens have no tab bar, and the job page's Apply stays on screen while scrolling", async ({ page }, info) => {
    await page.goto("/discover/jobs/301");
    await expect(page.getByRole("heading", { level: 1, name: "Frontend intern" })).toBeVisible();
    if (isPhone(info)) await expect(page.getByRole("navigation", { name: "Tabs" })).toHaveCount(0);
    await page.mouse.wheel(0, 2000);
    await expect(page.getByRole("button", { name: "Apply with your profile" })).toBeInViewport();
  });
});
