import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: true,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:4173",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "admin-desktop",
      use: { viewport: { width: 1440, height: 1000 } },
    },
    {
      name: "admin-compact",
      use: { viewport: { width: 768, height: 1024 } },
    },
    {
      name: "employee-mobile",
      use: { viewport: { width: 375, height: 812 } },
    },
  ],
  webServer: {
    command: "node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 4173",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
