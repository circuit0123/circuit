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
  // A second dev server that behaves like staging for the signed-out screens: no demo tools, fake Supabase keys (every Supabase
  // call is stubbed in the tests), and its own build folder so it can run beside `make dev`.
  webServer: {
    command: "pnpm exec next dev -p 3100",
    url: "http://localhost:3100/auth/callback",
    reuseExistingServer: true,
    timeout: 120_000,
    env: { NEXT_DIST_DIR: ".next-e2e", NEXT_PUBLIC_ENV: "staging", NEXT_PUBLIC_SUPABASE_URL: "http://127.0.0.1:54321", NEXT_PUBLIC_SUPABASE_ANON_KEY: "e2e-anon-key", NEXT_PUBLIC_API_URL: "http://localhost:8000", NEXT_PUBLIC_LANDING_URL: "http://localhost:3001" },
  },
  use: { baseURL: process.env.APP_URL ?? "http://localhost:3000", trace: "retain-on-failure", reducedMotion: "reduce" },
  projects: [
    { name: "phone", use: { ...devices["Pixel 7"], viewport: { width: 375, height: 812 }, deviceScaleFactor: 2 } },
    { name: "desktop", use: { viewport: { width: 1280, height: 800 } } },
  ],
});
