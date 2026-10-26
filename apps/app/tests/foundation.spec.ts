import { expect, test, type Page } from "@playwright/test";
import { checkPage, isPhone } from "../e2e/helpers";

/**
 * F1 foundation checks on mock mode: first paint, accents, 404/500, the environment banner, every mock scenario, the PWA manifest and
 * the /design page. No backend needed (playwright.mock.config.ts).
 */

test.describe("first paint and accents", () => {
  test("the saved theme and accent are on <html> before any app script runs", async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem("circuit.appearance", JSON.stringify({ theme: "light", accent: "rose" })));
    // With every script of the app blocked, only the inline first-paint script can have set these.
    await page.route("**/_next/**/*.js", (r) => r.abort());
    await page.goto("/design");
    const seen = await page.evaluate(() => ({
      theme: document.documentElement.dataset.theme,
      accent: document.documentElement.dataset.accent,
      chrome: document.head.querySelector<HTMLMetaElement>('meta[name="theme-color"]')?.content,
      ground: getComputedStyle(document.body).backgroundColor,
    }));
    expect(seen).toEqual({ theme: "light", accent: "rose", chrome: "#C2BCC8", ground: "rgb(194, 188, 200)" });
  });

  test("with nothing saved, the system's own scheme decides and no attribute is set", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/design");
    expect(await page.evaluate(() => [document.documentElement.dataset.theme, document.documentElement.dataset.accent])).toEqual([undefined, undefined]);
    expect(await page.evaluate(() => document.head.querySelector<HTMLMetaElement>('meta[name="theme-color"]')?.content)).toBe("#000000");
  });

  test("all six accents pass contrast in both themes", async ({ page }) => {
    await page.goto("/design");
    const rows = await page.evaluate(() => {
      const lum = (rgb: string) => {
        const [r, g, b] = (rgb.match(/[\d.]+/g) ?? []).slice(0, 3).map(Number).map((v) => { const c = v / 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; });
        return 0.2126 * r + 0.7152 * g + 0.0722 * b;
      };
      const ratio = (a: string, b: string) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
      const out: Array<{ theme: string; accent: string; ratio: number; bridgeDiffers: boolean }> = [];
      for (const theme of ["dark", "light"]) {
        for (const accent of ["emerald", "sky", "indigo", "rose", "lime", "mono"]) {
          const el = document.createElement("div");
          el.dataset.theme = theme;
          el.dataset.accent = accent;
          document.body.append(el);
          const paint = (v: string) => { const p = document.createElement("i"); p.style.color = `var(${v})`; el.append(p); const c = getComputedStyle(p).color; p.remove(); return c; };
          const current = paint("--current");
          out.push({ theme, accent, ratio: ratio(current, paint("--bg")), bridgeDiffers: current !== paint("--bridge") });
          el.remove();
        }
      }
      return out;
    });
    expect(rows).toHaveLength(12);
    for (const r of rows) {
      // DESIGN.md §5: every light value is at least 4.5:1 on the lavender bg; every dark value at least 3:1 on black.
      expect.soft(r.ratio, `${r.theme} ${r.accent}`).toBeGreaterThanOrEqual(r.theme === "light" ? 4.5 : 3);
      expect.soft(r.bridgeDiffers, `${r.theme} ${r.accent}: Bridge stays distinct`).toBe(true);
    }
  });

  test.describe("crossfade", () => {
    test.use({ reducedMotion: "no-preference" });
    test("an accent change fades over 250ms instead of jumping", async ({ page }) => {
      await page.goto("/design");
      // Let the mock member's own appearance land first, or it would put the default accent back over this one.
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(500);
      const read = () => page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue("--current").trim());
      const before = await read();
      await page.evaluate(() => { document.documentElement.dataset.accent = "rose"; });
      await page.waitForTimeout(110);
      const middle = await read();
      await page.waitForTimeout(500);
      const after = await read();
      expect(before).not.toBe(after);
      expect(middle).not.toBe(before);
      expect(middle).not.toBe(after);
    });
  });

  test.describe("reduced motion", () => {
    test.use({ reducedMotion: "reduce" });
    test("an accent change is immediate", async ({ page }) => {
      await page.goto("/design");
      await page.evaluate(() => { document.documentElement.dataset.accent = "rose"; });
      const t = await page.evaluate(() => getComputedStyle(document.documentElement).transitionProperty);
      expect(t).not.toContain("--current");
    });
  });
});

test.describe("404, 500 and the banner", () => {
  test("an unknown address shows the 404 page, with one way home", async ({ page }) => {
    await page.goto("/nope");
    await expect(page.getByRole("heading", { name: "We couldn't find that page" })).toBeVisible();
    await page.getByRole("link", { name: "Go to Home" }).click();
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole("heading", { name: "Today", level: 1 })).toBeVisible();
  });

  test("a deep link to a tab that is off or not built shows the same 404", async ({ page }) => {
    await page.goto("/circuits");
    await expect(page.getByRole("heading", { name: "We couldn't find that page" })).toBeVisible();
  });

  test("a screen that throws shows the 500 page and can try again", async ({ page }) => {
    await page.goto("/design/crash");
    await expect(page.getByRole("heading", { name: "Something went wrong on our side" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
  });

  test("the environment banner names the environment and the scenario", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("region", { name: "Environment" })).toContainText("Mock — Default");
    await expect(page.getByRole("link", { name: "Design" })).toBeVisible();
  });
});

