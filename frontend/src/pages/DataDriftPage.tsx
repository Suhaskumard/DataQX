import DataTable from "../components/DataTable";
import EmptyRunState from "../components/EmptyRunState";
import { useRun } from "../context/RunContext";

export default function DataDriftPage() {
  const { run } = useRun();

  if (!run) {
    return <EmptyRunState title="Data Drift" />;
  }

  const filename = Object.keys(run.drift.files)[0];
  const drift = run.drift.files[filename];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Data Drift</h1>
        <p className="text-sm text-slate-500 mt-1">{filename}</p>
      </div>

      {drift.overall_status === "no_history" ? (
        <div className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center">
          <p className="text-sm font-medium text-slate-600">No prior version to compare against</p>
          <p className="text-xs text-slate-400 mt-1">
            Upload another file with the same name to see drift on the next run.
          </p>
        </div>
      ) : (
        <>
          <p className="text-sm text-slate-600">
            Compared against run: <span className="font-mono">{drift.compared_against}</span>
          </p>
          <DataTable
            columns={[
              { key: "drift_type", label: "Drift Type" },
              { key: "column", label: "Column" },
              { key: "severity", label: "Severity" },
              { key: "description", label: "Description" },
            ]}
            rows={drift.findings}
            emptyMessage="No drift detected compared to the previous version."
          />
        </>
      )}
    </div>
  );
}
