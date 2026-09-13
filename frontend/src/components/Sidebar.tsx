import { NavLink } from "react-router-dom";
import { NAV_ITEMS } from "../types/navigation";

export default function Sidebar() {
  return (
    <aside className="w-64 shrink-0 border-r border-slate-200 bg-white flex flex-col">
      <div className="px-5 py-5 border-b border-slate-200">
        <span className="text-lg font-bold tracking-tight text-slate-900">DataQX</span>
        <p className="text-xs text-slate-400 mt-0.5">Data Quality &amp; Preparation</p>
      </div>
      <nav className="flex-1 overflow-y-auto py-3">
        <ul className="space-y-0.5 px-3">
          {NAV_ITEMS.map((item) => (
            <li key={item.path}>
              <NavLink
                to={item.path}
                end={item.path === "/"}
                className={({ isActive }) =>
                  [
                    "block rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-slate-900 text-white"
                      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
                  ].join(" ")
                }
              >
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  );
}
