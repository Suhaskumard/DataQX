import DataTable from "../components/DataTable";
import EmptyRunState from "../components/EmptyRunState";
import { useRun } from "../context/RunContext";

export default function CleaningActions() {
  const { run } = useRun();

  if (!run) {
    return <EmptyRunState title="Cleaning Actions" />;
  }

  const filename = Object.keys(run.cleanResult.files)[0];
  const fileResult = run.cleanResult.files[filename];
  const log: any[] = fileResult.status === "cleaned" ? fileResult.log : [];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Cleaning Actions</h1>
        <p className="text-sm text-slate-500 mt-1">{filename}</p>
      </div>

      {fileResult.status !== "cleaned" && (
        <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          This dataset was rolled back and not published: {fileResult.reason}
        </div>
      )}

      <DataTable
        columns={[
          { key: "issue_type", label: "Issue" },
          { key: "column", label: "Column" },
          { key: "confidence", label: "Confidence" },
          { key: "action_taken", label: "Action" },
          { key: "reason", label: "Reason" },
          { key: "affected_count", label: "Affected" },
        ]}
        rows={log}
        emptyMessage="No cleaning actions were applied."
      />
    </div>
  );
}
