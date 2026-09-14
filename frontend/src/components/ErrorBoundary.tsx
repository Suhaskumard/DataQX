import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertOctagon } from "lucide-react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Last-resort safety net. Several pages read nested fields off backend responses
 * without guarding against a per-file "stage failed" shape (a real, confirmed
 * backend response e.g. {"status": "failed", "reason": "..."}) -- if any of those
 * unguarded reads throws, this converts a silent white screen into a page the user
 * can actually act on (go back to Upload) instead of a blank tab with no explanation.
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("DataQX UI crashed:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen bg-canvas flex items-center justify-center p-6">
          <div className="max-w-xl space-y-4 text-center">
            <AlertOctagon className="mx-auto text-red-500" size={32} />
            <h1 className="text-xl font-semibold text-primary">Something went wrong</h1>
            <p className="text-sm text-secondary">
              <span className="font-medium text-primary">Why: </span>
              This page hit an unexpected error, possibly because the backend returned a result this view didn't
              expect (for example, a stage that failed for one of your files). Your run data has not been lost.
            </p>
            <p className="text-sm text-secondary">
              <span className="font-medium text-primary">What you can do: </span>
              Go back to the Dashboard and try the action again.
            </p>
            <button
              onClick={() => {
                this.setState({ error: null });
                window.location.assign("/");
              }}
              className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
            >
              Back to Dashboard
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
