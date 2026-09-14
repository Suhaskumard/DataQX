import { Link } from "react-router-dom";
import { Compass } from "lucide-react";

export default function NotFound() {
  return (
    <div className="max-w-xl mx-auto mt-16 space-y-4 text-center">
      <Compass className="mx-auto text-muted" size={32} />
      <h1 className="text-xl font-semibold text-primary">Page not found</h1>
      <p className="text-sm text-secondary">This page doesn't exist.</p>
      <Link
        to="/"
        className="inline-block rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
      >
        Back to Dashboard
      </Link>
    </div>
  );
}
