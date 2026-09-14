import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

const MOCK_RUN = {
  runId: "run_test_dict",
  dictionary: {
    files: {
      "sales.csv": [
        {
          column_name: "customer_id",
          data_type: "id",
          description: "Id column, no missing values.",
          missing_percentage: 0,
          unique_count: 40,
          example_values: "1; 2; 3",
          cleaning_actions: "trimmed",
          power_bi_role: "Key",
          tableau_role: "Dimension",
          sql_role: "Primary Key Candidate",
        },
        {
          column_name: "revenue",
          data_type: "float",
          description: "Float column, no missing values.",
          missing_percentage: 0,
          unique_count: 40,
          example_values: "100; 200",
          cleaning_actions: null,
          power_bi_role: "measure",
          python_role: null,
        },
      ],
    },
  },
};

describe("DataDictionaryPage with an active run", () => {
  it("renders the real dictionary rows", () => {
    renderWithRun(MOCK_RUN as any);

    expect(screen.getByText("sales.csv")).toBeInTheDocument();
    expect(screen.getByText("customer_id")).toBeInTheDocument();
  });

  it("expands a row to reveal the real platform-role information (fixes the known UI gap)", async () => {
    const user = userEvent.setup();
    renderWithRun(MOCK_RUN as any);

    await user.click(screen.getByText("customer_id"));

    expect(screen.getByText("Key")).toBeInTheDocument();
    expect(screen.getByText("Dimension")).toBeInTheDocument();
    expect(screen.getByText("Primary Key Candidate")).toBeInTheDocument();
  });

  it("filters columns by platform relevance", async () => {
    const user = userEvent.setup();
    renderWithRun(MOCK_RUN as any);

    const platformSelect = screen.getAllByRole("combobox")[1];
    await user.selectOptions(platformSelect, "sql_role");

    expect(screen.getByText("customer_id")).toBeInTheDocument();
    expect(screen.queryByText("revenue")).not.toBeInTheDocument();
  });

  it("expands a row via real keyboard focus + Enter, exposing aria-expanded state", async () => {
    const user = userEvent.setup();
    renderWithRun(MOCK_RUN as any);

    const expandButton = screen.getByRole("button", { name: /customer_id/ });
    expect(expandButton).toHaveAttribute("aria-expanded", "false");

    expandButton.focus();
    expect(expandButton).toHaveFocus();
    await user.keyboard("{Enter}");

    expect(expandButton).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Key")).toBeInTheDocument();

    await user.keyboard(" ");
    expect(expandButton).toHaveAttribute("aria-expanded", "false");
  });

  it("filters columns by search text", async () => {
    const user = userEvent.setup();
    renderWithRun(MOCK_RUN as any);

    await user.type(screen.getByPlaceholderText("Search columns..."), "revenue");

    expect(screen.getByText("revenue")).toBeInTheDocument();
    expect(screen.queryByText("customer_id")).not.toBeInTheDocument();
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
