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
export async function checkPage(page: Page, label: string) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  expect(overflow, `${label}: horizontal overflow`).toBe(false);
  const axe = await new AxeBuilder({ page }).analyze();
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
    await fn(theme);
  }
}
