import { ArrowRight } from "lucide-react";
import EmptyRunState from "../components/EmptyRunState";
import Badge from "../components/Badge";
import { useRun } from "../context/RunContext";

export default function DataLineagePage() {
  const { run } = useRun();

  if (!run) {
    return <EmptyRunState title="Data Lineage" />;
  }

  const filename = Object.keys(run.lineage.files ?? {})[0];
  const rawEntries = filename ? run.lineage.files[filename] : [];
  const entries: any[] = Array.isArray(rawEntries) ? rawEntries : [];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-primary">Data Lineage</h1>
        <p className="text-sm text-secondary mt-1">{filename}</p>
      </div>

      {entries.length === 0 ? (
        <div className="rounded-lg border border-dashed border-line-strong bg-surface p-6 text-center">
          <p className="text-sm font-medium text-secondary">No lineage data available.</p>
          <p className="text-xs text-muted mt-1">
            No columns were transformed during cleaning for this file, so there is nothing to trace.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {entries.map((entry, idx) => (
            <div
              key={idx}
              className="flex flex-wrap items-center gap-3 rounded-lg border border-line bg-surface p-4"
            >
              <span className="rounded-md bg-surface-raised px-2 py-1 text-sm font-medium text-primary">
                {entry.source_column}
              </span>
              <div className="flex items-center gap-1 text-xs text-secondary">
                <ArrowRight size={14} />
                <span>{entry.transformation}</span>
                <ArrowRight size={14} />
              </div>
              <span className="rounded-md bg-brand-50 dark:bg-brand-500/10 px-2 py-1 text-sm font-medium text-brand-700 dark:text-brand-400">
                {entry.output_column}
              </span>
              <span className="text-xs text-secondary">{entry.rule}</span>
              {entry.confidence && (
                <span className="ml-auto">
                  <Badge kind="confidence" value={entry.confidence} />
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
