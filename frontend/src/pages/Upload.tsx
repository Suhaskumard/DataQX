import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  analyzeRun,
  cleanRun,
  getBeforeAfter,
  getDictionary,
  getDrift,
  getIssues,
  getLineage,
  getPerformance,
  getPowerBiReadiness,
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
  const { setRun } = useRun();
  const navigate = useNavigate();

  const isBusy = step !== "idle" && step !== "done" && step !== "error";

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

      const [issues, quality, powerbi, drift, lineage, beforeAfter, dictionary, performance] = await Promise.all([
        getIssues(runId),
        getQuality(runId),
        getPowerBiReadiness(runId),
        getDrift(runId),
        getLineage(runId),
        getBeforeAfter(runId),
        getDictionary(runId),
        getPerformance(runId),
      ]);

      setRun({
        runId,
        uploadResult,
        analyzeResult,
        cleanResult,
        validateResult,
        issues,
        quality,
        powerbi,
        drift,
        lineage,
        beforeAfter,
        dictionary,
        performance,
      });
      setStep("done");
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error.");
      setStep("error");
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Upload Dataset</h1>
        <p className="text-sm text-slate-500 mt-1">
          Choose one or more dataset files, optionally describe your project, then analyze.
        </p>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-6 space-y-4">
        <div>
          <label htmlFor="dataset-file-input" className="block text-sm font-medium text-slate-700 mb-1">
            Dataset file(s)
          </label>
          <input
            id="dataset-file-input"
            type="file"
            multiple
            disabled={isBusy}
            onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
            className="block w-full text-sm text-slate-600 file:mr-4 file:rounded-md file:border-0 file:bg-slate-900 file:px-3 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-slate-700"
          />
          {files.length > 0 && (
            <ul className="mt-2 text-xs text-slate-500 space-y-0.5">
              {files.map((file) => (
                <li key={file.name}>
                  {file.name} ({file.size.toLocaleString()} bytes)
                </li>
              ))}
            </ul>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Project plan (optional)
          </label>
          <textarea
            disabled={isBusy}
            value={projectPlanText}
            onChange={(e) => setProjectPlanText(e.target.value)}
            rows={4}
            placeholder="Describe your project objective, required columns, columns that must not be modified, etc."
            className="block w-full rounded-md border border-slate-300 text-sm p-2 focus:outline-none focus:ring-2 focus:ring-slate-400"
          />
        </div>

        <button
          onClick={handleAnalyze}
          disabled={isBusy}
          className="w-full rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {isBusy ? STEP_LABELS[step] : "Analyze Dataset"}
        </button>

        {error && (
          <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
