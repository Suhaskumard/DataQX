import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { useEffect } from "react";
import DataLineagePage from "../src/pages/DataLineagePage";
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
          <DataLineagePage />
        </Seed>
      </RunProvider>
    </MemoryRouter>,
  );
}

describe("DataLineagePage with an active run", () => {
  it("renders real lineage rows", () => {
    renderWithRun({
      runId: "run_test_lin",
      lineage: {
        files: {
          "sales.csv": [
            { source_column: "Cust Name", transformation: "trim_whitespace", output_column: "customer_name", rule: "whitespace_formatting", confidence: "HIGH" },
          ],
        },
      },
    } as any);

    expect(screen.getByText("sales.csv")).toBeInTheDocument();
    expect(screen.getByText("Cust Name")).toBeInTheDocument();
    expect(screen.getByText("customer_name")).toBeInTheDocument();
  });

  it("shows the empty-lineage message when there are no entries", () => {
    renderWithRun({
      runId: "run_test_lin2",
      lineage: { files: { "sales.csv": [] } },
    } as any);

    expect(screen.getByText("No lineage data available.")).toBeInTheDocument();
  });
});

describe("DataLineagePage with no active run", () => {
  it("shows the empty state", () => {
    render(
      <MemoryRouter>
        <RunProvider>
          <DataLineagePage />
        </RunProvider>
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Data Lineage" })).toBeInTheDocument();
    expect(screen.getByText("No dataset analyzed yet")).toBeInTheDocument();
  });
});
