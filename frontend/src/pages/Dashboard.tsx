import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import DataTable from "../components/DataTable";
import EmptyRunState from "../components/EmptyRunState";
import StatCard from "../components/StatCard";
import ScoreRing from "../components/ScoreRing";
import Badge, { classifyDrift } from "../components/Badge";
import { useRun } from "../context/RunContext";
import { reportUrl } from "../services/api";
import { useChartColors } from "../lib/chartTheme";

const SEVERITY_ORDER = ["critical", "high", "medium", "low"] as const;
const SEVERITY_COLOR: Record<string, string> = {
  critical: "#dc2626",
  high: "#ea580c",
  medium: "#d97706",
  low: "#94a3b8",
};

export default function Dashboard() {
  const { run } = useRun();
  const chartColors = useChartColors();

  if (!run) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-xl font-semibold text-primary">Dashboard</h1>
          <p className="text-sm text-secondary mt-1">
            Upload a dataset to see real quality, cleaning, and analytics readiness metrics here.
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
            "Analytics Readiness",
          ].map((label) => (
            <StatCard key={label} label={label} />
          ))}
        </div>

        <div className="rounded-lg border border-dashed border-line-strong bg-surface p-8 text-center">
          <p className="text-sm font-medium text-secondary">No dataset uploaded yet</p>
          <p className="text-xs text-secondary mt-1">Go to Upload Dataset to analyze your first file.</p>
        </div>
      </div>
    );
  }

  // A run can contain multiple files; the dashboard summarizes the first one here
  // (per-file drill-down belongs to the other, not-yet-wired pages -- Phase 20).
  const filename = Object.keys(run.analyzeResult.files)[0];

  if (!filename) {
    return <EmptyRunState title="Dashboard" />;
  }

  const analyzeFile = run.analyzeResult.files[filename];
  const cleanFile = run.cleanResult.files?.[filename];
  const validateFile = run.validateResult.files?.[filename];
  const fileIssues: any[] = Array.isArray(run.issues?.files?.[filename]) ? run.issues.files[filename] : [];
  const qualityFile = run.quality?.files?.[filename];
  const readinessFile = run.analyticsReadiness?.files?.[filename];
  const driftFile = run.drift?.files?.[filename];
  const performanceTimes: Record<string, number> = run.performance?.processing_time_seconds ?? {};
  const bottleneckStage: string | null = run.performance?.bottleneck_stage ?? null;
  const bottleneckSeconds: number | null = run.performance?.bottleneck_seconds ?? null;

  // Any stage can independently fail for a given file (a real, confirmed backend
  // shape is {"status": "failed", "reason": "..."} instead of the full result) --
  // every field below is read defensively so one failed stage degrades gracefully
  // to "N/A" instead of crashing the whole dashboard.
  if (analyzeFile?.status === "failed") {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-semibold text-primary">Dashboard</h1>
        <div className="rounded-md border border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-950/30 p-4 text-sm text-red-700 dark:text-red-300">
          Analysis failed for "{filename}": {analyzeFile.reason ?? "Unknown error."}
        </div>
      </div>
    );
  }

  const cleanStatus = cleanFile?.status;
  const isPublished = cleanStatus === "cleaned";
  const issuesDetected = fileIssues.length;
  const issuesFixed = isPublished && Array.isArray(cleanFile?.log) ? cleanFile.log.length : 0;
  const reviewRequired = fileIssues.filter((i) => i.confidence?.confidence === "LOW").length;
  const criticalIssues = fileIssues.filter((i) => i.severity === "critical" || i.severity === "high").length;
  const qualityScore = qualityFile?.after?.overall_score;
  const qualityScoreBefore = qualityFile?.before?.overall_score;
  const analyticsReadinessScore = readinessFile?.overall_score;
  const platforms: Record<string, any> = readinessFile?.platforms ?? {};
  const validationStatus = validateFile?.overall_status;
  const driftStatus = driftFile?.overall_status;
  const driftFindingCount = Array.isArray(driftFile?.findings) ? driftFile.findings.length : 0;

  const severityData = SEVERITY_ORDER.map((sev) => ({
    severity: sev,
    count: fileIssues.filter((i) => i.severity === sev).length,
  })).filter((d) => d.count > 0);

  const qualityComparisonData =
    typeof qualityScoreBefore === "number" && typeof qualityScore === "number"
      ? [
          { stage: "Before", score: qualityScoreBefore },
          { stage: "After", score: qualityScore },
        ]
      : [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-primary">Dashboard</h1>
          <p className="text-sm text-secondary mt-1">{filename}</p>
        </div>
        <Badge kind="status" value={isPublished ? "cleaned" : "rolled_back"} />
      </div>

      {/* Hero row: the two headline 0-100 scores get a real radial gauge, in
          addition to (not instead of) the precise numeric stat cards below. */}
      <div className="flex flex-wrap gap-6 rounded-lg border border-line bg-surface p-4">
        <ScoreRing score={qualityScore} label="Data Quality" />
        <ScoreRing score={analyticsReadinessScore} label="Analytics Readiness" />
        <div className="flex-1 min-w-[160px] self-center space-y-2">
          <div className="flex items-center gap-2 text-sm">
            <span className="text-secondary w-20">Validation</span>
            {validationStatus ? <Badge kind="status" value={validationStatus} /> : <span className="text-secondary">N/A</span>}
          </div>
          <div className="flex items-center gap-2 text-sm">
            <span className="text-secondary w-20">Data Drift</span>
            {driftStatus ? (
              <Badge kind="drift" value={classifyDrift(driftStatus, driftFindingCount)} />
            ) : (
              <span className="text-secondary">N/A</span>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
        <StatCard label="Data Quality Score" value={qualityScore != null ? `${qualityScore}/100` : undefined} />
        <StatCard label="Rows" value={analyzeFile?.profile?.row_count} />
        <StatCard label="Columns" value={analyzeFile?.profile?.column_count} />
        <StatCard label="Issues Detected" value={issuesDetected} />
        <StatCard label="Issues Fixed" value={issuesFixed} />
        <StatCard label="Review Required" value={reviewRequired} />
        <StatCard label="Critical Issues" value={criticalIssues} />
        <StatCard
          label="Analytics Readiness"
          value={analyticsReadinessScore != null ? `${analyticsReadinessScore}/100` : undefined}
        />
      </div>

      {(severityData.length > 0 || qualityComparisonData.length > 0) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {severityData.length > 0 && (
            <div className="rounded-lg border border-line bg-surface p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-secondary mb-2">
                Issues by Severity
              </p>
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={severityData} layout="vertical" margin={{ left: 8, right: 16 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke={chartColors.grid} />
                  <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: chartColors.axis }} />
                  <YAxis type="category" dataKey="severity" tick={{ fontSize: 11, fill: chartColors.axis }} width={60} />
                  <Tooltip contentStyle={chartColors.tooltipStyle} />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                    {severityData.map((d) => (
                      <Cell key={d.severity} fill={SEVERITY_COLOR[d.severity]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
          {qualityComparisonData.length > 0 && (
            <div className="rounded-lg border border-line bg-surface p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-secondary mb-2">
                Quality Score: Before vs After
              </p>
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={qualityComparisonData} margin={{ left: 8, right: 16 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={chartColors.grid} />
                  <XAxis dataKey="stage" tick={{ fontSize: 11, fill: chartColors.axis }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: chartColors.axis }} width={30} />
                  <Tooltip contentStyle={chartColors.tooltipStyle} />
                  <Bar dataKey="score" fill="#4f46e5" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {Object.keys(platforms).length > 0 && (
        <div className="rounded-lg border border-line bg-surface p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-secondary mb-2">Platform Readiness</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {Object.entries(platforms).map(([key, platform]: [string, any]) => (
              <Link
                key={key}
                to="/analytics-readiness"
                className="rounded-md border border-line p-2 hover:bg-surface-raised transition-colors"
              >
                <p className="text-[11px] font-medium uppercase tracking-wide text-secondary truncate">
                  {platform.platform}
                </p>
                <p className="text-sm font-semibold text-primary">{platform.score}%</p>
                <Badge kind="platform_status" value={String(platform.status).toLowerCase()} />
              </Link>
            ))}
          </div>
        </div>
      )}

      {Object.keys(performanceTimes).length > 0 && (
        <div className="rounded-lg border border-line bg-surface p-4 space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium uppercase tracking-wide text-secondary">Performance</p>
            {bottleneckStage && (
              <p className="text-xs text-secondary">
                Slowest stage: <span className="font-semibold text-primary">{bottleneckStage}</span> (
                {bottleneckSeconds?.toFixed(4)}s)
              </p>
            )}
          </div>
          <DataTable
            columns={[
              { key: "stage", label: "Stage" },
              { key: "seconds", label: "Seconds" },
            ]}
            rows={Object.entries(performanceTimes).map(([stage, seconds]) => ({
              stage,
              seconds: seconds.toFixed(4),
            }))}
          />
        </div>
      )}

      <div className="flex gap-3">
        <a
          href={reportUrl(run.runId)}
          target="_blank"
          rel="noreferrer"
          className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
        >
          Download PDF Report
        </a>
        <Link
          to="/data-quality"
          className="rounded-md border border-line-strong px-4 py-2 text-sm font-medium text-primary hover:bg-surface-raised"
        >
          View Issues
        </Link>
      </div>
    </div>
  );
}
