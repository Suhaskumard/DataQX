import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import Upload from "../src/pages/Upload";
import { RunProvider } from "../src/context/RunContext";

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
      return new Response(JSON.stringify({ files: { "data.csv": [] } }), { status: 200 });
    }
    if (url.includes("/api/quality/")) {
      return new Response(
        JSON.stringify({ files: { "data.csv": { after: { overall_score: 90 } } } }),
        { status: 200 },
      );
    }
    if (url.includes("/api/powerbi/")) {
      return new Response(JSON.stringify({ files: { "data.csv": { score: 80 } } }), { status: 200 });
    }
    if (url.includes("/api/drift/")) {
      return new Response(
        JSON.stringify({ files: { "data.csv": { overall_status: "no_history" } } }),
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
        <RunProvider>
          <Upload />
        </RunProvider>
      </MemoryRouter>,
    );

    const file = new File(["id,name\n1,Alice\n"], "data.csv", { type: "text/csv" });
    const input = screen.getByLabelText(/dataset file/i, { selector: "input" }) as HTMLInputElement;
    await user.upload(input, file);

    await user.click(screen.getByRole("button", { name: /analyze dataset/i }));

    await waitFor(() => {
      expect(calls.some((c) => c.endsWith("/api/validate"))).toBe(true);
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
  });

  it("shows a real error message when a step fails", async () => {
    globalThis.fetch = vi.fn(async () =>
      new Response(JSON.stringify({ detail: "No uploaded files found for run." }), { status: 404 }),
    ) as any;
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <RunProvider>
          <Upload />
        </RunProvider>
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
});
