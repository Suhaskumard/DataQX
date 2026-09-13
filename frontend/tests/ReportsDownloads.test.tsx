import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { useEffect } from "react";
import ReportsDownloads from "../src/pages/ReportsDownloads";
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
          <ReportsDownloads />
        </Seed>
      </RunProvider>
    </MemoryRouter>,
  );
}

describe("ReportsDownloads with a cleaned (published) run", () => {
  it("shows real download links for the clean dataset", () => {
    renderWithRun({
      runId: "run_test_rd",
      cleanResult: { files: { "sales.csv": { status: "cleaned", log: [] } } },
    } as any);

    const csvLink = screen.getByRole("link", { name: /Download Clean Dataset \(CSV\)/i });
    expect(csvLink).toHaveAttribute("href", expect.stringContaining("/api/download/run_test_rd/sales_cleaned.csv"));

    const pdfLink = screen.getByRole("link", { name: /Download PDF Report/i });
    expect(pdfLink).toHaveAttribute("href", expect.stringContaining("/api/report/run_test_rd"));

    expect(screen.queryByText(/rolled back/i)).not.toBeInTheDocument();
  });
});

describe("ReportsDownloads with a rolled-back run", () => {
  it("hides the clean-dataset links and shows the rollback notice", () => {
    renderWithRun({
      runId: "run_test_rd2",
      cleanResult: { files: { "sales.csv": { status: "rolled_back", reason: "too risky" } } },
    } as any);

    expect(screen.queryByRole("link", { name: /Download Clean Dataset \(CSV\)/i })).not.toBeInTheDocument();
    expect(screen.getByText(/rolled back and has no published clean output/i)).toBeInTheDocument();
  });
});

describe("ReportsDownloads with no active run", () => {
  it("shows the empty state", () => {
    render(
      <MemoryRouter>
        <RunProvider>
          <ReportsDownloads />
        </RunProvider>
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Reports & Downloads" })).toBeInTheDocument();
    expect(screen.getByText("No dataset analyzed yet")).toBeInTheDocument();
  });
});
