import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { useEffect } from "react";
import Dashboard from "../src/pages/Dashboard";
import { RunProvider, useRun } from "../src/context/RunContext";
import { ThemeProvider } from "../src/context/ThemeContext";

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
  analyticsReadiness: {
    files: {
      "sales.csv": {
        overall_score: 73,
        platforms: { power_bi: { platform: "Power BI", score: 73, status: "READY_WITH_WARNINGS" } },
      },
    },
  },
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
      <ThemeProvider><RunProvider>
        <Seed>
          <Dashboard />
        </Seed>
      </RunProvider></ThemeProvider>
    </MemoryRouter>,
  );
}

describe("Dashboard with an active run", () => {
  it("renders real metric values from the run context, not placeholders", () => {
    renderWithRun();

    expect(screen.getByText("87/100")).toBeInTheDocument(); // quality score
    expect(screen.getByText("42")).toBeInTheDocument(); // rows
    expect(screen.getByText("6")).toBeInTheDocument(); // columns
    expect(screen.getByText("73/100")).toBeInTheDocument(); // analytics readiness

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

describe("Dashboard with a failed analyze stage (Phase 25 fix)", () => {
  it("shows a clear failure message instead of crashing with a white screen", () => {
    const failedRun = {
      ...MOCK_RUN,
      analyzeResult: { files: { "sales.csv": { status: "failed", reason: "Could not analyze this file." } } },
    };
    function SeedFailed({ children }: { children: React.ReactNode }) {
      const { setRun } = useRun();
      useEffect(() => {
        setRun(failedRun as any);
      }, [setRun]);
      return <>{children}</>;
    }
    render(
      <MemoryRouter>
        <ThemeProvider><RunProvider>
          <SeedFailed>
            <Dashboard />
          </SeedFailed>
        </RunProvider></ThemeProvider>
      </MemoryRouter>,
    );

    expect(screen.getByText(/Analysis failed for "sales.csv"/)).toBeInTheDocument();
    expect(screen.getByText(/Could not analyze this file\./)).toBeInTheDocument();
  });
});

describe("Dashboard with a failed quality/analytics-readiness stage but successful analyze/clean", () => {
  it("degrades individual stat cards to a placeholder instead of crashing", () => {
    const partialRun = {
      ...MOCK_RUN,
      quality: { files: { "sales.csv": { status: "failed", reason: "Quality scoring errored." } } },
      analyticsReadiness: { files: { "sales.csv": { status: "failed", reason: "Analytics readiness check errored." } } },
    };
    function SeedPartial({ children }: { children: React.ReactNode }) {
      const { setRun } = useRun();
      useEffect(() => {
        setRun(partialRun as any);
      }, [setRun]);
      return <>{children}</>;
    }
    render(
      <MemoryRouter>
        <ThemeProvider><RunProvider>
          <SeedPartial>
            <Dashboard />
          </SeedPartial>
        </RunProvider></ThemeProvider>
      </MemoryRouter>,
    );

    // Page renders (no crash) and the rest of the dashboard still shows real data.
    expect(screen.getByText("42")).toBeInTheDocument(); // rows still render
    expect(screen.getAllByText("No dataset analyzed yet").length).toBeGreaterThan(0); // degraded stat cards
  });
});

describe("Dashboard with no active run", () => {
  it("shows the empty state, no fabricated numbers", () => {
    render(
      <MemoryRouter>
        <ThemeProvider><RunProvider>
          <Dashboard />
        </RunProvider></ThemeProvider>
      </MemoryRouter>,
    );

    expect(screen.getByText("No dataset uploaded yet")).toBeInTheDocument();
    expect(screen.getAllByText("No dataset analyzed yet").length).toBeGreaterThan(0);
  });
});
