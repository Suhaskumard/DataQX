import DataTable from "../components/DataTable";
import EmptyRunState from "../components/EmptyRunState";
import { useRun } from "../context/RunContext";

export default function DataLineagePage() {
  const { run } = useRun();

  if (!run) {
    return <EmptyRunState title="Data Lineage" />;
  }

  const filename = Object.keys(run.lineage.files)[0];
  const entries: any[] = run.lineage.files[filename];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Data Lineage</h1>
        <p className="text-sm text-slate-500 mt-1">{filename}</p>
      </div>

      <DataTable
        columns={[
          { key: "source_column", label: "Raw Column" },
          { key: "transformation", label: "Transformation" },
          { key: "output_column", label: "Clean Column" },
          { key: "rule", label: "Rule" },
          { key: "confidence", label: "Confidence" },
        ]}
        rows={entries}
        emptyMessage="No lineage data available."
      />
    </div>
  );
}
