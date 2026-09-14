import { Link } from "react-router-dom";
import { FolderOpen } from "lucide-react";

interface EmptyRunStateProps {
  title: string;
  /** Defaults describe "no dataset uploaded at all" -- override for a page-specific
   * "a run exists, but this stage hasn't produced data yet" message instead. */
  heading?: string;
  description?: string;
  actionLabel?: string;
  actionTo?: string;
}

export default function EmptyRunState({
  title,
  heading = "No dataset analyzed yet",
  description = "Upload a dataset to begin the DataQX quality pipeline.",
  actionLabel = "Upload Dataset",
  actionTo = "/upload",
}: EmptyRunStateProps) {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-primary">{title}</h1>
      <div className="rounded-lg border border-dashed border-line-strong bg-surface p-8 text-center">
        <FolderOpen className="mx-auto mb-2 text-muted" size={28} />
        <p className="text-sm font-medium text-secondary">{heading}</p>
        <p className="text-xs text-muted mt-1 max-w-sm mx-auto">{description}</p>
        <Link
          to={actionTo}
          className="mt-4 inline-block rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
        >
          {actionLabel}
        </Link>
      </div>
    </div>
  );
}
