import { defineConfig, devices } from "@playwright/test";

/**
 * Builds the static export with test URLs and serves `out/` on :3101. The API and the app are never contacted: the waitlist call is
 * mocked in each test and every other request must stay on the landing origin. Two projects: a 375px phone and a 1280px desktop.
 */
export const TEST_ENV = {
  NEXT_PUBLIC_APP_URL: "http://app.test",
  NEXT_PUBLIC_API_URL: "http://api.test",
  NEXT_PUBLIC_LANDING_URL: "http://localhost:3101",
  NEXT_PUBLIC_CONTACT_EMAIL: "hello@example.com",
};

export default defineConfig({
  testDir: "e2e",
  timeout: 30_000,
  expect: { timeout: 8_000 },
  workers: 2,
  reporter: [["list"]],
  webServer: {
    command: "pnpm build && python3 -m http.server 3101 -d out",
    url: "http://localhost:3101/",
    reuseExistingServer: false,
    timeout: 180_000,
    env: TEST_ENV,
  },
  use: { baseURL: "http://localhost:3101", trace: "retain-on-failure" },
  projects: [
    { name: "phone", use: { ...devices["Pixel 7"], viewport: { width: 375, height: 812 }, deviceScaleFactor: 2 } },
    { name: "desktop", use: { viewport: { width: 1280, height: 800 } } },
  ],
});
