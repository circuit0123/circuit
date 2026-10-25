import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, type Route } from "@playwright/test";

import { PAGES } from "../src/content/pages";

export const APP = "http://app.test";
/** The same site built with every feature flag on (default) and off. */
export const ON = "http://localhost:3101";
export const OFF = "http://localhost:3102";
/** Home plus every audience page that has shipped. */
export const PATHS = ["/", ...PAGES.map((p) => `/${p.slug}/`)];
export const THEMES = ["dark", "light"] as const;

/** Answers the waitlist call (and its CORS preflight) from the test, so no real API is needed. Returns the bodies it received. */
export async function mockWaitlist(page: Page, answer: (body: Record<string, string>, n: number) => { status: number; body?: object } | "abort") {
  const bodies: Record<string, string>[] = [];
  const cors = { "access-control-allow-origin": "*", "access-control-allow-headers": "content-type", "access-control-allow-methods": "POST, OPTIONS" };
  await page.route("**/api/waitlist", async (route: Route) => {
    const req = route.request();
    if (req.method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
    const body = JSON.parse(req.postData() ?? "{}");
    bodies.push(body);
    const r = answer(body, bodies.length);
    if (r === "abort") return route.abort("connectionfailed");
    return route.fulfill({ status: r.status, headers: { ...cors, "content-type": "application/json" }, body: JSON.stringify(r.body ?? { status: "ok" }) });
  });
  return bodies;
}

export async function fillWaitlist(page: Page, v: { email: string; role?: string; city?: string }) {
  await page.getByLabel("Email").fill(v.email);
  await page.getByLabel("I am a").selectOption(v.role ?? "student");
  await page.getByLabel("City").fill(v.city ?? "Pune");
}

/** No horizontal page scroll and no axe violations. */
export async function checkPage(page: Page, label: string) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  expect(overflow, `${label}: horizontal overflow`).toBe(false);
  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations.map((v) => `${v.id} (${v.impact}) x${v.nodes.length}: ${v.nodes[0]?.html.slice(0, 120)}`), `${label}: axe`).toEqual([]);
}
