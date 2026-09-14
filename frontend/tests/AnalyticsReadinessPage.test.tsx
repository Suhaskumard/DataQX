import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { useEffect } from "react";
import AnalyticsReadinessPage from "../src/pages/AnalyticsReadinessPage";
import { RunProvider, useRun } from "../src/context/RunContext";

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
      <RunProvider>
        <Seed run={run}>
          <AnalyticsReadinessPage />
        </Seed>
      </RunProvider>
    </MemoryRouter>,
  );
}

const MOCK_RUN = {
  runId: "run_test_ar",
  analyticsReadiness: {
    files: {
      "sales.csv": {
        overall_score: 82,
        platforms: {
          power_bi: {
            platform: "Power BI",
            score: 90,
            status: "READY",
            checks: [{ check_name: "has_primary_key", status: "pass", message: "id column present" }],
            recommendations: [],
          },
          sql: {
            platform: "SQL",
            score: 74,
            status: "READY_WITH_WARNINGS",
            checks: [{ check_name: "primary_key_candidates", status: "warning", message: "No obvious key found." }],
            recommendations: ["Add a primary key column."],
          },
        },
      },
    },
  },
};

describe("AnalyticsReadinessPage with an active run", () => {
  it("renders the real overall score and every evaluated platform", () => {
    renderWithRun(MOCK_RUN as any);

    expect(screen.getByText("82")).toBeInTheDocument(); // overall ScoreRing value
    expect(screen.getByText("Power BI")).toBeInTheDocument();
    expect(screen.getByText("SQL")).toBeInTheDocument();
    expect(screen.getByText("90/100")).toBeInTheDocument();
    expect(screen.getByText("74/100")).toBeInTheDocument();
  });

  it("shows the checks for the first platform by default", () => {
    renderWithRun(MOCK_RUN as any);
    expect(screen.getByText("has_primary_key")).toBeInTheDocument();
  });

  it("switches the detail view when a different platform card is clicked", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    renderWithRun(MOCK_RUN as any);

    await user.click(screen.getByText("SQL"));
    expect(screen.getByText("primary_key_candidates")).toBeInTheDocument();
    expect(screen.getByText("Add a primary key column.")).toBeInTheDocument();
  });
});

describe("AnalyticsReadinessPage with no active run", () => {
  it("shows the empty state", () => {
    render(
      <MemoryRouter>
        <RunProvider>
          <AnalyticsReadinessPage />
        </RunProvider>
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Analytics Readiness" })).toBeInTheDocument();
    expect(screen.getByText("No dataset analyzed yet")).toBeInTheDocument();
  });
});
