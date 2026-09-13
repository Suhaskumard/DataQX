import DataTable from "../components/DataTable";
import EmptyRunState from "../components/EmptyRunState";
import { useRun } from "../context/RunContext";

export default function BeforeAfter() {
  const { run } = useRun();

  if (!run) {
    return <EmptyRunState title="Before vs After" />;
  }

  const filename = Object.keys(run.beforeAfter.files)[0];
  const summary: Record<string, { before: number; after: number; change: number }> =
    run.beforeAfter.files[filename];

  const rows = Object.entries(summary).map(([metric, values]) => ({
    metric,
    before: values.before,
    after: values.after,
    change: values.change,
  }));

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Before vs After</h1>
        <p className="text-sm text-slate-500 mt-1">{filename}</p>
      </div>

      <DataTable
        columns={[
          { key: "metric", label: "Metric" },
          { key: "before", label: "Before" },
          { key: "after", label: "After" },
          { key: "change", label: "Change" },
        ]}
        rows={rows}
      />
    </div>
  );
}
