import { isValidElement, useMemo, useState } from "react";
import { Search } from "lucide-react";

interface Column {
  key: string;
  label: string;
  sortable?: boolean;
}

interface DataTableProps {
  columns: Column[];
  rows: Record<string, any>[];
  emptyMessage?: string;
  searchable?: boolean;
  pageSize?: number;
}

function renderCell(value: unknown) {
  // A page may pass a React element (e.g. <Badge .../>) as a cell value for rich
  // rendering; anything else is stringified exactly as before.
  if (isValidElement(value)) return value;
  return String(value ?? "");
}

function cellText(value: unknown): string {
  if (isValidElement(value)) return "";
  return String(value ?? "");
}

export default function DataTable({ columns, rows, emptyMessage = "No rows.", searchable = false, pageSize }: DataTableProps) {
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState(0);

  const filtered = useMemo(() => {
    if (!search.trim()) return rows;
    const needle = search.trim().toLowerCase();
    return rows.filter((row) => columns.some((col) => cellText(row[col.key]).toLowerCase().includes(needle)));
  }, [rows, search, columns]);

  const sorted = useMemo(() => {
    if (!sortKey) return filtered;
    const copy = [...filtered];
    copy.sort((a, b) => {
      const aVal = cellText(a[sortKey]);
      const bVal = cellText(b[sortKey]);
      const cmp = aVal.localeCompare(bVal, undefined, { numeric: true });
      return sortDir === "asc" ? cmp : -cmp;
    });
    return copy;
  }, [filtered, sortKey, sortDir]);

  const totalPages = pageSize ? Math.max(1, Math.ceil(sorted.length / pageSize)) : 1;
  const paged = pageSize ? sorted.slice(page * pageSize, page * pageSize + pageSize) : sorted;

  function toggleSort(col: Column) {
    if (!col.sortable) return;
    if (sortKey !== col.key) {
      setSortKey(col.key);
      setSortDir("asc");
    } else {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    }
  }

  return (
    <div className="space-y-2">
      {searchable && (
        <div className="relative max-w-xs">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" />
          <input
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
            placeholder="Search..."
            className="w-full rounded-md border border-line bg-surface pl-8 pr-2 py-1.5 text-sm text-primary placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
      )}

      {rows.length === 0 ? (
        <div className="rounded-lg border border-dashed border-line-strong bg-surface p-6 text-center">
          <p className="text-sm text-secondary">{emptyMessage}</p>
        </div>
      ) : sorted.length === 0 ? (
        <div className="rounded-lg border border-dashed border-line-strong bg-surface p-6 text-center">
          <p className="text-sm text-secondary">No rows match your search.</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-line bg-surface">
          <table className="min-w-full text-sm">
            <thead className="sticky top-0 z-10 bg-surface-raised">
              <tr>
                {columns.map((col) => (
                  <th
                    key={col.key}
                    onClick={() => toggleSort(col)}
                    className={`px-3 py-2 text-left font-medium text-secondary border-b border-line whitespace-nowrap ${
                      col.sortable ? "cursor-pointer select-none hover:text-primary" : ""
                    }`}
                  >
                    {col.label}
                    {col.sortable && sortKey === col.key && (sortDir === "asc" ? " ↑" : " ↓")}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {paged.map((row, idx) => (
                <tr key={idx} className={`hover:bg-surface-raised transition-colors ${idx % 2 === 1 ? "bg-canvas/40" : ""}`}>
                  {columns.map((col) => (
                    <td key={col.key} className="px-3 py-2 text-primary align-top">
                      {renderCell(row[col.key])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {pageSize && totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-line px-3 py-2 text-xs text-secondary">
              <span>
                Page {page + 1} of {totalPages} ({sorted.length} rows)
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="rounded border border-line px-2 py-1 disabled:opacity-40 hover:bg-surface-raised"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                  disabled={page >= totalPages - 1}
                  className="rounded border border-line px-2 py-1 disabled:opacity-40 hover:bg-surface-raised"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
