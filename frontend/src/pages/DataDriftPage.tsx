import DataTable from "../components/DataTable";
import EmptyRunState from "../components/EmptyRunState";
import Badge, { classifyDrift } from "../components/Badge";
import { useRun } from "../context/RunContext";

export default function DataDriftPage() {
  const { run } = useRun();

  if (!run) {
    return <EmptyRunState title="Data Drift" />;
  }

  const filename = Object.keys(run.drift.files ?? {})[0];
  const drift = filename ? run.drift.files[filename] : undefined;

  if (!filename || !drift || typeof drift.overall_status !== "string") {
    return <EmptyRunState title="Data Drift" />;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-primary">Data Drift</h1>
          <p className="text-sm text-secondary mt-1">{filename}</p>
        </div>
        <Badge
          kind="drift"
          value={classifyDrift(drift.overall_status, Array.isArray(drift.findings) ? drift.findings.length : 0)}
        />
      </div>

      {drift.overall_status === "no_history" ? (
        <div className="rounded-lg border border-dashed border-line-strong bg-surface p-8 text-center">
          <p className="text-sm font-medium text-secondary">No prior version to compare against</p>
          <p className="text-xs text-secondary mt-1">
            Upload another file with the same name to see drift on the next run.
          </p>
        </div>
      ) : (
        <>
          <p className="text-sm text-secondary">
            Compared against run: <span className="font-mono">{drift.compared_against}</span>
          </p>
          <DataTable
            columns={[
              { key: "drift_type", label: "Drift Type" },
              { key: "column", label: "Column" },
              { key: "severity", label: "Severity" },
              { key: "description", label: "Description" },
            ]}
            rows={(Array.isArray(drift.findings) ? drift.findings : []).map((f: any) => ({
              ...f,
              severity: f.severity ? <Badge kind="severity" value={f.severity} /> : f.severity,
            }))}
            emptyMessage="No drift detected compared to the previous version."
          />
        </>
      )}
    </div>
  );
}
