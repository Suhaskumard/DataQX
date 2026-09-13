import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { useEffect } from "react";
import DataDriftPage from "../src/pages/DataDriftPage";
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
          <DataDriftPage />
        </Seed>
      </RunProvider>
    </MemoryRouter>,
  );
}

describe("DataDriftPage with no prior version", () => {
  it("shows the honest no-history message, not a fabricated comparison", () => {
    renderWithRun({
      runId: "run_test_drift1",
      drift: { files: { "sales.csv": { overall_status: "no_history" } } },
    } as any);

    expect(screen.getByText("No prior version to compare against")).toBeInTheDocument();
  });
});

describe("DataDriftPage with drift findings", () => {
  it("renders real drift findings and the compared-against run id", () => {
    renderWithRun({
      runId: "run_test_drift2",
      drift: {
        files: {
          "sales.csv": {
            overall_status: "drift_detected",
            compared_against: "run_20260101_000000_aaaaaaaa",
            findings: [
              { drift_type: "schema_change", column: "region", severity: "medium", description: "New column added" },
            ],
          },
        },
      },
    } as any);

    expect(screen.getByText("run_20260101_000000_aaaaaaaa")).toBeInTheDocument();
    expect(screen.getByText("schema_change")).toBeInTheDocument();
  });
});

describe("DataDriftPage with no active run", () => {
  it("shows the empty state", () => {
    render(
      <MemoryRouter>
        <RunProvider>
          <DataDriftPage />
        </RunProvider>
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Data Drift" })).toBeInTheDocument();
    expect(screen.getByText("No dataset analyzed yet")).toBeInTheDocument();
  });
});
