interface StatCardProps {
  label: string;
  value?: string | number | null;
}

export default function StatCard({ label, value }: StatCardProps) {
  const hasValue = value !== undefined && value !== null && value !== "";

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</p>
      {hasValue ? (
        <p className="mt-2 text-2xl font-semibold text-slate-900">{value}</p>
      ) : (
        <p className="mt-2 text-sm text-slate-400">No dataset analyzed yet</p>
      )}
    </div>
  );
}
