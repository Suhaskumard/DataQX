import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { useEffect } from "react";
import PowerBIReadinessPage from "../src/pages/PowerBIReadinessPage";
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
          <PowerBIReadinessPage />
        </Seed>
      </RunProvider>
    </MemoryRouter>,
  );
}

describe("PowerBIReadinessPage with an active run", () => {
  it("renders the real score, table role, and check results", () => {
    renderWithRun({
      runId: "run_test_pb",
      powerbi: {
        files: {
          "sales.csv": {
            score: 82,
            table_role: "fact",
            checks: [{ check_name: "has_primary_key", status: "pass", message: "id column present" }],
          },
        },
      },
    } as any);

    expect(screen.getByText("82/100")).toBeInTheDocument();
    expect(screen.getByText("fact")).toBeInTheDocument();
    expect(screen.getByText("has_primary_key")).toBeInTheDocument();
  });
});

describe("PowerBIReadinessPage with no active run", () => {
  it("shows the empty state", () => {
    render(
      <MemoryRouter>
        <RunProvider>
          <PowerBIReadinessPage />
        </RunProvider>
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Power BI Readiness" })).toBeInTheDocument();
    expect(screen.getByText("No dataset analyzed yet")).toBeInTheDocument();
  });
});
