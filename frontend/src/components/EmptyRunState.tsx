import { Link } from "react-router-dom";

export default function EmptyRunState({ title }: { title: string }) {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
      <div className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center">
        <p className="text-sm font-medium text-slate-600">No dataset analyzed yet</p>
        <p className="text-xs text-slate-400 mt-1">
          Go to{" "}
          <Link to="/upload" className="underline">
            Upload Dataset
          </Link>{" "}
          to analyze a file first.
        </p>
      </div>
    </div>
  );
}
