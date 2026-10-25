import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, type TestInfo } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { join } from "node:path";

const SHOTS = join(__dirname, "../../../screenshots/f2");

export const isPhone = (info: TestInfo) => info.project.name === "phone";
export const widthOf = (info: TestInfo) => (isPhone(info) ? 375 : 1280);

/** The mock "server": what the New member scenario holds right now (never called by the app). */
export async function serverState(page: Page) {
  return page.evaluate(async () => (await fetch("/mock-supabase/_state")).json()) as Promise<{
    consent: boolean; beta: boolean; signup_source: string; waitlist: Array<{ email: string; role: string; src: string }>;
    me: { name: string; role: string; city: string; college: string; bio: string; lat: number | null; lng: number | null; organisation_id: number | null; is_minor: boolean; profile_visibility: string; allow_requests: boolean };
    onboarding: { current_step: string | null; completed_at: string | null; answers: Record<string, Record<string, unknown>> };
    offers: Array<{ capability: string }>; needs: Array<{ capability: string }>;
  }>;
}

/** Opens the app as a brand-new member (signed out, beta on, nothing accepted). `path` may carry join-link parameters. */
export async function openAsNewMember(page: Page, path = "/", scenario = "signup") {
  const url = new URL(path, "http://x");
  url.searchParams.set("scenario", scenario);
  await page.goto(url.pathname + url.search);
}

/** Welcome → "Use email instead" → address → the 6 digits pasted into the first box. */
export async function signInByEmail(page: Page, email = "ravi.new@example.com", code = "123456") {
  await page.getByRole("button", { name: "Use email instead" }).click();
  await page.getByLabel("Email").fill(email);
  await page.getByRole("button", { name: "Send code" }).click();
  const first = page.getByLabel("Digit 1 of 6");
  await first.fill(code);
}

export async function shot(page: Page, screen: string, name: string) {
  const dir = join(SHOTS, screen);
  mkdirSync(dir, { recursive: true });
  await page.screenshot({ path: join(dir, `${name}.png`) });
}

/** Checks one step against the rules every sign-up screen shares, in both themes, and saves the screenshots. */
export async function checkStep(page: Page, info: TestInfo, screen: string, opts: { primary?: number; settle?: number } = {}) {
  await page.waitForTimeout(opts.settle ?? 400);
  for (const theme of ["dark", "light"] as const) {
    await page.emulateMedia({ colorScheme: theme, reducedMotion: "reduce" });
    await page.waitForTimeout(150);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    expect(overflow, `${screen} ${theme}: horizontal overflow`).toBe(false);
    const axe = await new AxeBuilder({ page }).analyze();
    expect(axe.violations.map((v) => `${v.id} (${v.impact}): ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`), `${screen} ${theme}: axe`).toEqual([]);
    await shot(page, screen, `${widthOf(info)}-${theme}`);
  }
  await page.emulateMedia({ colorScheme: "dark" });
  // One thing per screen: at most one primary button (DESIGN.md §1a).
  const primaries = await page.evaluate(() => [...document.querySelectorAll("button")].filter((b) => b.className.includes("bg-primary") && b.offsetParent !== null).length);
  expect(primaries, `${screen}: primary buttons`).toBeLessThanOrEqual(opts.primary ?? 1);
  const sizes = await page.evaluate(() => new Set([...document.querySelectorAll("body *")].filter((e) => e.childNodes.length && [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent?.trim())).map((e) => getComputedStyle(e).fontSize)).size);
  expect(sizes, `${screen}: font sizes`).toBeLessThanOrEqual(5);
}

/** The inline error on the screen (Next adds its own role=alert route announcer, which is not it). */
export const alertOf = (page: Page) => page.locator('[role="alert"]:not(#__next-route-announcer__)');

/** Signs in by email, accepts the terms and uses the open invite code: ends on the first onboarding screen. */
export async function intoOnboarding(page: Page, path = "/", opts: { google?: boolean; scenario?: string } = {}) {
  await openAsNewMember(page, path, opts.scenario);
  if (opts.google) await page.getByRole("button", { name: "Continue with Google" }).click();
  else await signInByEmail(page);
  await page.getByRole("button", { name: "I agree" }).click();
  // Either the invite screen (no code on the link) or straight to Name (the link's code was used).
  await page.getByRole("heading", { level: 1, name: /Got an invite code\?|What should we call you\?/ }).waitFor();
  const invite = page.getByLabel("Invite code");
  if (await invite.isVisible()) { await invite.fill("CIRCUIT-0001"); await invite.press("Enter"); }
}

/** The thin bar at the top: how far along, 0–100. */
export const progressOf = (page: Page) => page.getByRole("progressbar", { name: "Progress" }).last().getAttribute("aria-valuenow").then(Number);

/** A swipe from the left edge, as a finger would make it (touch events, because Playwright has no touch drag). */
export async function edgeSwipe(page: Page) {
  await page.evaluate(() => {
    const main = document.querySelector("main")!;
    const touch = (x: number, y: number) => new Touch({ identifier: 1, target: main, clientX: x, clientY: y });
    const fire = (type: string, x: number) => main.dispatchEvent(new TouchEvent(type, { touches: type === "touchend" ? [] : [touch(x, 400)], changedTouches: [touch(x, 400)], bubbles: true, cancelable: true }));
    fire("touchstart", 4); fire("touchmove", 40); fire("touchmove", 120); fire("touchend", 120);
  });
}
