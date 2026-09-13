import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { useEffect } from "react";
import Dashboard from "../src/pages/Dashboard";
import { RunProvider, useRun } from "../src/context/RunContext";

const MOCK_RUN = {
  runId: "run_test_456",
  uploadResult: { run_id: "run_test_456" },
  analyzeResult: {
    files: { "sales.csv": { profile: { row_count: 42, column_count: 6 } } },
  },
  cleanResult: {
    files: { "sales.csv": { status: "cleaned", log: [{ issue_type: "whitespace_formatting" }, { issue_type: "missing_value_placeholder" }] } },
  },
  validateResult: { files: { "sales.csv": { overall_status: "warning" } } },
  issues: {
    files: {
      "sales.csv": [
        { issue_type: "outlier", severity: "high", confidence: { confidence: "LOW" } },
        { issue_type: "whitespace_formatting", severity: "low", confidence: { confidence: "HIGH" } },
      ],
    },
  },
  quality: { files: { "sales.csv": { after: { overall_score: 87 } } } },
  powerbi: { files: { "sales.csv": { score: 73 } } },
  drift: { files: { "sales.csv": { overall_status: "no_history" } } },
  performance: {
    processing_time_seconds: { upload: 0.01, analyze: 0.25, clean: 0.12, validate: 0.05 },
    bottleneck_stage: "analyze",
    bottleneck_seconds: 0.25,
  },
};

function Seed({ children }: { children: React.ReactNode }) {
  const { setRun } = useRun();
  useEffect(() => {
    setRun(MOCK_RUN as any);
  }, [setRun]);
  return <>{children}</>;
}

function renderWithRun() {
  return render(
    <MemoryRouter>
      <RunProvider>
        <Seed>
          <Dashboard />
        </Seed>
      </RunProvider>
    </MemoryRouter>,
  );
}

describe("Dashboard with an active run", () => {
  it("renders real metric values from the run context, not placeholders", () => {
    renderWithRun();

    expect(screen.getByText("87/100")).toBeInTheDocument(); // quality score
    expect(screen.getByText("42")).toBeInTheDocument(); // rows
    expect(screen.getByText("6")).toBeInTheDocument(); // columns
    expect(screen.getByText("73/100")).toBeInTheDocument(); // powerbi readiness

    // Both Issues Detected and Issues Fixed happen to be 2 in this fixture --
    // scope each query to its own card rather than a bare text match.
    expect(screen.getByText("Issues Detected").closest("div")).toHaveTextContent("2");
    expect(screen.getByText("Issues Fixed").closest("div")).toHaveTextContent("2");
  });

  it("shows the dataset filename and published status", () => {
    renderWithRun();
    expect(screen.getByText("sales.csv")).toBeInTheDocument();
    expect(screen.getByText("Published")).toBeInTheDocument();
  });

  it("renders real per-stage performance timings and the bottleneck (Phase 21)", () => {
    renderWithRun();
    expect(screen.getByText("Performance")).toBeInTheDocument();
    expect(screen.getByText("0.2500")).toBeInTheDocument(); // analyze stage seconds
    expect(screen.getByText(/Slowest stage:/)).toBeInTheDocument();
    expect(screen.getAllByText("analyze").length).toBeGreaterThan(0);
  });

  it("computes review-required and critical-issue counts from real issue data", () => {
    renderWithRun();
    // 1 LOW-confidence issue (outlier), 1 high-severity issue (outlier) -- both count 1.
    const reviewRequiredCard = screen.getByText("Review Required").closest("div");
    expect(reviewRequiredCard).toHaveTextContent("1");

    const criticalCard = screen.getByText("Critical Issues").closest("div");
    expect(criticalCard).toHaveTextContent("1");
  });
});

describe("Dashboard with no active run", () => {
  it("shows the empty state, no fabricated numbers", () => {
    render(
      <MemoryRouter>
        <RunProvider>
          <Dashboard />
        </RunProvider>
      </MemoryRouter>,
    );

    expect(screen.getByText("No dataset uploaded yet")).toBeInTheDocument();
    expect(screen.getAllByText("No dataset analyzed yet").length).toBeGreaterThan(0);
  });
});
