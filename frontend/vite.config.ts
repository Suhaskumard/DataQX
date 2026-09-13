import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./tests/setup.ts",
    // e2e/ holds Playwright specs (run via `npm run test:e2e`), not Vitest tests.
    exclude: ["node_modules/**", "e2e/**"],
  },
});
