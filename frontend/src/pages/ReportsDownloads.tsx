import type { LucideIcon } from "lucide-react";
import { FileSpreadsheet, FileJson, FileText, FileType } from "lucide-react";
import EmptyRunState from "../components/EmptyRunState";
import { useRun } from "../context/RunContext";
import { downloadUrl, reportUrl } from "../services/api";

function iconForHref(href: string): LucideIcon {
  if (href.endsWith(".pdf") || href.includes("/report")) return FileText;
  if (href.endsWith(".json")) return FileJson;
  if (href.endsWith(".xlsx")) return FileType;
  return FileSpreadsheet;
}

function DownloadLink({ href, label }: { href: string; label: string }) {
  const Icon = iconForHref(href);
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="flex items-center gap-3 rounded-lg border border-line bg-surface px-4 py-3 text-sm font-medium text-primary hover:border-brand-200 dark:hover:border-brand-500/40 hover:bg-brand-50 dark:hover:bg-brand-500/10 hover:text-brand-700 dark:hover:text-brand-400 transition-colors"
    >
      <Icon size={18} className="text-muted shrink-0" />
      {label}
    </a>
  );
}

export default function ReportsDownloads() {
  const { run } = useRun();

  if (!run) {
    return <EmptyRunState title="Reports & Downloads" />;
  }

  const filename = Object.keys(run.cleanResult.files ?? {})[0];
  const fileResult = filename ? run.cleanResult.files[filename] : undefined;

  if (!filename || !fileResult) {
    return <EmptyRunState title="Reports & Downloads" />;
  }

  const stem = filename.replace(/\.[^.]+$/, "");
  const wasPublished = fileResult.status === "cleaned";

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-primary">Reports &amp; Downloads</h1>
        <p className="text-sm text-secondary mt-1">{filename}</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {wasPublished && (
          <>
            <DownloadLink href={downloadUrl(run.runId, `${stem}_cleaned.csv`)} label="Download Clean Dataset (CSV)" />
            <DownloadLink href={downloadUrl(run.runId, `${stem}_cleaned.xlsx`)} label="Download Clean Dataset (Excel)" />
          </>
        )}
        <DownloadLink href={reportUrl(run.runId)} label="Download PDF Report" />
        <DownloadLink href={downloadUrl(run.runId, "cleaning_log.csv")} label="Download Cleaning Log" />
        <DownloadLink href={downloadUrl(run.runId, "audit_log.csv")} label="Download Audit Log" />
        <DownloadLink href={downloadUrl(run.runId, "data_lineage.csv")} label="Download Data Lineage" />
        <DownloadLink href={downloadUrl(run.runId, "drift_report.json")} label="Download Drift Report" />
        <DownloadLink href={downloadUrl(run.runId, "validation_report.json")} label="Download Validation Report" />
        <DownloadLink href={downloadUrl(run.runId, "data_dictionary.csv")} label="Download Data Dictionary" />
        <DownloadLink href={downloadUrl(run.runId, "before_after_summary.csv")} label="Download Before/After Summary" />
        <DownloadLink href={downloadUrl(run.runId, "analytics_readiness.json")} label="Download Analytics Readiness" />
      </div>

      {!wasPublished && (
        <div className="rounded-md border border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-950/30 p-3 text-sm text-amber-800 dark:text-amber-300">
          This dataset was rolled back and has no published clean output — only diagnostic reports are available.
        </div>
      )}
    </div>
  );
}
