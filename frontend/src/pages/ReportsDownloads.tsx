import EmptyRunState from "../components/EmptyRunState";
import { useRun } from "../context/RunContext";
import { downloadUrl, reportUrl } from "../services/api";

function DownloadLink({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="block rounded-md border border-slate-200 bg-white px-4 py-3 text-sm font-medium text-slate-700 hover:bg-slate-50"
    >
      {label}
    </a>
  );
}

export default function ReportsDownloads() {
  const { run } = useRun();

  if (!run) {
    return <EmptyRunState title="Reports & Downloads" />;
  }

  const filename = Object.keys(run.cleanResult.files)[0];
  const fileResult = run.cleanResult.files[filename];
  const stem = filename.replace(/\.[^.]+$/, "");
  const wasPublished = fileResult.status === "cleaned";

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Reports &amp; Downloads</h1>
        <p className="text-sm text-slate-500 mt-1">{filename}</p>
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
        <DownloadLink href={downloadUrl(run.runId, "data_lineage.csv")} label="Download Data Lineage" />
        <DownloadLink href={downloadUrl(run.runId, "data_dictionary.csv")} label="Download Data Dictionary" />
        <DownloadLink href={downloadUrl(run.runId, "before_after_summary.csv")} label="Download Before/After Summary" />
      </div>

      {!wasPublished && (
        <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          This dataset was rolled back and has no published clean output — only diagnostic reports are available.
        </div>
      )}
    </div>
  );
}