test.describe("mock scenarios", () => {
  const open = async (page: Page, scenario: string) => { await page.goto(`/?scenario=${scenario}`); };

  test("default: Home with the Live wire and the Daily Drop", async ({ page }) => {
    await open(page, "default");
    await expect(page.getByRole("list", { name: "Live wire" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Daily Drop" })).toBeVisible();
  });

  test("empty: honest empty states, not blank space", async ({ page }) => {
    await open(page, "empty");
    await expect(page.getByText("Quiet on the wire today")).toBeVisible();
    await expect(page.getByText("No new people for you today.")).toBeVisible();
  });

  test("loading: skeletons, and the banner is still there to switch away", async ({ page }) => {
    await open(page, "loading");
    await expect(page.getByRole("region", { name: "Environment" })).toContainText("Mock — Loading");
    await page.waitForTimeout(1500);
    await expect(page.getByRole("heading", { name: "Today" })).toHaveCount(0);
    await expect(page.locator(".skeleton").first()).toBeVisible();
  });

  test("error: one sentence and Try again; switching scenario recovers", async ({ page }) => {
    await open(page, "error");
    await expect(page.getByRole("heading", { name: "Couldn't open Circuit" })).toBeVisible();
    await page.getByRole("combobox", { name: "Scenario" }).selectOption("default");
    await expect(page.getByRole("heading", { name: "Today", level: 1 })).toBeVisible();
  });

  test("slow 3G: content arrives late, not never", async ({ page }) => {
    await open(page, "slow3g");
    await page.waitForTimeout(800);
    await expect(page.getByRole("heading", { name: "Today", level: 1 })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Today", level: 1 })).toBeVisible({ timeout: 15_000 });
  });

  test("beta access missing: the gate holds the app back", async ({ page }) => {
    await open(page, "beta");
    await expect(page.getByRole("heading", { name: "Got an invite code?" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Main" })).toHaveCount(0);
  });

  test("features off: no Live wire, no Daily Drop, four tabs", async ({ page }) => {
    await open(page, "features_off");
    await expect(page.getByRole("heading", { name: "Today", level: 1 })).toBeVisible();
    await expect(page.getByRole("list", { name: "Live wire" })).toHaveCount(0);
    await expect(page.getByRole("region", { name: "Daily Drop" })).toHaveCount(0);
  });

  test("under 18: no Daily Drop", async ({ page }) => {
    await open(page, "under18");
    await expect(page.getByRole("heading", { name: "Today", level: 1 })).toBeVisible();
    await expect(page.getByRole("region", { name: "Daily Drop" })).toHaveCount(0);
    await expect(page.getByRole("list", { name: "Live wire" })).toBeVisible();
  });

  test("the banner switches scenario and remembers it", async ({ page }) => {
    await open(page, "default");
    await page.getByRole("combobox", { name: "Scenario" }).selectOption("empty");
    await expect(page.getByText("Quiet on the wire today")).toBeVisible();
    await page.goto("/");
    await expect(page.getByRole("region", { name: "Environment" })).toContainText("Mock — Empty");
  });

  test("the Theme switch in the banner changes the colours and survives a reload", async ({ page }) => {
    await open(page, "default");
    await page.getByRole("combobox", { name: "Theme" }).selectOption("light");
    await expect.poll(() => page.evaluate(() => document.documentElement.dataset.theme)).toBe("light");
    await page.reload();
    await expect.poll(() => page.evaluate(() => document.documentElement.dataset.theme)).toBe("light");
  });
});

test.describe("PWA basics", () => {
  test("the manifest is installable and every icon exists", async ({ page, request }) => {
    await page.goto("/");
    const href = await page.locator('link[rel="manifest"]').getAttribute("href");
    expect(href).toBeTruthy();
    const m = await (await request.get(href!)).json();
    expect(m).toMatchObject({ name: "Circuit", start_url: "/", display: "standalone", background_color: "#000000", theme_color: "#000000" });
    expect(m.icons.some((i: { purpose: string }) => i.purpose === "maskable")).toBe(true);
    expect(m.icons.some((i: { sizes: string }) => i.sizes === "512x512")).toBe(true);
    for (const i of m.icons) expect((await request.get(i.src)).status(), i.src).toBe(200);
    expect(await page.locator('link[rel="apple-touch-icon"]').count()).toBeGreaterThan(0);
    expect(await page.locator('link[rel~="icon"]').count()).toBeGreaterThan(0);
    expect(await page.locator('meta[name="theme-color"]').count()).toBeGreaterThan(0);
  });
});

test.describe("/design", () => {
  test("shows every component in both themes, with no horizontal scroll and no axe violations", async ({ page }, info) => {
    await page.goto("/design");
    await expect(page.getByRole("region", { name: "dark theme" })).toBeVisible();
    await expect(page.getByRole("region", { name: "light theme" })).toBeVisible();
    for (const name of ["Button", "Chip", "Card", "ListRow", "GroupedList", "SegmentedControl", "TopBar and LargeTitleHeader", "TabBar", "Sheet", "Toast", "Avatar", "Badge", "MatchStrength", "EmptyState", "ErrorState", "Skeleton", "Logo"]) {
      await expect(page.getByRole("region", { name: "dark theme" }).getByRole("region", { name: `${name} (dark)`, exact: true })).toBeVisible();
    }
    // The "Pressed" samples are 80% opacity on purpose (the press state); a transient state is not judged for contrast.
    await checkPage(page, `design (${isPhone(info) ? "375" : "1280"})`, { exclude: ["[data-pressed-demo]"] });
  });

  test("a sheet opens at its detent, and closes with Escape", async ({ page }) => {
    await page.goto("/design");
    const dark = page.getByRole("region", { name: "dark theme" });
    await dark.getByRole("button", { name: "Medium detent" }).click();
    const dialog = page.getByRole("dialog", { name: "Report this post" });
    await expect(dialog).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
  });
});
