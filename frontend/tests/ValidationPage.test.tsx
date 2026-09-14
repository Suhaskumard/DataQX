import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { useEffect } from "react";
import ValidationPage from "../src/pages/ValidationPage";
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
          <ValidationPage />
        </Seed>
      </RunProvider>
    </MemoryRouter>,
  );
}

describe("ValidationPage with a passing run", () => {
  it("renders the real overall status and checks", () => {
    renderWithRun({
      runId: "run_test_val",
      validateResult: {
        files: {
          "sales.csv": {
            overall_status: "pass",
            checks: [{ check_name: "schema_integrity", status: "pass", message: "Schema is consistent." }],
          },
        },
      },
    } as any);

    expect(screen.getByText("sales.csv")).toBeInTheDocument();
    expect(screen.getByText("Dataset Validated")).toBeInTheDocument();
    expect(screen.getByText("schema_integrity")).toBeInTheDocument();
  });
});

describe("ValidationPage keyboard accessibility (real keyboard interaction, not just click)", () => {
  it("sorts the Check column via keyboard focus + Enter, not just mouse click", async () => {
    const user = userEvent.setup();
    renderWithRun({
      runId: "run_test_val_kb",
      validateResult: {
        files: {
          "sales.csv": {
            overall_status: "pass",
            checks: [
              { check_name: "zeta_check", status: "pass", message: "z" },
              { check_name: "alpha_check", status: "pass", message: "a" },
            ],
          },
        },
      },
    } as any);

    const checkHeaderButton = screen.getByRole("button", { name: "Check" });
    const columnHeader = checkHeaderButton.closest("th")!;
    expect(columnHeader).toHaveAttribute("aria-sort", "none");

    checkHeaderButton.focus();
    expect(checkHeaderButton).toHaveFocus();
    await user.keyboard("{Enter}");

    expect(columnHeader).toHaveAttribute("aria-sort", "ascending");
    const rowsAfterFirstSort = screen.getAllByRole("row").slice(1); // skip header row
    expect(rowsAfterFirstSort[0]).toHaveTextContent("alpha_check");

    await user.keyboard("{Enter}");
    expect(columnHeader).toHaveAttribute("aria-sort", "descending");
    const rowsAfterSecondSort = screen.getAllByRole("row").slice(1);
    expect(rowsAfterSecondSort[0]).toHaveTextContent("zeta_check");
  });
});

describe("ValidationPage with a failing run", () => {
  it("shows the not-ready-for-publication message", () => {
    renderWithRun({
      runId: "run_test_val2",
      validateResult: {
        files: {
          "sales.csv": {
            overall_status: "fail",
            checks: [{ check_name: "id_uniqueness", status: "fail", message: "Duplicate IDs found." }],
          },
        },
      },
    } as any);

    expect(screen.getByText("Dataset Failed Validation")).toBeInTheDocument();
    expect(screen.getByText(/not ready for publication/i)).toBeInTheDocument();
  });
});

describe("ValidationPage with no active run", () => {
  it("shows the empty state", () => {
    render(
      <MemoryRouter>
        <RunProvider>
          <ValidationPage />
        </RunProvider>
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Validation" })).toBeInTheDocument();
    expect(screen.getByText("No dataset analyzed yet")).toBeInTheDocument();
  });
});
