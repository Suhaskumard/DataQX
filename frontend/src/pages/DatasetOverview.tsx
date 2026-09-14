import DataTable from "../components/DataTable";
import EmptyRunState from "../components/EmptyRunState";
import StatCard from "../components/StatCard";
import { useRun } from "../context/RunContext";

export default function DatasetOverview() {
  const { run } = useRun();

  if (!run) {
    return <EmptyRunState title="Dataset Overview" />;
  }

  const filename = Object.keys(run.analyzeResult.files ?? {})[0];
  const fileResult = filename ? run.analyzeResult.files[filename] : undefined;
  const profile = fileResult?.profile;

  if (!filename || !profile) {
    return <EmptyRunState title="Dataset Overview" />;
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-primary">Dataset Overview</h1>
        <p className="text-sm text-secondary mt-1">{filename}</p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <StatCard label="Rows" value={profile.row_count} />
        <StatCard label="Columns" value={profile.column_count} />
        <StatCard label="File Size (bytes)" value={profile.file_size_bytes ?? "N/A"} />
        <StatCard label="Duplicate Rows" value={profile.duplicate_row_count} />
      </div>

      <DataTable
        columns={[
          { key: "original_name", label: "Column" },
          { key: "inferred_type", label: "Type" },
          { key: "missing_percentage", label: "Missing %" },
          { key: "unique_percentage", label: "Unique %" },
        ]}
        rows={Array.isArray(profile.columns) ? profile.columns : []}
      />
    </div>
  );
}
