import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { useEffect } from "react";
import AuditPage from "../src/pages/AuditPage";
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
          <AuditPage />
        </Seed>
      </RunProvider>
    </MemoryRouter>,
  );
}

const MOCK_RUN = {
  runId: "run_test_audit",
  audit: {
    rows: [
      {
        timestamp: "2026-01-01T00:00:00Z",
        dataset: "sales.csv",
        column: "customer_id",
        row_reference: "3",
        issue_type: "duplicate_id",
        original_value: "9",
        new_value: "9",
        action: "flagged_for_review",
        rule: "duplicate_id",
        reason: "Duplicate ID found.",
        confidence: "LOW",
        severity: "critical",
        status: "flagged_for_review",
      },
      {
        timestamp: "2026-01-01T00:00:01Z",
        dataset: "sales.csv",
        column: "name",
        row_reference: "1",
        issue_type: "whitespace_formatting",
        original_value: "  Alice  ",
        new_value: "Alice",
        action: "trimmed",
        rule: "whitespace_formatting",
        reason: "Whitespace trimmed.",
        confidence: "HIGH",
        severity: "low",
        status: "applied",
      },
    ],
  },
};

describe("AuditPage with real audit rows", () => {
  it("renders every real audit entry", () => {
    renderWithRun(MOCK_RUN as any);

    expect(screen.getByText("duplicate_id")).toBeInTheDocument();
    expect(screen.getByText("whitespace_formatting")).toBeInTheDocument();
  });

  it("filters by severity", async () => {
    const user = userEvent.setup();
    renderWithRun(MOCK_RUN as any);

    const severitySelect = screen.getAllByRole("combobox")[0];
    await user.selectOptions(severitySelect, "critical");

    expect(screen.getByText("duplicate_id")).toBeInTheDocument();
    expect(screen.queryByText("whitespace_formatting")).not.toBeInTheDocument();
  });

  it("filters by action", async () => {
    const user = userEvent.setup();
    renderWithRun(MOCK_RUN as any);

    const actionSelect = screen.getAllByRole("combobox")[1];
    await user.selectOptions(actionSelect, "trimmed");

    expect(screen.getByText("whitespace_formatting")).toBeInTheDocument();
    expect(screen.queryByText("duplicate_id")).not.toBeInTheDocument();
  });
});

describe("AuditPage with no audit rows", () => {
  it("shows a real empty state, not a raw dump", () => {
    renderWithRun({ runId: "run_test_audit_empty", audit: { rows: [] } } as any);
    expect(screen.getByText("No audit entries for this run")).toBeInTheDocument();
  });
});

describe("AuditPage with no active run", () => {
  it("shows the empty state", () => {
    render(
      <MemoryRouter>
        <RunProvider>
          <AuditPage />
        </RunProvider>
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Audit" })).toBeInTheDocument();
  });
});
