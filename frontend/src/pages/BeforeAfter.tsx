import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import DataTable from "../components/DataTable";
import EmptyRunState from "../components/EmptyRunState";
import { useRun } from "../context/RunContext";
import { useChartColors } from "../lib/chartTheme";

export default function BeforeAfter() {
  const { run } = useRun();
  const chartColors = useChartColors();

  if (!run) {
    return <EmptyRunState title="Before vs After" />;
  }

  const filename = Object.keys(run.beforeAfter.files ?? {})[0];
  const summary = filename ? run.beforeAfter.files[filename] : undefined;

  // A per-file failure shape ({"status": "failed", "reason": "..."}) is a real,
  // confirmed backend response -- Object.entries on it would otherwise produce
  // plausible-looking but meaningless rows (metric: "status", before: undefined,
  // ...) instead of a clear error, silently misleading the user into thinking a
  // stage produced real numbers.
  const isValidSummary =
    summary != null &&
    typeof summary === "object" &&
    !("status" in summary) &&
    Object.values(summary).every((v) => v && typeof v === "object" && "before" in v && "after" in v);

  if (!filename || !isValidSummary) {
    return <EmptyRunState title="Before vs After" />;
  }

  const rows = Object.entries(summary as Record<string, { before: number; after: number; change: number }>).map(
    ([metric, values]) => ({
      metric,
      before: values.before,
      after: values.after,
      change: values.change,
    }),
  );

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-primary">Before vs After</h1>
        <p className="text-sm text-secondary mt-1">{filename}</p>
      </div>

      {rows.length > 0 && (
        <div className="rounded-lg border border-line bg-surface p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-secondary mb-2">
            Before vs After by Metric
          </p>
          <ResponsiveContainer width="100%" height={Math.max(160, rows.length * 48)}>
            <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 16 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke={chartColors.grid} />
              <XAxis type="number" tick={{ fontSize: 11, fill: chartColors.axis }} />
              <YAxis type="category" dataKey="metric" tick={{ fontSize: 11, fill: chartColors.axis }} width={140} />
              <Tooltip contentStyle={chartColors.tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: 11, color: chartColors.axis }} />
              <Bar dataKey="before" fill="#94a3b8" name="Before" radius={[0, 4, 4, 0]} />
              <Bar dataKey="after" fill="#4f46e5" name="After" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

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
