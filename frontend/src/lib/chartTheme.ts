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
    // recharts' default tooltip only reads `contentStyle.color` on the outer
    // wrapper div -- the "name"/"value" spans inside it render with their own
    // (black, non-theme-aware) default color, which axe correctly flags as
    // unreadable on a dark card. itemStyle/labelStyle theme those spans too.
    tooltipItemStyle: { color: isDark ? "#e8ecf5" : "#0f172a" },
    tooltipLabelStyle: { color: isDark ? "#e8ecf5" : "#0f172a" },
    // The hover cursor recharts draws behind a bar defaults to a flat gray fill
    // that reads as a jarring white/gray flash on a dark card -- a low-opacity
    // themed tint keeps the hover affordance subtle in both themes.
    cursorFill: isDark ? "rgba(148, 163, 184, 0.08)" : "rgba(100, 116, 139, 0.08)",
  };
}
