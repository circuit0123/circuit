import { defineConfig, devices } from "@playwright/test";

/**
 * Runs against the local stack (`make dev`: API on :8000, app on :3000), signing in as demo personas.
 * Two projects: a 375px phone (touch) and a 1280px desktop. Screenshots land in /screenshots/frontend-core/.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: { baseURL: process.env.APP_URL ?? "http://localhost:3000", trace: "retain-on-failure", reducedMotion: "reduce" },
  projects: [
    { name: "phone", use: { ...devices["Pixel 7"], viewport: { width: 375, height: 812 }, deviceScaleFactor: 2 } },
    { name: "desktop", use: { viewport: { width: 1280, height: 800 } } },
  ],
});
