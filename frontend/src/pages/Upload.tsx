import { useState, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";
import { CheckCircle2, FileSpreadsheet, Loader2, UploadCloud } from "lucide-react";
import {
  analyzeRun,
  cleanRun,
  getAnalyticsReadiness,
  getAudit,
  getBeforeAfter,
  getDictionary,
  getDrift,
  getIssues,
  getLineage,
  getPerformance,
  getQuality,
  uploadDataset,
  validateRun,
} from "../services/api";
import { useRun } from "../context/RunContext";

type Step = "idle" | "uploading" | "analyzing" | "cleaning" | "validating" | "done" | "error";

const STEP_LABELS: Record<Step, string> = {
  idle: "",
  uploading: "Uploading dataset...",
  analyzing: "Analyzing dataset...",
  cleaning: "Cleaning dataset...",
  validating: "Validating results...",
  done: "Complete!",
  error: "Something went wrong.",
};

export default function Upload() {
  const [files, setFiles] = useState<File[]>([]);
  const [projectPlanText, setProjectPlanText] = useState("");
  const [step, setStep] = useState<Step>("idle");
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const { setRun } = useRun();
  const navigate = useNavigate();

  const isBusy = step !== "idle" && step !== "done" && step !== "error";

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setIsDragging(false);
    if (isBusy) return;
    const dropped = Array.from(e.dataTransfer.files ?? []);
    if (dropped.length > 0) setFiles(dropped);
  }

  async function handleAnalyze() {
    if (files.length === 0) {
      setError("Please choose at least one file to upload.");
      return;
    }
    setError(null);

    try {
      setStep("uploading");
      const uploadResult = await uploadDataset(files, projectPlanText || undefined);
      const runId = uploadResult.run_id;

      setStep("analyzing");
      const analyzeResult = await analyzeRun(runId);

      setStep("cleaning");
      const cleanResult = await cleanRun(runId);

      setStep("validating");
      const validateResult = await validateRun(runId);

      // Promise.allSettled, not Promise.all: an endpoint can legitimately 404 for a
      // file that failed cleaning entirely (e.g. no data dictionary was ever built
      // for it) even though every other enrichment call succeeded -- with
      // Promise.all, that one rejection would discard every already-fetched result
      // and drop the user back to a bare error message instead of a Dashboard that
      // still has real (if partial) data to show.
      const settledResults = await Promise.allSettled([
        getIssues(runId),
        getQuality(runId),
        getAnalyticsReadiness(runId),
        getDrift(runId),
        getLineage(runId),
        getBeforeAfter(runId),
        getDictionary(runId),
        getPerformance(runId),
        getAudit(runId),
      ]);
      const emptyFilesFallback = { files: {} };
      const emptyRowsFallback = { rows: [] };
      const fallbacks = [
        emptyFilesFallback, emptyFilesFallback, emptyFilesFallback, emptyFilesFallback,
        emptyFilesFallback, emptyFilesFallback, emptyFilesFallback, emptyFilesFallback,
        emptyRowsFallback,
      ];
      const [issues, quality, analyticsReadiness, drift, lineage, beforeAfter, dictionary, performance, audit] =
        settledResults.map((result, idx) => (result.status === "fulfilled" ? result.value : fallbacks[idx]));

      setRun({
        runId,
        uploadResult,
        analyzeResult,
        cleanResult,
        validateResult,
        issues,
        quality,
        analyticsReadiness,
        drift,
        lineage,
        beforeAfter,
        dictionary,
        performance,
        audit,
      });
      setStep("done");
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error.");
      setStep("error");
    }
  }

  const stepNumber = files.length > 0 ? (projectPlanText ? 3 : 2) : 1;

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-primary">Upload Dataset</h1>
        <p className="text-sm text-secondary mt-1">
          Choose one or more dataset files, optionally describe your project, then analyze.
        </p>
      </div>

      {/* Numbered stepper: 1 Dataset -> 2 Project Plan -> 3 Analyze, driven by the
          same files/projectPlanText state already tracked -- no new logic. */}
      <ol className="flex items-center gap-2 text-xs font-medium text-secondary">
        {["Dataset", "Project Plan", "Analyze"].map((label, idx) => {
          const n = idx + 1;
          const reached = n <= stepNumber || (n === 3 && files.length > 0);
          return (
            <li key={label} className="flex items-center gap-2">
              <span
                className={`flex h-5 w-5 items-center justify-center rounded-full text-[11px] ${
                  reached ? "bg-brand-600 text-white" : "bg-surface-raised text-secondary"
                }`}
              >
                {n}
              </span>
              <span className={reached ? "text-primary" : undefined}>{label}</span>
              {n < 3 && <span className="mx-1 text-muted">&rarr;</span>}
            </li>
          );
        })}
      </ol>

      <div className="rounded-lg border border-line bg-surface p-6 space-y-4">
        <div>
          <label htmlFor="dataset-file-input" className="block text-sm font-medium text-primary mb-1">
            Dataset file(s)
          </label>
          <div
            onDragOver={(e) => {
              e.preventDefault();
              if (!isBusy) setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            className={`rounded-lg border-2 border-dashed p-6 text-center transition-colors ${
              isDragging ? "border-brand-500 bg-brand-50 dark:bg-brand-500/10" : "border-line-strong bg-surface-raised"
            }`}
          >
            <UploadCloud className="mx-auto mb-2 text-muted" size={28} />
            <p className="text-sm text-secondary">Drag and drop CSV, TSV, Excel, JSON, or Parquet files here</p>
            <p className="text-xs text-secondary mt-1">or</p>
            <label
              htmlFor="dataset-file-input"
              className="mt-2 inline-block cursor-pointer rounded-md bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-700"
            >
              Choose Files
            </label>
            <input
              id="dataset-file-input"
              type="file"
              multiple
              disabled={isBusy}
              onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
              className="hidden"
            />
          </div>
          {files.length > 0 && (
            <ul className="mt-3 space-y-1">
              {files.map((file) => (
                <li key={file.name} className="flex items-center gap-2 text-xs text-secondary">
                  <FileSpreadsheet size={14} className="text-muted shrink-0" />
                  {file.name} ({file.size.toLocaleString()} bytes)
                </li>
              ))}
            </ul>
          )}
        </div>

        <div>
          <label htmlFor="project-plan-textarea" className="block text-sm font-medium text-primary mb-1">
            Project plan (optional)
          </label>
          <textarea
            id="project-plan-textarea"
            disabled={isBusy}
            value={projectPlanText}
            onChange={(e) => setProjectPlanText(e.target.value)}
            rows={4}
            placeholder="Describe your project objective, required columns, columns that must not be modified, etc."
            className="block w-full rounded-md border border-line-strong bg-surface text-primary placeholder:text-muted text-sm p-2 focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>

        <button
          onClick={handleAnalyze}
          disabled={isBusy}
          className="flex w-full items-center justify-center gap-2 rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60"
        >
          {isBusy ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              {STEP_LABELS[step]}
            </>
          ) : step === "done" ? (
            <>
              <CheckCircle2 size={16} />
              Complete
            </>
          ) : (
            "Analyze Dataset"
          )}
        </button>

        {error && (
          <div className="rounded-md border border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-950/30 p-3 text-sm text-red-700 dark:text-red-300 space-y-1">
            <p className="font-medium">Unable to process this dataset.</p>
            <p>
              <span className="font-medium">Why: </span>
              {error}
            </p>
            <p>
              <span className="font-medium">What you can do: </span>
              Check the file format and project plan, then try again.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
