import { useMemo, useState } from "react";
import DataTable from "../components/DataTable";
import EmptyRunState from "../components/EmptyRunState";
import Badge from "../components/Badge";
import { useRun } from "../context/RunContext";

export default function AuditPage() {
  const { run } = useRun();
  const [severityFilter, setSeverityFilter] = useState("all");
  const [actionFilter, setActionFilter] = useState("all");

  const allRows: any[] = Array.isArray(run?.audit?.rows) ? run.audit.rows : [];

  const severities = useMemo(() => Array.from(new Set(allRows.map((r) => r.severity).filter(Boolean))), [allRows]);
  const actions = useMemo(() => Array.from(new Set(allRows.map((r) => r.action).filter(Boolean))), [allRows]);

  const filtered = useMemo(() => {
    return allRows.filter((row) => {
      const severityOk = severityFilter === "all" || row.severity === severityFilter;
      const actionOk = actionFilter === "all" || row.action === actionFilter;
      return severityOk && actionOk;
    });
  }, [allRows, severityFilter, actionFilter]);

  if (!run) {
    return <EmptyRunState title="Audit" />;
  }

  if (allRows.length === 0) {
    return (
      <div className="space-y-4">
        <div>
          <h1 className="text-xl font-semibold text-primary">Audit</h1>
          <p className="text-sm text-secondary mt-1">Every cleaning decision DataQX made, for review and trust.</p>
        </div>
        <div className="rounded-lg border border-dashed border-line-strong bg-surface p-8 text-center">
          <p className="text-sm font-medium text-secondary">No audit entries for this run</p>
          <p className="text-xs text-muted mt-1">Audit entries appear once a dataset has been cleaned.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-primary">Audit</h1>
        <p className="text-sm text-secondary mt-1">Every cleaning decision DataQX made, for review and trust.</p>
      </div>

      <div className="flex flex-wrap gap-3">
        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
          className="rounded-md border border-line bg-surface text-sm px-2 py-1.5 text-primary"
        >
          <option value="all">All severities</option>
          {severities.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          className="rounded-md border border-line bg-surface text-sm px-2 py-1.5 text-primary"
        >
          <option value="all">All actions</option>
          {actions.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
      </div>

      <DataTable
        columns={[
          { key: "timestamp", label: "Timestamp", sortable: true },
          { key: "dataset", label: "Dataset" },
          { key: "column", label: "Column", sortable: true },
          { key: "issue_type", label: "Issue" },
          { key: "action", label: "Action" },
          { key: "severity", label: "Severity" },
          { key: "confidence", label: "Confidence" },
          { key: "status", label: "Status" },
        ]}
        rows={filtered.map((row) => ({
          ...row,
          severity: row.severity ? <Badge kind="severity" value={row.severity} /> : row.severity,
          confidence: row.confidence ? <Badge kind="confidence" value={row.confidence} /> : row.confidence,
        }))}
        searchable
        pageSize={20}
        emptyMessage="No audit entries match the current filters."
      />
    </div>
  );
}
