/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Single restrained primary accent for primary actions / active nav / links --
        // replaces the previous all-slate-900 buttons with one deliberate brand color.
        brand: {
          50: "#eef2ff",
          100: "#e0e7ff",
          200: "#c7d2fe",
          500: "#4f46e5",
          600: "#4338ca",
          700: "#3730a3",
        },
        // Secondary accent (cyan/teal) for readiness/analytics highlights, kept
        // deliberately rare per the anti-"rainbow UI" constraint.
        teal: {
          400: "#2dd4bf",
          500: "#14b8a6",
          600: "#0d9488",
        },
        // Semantic surface/text tokens backed by CSS variables (see src/index.css) so
        // the same class names ("bg-canvas", "text-primary", ...) resolve to the
        // correct light/dark value instead of hand-writing dark: on every element.
        canvas: "rgb(var(--color-canvas) / <alpha-value>)",
        surface: "rgb(var(--color-surface) / <alpha-value>)",
        "surface-raised": "rgb(var(--color-surface-raised) / <alpha-value>)",
        line: "rgb(var(--color-border) / <alpha-value>)",
        "line-strong": "rgb(var(--color-border-strong) / <alpha-value>)",
        primary: "rgb(var(--color-text-primary) / <alpha-value>)",
        secondary: "rgb(var(--color-text-secondary) / <alpha-value>)",
        muted: "rgb(var(--color-text-muted) / <alpha-value>)",
      },
    },
  },
  plugins: [],
};
