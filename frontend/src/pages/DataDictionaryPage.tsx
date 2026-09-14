import { Fragment, useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Search } from "lucide-react";
import EmptyRunState from "../components/EmptyRunState";
import { useRun } from "../context/RunContext";

const PLATFORM_ROLE_FIELDS: { key: string; label: string }[] = [
  { key: "power_bi_role", label: "Power BI" },
  { key: "tableau_role", label: "Tableau" },
  { key: "alteryx_role", label: "Alteryx" },
  { key: "excel_relevance", label: "Excel" },
  { key: "looker_role", label: "Looker" },
  { key: "looker_studio_role", label: "Looker Studio" },
  { key: "qlik_role", label: "Qlik" },
  { key: "sql_role", label: "SQL" },
  { key: "python_role", label: "Python" },
  { key: "r_role", label: "R" },
];

function semanticRole(dataType: string): string {
  if (dataType === "id") return "Identifier";
  if (dataType === "integer" || dataType === "float") return "Measure";
  if (dataType === "date" || dataType === "datetime") return "Date";
  if (dataType === "boolean") return "Flag";
  return "Dimension";
}

export default function DataDictionaryPage() {
  const { run } = useRun();
  const [search, setSearch] = useState("");
  const [platformFilter, setPlatformFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const filename = run ? Object.keys(run.dictionary?.files ?? {})[0] : undefined;
  const rawRows = filename && run ? run.dictionary.files[filename] : [];
  const allRows: any[] = Array.isArray(rawRows) ? rawRows : [];

  const types = useMemo(() => Array.from(new Set(allRows.map((r) => r.data_type).filter(Boolean))), [allRows]);

  const filtered = useMemo(() => {
    return allRows.filter((row) => {
      const searchOk =
        !search.trim() || String(row.column_name ?? row.original_name ?? "").toLowerCase().includes(search.trim().toLowerCase());
      const typeOk = typeFilter === "all" || row.data_type === typeFilter;
      const platformOk = platformFilter === "all" || Boolean(row[platformFilter]);
      return searchOk && typeOk && platformOk;
    });
  }, [allRows, search, typeFilter, platformFilter]);

  if (!run) {
    return <EmptyRunState title="Data Dictionary" />;
  }

  if (!filename) {
    return <EmptyRunState title="Data Dictionary" />;
  }

  function toggleExpanded(key: string) {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-primary">Data Dictionary</h1>
        <p className="text-sm text-secondary mt-1">{filename}</p>
      </div>

      <div className="flex flex-wrap gap-3">
        <div className="relative">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search columns..."
            className="rounded-md border border-line bg-surface pl-8 pr-2 py-1.5 text-sm text-primary placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="rounded-md border border-line bg-surface text-sm px-2 py-1.5 text-primary"
        >
          <option value="all">All types</option>
          {types.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <select
          value={platformFilter}
          onChange={(e) => setPlatformFilter(e.target.value)}
          className="rounded-md border border-line bg-surface text-sm px-2 py-1.5 text-primary"
        >
          <option value="all">Show fields useful for: All platforms</option>
          {PLATFORM_ROLE_FIELDS.map((p) => (
            <option key={p.key} value={p.key}>
              Show fields useful for: {p.label}
            </option>
          ))}
        </select>
      </div>

      {filtered.length === 0 ? (
        <div className="rounded-lg border border-dashed border-line-strong bg-surface p-6 text-center">
          <p className="text-sm text-secondary">No columns match the current filters.</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-line bg-surface">
          <table className="min-w-full text-sm">
            <thead className="bg-surface-raised">
              <tr>
                <th className="w-8 px-2 py-2 border-b border-line" />
                <th className="px-3 py-2 text-left font-medium text-secondary border-b border-line">Column</th>
                <th className="px-3 py-2 text-left font-medium text-secondary border-b border-line">Type</th>
                <th className="px-3 py-2 text-left font-medium text-secondary border-b border-line">Semantic Role</th>
                <th className="px-3 py-2 text-left font-medium text-secondary border-b border-line">Missing %</th>
                <th className="px-3 py-2 text-left font-medium text-secondary border-b border-line">Unique</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {filtered.map((row, idx) => {
                const key = row.column_name ?? row.original_name ?? String(idx);
                const isOpen = expanded.has(key);
                const roleEntries = PLATFORM_ROLE_FIELDS.filter((p) => row[p.key]);
                return (
                  <Fragment key={key}>
                    <tr
                      onClick={() => toggleExpanded(key)}
                      className="cursor-pointer hover:bg-surface-raised transition-colors"
                    >
                      <td className="px-2 py-2 text-muted">
                        {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                      </td>
                      <td className="px-3 py-2 text-primary font-medium align-top">{row.column_name}</td>
                      <td className="px-3 py-2 text-secondary align-top">{row.data_type}</td>
                      <td className="px-3 py-2 text-secondary align-top">{semanticRole(row.data_type)}</td>
                      <td className="px-3 py-2 text-secondary align-top">
                        {row.missing_percentage != null ? `${row.missing_percentage}%` : "—"}
                      </td>
                      <td className="px-3 py-2 text-secondary align-top">{row.unique_count ?? "—"}</td>
                    </tr>
                    {isOpen && (
                      <tr className="bg-canvas/40">
                        <td />
                        <td colSpan={5} className="px-3 py-3">
                          <p className="text-xs font-medium uppercase tracking-wide text-muted mb-2">Platform Roles</p>
                          {roleEntries.length === 0 ? (
                            <p className="text-xs text-secondary">
                              No platform role information available for this column.
                            </p>
                          ) : (
                            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
                              {roleEntries.map((p) => (
                                <div key={p.key} className="rounded-md border border-line bg-surface px-2 py-1.5">
                                  <p className="text-[10px] uppercase tracking-wide text-muted">{p.label}</p>
                                  <p className="text-xs font-medium text-primary">{row[p.key]}</p>
                                </div>
                              ))}
                            </div>
                          )}
                          {row.description && <p className="text-xs text-secondary mt-2">{row.description}</p>}
                          {row.cleaning_actions && (
                            <p className="text-xs text-secondary mt-1">Cleaning: {row.cleaning_actions}</p>
                          )}
                          {row.example_values && (
                            <p className="text-xs text-muted mt-1">Examples: {row.example_values}</p>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
