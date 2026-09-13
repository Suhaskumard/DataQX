import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { useEffect } from "react";
import DataDictionaryPage from "../src/pages/DataDictionaryPage";
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
          <DataDictionaryPage />
        </Seed>
      </RunProvider>
    </MemoryRouter>,
  );
}

describe("DataDictionaryPage with an active run", () => {
  it("renders the real dictionary rows", () => {
    renderWithRun({
      runId: "run_test_dict",
      dictionary: {
        files: {
          "sales.csv": [
            { column_name: "customer_name", data_type: "string", description: "Customer full name", missing_percentage: 0, unique_count: 40, example_values: "Alice; Bob", cleaning_actions: "trimmed" },
          ],
        },
      },
    } as any);

    expect(screen.getByText("sales.csv")).toBeInTheDocument();
    expect(screen.getByText("customer_name")).toBeInTheDocument();
    expect(screen.getByText("trimmed")).toBeInTheDocument();
  });
});

describe("DataDictionaryPage with no active run", () => {
  it("shows the empty state", () => {
    render(
      <MemoryRouter>
        <RunProvider>
          <DataDictionaryPage />
        </RunProvider>
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Data Dictionary" })).toBeInTheDocument();
    expect(screen.getByText("No dataset analyzed yet")).toBeInTheDocument();
  });
});
