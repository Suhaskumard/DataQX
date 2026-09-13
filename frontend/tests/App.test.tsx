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

  it("renders a placeholder page for a non-dashboard route", () => {
    render(
      <MemoryRouter initialEntries={["/upload"]}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Upload Dataset" })).toBeInTheDocument();
    expect(screen.getByText("Not available yet")).toBeInTheDocument();
  });
});
