import DataTable from "../components/DataTable";
import EmptyRunState from "../components/EmptyRunState";
import Badge from "../components/Badge";
import { useRun } from "../context/RunContext";

export default function CleaningActions() {
  const { run } = useRun();

  if (!run) {
    return <EmptyRunState title="Cleaning Actions" />;
  }

  const filename = Object.keys(run.cleanResult.files ?? {})[0];
  const fileResult = filename ? run.cleanResult.files[filename] : undefined;

  if (!filename || !fileResult) {
    return <EmptyRunState title="Cleaning Actions" />;
  }

  const log: any[] = fileResult.status === "cleaned" && Array.isArray(fileResult.log) ? fileResult.log : [];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-primary">Cleaning Actions</h1>
        <p className="text-sm text-secondary mt-1">{filename}</p>
      </div>

      {fileResult.status !== "cleaned" && (
        <div className="rounded-md border border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-950/30 p-3 text-sm text-amber-800 dark:text-amber-300">
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
        rows={log.map((entry) => ({
          ...entry,
          confidence: entry.confidence ? <Badge kind="confidence" value={entry.confidence} /> : entry.confidence,
        }))}
        emptyMessage="No cleaning actions were applied."
      />
    </div>
  );
}
