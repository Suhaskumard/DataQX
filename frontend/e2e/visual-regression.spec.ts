import { test, expect, type Page } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SAMPLE_CSV = path.join(__dirname, "fixtures", "sample.csv");

// Screenshot rendering (font hinting/anti-aliasing) genuinely differs per browser
// engine -- and even within the same Chromium engine, per channel (plain chromium
// vs. the "msedge" channel render subtly differently) -- so baselines are
// maintained for exactly one project, keyed by project name, not engine name
// (msedge reports browserName "chromium" too, so that alone won't distinguish it).
test.beforeEach(({}, testInfo) => {
  test.skip(testInfo.project.name !== "chromium", "Visual baselines are maintained for the chromium project only (rendering differs per engine/channel).");
});

async function setTheme(page: Page, theme: "light" | "dark") {
  await page.addInitScript((t) => window.localStorage.setItem("dataqx-theme", t), theme);
}

async function uploadAndAnalyze(page: Page) {
  await page.goto("/upload");
  await page.locator("#dataset-file-input").setInputFiles(SAMPLE_CSV);
  await page.getByRole("button", { name: "Analyze Dataset" }).click();
  await page.waitForURL("/", { timeout: 30_000 });
  await expect(page.getByText("Data Quality Score")).toBeVisible();
}

// The run-id/timestamp in the header, and per-run timing numbers on the
// Dashboard's Performance table, are genuinely nondeterministic run-to-run --
// masked (painted over, not pixel-compared) rather than causing every run to
// "fail" on irrelevant digits, per the brief's own anti-brittleness rule.
function dynamicMasks(page: Page) {
  return [page.getByTestId("run-context"), page.getByTestId("performance-section")];
}

// Wherever the mouse happens to land after prior clicks/navigation can sit over a
// recharts bar and pop a hover tooltip into the page -- not masked, since a
// stray tooltip is cursor-position nondeterminism, not genuinely-changing
// content. Parking the cursor off the page before every screenshot removes the
// nondeterminism at its source instead of hiding it.
async function parkMouse(page: Page) {
  await page.mouse.move(0, 0);
}

test.describe("Visual regression baselines", () => {
  test("Dashboard - light", async ({ page }) => {
    await setTheme(page, "light");
    await uploadAndAnalyze(page);
    await parkMouse(page);
    await expect(page).toHaveScreenshot("dashboard-light.png", { mask: dynamicMasks(page), fullPage: true });
  });

  test("Dashboard - dark", async ({ page }) => {
    await setTheme(page, "dark");
    await uploadAndAnalyze(page);
    await parkMouse(page);
    await expect(page).toHaveScreenshot("dashboard-dark.png", { mask: dynamicMasks(page), fullPage: true });
  });

  test("Analytics Readiness - light", async ({ page }) => {
    await setTheme(page, "light");
    await uploadAndAnalyze(page);
    await page.getByRole("link", { name: "Analytics Readiness", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Analytics Readiness" })).toBeVisible();
    await parkMouse(page);
    await expect(page).toHaveScreenshot("analytics-readiness-light.png", { mask: dynamicMasks(page), fullPage: true });
  });

  test("Analytics Readiness - dark", async ({ page }) => {
    await setTheme(page, "dark");
    await uploadAndAnalyze(page);
    await page.getByRole("link", { name: "Analytics Readiness", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Analytics Readiness" })).toBeVisible();
    await parkMouse(page);
    await expect(page).toHaveScreenshot("analytics-readiness-dark.png", { mask: dynamicMasks(page), fullPage: true });
  });

  test("Upload - light", async ({ page }) => {
    await setTheme(page, "light");
    await page.goto("/upload");
    await parkMouse(page);
    await expect(page).toHaveScreenshot("upload-light.png", { fullPage: true });
  });

  test("Upload - dark", async ({ page }) => {
    await setTheme(page, "dark");
    await page.goto("/upload");
    await parkMouse(page);
    await expect(page).toHaveScreenshot("upload-dark.png", { fullPage: true });
  });

  test("Data Quality - light", async ({ page }) => {
    await setTheme(page, "light");
    await uploadAndAnalyze(page);
    await page.getByRole("link", { name: "Data Quality", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Data Quality" })).toBeVisible();
    await parkMouse(page);
    await expect(page).toHaveScreenshot("data-quality-light.png", { mask: dynamicMasks(page), fullPage: true });
  });

  test("Data Quality - dark", async ({ page }) => {
    await setTheme(page, "dark");
    await uploadAndAnalyze(page);
    await page.getByRole("link", { name: "Data Quality", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Data Quality" })).toBeVisible();
    await parkMouse(page);
    await expect(page).toHaveScreenshot("data-quality-dark.png", { mask: dynamicMasks(page), fullPage: true });
  });

  test("Data Dictionary - light", async ({ page }) => {
    await setTheme(page, "light");
    await uploadAndAnalyze(page);
    await page.getByRole("link", { name: "Data Dictionary", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Data Dictionary" })).toBeVisible();
    await parkMouse(page);
    await expect(page).toHaveScreenshot("data-dictionary-light.png", { mask: dynamicMasks(page), fullPage: true });
  });

  test("Data Dictionary - dark", async ({ page }) => {
    await setTheme(page, "dark");
    await uploadAndAnalyze(page);
    await page.getByRole("link", { name: "Data Dictionary", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Data Dictionary" })).toBeVisible();
    await parkMouse(page);
    await expect(page).toHaveScreenshot("data-dictionary-dark.png", { mask: dynamicMasks(page), fullPage: true });
  });

  test("Reports & Downloads - light", async ({ page }) => {
    await setTheme(page, "light");
    await uploadAndAnalyze(page);
    await page.getByRole("link", { name: "Reports & Downloads", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Reports & Downloads" })).toBeVisible();
    await parkMouse(page);
    await expect(page).toHaveScreenshot("reports-downloads-light.png", { mask: dynamicMasks(page), fullPage: true });
  });

  test("Reports & Downloads - dark", async ({ page }) => {
    await setTheme(page, "dark");
    await uploadAndAnalyze(page);
    await page.getByRole("link", { name: "Reports & Downloads", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Reports & Downloads" })).toBeVisible();
    await parkMouse(page);
    await expect(page).toHaveScreenshot("reports-downloads-dark.png", { mask: dynamicMasks(page), fullPage: true });
  });
});
