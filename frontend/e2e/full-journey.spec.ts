import { test, expect } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SAMPLE_CSV = path.join(__dirname, "fixtures", "sample.csv");

// Real browser, real backend, real frontend -- no mocked fetch. Walks the exact user
// journey DATAQX.pdf S71 describes: upload a dataset, land on a Dashboard populated
// from real API responses, then visit every sidebar page and confirm each renders
// real data (not the "no dataset" empty state), and finally trigger a real file
// download. This is the one test in the suite that proves the shipped product works
// end-to-end, not just that individual components render given mocked data.
test("uploads a dataset and walks the full journey through every page", async ({ page }) => {
  await page.goto("/upload");

  await page.locator("#dataset-file-input").setInputFiles(SAMPLE_CSV);
  await page.getByRole("button", { name: "Analyze Dataset" }).click();

  // The real upload -> analyze -> clean -> validate chain runs against the live
  // backend before the app navigates to the Dashboard.
  await page.waitForURL("/", { timeout: 30_000 });
  await expect(page.getByText("No dataset uploaded yet")).toHaveCount(0);
  await expect(page.getByText("Data Quality Score")).toBeVisible();

  const pagesToVisit: Array<{ label: string; heading: string }> = [
    { label: "Dataset Overview", heading: "Dataset Overview" },
    { label: "Data Quality", heading: "Data Quality" },
    { label: "Cleaning Actions", heading: "Cleaning Actions" },
    { label: "Before vs After", heading: "Before vs After" },
    { label: "Data Lineage", heading: "Data Lineage" },
    { label: "Data Drift", heading: "Data Drift" },
    { label: "Analytics Readiness", heading: "Analytics Readiness" },
    { label: "Data Dictionary", heading: "Data Dictionary" },
  ];

  for (const { label, heading } of pagesToVisit) {
    await page.getByRole("link", { name: label, exact: true }).click();
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
    // SPA-level RunContext state must have survived client-side navigation --
    // otherwise every page would fall back to its EmptyRunState.
    await expect(page.getByText("No dataset analyzed yet")).toHaveCount(0);
  }

  await page.getByRole("link", { name: "Reports & Downloads", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Reports & Downloads" })).toBeVisible();

  // The PDF report link opens inline (no Content-Disposition: attachment), so use
  // the cleaning log link, which is served via /api/download with a real attachment
  // header and is always present regardless of whether cleaning published output.
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download Cleaning Log" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("cleaning_log.csv");
});
