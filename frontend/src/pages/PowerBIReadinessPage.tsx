import DataTable from "../components/DataTable";
import EmptyRunState from "../components/EmptyRunState";
import { useRun } from "../context/RunContext";

export default function PowerBIReadinessPage() {
  const { run } = useRun();

  if (!run) {
    return <EmptyRunState title="Power BI Readiness" />;
  }

  const filename = Object.keys(run.powerbi.files)[0];
  const pb = run.powerbi.files[filename];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Power BI Readiness</h1>
        <p className="text-sm text-slate-500 mt-1">{filename}</p>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-4 flex items-center gap-6">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Readiness Score</p>
          <p className="mt-1 text-2xl font-semibold text-slate-900">{pb.score}/100</p>
        </div>
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Table Role</p>
          <p className="mt-1 text-2xl font-semibold text-slate-900 capitalize">{pb.table_role}</p>
        </div>
      </div>

      <DataTable
        columns={[
          { key: "check_name", label: "Check" },
          { key: "status", label: "Status" },
          { key: "message", label: "Message" },
        ]}
        rows={pb.checks}
      />
    </div>
  );
}
