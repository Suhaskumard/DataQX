import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { useEffect } from "react";
import DatasetOverview from "../src/pages/DatasetOverview";
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
          <DatasetOverview />
        </Seed>
      </RunProvider>
    </MemoryRouter>,
  );
}

describe("DatasetOverview with an active run", () => {
  it("renders real profile stats and column rows", () => {
    renderWithRun({
      runId: "run_test_do",
      analyzeResult: {
        files: {
          "sales.csv": {
            profile: {
              row_count: 150,
              column_count: 8,
              file_size_bytes: 20480,
              duplicate_row_count: 3,
              columns: [
                { original_name: "customer_name", inferred_type: "string", missing_percentage: 0, unique_percentage: 90 },
              ],
            },
          },
        },
      },
    } as any);

    expect(screen.getByText("sales.csv")).toBeInTheDocument();
    expect(screen.getByText("150")).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getByText("20480")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("customer_name")).toBeInTheDocument();
  });
});

describe("DatasetOverview with no active run", () => {
  it("shows the empty state", () => {
    render(
      <MemoryRouter>
        <RunProvider>
          <DatasetOverview />
        </RunProvider>
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Dataset Overview" })).toBeInTheDocument();
    expect(screen.getByText("No dataset analyzed yet")).toBeInTheDocument();
  });
});
