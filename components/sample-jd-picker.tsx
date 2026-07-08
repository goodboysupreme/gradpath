"use client";

import { useMemo, useState } from "react";
import { Building2, Check, ChevronDown, Sparkles } from "lucide-react";
import {
  getSamplesForRole,
  type RoleId,
  type SampleJd,
} from "@/lib/sample-jds";

type Props = {
  roleId: RoleId | "";
  selectedId: string | null;
  onSelect: (sample: SampleJd) => void;
};

export function SampleJdPicker({ roleId, selectedId, onSelect }: Props) {
  const samples = useMemo(() => getSamplesForRole(roleId), [roleId]);
  const [open, setOpen] = useState(true);
  const [query, setQuery] = useState("");

  if (!roleId) {
    return (
      <div className="rounded-[18px] border border-white/10 bg-white/[0.03] px-3 py-3 text-xs leading-5 text-zinc-500">
        Pick a role on the left to load ~20 sample JDs (Google, Amazon, DE Shaw, Flipkart, …).
      </div>
    );
  }

  const filtered = samples.filter((sample) => {
    if (!query.trim()) return true;
    const q = query.toLowerCase();
    return sample.company.toLowerCase().includes(q) || sample.title.toLowerCase().includes(q);
  });

  return (
    <div className="rounded-[18px] border border-white/10 bg-black/30">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left"
      >
        <span className="flex items-center gap-2 text-xs font-medium text-zinc-300">
          <Sparkles className="h-3.5 w-3.5 text-[#e1ff5f]" />
          Sample JDs for this role
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
            placeholder="Filter by company…"
            className="mb-2 w-full rounded-xl border border-white/10 bg-[#090a10] px-3 py-2 text-xs text-white outline-none placeholder:text-zinc-600 focus:border-[#e1ff5f]/40"
          />
          <div className="max-h-44 space-y-1.5 overflow-y-auto pr-1">
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
                    <span className="block truncate text-xs font-semibold text-white">{sample.company}</span>
                    <span className="mt-0.5 block truncate text-[11px] text-zinc-500">{sample.title}</span>
                  </span>
                </button>
              );
            })}
            {filtered.length === 0 && (
              <div className="px-2 py-4 text-center text-[11px] text-zinc-500">No samples match that filter.</div>
            )}
          </div>
          <p className="mt-2 px-1 text-[10px] leading-4 text-zinc-600">
            Samples are synthesized from common public campus/new-grad patterns — not official postings.
          </p>
        </div>
      )}
    </div>
  );
}
