import { test, expect } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const UNSUPPORTED_FILE = path.join(__dirname, "fixtures", "unsupported.exe");
const CORRUPT_XLSX = path.join(__dirname, "fixtures", "corrupt.xlsx");
const SAMPLE_CSV = path.join(__dirname, "fixtures", "sample.csv");

// Real browser, real backend -- exercises Upload.tsx's actual error/failure paths
// against real backend rejection responses, per the campaign's chaos-testing ask.
// No mocking: if either the backend's error shape or the frontend's handling of it
// regresses, these fail for real.
test.describe("Error paths", () => {
  test("an entirely unsupported file type shows a real in-app error, not a white screen", async ({ page }) => {
    await page.goto("/upload");
    await page.locator("#dataset-file-input").setInputFiles(UNSUPPORTED_FILE);
    await page.getByRole("button", { name: "Analyze Dataset" }).click();

    // The backend rejects the file at upload (unsupported extension), leaving zero
    // saved files for the run; /api/analyze then 404s "No uploaded files found" --
    // Upload.tsx's catch block must surface that as a visible, real error message.
    await expect(page.getByText(/no uploaded files found/i)).toBeVisible({ timeout: 15_000 });
    // Must still be on the upload page, not silently redirected or blanked.
    await expect(page.getByRole("heading", { name: "Upload Dataset" })).toBeVisible();
  });

  test("a corrupt file that fails analysis still reaches the Dashboard with a friendly message", async ({ page }) => {
    await page.goto("/upload");
    await page.locator("#dataset-file-input").setInputFiles(CORRUPT_XLSX);
    await page.getByRole("button", { name: "Analyze Dataset" }).click();

    // A corrupt-but-allowed-extension file saves successfully and the whole
    // upload->analyze->clean->validate chain returns 200s (the backend's per-file
    // try/except keeps the run alive) -- the failure only shows up as this file's
    // per-file status. One enrichment endpoint (data dictionary) legitimately 404s
    // for a file that never produced cleaned output -- a real bug this test caught:
    // that single 404 used to reject the whole Promise.all and strand the user on
    // an error message despite every other stage having real, useful results.
    // Fixed to Promise.allSettled (see src/pages/Upload.tsx) so the run still loads.
    await page.waitForURL("/", { timeout: 30_000 });
    await expect(page.getByText(/Analysis failed for "corrupt\.xlsx"/)).toBeVisible();
  });

  test("recovers cleanly: a failed upload does not prevent a subsequent successful one", async ({ page }) => {
    await page.goto("/upload");
    await page.locator("#dataset-file-input").setInputFiles(UNSUPPORTED_FILE);
    await page.getByRole("button", { name: "Analyze Dataset" }).click();
    await expect(page.getByText(/no uploaded files found/i)).toBeVisible({ timeout: 15_000 });

    // Reset and try again with a real, valid file in the same session.
    await page.reload();
    await page.locator("#dataset-file-input").setInputFiles(SAMPLE_CSV);
    await page.getByRole("button", { name: "Analyze Dataset" }).click();
    await page.waitForURL("/", { timeout: 30_000 });
    await expect(page.getByText("Data Quality Score")).toBeVisible();
  });
});
