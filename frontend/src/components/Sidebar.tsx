import { NavLink } from "react-router-dom";
import { NAV_ITEMS, NAV_GROUPS } from "../types/navigation";

export default function Sidebar() {
  return (
    <aside className="w-full sm:w-64 sm:shrink-0 border-b sm:border-b-0 sm:border-r border-line bg-surface flex flex-col">
      <div className="px-5 py-3 sm:py-5 border-b border-line">
        <span className="text-lg font-bold tracking-tight text-brand-600 dark:text-brand-500">DataQX</span>
        <p className="text-xs text-secondary mt-0.5 hidden sm:block">Data Quality &amp; Analytics Readiness</p>
      </div>
      {/* Vertical, grouped list on sm+ screens; a horizontally-scrollable row of
          pills below sm, since a full-height vertical nav would otherwise push all
          page content below the fold on a narrow viewport. */}
      <nav aria-label="Main navigation" className="sm:flex-1 sm:overflow-y-auto py-2 sm:py-3 overflow-x-auto">
        <div className="flex sm:block gap-4 sm:gap-0 px-3 whitespace-nowrap sm:whitespace-normal">
          {NAV_GROUPS.map((group) => (
            <div key={group} className="sm:mb-4">
              <p className="hidden sm:block px-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted">
                {group}
              </p>
              <ul className="flex sm:block gap-1 sm:gap-0 sm:space-y-0.5">
                {NAV_ITEMS.filter((item) => item.group === group).map((item) => {
                  const Icon = item.icon;
                  return (
                    <li key={item.path} className="shrink-0 sm:shrink">
                      <NavLink
                        to={item.path}
                        end={item.path === "/"}
                        className={({ isActive }) =>
                          [
                            "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                            isActive
                              ? "bg-brand-600 text-white"
                              : "text-secondary hover:bg-surface-raised hover:text-primary",
                          ].join(" ")
                        }
                      >
                        <Icon size={16} className="shrink-0" />
                        {item.label}
                      </NavLink>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      </nav>
    </aside>
  );
}
