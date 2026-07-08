"use client";

interface Props {
  used: number;
  limit: number;
}

export function UsageBadge({ used, limit }: Props) {
  const remaining = limit - used;
  const isLow = remaining <= 1;

  return (
    <div className={`rounded-2xl px-3 py-2 text-xs font-bold border ${
      isLow
        ? "border-rose-300/25 bg-rose-400/10 text-rose-200"
        : "border-white/10 bg-white/[0.03] text-zinc-300"
    }`}>
      {remaining}/{limit} left
    </div>
  );
}
