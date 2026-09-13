import { useMemo, useState } from "react";
import DataTable from "../components/DataTable";
import EmptyRunState from "../components/EmptyRunState";
import { useRun } from "../context/RunContext";

export default function DataQuality() {
  const { run } = useRun();
  const [severityFilter, setSeverityFilter] = useState("all");
  const [confidenceFilter, setConfidenceFilter] = useState("all");

  const filename = run ? Object.keys(run.issues.files)[0] : null;
  const allIssues: any[] = run && filename ? run.issues.files[filename] : [];

  const filtered = useMemo(() => {
    return allIssues.filter((issue) => {
      const severityOk = severityFilter === "all" || issue.severity === severityFilter;
      const confidenceOk =
        confidenceFilter === "all" || issue.confidence?.confidence === confidenceFilter;
      return severityOk && confidenceOk;
    });
  }, [allIssues, severityFilter, confidenceFilter]);

  if (!run) {
    return <EmptyRunState title="Data Quality" />;
  }

  const severities = Array.from(new Set(allIssues.map((i) => i.severity)));
  const confidences = Array.from(new Set(allIssues.map((i) => i.confidence?.confidence)));

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Data Quality</h1>
        <p className="text-sm text-slate-500 mt-1">{filename}</p>
      </div>

      <div className="flex gap-3">
        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
          className="rounded-md border border-slate-300 text-sm px-2 py-1"
        >
          <option value="all">All severities</option>
          {severities.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          value={confidenceFilter}
          onChange={(e) => setConfidenceFilter(e.target.value)}
          className="rounded-md border border-slate-300 text-sm px-2 py-1"
        >
          <option value="all">All confidence levels</option>
          {confidences.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>

      <DataTable
        columns={[
          { key: "issue_type", label: "Issue" },
          { key: "column", label: "Column" },
          { key: "severity", label: "Severity" },
          { key: "confidence_level", label: "Confidence" },
          { key: "affected_count", label: "Affected" },
          { key: "description", label: "Description" },
        ]}
        rows={filtered.map((issue) => ({
          ...issue,
          confidence_level: issue.confidence?.confidence,
        }))}
        emptyMessage={allIssues.length === 0 ? "No issues detected." : "No issues match the current filters."}
      />
    </div>
  );
}
