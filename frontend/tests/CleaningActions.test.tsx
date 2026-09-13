import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { useEffect } from "react";
import CleaningActions from "../src/pages/CleaningActions";
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
          <CleaningActions />
        </Seed>
      </RunProvider>
    </MemoryRouter>,
  );
}

describe("CleaningActions with a cleaned run", () => {
  it("renders real cleaning log rows", () => {
    renderWithRun({
      runId: "run_test_ca",
      cleanResult: {
        files: {
          "sales.csv": {
            status: "cleaned",
            log: [
              { issue_type: "missing_value_placeholder", column: "region", confidence: "HIGH", action_taken: "filled", reason: "placeholder replaced", affected_count: 5 },
            ],
          },
        },
      },
    } as any);

    expect(screen.getByText("sales.csv")).toBeInTheDocument();
    expect(screen.getByText("missing_value_placeholder")).toBeInTheDocument();
    expect(screen.getByText("filled")).toBeInTheDocument();
    expect(screen.queryByText(/rolled back/i)).not.toBeInTheDocument();
  });
});

describe("CleaningActions with a rolled-back run", () => {
  it("shows the rollback reason banner instead of fabricating a log", () => {
    renderWithRun({
      runId: "run_test_ca2",
      cleanResult: {
        files: {
          "sales.csv": {
            status: "rolled_back",
            reason: "too many rows affected",
            log: [{ issue_type: "should_not_render", column: "x", confidence: "HIGH", action_taken: "x", reason: "x", affected_count: 1 }],
          },
        },
      },
    } as any);

    expect(screen.getByText(/rolled back and not published/i)).toBeInTheDocument();
    expect(screen.getByText(/too many rows affected/i)).toBeInTheDocument();
    expect(screen.getByText("No cleaning actions were applied.")).toBeInTheDocument();
  });
});

describe("CleaningActions with no active run", () => {
  it("shows the empty state", () => {
    render(
      <MemoryRouter>
        <RunProvider>
          <CleaningActions />
        </RunProvider>
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Cleaning Actions" })).toBeInTheDocument();
    expect(screen.getByText("No dataset analyzed yet")).toBeInTheDocument();
  });
});
