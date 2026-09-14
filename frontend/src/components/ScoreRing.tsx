interface ScoreRingProps {
  score: number | null | undefined;
  size?: number;
  label?: string;
}

function ringColor(score: number): string {
  if (score >= 80) return "#059669"; // emerald-600
  if (score >= 50) return "#d97706"; // amber-600
  return "#dc2626"; // red-600
}

/** SVG radial gauge for a real 0-100 score (quality score, analytics readiness).
 * Renders a plain "—" placeholder -- never a fabricated ring -- when no score is
 * available yet (matches StatCard's existing "no data" convention). */
export default function ScoreRing({ score, size = 72, label }: ScoreRingProps) {
  const hasScore = typeof score === "number" && Number.isFinite(score);
  const radius = (size - 8) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = hasScore ? Math.max(0, Math.min(100, score as number)) : 0;
  const offset = circumference * (1 - clamped / 100);

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            style={{ stroke: "rgb(var(--color-border))" }}
            strokeWidth={6}
          />
          {hasScore && (
            <circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke={ringColor(clamped)}
              strokeWidth={6}
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
            />
          )}
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <p className="text-lg font-semibold text-primary">{hasScore ? Math.round(clamped) : "—"}</p>
        </div>
      </div>
      {label && <p className="text-[10px] uppercase tracking-wide text-muted">{label}</p>}
    </div>
  );
}
