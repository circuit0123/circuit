import { defineConfig, devices } from "@playwright/test";

/**
 * Builds the static export twice with test URLs and serves both: feature flags ON on :3101 (the default baseURL) and OFF on :3102
 * (e2e/serve-test-builds.sh). The API and the app are never contacted: the waitlist call is mocked in each test and every other request
 * must stay on the landing origin. Two projects: a 375px phone and a 1280px desktop.
 */
const ON = "http://localhost:3101";
const OFF = "http://localhost:3102";

export default defineConfig({
  testDir: "e2e",
  timeout: 30_000,
  expect: { timeout: 8_000 },
  workers: 2,
  reporter: [["list"]],
  webServer: {
    command: "e2e/serve-test-builds.sh",
    url: OFF,
    reuseExistingServer: false,
    timeout: 360_000,
  },
  use: { baseURL: ON, trace: "retain-on-failure" },
  projects: [
    { name: "phone", use: { ...devices["Pixel 7"], viewport: { width: 375, height: 812 }, deviceScaleFactor: 2 } },
    { name: "desktop", use: { viewport: { width: 1280, height: 800 } } },
  ],
});
