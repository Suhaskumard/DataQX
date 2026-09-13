import { defineConfig, devices } from "@playwright/test";

// Self-contained: starts both the real backend (uvicorn) and the real frontend
// (Vite dev server) so `npm run test:e2e` requires no manual setup, matching the
// two-terminal local-dev convention documented in README but automated for CI/local
// test runs. Both servers talk over the same ports the app uses in normal dev
// (backend :8000, frontend :5173) -- see frontend/src/services/api.ts.
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command: ".venv\\Scripts\\python -m uvicorn main:app",
      cwd: "../backend",
      url: "http://localhost:8000/health",
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: "npm run dev",
      url: "http://localhost:5173",
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
});
