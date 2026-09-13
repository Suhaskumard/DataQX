import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import App from "../src/App";
import { NAV_ITEMS } from "../src/types/navigation";

describe("App routing and layout shell", () => {
  it("renders the sidebar with all main nav items", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );

    for (const item of NAV_ITEMS) {
      expect(screen.getByRole("link", { name: item.label })).toBeInTheDocument();
    }
  });

  it("renders the dashboard shell at the root route", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Dashboard" })).toBeInTheDocument();
    expect(screen.getByText("Data Quality Score")).toBeInTheDocument();
    expect(screen.getByText("No dataset uploaded yet")).toBeInTheDocument();
  });

  it("renders the real Data Quality page's empty state when no run is active (Phase 20 -- no longer a placeholder)", () => {
    render(
      <MemoryRouter initialEntries={["/data-quality"]}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Data Quality" })).toBeInTheDocument();
    expect(screen.getByText("No dataset analyzed yet")).toBeInTheDocument();
    expect(screen.queryByText("Not available yet")).not.toBeInTheDocument();
  });

  it("renders the real Upload page (wired to the backend as of Phase 19), not a placeholder", () => {
    render(
      <MemoryRouter initialEntries={["/upload"]}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Upload Dataset" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /analyze dataset/i })).toBeInTheDocument();
    expect(screen.queryByText("Not available yet")).not.toBeInTheDocument();
  });
});
