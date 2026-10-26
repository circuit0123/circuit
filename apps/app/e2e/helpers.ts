import AxeBuilder from "@axe-core/playwright";
import { expect, type BrowserContext, type Page, type TestInfo } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { join } from "node:path";

export const API = process.env.API_URL ?? "http://localhost:8000";
const SHOTS = join(__dirname, "../../../screenshots/frontend-core");

/** A persona token from the dev API (the same call the sign-in screen makes). */
export async function personaToken(persona: string): Promise<string> {
  const res = await fetch(`${API}/api/demo/token`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ persona }) });
  return (await res.json()).access_token as string;
}

/** Signs a browser context in as a persona before any page script runs. */
export async function signInAs(ctx: BrowserContext, persona: string) {
  const token = await personaToken(persona);
  await ctx.addInitScript((t) => localStorage.setItem("circuit.token", t), token);
}

export const isPhone = (info: TestInfo) => info.project.name === "phone";

/** No horizontal page scroll, and no axe violations. */
export async function checkPage(page: Page, label: string, opts: { exclude?: string[] } = {}) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  expect(overflow, `${label}: horizontal overflow`).toBe(false);
  const builder = new AxeBuilder({ page });
  for (const sel of opts.exclude ?? []) builder.exclude(sel);
  const axe = await builder.analyze();
  expect(axe.violations.map((v) => `${v.id} (${v.impact}) x${v.nodes.length}`), `${label}: axe`).toEqual([]);
}

/** Saves <screen>-<width>[-theme].png under screenshots/frontend-core/<screen>/. */
export async function shot(page: Page, screen: string, name: string) {
  const dir = join(SHOTS, screen);
  mkdirSync(dir, { recursive: true });
  await page.screenshot({ path: join(dir, `${name}.png`) });
}

/** Runs `fn` once per colour scheme (dark first), with the page already emulating it. */
export async function inBothThemes(page: Page, fn: (theme: "dark" | "light") => Promise<void>) {
  for (const theme of ["dark", "light"] as const) {
    await page.emulateMedia({ colorScheme: theme });
    // The accent crossfades for 250ms (tokens.css); axe must measure the settled colours, not a blend.
    await page.waitForTimeout(350);
    await fn(theme);
  }
}

export const STAGING = "http://localhost:3100";
export const SUPABASE = "http://127.0.0.1:54321";

/**
 * For the staging-like server on :3100. The API only allows :3000 (CORS), so API calls go through the test runner, which adds the
 * headers; and every Supabase call is answered here. Returns what the page asked Supabase for.
 */
export async function stubBackends(page: Page, opts: { verify?: "ok" | "bad"; personaToken?: string } = {}) {
  const seen = { otp: [] as unknown[], verify: [] as unknown[], authorize: [] as string[] };
  const cors = { "access-control-allow-origin": "*", "access-control-allow-headers": "authorization,content-type,x-request-id", "access-control-allow-methods": "GET,POST,PATCH,PUT,DELETE" };
  await page.route("http://localhost:8000/**", async (route) => {
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
    const res = await route.fetch();
    await route.fulfill({ response: res, headers: { ...res.headers(), ...cors } });
  });
  await page.route(`${SUPABASE}/auth/v1/otp**`, async (route) => {
    seen.otp.push(route.request().postDataJSON());
    await route.fulfill({ status: 200, json: {}, headers: cors });
  });
  await page.route(`${SUPABASE}/auth/v1/verify**`, async (route) => {
    seen.verify.push(route.request().postDataJSON());
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
    if (opts.verify === "bad") return route.fulfill({ status: 403, json: { code: 403, error_code: "otp_expired", msg: "Token has expired or is invalid" }, headers: cors });
    const now = Math.floor(Date.now() / 1000);
    await route.fulfill({
      status: 200,
      headers: cors,
      json: {
        access_token: opts.personaToken, token_type: "bearer", expires_in: 3600, expires_at: now + 3600, refresh_token: "e2e-refresh",
        user: { id: "00000000-0000-0000-0000-000000000001", aud: "authenticated", role: "authenticated", email: "someone@example.com", app_metadata: { provider: "email" }, user_metadata: {}, created_at: new Date().toISOString() },
      },
    });
  });
  await page.route(`${SUPABASE}/auth/v1/authorize**`, async (route) => {
    seen.authorize.push(route.request().url());
    await route.fulfill({ status: 200, contentType: "text/html", body: "<html><body>Google</body></html>" });
  });
  return seen;
}
