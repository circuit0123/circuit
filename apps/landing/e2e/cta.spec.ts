import { expect, test } from "@playwright/test";
import { APP } from "./support";

const TILES = [
  { who: "Students", id: "students", role: "student", cta: "Find work near you" },
  { who: "Founders", id: "founders", role: "founder", cta: "Claim your startup" },
  { who: "Mentors", id: "mentors", role: "mentor", cta: "Start mentoring" },
  { who: "Investors", id: "investors", role: "investor", cta: "Set your focus" },
  { who: "Partners", id: "partners", role: "partner", cta: "Bring Circuit to your campus" },
];

test.beforeEach(async ({ page }) => { await page.goto("/"); });

test("hero button goes to the app join screen with the source and no role", async ({ page }) => {
  const hero = page.getByRole("region", { name: "Introduction" }).getByRole("link", { name: "Join the beta" });
  await expect(hero).toHaveAttribute("href", `${APP}/join?src=landing-home`);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Build with people near you.");
});

for (const t of TILES) {
  test(`${t.who} tile carries role=${t.role} and src=landing-home`, async ({ page }) => {
    const tile = page.locator(`a#${t.id}`);
    await expect(tile).toContainText(t.cta);
    await expect(tile).toHaveAttribute("href", `${APP}/join?role=${t.role}&src=landing-home`);
  });

  test(`header link ${t.who} jumps to its tile`, async ({ page }) => {
    await page.getByRole("navigation", { name: "Audiences" }).getByRole("link", { name: t.who }).click();
    await expect(page).toHaveURL(new RegExp(`#${t.id}$`));
    await expect(page.locator(`a#${t.id}`)).toBeInViewport();
  });
}

test("exactly one primary button on the page", async ({ page }) => {
  const primaries = await page.evaluate(() => {
    const probe = document.createElement("i");
    probe.style.color = "var(--primary)";
    document.body.append(probe);
    const primary = getComputedStyle(probe).color;
    probe.remove();
    return Array.from(document.querySelectorAll("a, button")).filter((el) => getComputedStyle(el).backgroundColor === primary).map((el) => el.textContent?.trim());
  });
  expect(primaries).toEqual(["Join the beta"]);
});

test("footer links: privacy, terms and contact", async ({ page }) => {
  const legal = page.getByRole("navigation", { name: "Legal" });
  await expect(legal.getByRole("link", { name: "Privacy" })).toHaveAttribute("href", "/privacy/");
  await expect(legal.getByRole("link", { name: "Terms" })).toHaveAttribute("href", "/terms/");
  await expect(legal.getByRole("link", { name: "Contact" })).toHaveAttribute("href", "mailto:hello@example.com");
  await legal.getByRole("link", { name: "Privacy" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Privacy" })).toBeVisible();
});
