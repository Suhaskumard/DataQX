import { Link } from "react-router-dom";
import StatCard from "../components/StatCard";
import { useRun } from "../context/RunContext";
import { reportUrl } from "../services/api";

export default function Dashboard() {
  const { run } = useRun();

  if (!run) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1">
            Upload a dataset to see real quality, cleaning, and Power BI readiness metrics here.
          </p>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          {[
            "Data Quality Score",
            "Rows",
            "Columns",
            "Issues Detected",
            "Issues Fixed",
            "Review Required",
            "Critical Issues",
            "Power BI Readiness",
          ].map((label) => (
            <StatCard key={label} label={label} />
          ))}
        </div>

        <div className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center">
          <p className="text-sm font-medium text-slate-600">No dataset uploaded yet</p>
          <p className="text-xs text-slate-400 mt-1">Go to Upload Dataset to analyze your first file.</p>
        </div>
      </div>
    );
  }

  // A run can contain multiple files; the dashboard summarizes the first one here
  // (per-file drill-down belongs to the other, not-yet-wired pages -- Phase 20).
  const filename = Object.keys(run.analyzeResult.files)[0];
  const analyzeFile = run.analyzeResult.files[filename];
  const cleanFile = run.cleanResult.files[filename];
  const validateFile = run.validateResult.files[filename];
  const fileIssues: any[] = run.issues.files[filename] ?? [];
  const qualityFile = run.quality.files[filename];
  const powerbiFile = run.powerbi.files[filename];
  const driftFile = run.drift.files[filename];

  const issuesDetected = fileIssues.length;
  const issuesFixed = cleanFile.status === "cleaned" ? cleanFile.log.length : 0;
  const reviewRequired = fileIssues.filter((i) => i.confidence?.confidence === "LOW").length;
  const criticalIssues = fileIssues.filter((i) => i.severity === "critical" || i.severity === "high").length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1">{filename}</p>
        </div>
        <span
          className={`rounded-full px-3 py-1 text-xs font-medium ${
            cleanFile.status === "cleaned"
              ? "bg-green-100 text-green-800"
              : "bg-amber-100 text-amber-800"
          }`}
        >
          {cleanFile.status === "cleaned" ? "Published" : "Rolled Back"}
        </span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
        <StatCard label="Data Quality Score" value={`${qualityFile.after.overall_score}/100`} />
        <StatCard label="Rows" value={analyzeFile.profile.row_count} />
        <StatCard label="Columns" value={analyzeFile.profile.column_count} />
        <StatCard label="Issues Detected" value={issuesDetected} />
        <StatCard label="Issues Fixed" value={issuesFixed} />
        <StatCard label="Review Required" value={reviewRequired} />
        <StatCard label="Critical Issues" value={criticalIssues} />
        <StatCard label="Power BI Readiness" value={`${powerbiFile.score}/100`} />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Validation</p>
          <p className="mt-2 text-lg font-semibold text-slate-900">
            {validateFile.overall_status.toUpperCase()}
          </p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Data Drift</p>
          <p className="mt-2 text-lg font-semibold text-slate-900">
            {driftFile.overall_status.replace("_", " ").toUpperCase()}
          </p>
        </div>
      </div>

      <div className="flex gap-3">
        <a
          href={reportUrl(run.runId)}
          target="_blank"
          rel="noreferrer"
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
        >
          Download PDF Report
        </a>
        <Link
          to="/data-quality"
          className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
        >
          View Issues
        </Link>
      </div>
    </div>
  );
}
