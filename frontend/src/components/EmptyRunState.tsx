import { Link } from "react-router-dom";
import { FolderOpen } from "lucide-react";

export default function EmptyRunState({ title }: { title: string }) {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-primary">{title}</h1>
      <div className="rounded-lg border border-dashed border-line-strong bg-surface p-8 text-center">
        <FolderOpen className="mx-auto mb-2 text-muted" size={28} />
        <p className="text-sm font-medium text-secondary">No dataset analyzed yet</p>
        <p className="text-xs text-muted mt-1">Upload a dataset to begin the DataQX quality pipeline.</p>
        <Link
          to="/upload"
          className="mt-4 inline-block rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
        >
          Upload Dataset
        </Link>
      </div>
    </div>
  );
}
