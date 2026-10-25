import { defineConfig, devices } from "@playwright/test";

/**
 * Design checks and gesture tests on mock mode (`NEXT_PUBLIC_MOCK=1`): no backend, no login, the same fixtures every run.
 * Runs inside `make check` (via `make test-web`). Two projects: a 375px phone (touch) and a 1280px desktop.
 * The sign-in and shell journeys that need the real API stay in playwright.config.ts (`make e2e`).
 */
const PORT = 3200;
export default defineConfig({
  testDir: "tests",
  testMatch: ["**/*.spec.ts"],
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  webServer: {
    command: `pnpm exec next dev -p ${PORT}`,
    url: `http://localhost:${PORT}/design`,
    reuseExistingServer: true,
    timeout: 120_000,
    env: { NEXT_DIST_DIR: ".next-mock-e2e", NEXT_PUBLIC_MOCK: "1", NEXT_PUBLIC_ENV: "dev", NEXT_PUBLIC_API_URL: `http://localhost:${PORT}` },
  },
  use: { baseURL: `http://localhost:${PORT}`, trace: "retain-on-failure", reducedMotion: "reduce" },
  projects: [
    { name: "phone", use: { ...devices["Pixel 7"], viewport: { width: 375, height: 812 }, deviceScaleFactor: 2 } },
    { name: "desktop", use: { viewport: { width: 1280, height: 800 } } },
  ],
});
