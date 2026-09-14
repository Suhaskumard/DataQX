import { AlertOctagon, CheckCircle2 } from "lucide-react";
import DataTable from "../components/DataTable";
import EmptyRunState from "../components/EmptyRunState";
import Badge from "../components/Badge";
import { useRun } from "../context/RunContext";

export default function ValidationPage() {
  const { run } = useRun();

  if (!run) {
    return <EmptyRunState title="Validation" />;
  }

  const filename = Object.keys(run.validateResult?.files ?? {})[0];
  const fileResult = filename ? run.validateResult.files[filename] : undefined;

  if (!filename || !fileResult || typeof fileResult.overall_status !== "string") {
    return <EmptyRunState title="Validation" />;
  }

  const overallStatus: string = fileResult.overall_status;
  const checks: any[] = Array.isArray(fileResult.checks) ? fileResult.checks : [];
  const passCount = checks.filter((c) => c.status === "pass").length;
  const warningCount = checks.filter((c) => c.status === "warning").length;
  const failCount = checks.filter((c) => c.status === "fail").length;
  const score = checks.length > 0 ? Math.round((passCount / checks.length) * 100) : 100;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-primary">Validation</h1>
        <p className="text-sm text-secondary mt-1">{filename}</p>
      </div>

      <div className="rounded-lg border border-line bg-surface p-5">
        <div className="flex flex-wrap items-center gap-4">
          {overallStatus === "fail" ? (
            <AlertOctagon className="text-red-500 shrink-0" size={32} />
          ) : (
            <CheckCircle2 className={`shrink-0 ${overallStatus === "warning" ? "text-amber-500" : "text-emerald-500"}`} size={32} />
          )}
          <div className="flex-1 min-w-[180px]">
            <p className="text-lg font-semibold text-primary">
              {overallStatus === "fail"
                ? "Dataset Failed Validation"
                : overallStatus === "warning"
                  ? "Dataset Validated with Warnings"
                  : "Dataset Validated"}
            </p>
            <p className="text-sm text-secondary mt-0.5">{score}/100 checks passed</p>
          </div>
          <Badge kind="status" value={overallStatus} />
        </div>

        {overallStatus === "fail" && (
          <div className="mt-4 rounded-md border border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-950/30 p-3 text-sm text-red-700 dark:text-red-300">
            This dataset is not ready for publication until the failing checks below are resolved.
          </div>
        )}

        <div className="mt-4 grid grid-cols-3 gap-3 text-center">
          <div>
            <p className="text-2xl font-semibold text-emerald-500">{passCount}</p>
            <p className="text-xs uppercase tracking-wide text-muted">Pass</p>
          </div>
          <div>
            <p className="text-2xl font-semibold text-amber-500">{warningCount}</p>
            <p className="text-xs uppercase tracking-wide text-muted">Warning</p>
          </div>
          <div>
            <p className="text-2xl font-semibold text-red-500">{failCount}</p>
            <p className="text-xs uppercase tracking-wide text-muted">Fail</p>
          </div>
        </div>
      </div>

      <DataTable
        columns={[
          { key: "check_name", label: "Check", sortable: true },
          { key: "status", label: "Status" },
          { key: "message", label: "Message" },
        ]}
        rows={checks.map((c) => ({
          ...c,
          status: c.status ? <Badge kind="status" value={c.status} /> : c.status,
        }))}
        searchable
      />
    </div>
  );
}
