import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import Upload from "../src/pages/Upload";
import Dashboard from "../src/pages/Dashboard";
import { RunProvider } from "../src/context/RunContext";
import { ThemeProvider } from "../src/context/ThemeContext";

const RUN_ID = "run_test_123";

function mockFetchSequence() {
  const calls: string[] = [];
  globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : input.toString();
    calls.push(url);

    if (url.endsWith("/api/upload")) {
      return new Response(JSON.stringify({ run_id: RUN_ID, files: {} }), { status: 200 });
    }
    if (url.endsWith("/api/analyze")) {
      return new Response(
        JSON.stringify({ run_id: RUN_ID, files: { "data.csv": { profile: { row_count: 4, column_count: 2 } } } }),
        { status: 200 },
      );
    }
    if (url.endsWith("/api/clean")) {
      return new Response(
        JSON.stringify({ run_id: RUN_ID, files: { "data.csv": { status: "cleaned", log: [] } } }),
        { status: 200 },
      );
    }
    if (url.endsWith("/api/validate")) {
      return new Response(
        JSON.stringify({ run_id: RUN_ID, files: { "data.csv": { overall_status: "pass" } } }),
        { status: 200 },
      );
    }
    if (url.includes("/api/issues/")) {
      return new Response(
        JSON.stringify({
          files: {
            "data.csv": [
              { issue_type: "missing_value_placeholder", column: "name", severity: "medium", affected_count: 1, confidence: { confidence: "HIGH" } },
            ],
          },
        }),
        { status: 200 },
      );
    }
    if (url.includes("/api/quality/")) {
      // Realistic shape: both before/after present, not just the field the page reads.
      return new Response(
        JSON.stringify({
          files: {
            "data.csv": {
              before: { overall_score: 62 },
              after: { overall_score: 90 },
            },
          },
        }),
        { status: 200 },
      );
    }
    if (url.includes("/api/analytics-readiness/")) {
      return new Response(
        JSON.stringify({
          files: {
            "data.csv": {
              overall_score: 80,
              platforms: { power_bi: { platform: "Power BI", score: 80, status: "READY", checks: [] } },
            },
          },
        }),
        { status: 200 },
      );
    }
    if (url.includes("/api/drift/")) {
      return new Response(
        JSON.stringify({ files: { "data.csv": { overall_status: "no_history", compared_against: null, findings: [] } } }),
        { status: 200 },
      );
    }
    if (url.includes("/api/lineage/")) {
      return new Response(
        JSON.stringify({
          files: {
            "data.csv": [
              { source_column: "name", transformation: "trimmed whitespace", output_column: "name", rule: "whitespace_formatting", confidence: "HIGH" },
            ],
          },
        }),
        { status: 200 },
      );
    }
    if (url.includes("/api/before-after/")) {
      return new Response(
        JSON.stringify({ files: { "data.csv": { missing_values: { before: 1, after: 0, change: -1 } } } }),
        { status: 200 },
      );
    }
    if (url.includes("/api/dictionary/")) {
      return new Response(
        JSON.stringify({
          files: {
            "data.csv": [
              { column_name: "name", data_type: "string", description: "Customer name", missing_percentage: 0, unique_count: 4, example_values: ["Alice"], cleaning_actions: null },
            ],
          },
        }),
        { status: 200 },
      );
    }
    if (url.includes("/api/performance/")) {
      return new Response(
        JSON.stringify({ processing_time_seconds: { upload: 0.01 }, bottleneck_stage: null, bottleneck_seconds: null }),
        { status: 200 },
      );
    }
    throw new Error(`Unexpected fetch: ${url}`);
  }) as any;
  return calls;
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("Upload page", () => {
  it("runs the full upload -> analyze -> clean -> validate chain in order", async () => {
    const calls = mockFetchSequence();
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <ThemeProvider><RunProvider>
          <Upload />
        </RunProvider></ThemeProvider>
      </MemoryRouter>,
    );

    const file = new File(["id,name\n1,Alice\n"], "data.csv", { type: "text/csv" });
    const input = screen.getByLabelText(/dataset file/i, { selector: "input" }) as HTMLInputElement;
    await user.upload(input, file);

    await user.click(screen.getByRole("button", { name: /analyze dataset/i }));

    await waitFor(() => {
      expect(calls.some((c) => c.includes("/api/performance/"))).toBe(true);
    });

    const orderedRelevant = calls.filter((c) =>
      ["/api/upload", "/api/analyze", "/api/clean", "/api/validate"].some((p) => c.endsWith(p)),
    );
    expect(orderedRelevant.map((c) => c.split("/api/")[1])).toEqual([
      "upload",
      "analyze",
      "clean",
      "validate",
    ]);

    expect(calls.some((c) => c.includes("/api/lineage/"))).toBe(true);
    expect(calls.some((c) => c.includes("/api/before-after/"))).toBe(true);
  });

  it("populates RunContext with real values that Dashboard actually renders after the full chain", async () => {
    mockFetchSequence();
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/upload"]}>
        <ThemeProvider><RunProvider>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/upload" element={<Upload />} />
          </Routes>
        </RunProvider></ThemeProvider>
      </MemoryRouter>,
    );

    const file = new File(["id,name\n1,Alice\n"], "data.csv", { type: "text/csv" });
    const input = screen.getByLabelText(/dataset file/i, { selector: "input" }) as HTMLInputElement;
    await user.upload(input, file);
    await user.click(screen.getByRole("button", { name: /analyze dataset/i }));

    // Upload navigates to "/" (Dashboard) once the full chain + enrichment calls finish.
    await waitFor(() => {
      expect(screen.getByText("90/100")).toBeInTheDocument(); // real quality.after.overall_score
    });
    expect(screen.getByText("4")).toBeInTheDocument(); // real profile.row_count
    expect(screen.getByText("80/100")).toBeInTheDocument(); // real analyticsReadiness.overall_score
    expect(screen.getByText("Published")).toBeInTheDocument(); // real cleanResult.status === "cleaned"
  });

  it("still reaches the Dashboard when one enrichment endpoint 404s (Phase 25 fix: Promise.allSettled)", async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/upload")) {
        return new Response(JSON.stringify({ run_id: RUN_ID, files: {} }), { status: 200 });
      }
      if (url.endsWith("/api/analyze")) {
        return new Response(
          JSON.stringify({ run_id: RUN_ID, files: { "data.csv": { status: "failed", reason: "Could not open Excel file." } } }),
          { status: 200 },
        );
      }
      if (url.endsWith("/api/clean") || url.endsWith("/api/validate")) {
        return new Response(
          JSON.stringify({ run_id: RUN_ID, files: { "data.csv": { status: "failed", reason: "Could not open Excel file." } } }),
          { status: 200 },
        );
      }
      // Every enrichment GET succeeds except the data dictionary, which 404s --
      // exactly the real backend behavior discovered for a file with no cleaned
      // output. Before the fix, this single rejection lost every other result.
      if (url.includes("/api/dictionary/")) {
        return new Response(JSON.stringify({ detail: "No data dictionary found for this run." }), { status: 404 });
      }
      return new Response(JSON.stringify({ files: {} }), { status: 200 });
    }) as any;

    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/upload"]}>
        <ThemeProvider><RunProvider>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/upload" element={<Upload />} />
          </Routes>
        </RunProvider></ThemeProvider>
      </MemoryRouter>,
    );

    const file = new File(["garbage"], "data.csv", { type: "text/csv" });
    const input = screen.getByLabelText(/dataset file/i, { selector: "input" }) as HTMLInputElement;
    await user.upload(input, file);
    await user.click(screen.getByRole("button", { name: /analyze dataset/i }));

    // Must reach the Dashboard (not get stuck on an Upload-page error banner)
    // despite the dictionary endpoint having 404'd.
    await waitFor(() => {
      expect(screen.getByText(/Analysis failed for "data\.csv"/)).toBeInTheDocument();
    });
  });

  it("shows a real error message when a step fails", async () => {
    globalThis.fetch = vi.fn(async () =>
      new Response(JSON.stringify({ detail: "No uploaded files found for run." }), { status: 404 }),
    ) as any;
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <ThemeProvider><RunProvider>
          <Upload />
        </RunProvider></ThemeProvider>
      </MemoryRouter>,
    );

    const file = new File(["a,b\n1,2\n"], "data.csv", { type: "text/csv" });
    const input = screen.getByLabelText(/dataset file/i, { selector: "input" }) as HTMLInputElement;
    await user.upload(input, file);
    await user.click(screen.getByRole("button", { name: /analyze dataset/i }));

    await waitFor(() => {
      expect(screen.getByText("No uploaded files found for run.")).toBeInTheDocument();
    });
  });

  it("associates the Project Plan label with its textarea (accessibility fix)", () => {
    render(
      <MemoryRouter>
        <ThemeProvider><RunProvider>
          <Upload />
        </RunProvider></ThemeProvider>
      </MemoryRouter>,
    );

    // getByLabelText only succeeds if the <label> is properly associated (htmlFor/id)
    // with the textarea -- this previously had no association at all.
    const textarea = screen.getByLabelText(/project plan/i);
    expect(textarea.tagName).toBe("TEXTAREA");
  });
});
