import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SAMPLE_CSV_PATH = path.join(__dirname, "fixtures", "sample.csv");

// Exercises Upload.tsx's actual onDrop handler via a synthetic DOM drop event
// (a real DataTransfer carrying a real File, dispatched as "dragover" then
// "drop") -- this is the standard, documented way Playwright simulates a file
// drop; it is NOT a real OS-level mouse-drag gesture (Playwright/Chromium DevTools
// Protocol cannot drive that), and this test does not claim otherwise. The
// pre-existing setInputFiles() test covers the "Choose Files" path; this one is
// the one and only test that actually exercises the dropzone's onDrop wiring.
test("dropping a file onto the dropzone is accepted via the real onDrop handler", async ({ page }) => {
  await page.goto("/upload");

  const fileContent = fs.readFileSync(SAMPLE_CSV_PATH, "utf-8");
  const dataTransfer = await page.evaluateHandle(
    ({ content, name }) => {
      const dt = new DataTransfer();
      const file = new File([content], name, { type: "text/csv" });
      dt.items.add(file);
      return dt;
    },
    { content: fileContent, name: "sample.csv" },
  );

  const dropzone = page.getByText("Drag and drop CSV, TSV, Excel, JSON, or Parquet files here").locator("..");
  await dropzone.dispatchEvent("dragover", { dataTransfer });
  await dropzone.dispatchEvent("drop", { dataTransfer });

  // Real proof the file was accepted through onDrop (not the hidden input path):
  // the same file-list UI that setInputFiles() would populate.
  await expect(page.getByText("sample.csv (")).toBeVisible();

  // Confirm the accepted file can actually proceed through the real pipeline,
  // not just render in the UI.
  await page.getByRole("button", { name: "Analyze Dataset" }).click();
  await page.waitForURL("/", { timeout: 30_000 });
  await expect(page.getByText("No dataset uploaded yet")).toHaveCount(0);
});
