import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { useEffect } from "react";
import DataQuality from "../src/pages/DataQuality";
import { RunProvider, useRun } from "../src/context/RunContext";

const MOCK_RUN = {
  runId: "run_test_dq",
  issues: {
    files: {
      "sales.csv": [
        { issue_type: "outlier", column: "revenue", severity: "high", confidence: { confidence: "LOW" }, affected_count: 3, description: "Extreme value" },
        { issue_type: "whitespace_formatting", column: "name", severity: "low", confidence: { confidence: "HIGH" }, affected_count: 10, description: "Leading/trailing spaces" },
      ],
    },
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
      <RunProvider>
        <Seed>
          <DataQuality />
        </Seed>
      </RunProvider>
    </MemoryRouter>,
  );
}

describe("DataQuality with an active run", () => {
  it("renders real issue rows from run context", () => {
    renderWithRun();
    expect(screen.getByText("sales.csv")).toBeInTheDocument();
    expect(screen.getByText("outlier")).toBeInTheDocument();
    expect(screen.getByText("whitespace_formatting")).toBeInTheDocument();
    expect(screen.getByText("revenue")).toBeInTheDocument();
  });

  it("filters issues by severity", async () => {
    const user = userEvent.setup();
    renderWithRun();

    const severitySelect = screen.getAllByRole("combobox")[0];
    await user.selectOptions(severitySelect, "high");

    expect(screen.getByText("outlier")).toBeInTheDocument();
    expect(screen.queryByText("whitespace_formatting")).not.toBeInTheDocument();
  });
});

describe("DataQuality with no active run", () => {
  it("shows the empty state, no fabricated issues", () => {
    render(
      <MemoryRouter>
        <RunProvider>
          <DataQuality />
        </RunProvider>
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Data Quality" })).toBeInTheDocument();
    expect(screen.getByText("No dataset analyzed yet")).toBeInTheDocument();
  });
});
