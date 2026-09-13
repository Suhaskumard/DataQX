import StatCard from "../components/StatCard";

// Phase 2 renders the dashboard shell only. Every value is intentionally empty --
// metrics are wired to the real backend analysis pipeline starting in a later phase
// (DATAQX.pdf S48/S68: "Do not hardcode dashboard values. All metrics must come from
// the backend.").
const METRIC_LABELS = [
  "Data Quality Score",
  "Rows",
  "Columns",
  "Issues Detected",
  "Issues Fixed",
  "Review Required",
  "Critical Issues",
  "Power BI Readiness",
];

export default function Dashboard() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Dashboard</h1>
        <p className="text-sm text-slate-500 mt-1">
          Upload a dataset to see real quality, cleaning, and Power BI readiness metrics here.
        </p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
        {METRIC_LABELS.map((label) => (
          <StatCard key={label} label={label} />
        ))}
      </div>

      <div className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center">
        <p className="text-sm font-medium text-slate-600">No dataset uploaded yet</p>
        <p className="text-xs text-slate-400 mt-1">
          Go to Upload Dataset to analyze your first file.
        </p>
      </div>
    </div>
  );
}
