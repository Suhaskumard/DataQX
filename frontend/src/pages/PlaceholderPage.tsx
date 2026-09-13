interface PlaceholderPageProps {
  title: string;
}

export default function PlaceholderPage({ title }: PlaceholderPageProps) {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
      <div className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center">
        <p className="text-sm font-medium text-slate-600">Not available yet</p>
        <p className="text-xs text-slate-400 mt-1">
          This section will populate once its backend processing phase is implemented.
        </p>
      </div>
    </div>
  );
}
