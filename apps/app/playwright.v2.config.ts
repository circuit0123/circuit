import { defineConfig, devices } from "@playwright/test";

/**
 * The ui_v2 screens on mock mode with NEXT_PUBLIC_UI_V2=on (own port and build folder, so it never disturbs the flag-off run in
 * playwright.mock.config.ts). `make test-web-v2`. Two projects: a 390px phone and a 1440px desktop.
 */
const PORT = 3201;
export default defineConfig({
  testDir: "tests",
  testMatch: ["**/ui-v2.spec.ts"],
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
    env: { NEXT_DIST_DIR: ".next-mock-v2", NEXT_PUBLIC_UI_V2: "on", NEXT_PUBLIC_MOCK: "1", NEXT_PUBLIC_ENV: "dev", NEXT_PUBLIC_API_URL: `http://localhost:${PORT}`, NEXT_PUBLIC_SUPABASE_URL: `http://localhost:${PORT}/mock-supabase`, NEXT_PUBLIC_SUPABASE_ANON_KEY: "mock" },
  },
  use: { baseURL: `http://localhost:${PORT}`, trace: "retain-on-failure", reducedMotion: "reduce" },
  projects: [
    { name: "phone", use: { ...devices["Pixel 7"], viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 } },
    { name: "desktop", use: { viewport: { width: 1440, height: 900 } } },
  ],
});
