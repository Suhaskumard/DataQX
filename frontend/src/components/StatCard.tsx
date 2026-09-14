import type { LucideIcon } from "lucide-react";

interface StatCardProps {
  label: string;
  value?: string | number | null;
  icon?: LucideIcon;
}

export default function StatCard({ label, value, icon: Icon }: StatCardProps) {
  const hasValue = value !== undefined && value !== null && value !== "";

  return (
    <div className="relative rounded-lg border border-line bg-surface p-4 transition-shadow hover:shadow-sm hover:shadow-black/5">
      {Icon && <Icon size={16} className="absolute right-4 top-4 text-muted" />}
      <p className="text-xs font-medium uppercase tracking-wide text-secondary pr-5">{label}</p>
      {hasValue ? (
        <p className="mt-2 text-2xl font-semibold text-primary">{value}</p>
      ) : (
        <p className="mt-2 text-sm text-secondary">No dataset analyzed yet</p>
      )}
    </div>
  );
}
