import { describe, it, expect, vi, afterEach } from "vitest";
import { analyzeRun } from "../src/services/api";

describe("API error handling (Phase 25 fix)", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("formats a FastAPI-style array validation-error detail into a readable message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        json: async () => ({
          detail: [
            { loc: ["body", "run_id"], msg: "field required", type: "value_error.missing" },
            { loc: ["body", "extra"], msg: "unexpected field", type: "value_error" },
          ],
        }),
      }),
    );

    await expect(analyzeRun("run_1")).rejects.toThrow(/field required/);
    await expect(analyzeRun("run_1")).rejects.toThrow(/unexpected field/);
  });

  it("still uses a plain string detail when the backend returns one", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({ detail: "No uploaded files found for run 'run_1'." }),
      }),
    );

    await expect(analyzeRun("run_1")).rejects.toThrow("No uploaded files found for run 'run_1'.");
  });

  it("falls back to a generic status message when the body has no usable detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => {
          throw new Error("not json");
        },
      }),
    );

    await expect(analyzeRun("run_1")).rejects.toThrow("Request failed with status 500");
  });
});
