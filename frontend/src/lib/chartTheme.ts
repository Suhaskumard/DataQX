import { useTheme } from "../context/ThemeContext";

/** Recharts renders to raw SVG/CSS with hex props, not Tailwind classes -- this
 * hook is the one place that maps the current theme to the handful of chart
 * colors (grid lines, axis labels, tooltip chrome) every chart needs, so a
 * dark-mode chart never ends up with invisible axis text or a jarring white
 * tooltip floating on a navy card. */
export function useChartColors() {
  const { theme } = useTheme();
  const isDark = theme === "dark";
  return {
    grid: isDark ? "#26314a" : "#e2e6ee",
    axis: isDark ? "#8c98b2" : "#64748b",
    tooltipStyle: {
      background: isDark ? "#121a2b" : "#ffffff",
      border: `1px solid ${isDark ? "#26314a" : "#e2e6ee"}`,
      borderRadius: 8,
      fontSize: 12,
      color: isDark ? "#e8ecf5" : "#0f172a",
    },
  };
}
