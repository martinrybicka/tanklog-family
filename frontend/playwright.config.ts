import { defineConfig, devices } from "@playwright/test";

if (
  (process.env.E2E_PRODUCTION || process.env.E2E_HTTPS) &&
  !["localhost", "127.0.0.1"].includes(
    new URL(process.env.E2E_BASE_URL || "http://localhost:8080").hostname,
  )
) {
  throw new Error(
    "HTTPS produkční ověření smí cílit jen na místní syntetické prostředí.",
  );
}

export default defineConfig({
  testDir: "./e2e",
  outputDir: process.env.E2E_PRODUCTION
    ? "../.runtime/playwright-production"
    : "../.runtime/playwright-development",
  fullyParallel: false,
  workers: 1,
  timeout: 30_000,
  reporter: "list",
  use: {
    ignoreHTTPSErrors: !!process.env.E2E_HTTPS,
    launchOptions: {
      args: process.env.E2E_HTTPS ? ["--ignore-certificate-errors"] : [],
    },
    baseURL: process.env.E2E_BASE_URL || "http://localhost:8080",
    channel: process.env.E2E_BROWSER_CHANNEL || "chrome",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    {
      name: "mobile",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
      },
    },
  ],
});
