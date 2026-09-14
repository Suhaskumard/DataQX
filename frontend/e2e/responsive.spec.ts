import { test, expect } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SAMPLE_CSV = path.join(__dirname, "fixtures", "sample.csv");

// Representative breakpoints from the campaign's requested matrix -- narrow mobile,
// tablet, and desktop. The DataTable component only has one CSS-level responsive
// strategy (overflow-x-auto on the table wrapper), so the real thing worth proving
// is "the page body itself never grows a horizontal scrollbar" -- a wide table should
// scroll *within its own box*, not blow out the whole page layout.
const VIEWPORTS = [
  { name: "mobile-320", width: 320, height: 700 },
  { name: "mobile-375", width: 375, height: 700 },
  { name: "tablet-768", width: 768, height: 900 },
  { name: "desktop-1440", width: 1440, height: 900 },
];

test.describe("Responsive layout", () => {
  for (const viewport of VIEWPORTS) {
    test(`dashboard has no page-level horizontal overflow at ${viewport.name}`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto("/upload");
      await page.locator("#dataset-file-input").setInputFiles(SAMPLE_CSV);
      await page.getByRole("button", { name: "Analyze Dataset" }).click();
      await page.waitForURL("/", { timeout: 30_000 });

      const hasHorizontalOverflow = await page.evaluate(
        () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
      );
      expect(hasHorizontalOverflow, "page body should never require horizontal scrolling").toBe(false);
    });

    test(`data quality table stays usable at ${viewport.name}`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto("/upload");
      await page.locator("#dataset-file-input").setInputFiles(SAMPLE_CSV);
      await page.getByRole("button", { name: "Analyze Dataset" }).click();
      await page.waitForURL("/", { timeout: 30_000 });

      await page.getByRole("link", { name: "Data Quality", exact: true }).click();
      await expect(page.getByRole("heading", { name: "Data Quality" })).toBeVisible();

      const hasHorizontalOverflow = await page.evaluate(
        () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
      );
      expect(hasHorizontalOverflow, "wide table must scroll within its own container, not the whole page").toBe(
        false,
      );
    });
  }
});
