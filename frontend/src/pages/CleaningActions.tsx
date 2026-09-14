import DataTable from "../components/DataTable";
import EmptyRunState from "../components/EmptyRunState";
import Badge from "../components/Badge";
import PipelineSteps from "../components/PipelineSteps";
import { useRun } from "../context/RunContext";

export default function CleaningActions() {
  const { run } = useRun();

  if (!run) {
    return <EmptyRunState title="Cleaning Actions" />;
  }

  const filename = Object.keys(run.cleanResult.files ?? {})[0];
  const fileResult = filename ? run.cleanResult.files[filename] : undefined;

  if (!filename || !fileResult) {
    return (
      <EmptyRunState
        title="Cleaning Actions"
        heading="No cleaning results yet"
        description="Cleaning runs automatically right after analysis. Upload a dataset to see which issues DataQX fixed, and why."
      />
    );
  }

  const log: any[] = fileResult.status === "cleaned" && Array.isArray(fileResult.log) ? fileResult.log : [];
  const skippedLowConfidence: any[] = Array.isArray(fileResult.skipped_low_confidence)
    ? fileResult.skipped_low_confidence
    : [];
  const detectedIssues: any[] = Array.isArray(run.issues?.files?.[filename]) ? run.issues.files[filename] : [];
  const validateChecks: any[] = Array.isArray(run.validateResult?.files?.[filename]?.checks)
    ? run.validateResult.files[filename].checks
    : [];
  const validatePassed = validateChecks.filter((c: any) => c.status === "pass").length;

  const pipelineSteps = [
    { label: "Detected", count: detectedIssues.length, done: detectedIssues.length > 0 },
    { label: "Recommended", count: log.length + skippedLowConfidence.length, done: log.length + skippedLowConfidence.length > 0 },
    { label: "Applied", count: log.length, done: log.length > 0 },
    { label: "Validated", count: validatePassed, done: validateChecks.length > 0 },
  ];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-primary">Cleaning Actions</h1>
        <p className="text-sm text-secondary mt-1">{filename}</p>
      </div>

      <PipelineSteps steps={pipelineSteps} />

      {fileResult.status !== "cleaned" && (
        <div className="rounded-md border border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-950/30 p-3 text-sm text-amber-800 dark:text-amber-300">
          This dataset was rolled back and not published: {fileResult.reason}
        </div>
      )}

      <DataTable
        columns={[
          { key: "issue_type", label: "Issue" },
          { key: "column", label: "Column" },
          { key: "confidence", label: "Confidence" },
          { key: "action_taken", label: "Action" },
          { key: "reason", label: "Reason" },
          { key: "affected_count", label: "Affected" },
        ]}
        rows={log.map((entry) => ({
          ...entry,
          confidence: entry.confidence ? <Badge kind="confidence" value={entry.confidence} /> : entry.confidence,
        }))}
        emptyMessage="No cleaning actions were applied."
      />
    </div>
  );
}
