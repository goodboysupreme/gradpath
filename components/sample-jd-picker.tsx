"use client";

import { useMemo, useState } from "react";
import { Building2, Check, ChevronDown, Sparkles, Timer } from "lucide-react";
import {
  getSamplesForRole,
  type RoleId,
  type SampleJd,
  type SeasonId,
} from "@/lib/sample-jds";

type Props = {
  roleId: RoleId | "";
  seasonId: SeasonId | "";
  selectedId: string | null;
  onSelect: (sample: SampleJd) => void;
};

export function SampleJdPicker({ roleId, seasonId, selectedId, onSelect }: Props) {
  const samples = useMemo(
    () => getSamplesForRole(roleId, seasonId || undefined),
    [roleId, seasonId],
  );
  const [open, setOpen] = useState(true);
  const [query, setQuery] = useState("");

  if (!seasonId) {
    return (
      <div className="rounded-[18px] border border-white/10 bg-white/[0.03] px-3 py-3 text-xs leading-5 text-zinc-500">
        Select a <span className="text-zinc-300">season</span> first (Internship / Placement / PS conversion). Sample JDs are season-specific — summer intern JDs are not senior FT postings.
      </div>
    );
  }

  if (!roleId) {
    return (
      <div className="rounded-[18px] border border-white/10 bg-white/[0.03] px-3 py-3 text-xs leading-5 text-zinc-500">
        {seasonId === "internship"
          ? "Pick a summer intern role to load ~20 company internship JDs (Google SWE Intern Summer, Microsoft Explore/University, Amazon SDE Intern, …)."
          : "Pick a full-time / conversion role to load ~20 campus hire style JDs for this season."}
      </div>
    );
  }

  const filtered = samples.filter((sample) => {
    if (!query.trim()) return true;
    const q = query.toLowerCase();
    return (
      sample.company.toLowerCase().includes(q) ||
      sample.title.toLowerCase().includes(q) ||
      sample.program.toLowerCase().includes(q)
    );
  });

  const levelBadge =
    seasonId === "internship"
      ? "Summer intern level"
      : seasonId === "ps-conversion"
        ? "Conversion bar"
        : "New-grad FT";

  return (
    <div className="rounded-[18px] border border-white/10 bg-black/30">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left"
      >
        <span className="flex flex-wrap items-center gap-2 text-xs font-medium text-zinc-300">
          <Sparkles className="h-3.5 w-3.5 text-[#e1ff5f]" />
          Sample JDs
          <span className="rounded-full border border-[#e1ff5f]/25 bg-[#e1ff5f]/10 px-2 py-0.5 text-[10px] text-[#e1ff5f]">
            {levelBadge}
          </span>
          <span className="rounded-full border border-white/10 px-2 py-0.5 text-[10px] text-zinc-500">
            {samples.length}
          </span>
        </span>
        <ChevronDown className={`h-4 w-4 text-zinc-500 transition-transform duration-150 ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="border-t border-white/8 px-2 pb-2 pt-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter by company or program…"
            className="mb-2 w-full rounded-xl border border-white/10 bg-[#090a10] px-3 py-2 text-xs text-white outline-none placeholder:text-zinc-600 focus:border-[#e1ff5f]/40"
          />
          <div className="max-h-52 space-y-1.5 overflow-y-auto pr-1">
            {filtered.map((sample) => {
              const active = selectedId === sample.id;
              return (
                <button
                  key={sample.id}
                  type="button"
                  onClick={() => onSelect(sample)}
                  className={`flex w-full items-start gap-2 rounded-xl border px-3 py-2 text-left transition-all duration-150 ${
                    active
                      ? "border-[#e1ff5f]/40 bg-[#e1ff5f]/10"
                      : "border-white/8 bg-white/[0.02] hover:border-white/15 hover:bg-white/[0.04]"
                  }`}
                >
                  <span className={`mt-0.5 grid h-6 w-6 flex-shrink-0 place-items-center rounded-lg ${
                    active ? "bg-[#e1ff5f] text-zinc-950" : "bg-white/[0.05] text-zinc-400"
                  }`}>
                    {active ? <Check className="h-3.5 w-3.5" /> : <Building2 className="h-3.5 w-3.5" />}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-2">
                      <span className="truncate text-xs font-semibold text-white">{sample.company}</span>
                      <span className="inline-flex items-center gap-1 rounded-full bg-white/[0.04] px-1.5 py-0.5 text-[10px] text-zinc-500">
                        <Timer className="h-2.5 w-2.5" />
                        {sample.duration.includes("week") ? sample.duration.split("(")[0].trim() : sample.level === "summer-intern" ? "Summer" : "FT"}
                      </span>
                    </span>
                    <span className="mt-0.5 block truncate text-[11px] text-zinc-400">{sample.program}</span>
                    <span className="mt-0.5 block truncate text-[10px] text-zinc-600">{sample.title}</span>
                  </span>
                </button>
              );
            })}
            {filtered.length === 0 && (
              <div className="px-2 py-4 text-center text-[11px] text-zinc-500">No samples match that filter.</div>
            )}
          </div>
          <p className="mt-2 px-1 text-[10px] leading-4 text-zinc-600">
            Synthesized from public student/intern posting patterns (Google Summer SWE Intern, Microsoft Explore/University, Amazon SDE Intern, Meta university programs). Not official employer postings.
          </p>
        </div>
      )}
    </div>
  );
}
