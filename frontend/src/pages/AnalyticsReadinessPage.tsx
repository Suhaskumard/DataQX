import { useState } from "react";
import DataTable from "../components/DataTable";
import EmptyRunState from "../components/EmptyRunState";
import ScoreRing from "../components/ScoreRing";
import Badge from "../components/Badge";
import { useRun } from "../context/RunContext";

const PLATFORM_ORDER = [
  "power_bi", "tableau", "alteryx", "excel", "looker",
  "looker_studio", "qlik", "sql", "python", "r",
];

function statusValue(status: string): string {
  return status.toLowerCase();
}

export default function AnalyticsReadinessPage() {
  const { run } = useRun();
  const [selectedPlatform, setSelectedPlatform] = useState<string | null>(null);

  if (!run) {
    return <EmptyRunState title="Analytics Readiness" />;
  }

  const filename = Object.keys(run.analyticsReadiness?.files ?? {})[0];
  const readiness = filename ? run.analyticsReadiness.files[filename] : undefined;

  if (!filename || !readiness || typeof readiness.overall_score !== "number") {
    return <EmptyRunState title="Analytics Readiness" />;
  }

  const platforms: Record<string, any> = readiness.platforms ?? {};
  const platformNames = PLATFORM_ORDER.filter((name) => name in platforms);
  const activePlatform = selectedPlatform && platforms[selectedPlatform] ? selectedPlatform : platformNames[0];
  const active = activePlatform ? platforms[activePlatform] : undefined;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-primary">Analytics Readiness</h1>
        <p className="text-sm text-secondary mt-1">{filename}</p>
        <p className="text-xs text-muted mt-1">
          Your data is not just clean -- it is evaluated for the analytics workflow you choose.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-6 rounded-lg border border-line bg-surface p-4">
        <ScoreRing score={readiness.overall_score} label="Overall Readiness" />
        <p className="text-sm text-secondary max-w-md">
          Evaluated against {platformNames.length} platform{platformNames.length === 1 ? "" : "s"} using the same
          underlying data-quality facts. This is a readiness assessment, not a vendor certification.
        </p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {platformNames.map((name) => {
          const platform = platforms[name];
          const isActive = name === activePlatform;
          return (
            <button
              key={name}
              onClick={() => setSelectedPlatform(name)}
              className={`text-left rounded-lg border p-3 transition-colors ${
                isActive
                  ? "border-brand-500 bg-brand-50 dark:bg-brand-500/10"
                  : "border-line bg-surface hover:bg-surface-raised"
              }`}
            >
              <p className="text-xs font-medium uppercase tracking-wide text-secondary truncate">
                {platform.platform}
              </p>
              <p className="mt-1 text-xl font-semibold text-primary">{platform.score}/100</p>
              <div className="mt-1">
                <Badge kind="platform_status" value={statusValue(platform.status)} />
              </div>
            </button>
          );
        })}
      </div>

      {active && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-primary">{active.platform} Checks</h2>
            <Badge kind="platform_status" value={statusValue(active.status)} />
          </div>
          <DataTable
            columns={[
              { key: "check_name", label: "Check" },
              { key: "status", label: "Status" },
              { key: "message", label: "Message" },
            ]}
            rows={(Array.isArray(active.checks) ? active.checks : []).map((c: any) => ({
              ...c,
              status: c.status ? <Badge kind="status" value={c.status} /> : c.status,
            }))}
          />
          {Array.isArray(active.recommendations) && active.recommendations.length > 0 && (
            <div className="rounded-lg border border-line bg-surface p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-secondary mb-2">Recommendations</p>
              <ul className="list-disc list-inside space-y-1 text-sm text-primary">
                {active.recommendations.map((rec: string, idx: number) => (
                  <li key={idx}>{rec}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
