import DataTable from "../components/DataTable";
import EmptyRunState from "../components/EmptyRunState";
import { useRun } from "../context/RunContext";

export default function DataDictionaryPage() {
  const { run } = useRun();

  if (!run) {
    return <EmptyRunState title="Data Dictionary" />;
  }

  const filename = Object.keys(run.dictionary.files)[0];
  const rows: any[] = run.dictionary.files[filename];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Data Dictionary</h1>
        <p className="text-sm text-slate-500 mt-1">{filename}</p>
      </div>

      <DataTable
        columns={[
          { key: "column_name", label: "Column" },
          { key: "data_type", label: "Type" },
          { key: "description", label: "Description" },
          { key: "missing_percentage", label: "Missing %" },
          { key: "unique_count", label: "Unique" },
          { key: "example_values", label: "Examples" },
          { key: "cleaning_actions", label: "Cleaning Actions" },
        ]}
        rows={rows}
      />
    </div>
  );
}
