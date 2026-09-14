import { test, expect } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SAMPLE_CSV = path.join(__dirname, "fixtures", "sample.csv");

// No pre-redesign timing was ever captured, so there is nothing honest to compare
// against -- this reports real, current numbers as a post-redesign baseline for
// future regressions to be measured against, not as a "before vs after" claim.
test.describe("Performance (post-redesign baseline, real measurements)", () => {
  test("initial load: navigation timing on the Upload page", async ({ page }) => {
    await page.goto("/upload");
    await expect(page.getByRole("heading", { name: "Upload Dataset" })).toBeVisible();

    const timing = await page.evaluate(() => {
      const [nav] = performance.getEntriesByType("navigation") as PerformanceNavigationTiming[];
      return {
        domContentLoaded: nav.domContentLoadedEventEnd - nav.startTime,
        loadEvent: nav.loadEventEnd - nav.startTime,
        domInteractive: nav.domInteractive - nav.startTime,
        transferSizeBytes: nav.transferSize,
      };
    });

    console.log(`[perf] Upload page initial load: domInteractive=${timing.domInteractive.toFixed(1)}ms domContentLoaded=${timing.domContentLoaded.toFixed(1)}ms loadEvent=${timing.loadEvent.toFixed(1)}ms transferSize=${timing.transferSizeBytes}B`);

    expect(timing.domContentLoaded).toBeGreaterThan(0);
  });

  test("render timing: Dashboard and Analytics Readiness after a real analyze run", async ({ page }) => {
    await page.goto("/upload");
    await page.locator("#dataset-file-input").setInputFiles(SAMPLE_CSV);

    const analyzeStart = Date.now();
    await page.getByRole("button", { name: "Analyze Dataset" }).click();
    await page.waitForURL("/", { timeout: 30_000 });
    await expect(page.getByText("Data Quality Score")).toBeVisible();
    const analyzeToRenderMs = Date.now() - analyzeStart;
    console.log(`[perf] Upload click -> Dashboard rendered with real data: ${analyzeToRenderMs}ms (includes real backend analyze+clean+validate round trip, not just client render)`);

    const readinessStart = Date.now();
    await page.getByRole("link", { name: "Analytics Readiness", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Analytics Readiness" })).toBeVisible();
    const readinessRenderMs = Date.now() - readinessStart;
    console.log(`[perf] Sidebar click -> Analytics Readiness rendered: ${readinessRenderMs}ms (client-side route render only, data already in RunContext)`);

    expect(analyzeToRenderMs).toBeGreaterThan(0);
    expect(readinessRenderMs).toBeGreaterThan(0);
  });
});
