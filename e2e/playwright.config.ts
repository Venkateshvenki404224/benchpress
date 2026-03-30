import { defineConfig, devices } from "@playwright/test";

const BASE_URL =
  process.env.FRAPPE_BASE_URL || "http://benchpress.localhost:8014";

export default defineConfig({
  testDir: ".",
  timeout: 60_000,
  retries: 1,
  workers: 1,
  reporter: [["html", { outputFolder: "playwright-report" }], ["list"]],
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "on-first-retry",
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },
  projects: [
    {
      name: "auth-setup",
      testMatch: /auth\.setup\.ts/,
    },
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        storageState: ".auth/admin.json",
      },
      dependencies: ["auth-setup"],
    },
  ],
});
