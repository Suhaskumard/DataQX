import type { LucideIcon } from "lucide-react";
import {
  AlertTriangle,
  CheckCircle2,
  XCircle,
  AlertCircle,
  ShieldCheck,
  ShieldAlert,
  ShieldQuestion,
  TrendingUp,
  Minus,
  Activity,
} from "lucide-react";

export type BadgeKind = "severity" | "confidence" | "status" | "drift" | "readiness" | "platform_status";

interface StyleEntry {
  label: string;
  className: string;
  icon: LucideIcon;
}

// One place defining every semantic color+icon+label combination DataQX uses, so
// every page renders severity/confidence/validation/drift/readiness identically
// instead of each page inventing its own bg-*-100 text-*-800 pair.
// Each semantic color family gets one light + dark pairing, reused everywhere below
// so the same meaning always renders identically across every Badge kind, in both themes.
const RED = "bg-red-100 text-red-800 ring-red-200 dark:bg-red-500/15 dark:text-red-300 dark:ring-red-500/30";
const ORANGE = "bg-orange-100 text-orange-800 ring-orange-200 dark:bg-orange-500/15 dark:text-orange-300 dark:ring-orange-500/30";
const AMBER = "bg-amber-100 text-amber-800 ring-amber-200 dark:bg-amber-500/15 dark:text-amber-300 dark:ring-amber-500/30";
const EMERALD = "bg-emerald-100 text-emerald-800 ring-emerald-200 dark:bg-emerald-500/15 dark:text-emerald-300 dark:ring-emerald-500/30";
const NEUTRAL = "bg-slate-100 text-slate-700 ring-slate-200 dark:bg-slate-500/15 dark:text-slate-300 dark:ring-slate-500/30";

const STYLES: Record<BadgeKind, Record<string, StyleEntry>> = {
  severity: {
    critical: { label: "Critical", className: RED, icon: XCircle },
    high: { label: "High", className: ORANGE, icon: AlertTriangle },
    medium: { label: "Medium", className: AMBER, icon: AlertCircle },
    low: { label: "Low", className: NEUTRAL, icon: Minus },
  },
  confidence: {
    high: { label: "HIGH", className: EMERALD, icon: ShieldCheck },
    medium: { label: "MEDIUM", className: AMBER, icon: ShieldAlert },
    low: { label: "LOW", className: NEUTRAL, icon: ShieldQuestion },
  },
  status: {
    pass: { label: "PASS", className: EMERALD, icon: CheckCircle2 },
    cleaned: { label: "Published", className: EMERALD, icon: CheckCircle2 },
    warning: { label: "WARNING", className: AMBER, icon: AlertTriangle },
    fail: { label: "FAIL", className: RED, icon: XCircle },
    rolled_back: { label: "Rolled Back", className: AMBER, icon: AlertTriangle },
    applied: { label: "Applied", className: EMERALD, icon: CheckCircle2 },
    skipped_protected: { label: "Protected", className: NEUTRAL, icon: ShieldCheck },
    flagged_for_review: { label: "Review", className: AMBER, icon: AlertCircle },
  },
  drift: {
    stable: { label: "Stable", className: EMERALD, icon: CheckCircle2 },
    no_history: { label: "Stable", className: NEUTRAL, icon: Minus },
    changed: { label: "Changed", className: AMBER, icon: Activity },
    significant: { label: "Significant Drift", className: RED, icon: TrendingUp },
  },
  readiness: {
    ready: { label: "Ready", className: EMERALD, icon: CheckCircle2 },
    attention: { label: "Needs Attention", className: AMBER, icon: AlertTriangle },
    "not-ready": { label: "Not Ready", className: RED, icon: XCircle },
  },
  // Maps the Analytics Readiness Engine's per-platform status values
  // (READY | READY_WITH_WARNINGS | NEEDS_CLEANING | NOT_READY) onto the same
  // green/amber/red palette used everywhere else -- no new colors invented.
  platform_status: {
    ready: { label: "Ready", className: EMERALD, icon: CheckCircle2 },
    ready_with_warnings: { label: "Ready with Warnings", className: AMBER, icon: AlertTriangle },
    needs_cleaning: { label: "Needs Cleaning", className: AMBER, icon: AlertCircle },
    not_ready: { label: "Not Ready", className: RED, icon: XCircle },
  },
};

interface BadgeProps {
  kind: BadgeKind;
  value: string;
  /** Override the display label without changing the color/icon lookup key. */
  label?: string;
  className?: string;
}

export default function Badge({ kind, value, label, className }: BadgeProps) {
  const normalized = value?.toLowerCase?.() ?? String(value);
  const entry = STYLES[kind]?.[normalized] ?? {
    label: value,
    className: NEUTRAL,
    icon: Minus,
  };
  const Icon = entry.icon;

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${entry.className} ${className ?? ""}`}
    >
      <Icon size={12} strokeWidth={2.5} />
      {label ?? entry.label}
    </span>
  );
}

/** Pure helper (no React) so pages can derive a drift Badge value from real
 * overall_status/findings data without inventing new backend fields. */
export function classifyDrift(overallStatus: string, findingCount: number): string {
  if (overallStatus === "no_history") return "no_history";
  if (findingCount === 0) return "stable";
  return findingCount >= 3 ? "significant" : "changed";
}

/** Pure helper deriving an Analytics Readiness Badge value from the real 0-100
 * overall score already returned by the backend -- no new backend field required. */
export function classifyReadiness(score: number): string {
  if (score >= 80) return "ready";
  if (score >= 50) return "attention";
  return "not-ready";
}
