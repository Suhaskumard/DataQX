import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";

export default function Layout() {
  return (
    <div className="flex h-full min-h-screen bg-slate-50">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 border-b border-slate-200 bg-white flex items-center px-6">
          <span className="text-sm font-medium text-slate-500">
            Stateless, file-based data quality &amp; preparation platform
          </span>
        </header>
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
