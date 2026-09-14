import { Outlet, useLocation } from "react-router-dom";
import { Moon, Sun } from "lucide-react";
import Sidebar from "./Sidebar";
import Badge from "./Badge";
import { useRun } from "../context/RunContext";
import { useTheme } from "../context/ThemeContext";
import { NAV_ITEMS } from "../types/navigation";

function useBreadcrumb(): string[] {
  const location = useLocation();
  const item = NAV_ITEMS.find((navItem) => navItem.path === location.pathname);
  if (!item) return ["Dashboard"];
  if (item.path === "/") return ["Dashboard"];
  return ["Dashboard", item.label];
}

export default function Layout() {
  const { run } = useRun();
  const { theme, toggleTheme } = useTheme();
  const breadcrumb = useBreadcrumb();
  const filename = run ? Object.keys(run.analyzeResult?.files ?? {})[0] : undefined;
  const cleanStatus = filename ? run?.cleanResult?.files?.[filename]?.status : undefined;

  return (
    <div className="flex flex-col sm:flex-row h-full min-h-screen bg-canvas">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 border-b border-line bg-surface flex items-center justify-between px-4 sm:px-6 gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <nav aria-label="Breadcrumb" className="hidden md:flex items-center gap-1 text-xs text-muted shrink-0">
              {breadcrumb.map((crumb, idx) => (
                <span key={crumb} className="flex items-center gap-1">
                  {idx > 0 && <span>/</span>}
                  <span className={idx === breadcrumb.length - 1 ? "text-secondary font-medium" : undefined}>
                    {crumb}
                  </span>
                </span>
              ))}
            </nav>
            {run && filename ? (
              <div data-testid="run-context" className="flex items-center gap-3 min-w-0 md:border-l md:border-line md:pl-3">
                <span className="text-sm font-medium text-primary truncate">{filename}</span>
                <span className="text-xs text-muted font-mono truncate hidden sm:inline">{run.runId}</span>
                {cleanStatus && <Badge kind="status" value={cleanStatus} />}
              </div>
            ) : (
              <span className="text-sm font-medium text-secondary truncate">
                Clean. Validate. Trust. Analyze.
              </span>
            )}
          </div>
          <button
            onClick={toggleTheme}
            aria-label={theme === "dark" ? "Dark mode enabled. Switch to light mode" : "Light mode enabled. Switch to dark mode"}
            aria-pressed={theme === "dark"}
            className="shrink-0 rounded-md p-2 text-secondary hover:bg-surface-raised hover:text-primary transition-colors"
          >
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </header>
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
