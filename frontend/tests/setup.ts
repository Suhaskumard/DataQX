import "@testing-library/jest-dom/vitest";

// jsdom doesn't implement ResizeObserver, which recharts' <ResponsiveContainer>
// requires -- this is a standard, minimal test-environment shim (not app code),
// not a workaround for any real bug.
if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}
