import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { useEffect } from "react";
import BeforeAfter from "../src/pages/BeforeAfter";
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
          <BeforeAfter />
        </Seed>
      </RunProvider>
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

describe("BeforeAfter with no active run", () => {
  it("shows the empty state", () => {
    render(
      <MemoryRouter>
        <RunProvider>
          <BeforeAfter />
        </RunProvider>
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Before vs After" })).toBeInTheDocument();
    expect(screen.getByText("No dataset analyzed yet")).toBeInTheDocument();
  });
});
