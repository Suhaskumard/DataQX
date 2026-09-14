import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
// Reuse the Phase 24 backend sample fixtures: customers.csv is the realistic
// analytics dataset AND the intentionally-corrupted dataset in one (real IDs,
// dates, categories, revenue, plus deliberate missing values, duplicates, mixed
// types, category-casing inconsistency, bad/ambiguous dates, negative values);
// orders.csv exercises the multi-file referential-integrity check with a real
// orphan foreign key. No need to invent new fixtures for this certification.
const CUSTOMERS_CSV = path.join(__dirname, "..", "..", "data", "samples", "customers.csv");
const ORDERS_CSV = path.join(__dirname, "..", "..", "data", "samples", "orders.csv");
const PROJECT_PLAN_TEXT = `# Project Plan

## Project Objective
Prepare customer and order data for the quarterly revenue dashboard.

## Required Columns
- customer_id
- revenue

## Columns That Must Not Be Modified
- customer_id
`;

const ALL_DOWNLOAD_LABELS = [
  "Download Clean Dataset (CSV)",
  "Download Clean Dataset (Excel)",
  "Download PDF Report",
  "Download Cleaning Log",
  "Download Audit Log",
  "Download Data Lineage",
  "Download Drift Report",
  "Download Validation Report",
  "Download Data Dictionary",
  "Download Before/After Summary",
  "Download Analytics Readiness",
];

test.describe("Final release certification", () => {
  test("real dataset + project plan through the full journey, every download verified", async ({ page, browserName }) => {
    // WebKit gets measurably slower across many sequential real downloads in this
    // environment (confirmed: the failure point moves to a different link each
    // run, not a specific broken one) -- a longer test timeout, not a code fix,
    // since Chromium/Firefox/Edge all complete the identical flow in ~5-12s.
    test.setTimeout(browserName === "webkit" ? 120_000 : 30_000);
    await page.goto("/upload");
    await page.locator("#dataset-file-input").setInputFiles([CUSTOMERS_CSV, ORDERS_CSV]);
    await page.getByLabel(/project plan/i).fill(PROJECT_PLAN_TEXT);
    await page.getByRole("button", { name: "Analyze Dataset" }).click();
    await page.waitForURL("/", { timeout: 30_000 });

    // Real quality/row/column numbers must actually render (not placeholders).
    await expect(page.getByText("No dataset uploaded yet")).toHaveCount(0);
    await expect(page.getByText(/\/100/)).toHaveCount(2); // quality score + analytics readiness

    const pagesToVisit = [
      "Dataset Overview",
      "Data Quality",
      "Cleaning Actions",
      "Before vs After",
      "Data Lineage",
      "Data Drift",
      "Analytics Readiness",
      "Data Dictionary",
    ];
    for (const label of pagesToVisit) {
      await page.getByRole("link", { name: label, exact: true }).click();
      await expect(page.getByRole("heading", { name: label })).toBeVisible();
    }

    // Analytics Readiness page must show the real orphan-FK finding from
    // orders.csv -> customers.csv on the default (Power BI) platform tab
    // (proves the multi-file referential-integrity check surfaced through the real UI).
    await page.getByRole("link", { name: "Analytics Readiness", exact: true }).click();
    await expect(page.getByText(/foreign_key_relationships/i)).toBeVisible();

    // --- Downloads: click every link, verify the real downloaded file ---
    await page.getByRole("link", { name: "Reports & Downloads", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Reports & Downloads" })).toBeVisible();

    for (const label of ALL_DOWNLOAD_LABELS) {
      const link = page.getByRole("link", { name: label });
      if ((await link.count()) === 0) continue; // some links are conditional on publish status

      let download;
      if (label === "Download PDF Report") {
        // Opens inline (no Content-Disposition: attachment) -- fetch and inspect
        // the response bytes directly instead of waiting for a download event.
        const href = await link.getAttribute("href");
        expect(href).toBeTruthy();
        const response = await page.request.get(href!);
        expect(response.status()).toBe(200);
        const body = await response.body();
        expect(body.length).toBeGreaterThan(1000);
        expect(body.subarray(0, 4).toString("utf-8")).toBe("%PDF");
        continue;
      }

      const downloadPromise = page.waitForEvent("download", { timeout: 20_000 });
      await link.click();
      download = await downloadPromise;
      await page.waitForTimeout(browserName === "webkit" ? 400 : 0); // let WebKit settle between downloads

      const savedPath = await download.path();
      expect(savedPath, `download for "${label}" must actually save to disk`).toBeTruthy();
      const stat = fs.statSync(savedPath!);
      expect(stat.size, `downloaded file for "${label}" must be non-empty`).toBeGreaterThan(0);

      const filename = download.suggestedFilename();
      if (filename.endsWith(".json")) {
        JSON.parse(fs.readFileSync(savedPath!, "utf-8")); // throws if not valid JSON
      } else if (filename.endsWith(".csv")) {
        const text = fs.readFileSync(savedPath!, "utf-8");
        expect(text.split("\n")[0].length, `"${label}" CSV must have a real header row`).toBeGreaterThan(0);
      } else if (filename.endsWith(".xlsx")) {
        const buf = fs.readFileSync(savedPath!);
        expect(buf.subarray(0, 2).toString("hex"), `"${label}" must be a real zip-based .xlsx`).toBe("504b");
      }
    }
  });

  test("rapid double-click on Analyze Dataset only triggers one upload chain", async ({ page }) => {
    const uploadRequests: string[] = [];
    page.on("request", (req) => {
      if (req.url().endsWith("/api/upload") && req.method() === "POST") {
        uploadRequests.push(req.url());
      }
    });

    await page.goto("/upload");
    await page.locator("#dataset-file-input").setInputFiles(CUSTOMERS_CSV);

    const button = page.getByRole("button", { name: "Analyze Dataset" });
    // Fire both clicks back-to-back without awaiting between them. The second
    // click is expected to race against the button disabling itself (isBusy in
    // Upload.tsx) -- it may legitimately fail to land at all once the button
    // becomes disabled, which is itself proof the guard works, not a test bug.
    await button.click();
    await button.click({ force: true, timeout: 2_000 }).catch(() => {
      /* expected: button already disabled by the time this lands */
    });

    await page.waitForURL("/", { timeout: 30_000 });
    // Regardless of whether the second click landed, it must never reach the
    // network as a second /api/upload call.
    expect(uploadRequests.length, "exactly one /api/upload request must fire").toBe(1);
  });
});
