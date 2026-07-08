"use client";

interface Props {
  score: number;
  compact?: boolean;
}

export function ScoreRing({ score, compact = false }: Props) {
  const radius = compact ? 34 : 52;
  const viewBox = compact ? 84 : 120;
  const center = viewBox / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;

  const color = score >= 85 ? "#34d399" : score >= 70 ? "#e1ff5f" : score >= 55 ? "#fbbf24" : "#fb7185";

  return (
    <div className={`relative flex-shrink-0 ${compact ? "h-20 w-20" : "h-32 w-32"}`}>
      <svg className="score-ring h-full w-full" viewBox={`0 0 ${viewBox} ${viewBox}`}>
        <circle cx={center} cy={center} r={radius} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth={compact ? "6" : "8"} />
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={compact ? "6" : "8"}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={compact ? "text-xl font-black" : "text-3xl font-black"} style={{ color }}>{score}</span>
        {!compact && <span className="text-xs text-zinc-500">/ 100</span>}
      </div>
    </div>
  );
}
