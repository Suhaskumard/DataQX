import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { useEffect } from "react";
import BeforeAfter from "../src/pages/BeforeAfter";
import { RunProvider, useRun } from "../src/context/RunContext";
import { ThemeProvider } from "../src/context/ThemeContext";

function Seed({ run, children }: { run: any; children: React.ReactNode }) {
  const { setRun } = useRun();
  useEffect(() => {
    setRun(run);
  }, [setRun, run]);
  return <>{children}</>;
}

function renderWithRun(run: any) {
  return render(
    <MemoryRouter>
      <ThemeProvider><RunProvider>
        <Seed run={run}>
          <BeforeAfter />
        </Seed>
      </RunProvider></ThemeProvider>
    </MemoryRouter>,
  );
}

describe("BeforeAfter with an active run", () => {
  it("renders real before/after metric rows", () => {
    renderWithRun({
      runId: "run_test_ba",
      beforeAfter: {
        files: {
          "sales.csv": {
            missing_values: { before: 120, after: 0, change: -120 },
          },
        },
      },
    } as any);

    expect(screen.getByText("sales.csv")).toBeInTheDocument();
    expect(screen.getByText("missing_values")).toBeInTheDocument();
    expect(screen.getByText("120")).toBeInTheDocument();
    expect(screen.getByText("-120")).toBeInTheDocument();
  });
});

describe("BeforeAfter with a failed before/after stage (Phase 25 fix)", () => {
  it("shows the empty state instead of rendering the failure object as fake metric rows", () => {
    renderWithRun({
      runId: "run_test_ba_failed",
      beforeAfter: {
        files: {
          "sales.csv": { status: "failed", reason: "Before/after computation errored." },
        },
      },
    } as any);

    // Must NOT render "status"/"reason" as if they were real before/after metrics.
    expect(screen.queryByText("status")).not.toBeInTheDocument();
    expect(screen.getByText("No dataset analyzed yet")).toBeInTheDocument();
  });
});

describe("BeforeAfter with no active run", () => {
  it("shows the empty state", () => {
    render(
      <MemoryRouter>
        <ThemeProvider><RunProvider>
          <BeforeAfter />
        </RunProvider></ThemeProvider>
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Before vs After" })).toBeInTheDocument();
    expect(screen.getByText("No dataset analyzed yet")).toBeInTheDocument();
  });
});
