import { defineConfig, devices } from "@playwright/test";

/**
 * Builds the static export three times with test URLs (e2e/serve-test-builds.sh): feature flags ON on :3101 (the default baseURL), flags OFF
 * on :3102, both with NEXT_PUBLIC_JOIN_LIVE=true; and flags ON with the join switch off (the default) on :3103. The API and the app are never contacted: the waitlist call is mocked in each test and every other request
 * must stay on the landing origin. Two projects: a 375px phone and a 1280px desktop.
 */
const ON = "http://localhost:3101";
const OFF = "http://localhost:3102";
const WAIT = "http://localhost:3103";

export default defineConfig({
  testDir: "e2e",
  timeout: 30_000,
  expect: { timeout: 8_000 },
  workers: 2,
  reporter: [["list"]],
  webServer: {
    command: "e2e/serve-test-builds.sh",
    url: WAIT,
    reuseExistingServer: false,
    timeout: 360_000,
  },
  use: { baseURL: ON, trace: "retain-on-failure" },
  projects: [
    { name: "phone", use: { ...devices["Pixel 7"], viewport: { width: 375, height: 812 }, deviceScaleFactor: 2 } },
    { name: "desktop", use: { viewport: { width: 1280, height: 800 } } },
  ],
});
