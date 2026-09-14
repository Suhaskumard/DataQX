import { test, expect } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATASET_A = path.join(__dirname, "fixtures", "dataset_a.csv"); // 3 rows, 2 cols
const DATASET_B = path.join(__dirname, "fixtures", "dataset_b.csv"); // 5 rows, 4 cols

async function uploadAndWaitForDashboard(page: import("@playwright/test").Page, fixture: string) {
  await page.goto("/upload");
  await page.locator("#dataset-file-input").setInputFiles(fixture);
  await page.getByRole("button", { name: "Analyze Dataset" }).click();
  await page.waitForURL("/", { timeout: 30_000 });
}

// Real browser, real backend. Proves RunContext's full-replace-on-upload behavior
// holds against the live app, not just at the unit level: a second (and third)
// upload in the same session must never leave any trace of a prior run's filename
// or stats on the Dashboard.
function rowsStatCardValue(page: import("@playwright/test").Page) {
  return page.getByText("Rows", { exact: true }).locator("..").locator("p").nth(1);
}

test("uploading dataset B after A never shows A's data, and C never shows B's", async ({ page }) => {
  // Scoped to <main>: the redesigned global header also shows the active dataset
  // filename (a real, intentional addition), so an unscoped getByText now matches
  // both the header badge and the page body -- scoping to main keeps this test's
  // actual intent (no stale run data lingers in the page body) unambiguous.
  await uploadAndWaitForDashboard(page, DATASET_A);
  await expect(page.getByRole("main").getByText("dataset_a.csv")).toBeVisible();
  await expect(rowsStatCardValue(page)).toHaveText("3");

  await uploadAndWaitForDashboard(page, DATASET_B);
  await expect(page.getByRole("main").getByText("dataset_b.csv")).toBeVisible();
  await expect(page.getByRole("main").getByText("dataset_a.csv")).toHaveCount(0);
  await expect(rowsStatCardValue(page)).toHaveText("5");

  await uploadAndWaitForDashboard(page, DATASET_A);
  await expect(page.getByRole("main").getByText("dataset_a.csv")).toBeVisible();
  await expect(page.getByRole("main").getByText("dataset_b.csv")).toHaveCount(0);
  await expect(rowsStatCardValue(page)).toHaveText("3");
});
