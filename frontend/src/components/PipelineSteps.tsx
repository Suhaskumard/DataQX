import { CheckCircle2, Circle } from "lucide-react";

export interface PipelineStepData {
  label: string;
  count: number;
  /** Whether this stage has actually run/produced a result -- never fabricated,
   * always derived from real backend data by the caller. */
  done: boolean;
}

/** Reusable horizontal pipeline indicator (Detected -> Recommended -> Applied ->
 * Validated, etc.) -- every count and done-state is supplied by the caller from
 * real data; this component only renders what it's given. */
export default function PipelineSteps({ steps }: { steps: PipelineStepData[] }) {
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-3">
      {steps.map((step, idx) => (
        <div key={step.label} className="flex items-center gap-2">
          <div
            className={`flex items-center gap-2 rounded-lg border px-3 py-2 ${
              step.done
                ? "border-emerald-200 dark:border-emerald-900/50 bg-emerald-50 dark:bg-emerald-950/30"
                : "border-line bg-surface"
            }`}
          >
            {step.done ? (
              <CheckCircle2 size={16} className="text-emerald-600 dark:text-emerald-400 shrink-0" />
            ) : (
              <Circle size={16} className="text-muted shrink-0" />
            )}
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-secondary">{step.label}</p>
              <p className="text-sm font-semibold text-primary">{step.count}</p>
            </div>
          </div>
          {idx < steps.length - 1 && <span className="text-muted" aria-hidden="true">→</span>}
        </div>
      ))}
    </div>
  );
}
