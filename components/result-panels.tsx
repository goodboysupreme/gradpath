"use client";

import { useState } from "react";
import { AlertTriangle, CheckCircle2, ClipboardList, FileText, Gauge, Lightbulb, Map, Rocket, Wrench } from "lucide-react";
import type { AnalysisResult } from "@/lib/analysis";

interface Props {
  result: AnalysisResult;
}

type TabId = "gaps" | "roadmap" | "projects" | "prep" | "resume" | "strategy" | "strengths" | "wins";

const tabMeta = {
  gaps: { label: "Gaps", icon: AlertTriangle },
  roadmap: { label: "Roadmap", icon: Map },
  projects: { label: "Projects", icon: Wrench },
  prep: { label: "Prep", icon: Gauge },
  resume: { label: "Resume", icon: FileText },
  strategy: { label: "Strategy", icon: Rocket },
  strengths: { label: "Strengths", icon: CheckCircle2 },
  wins: { label: "Quick Wins", icon: Lightbulb },
};

export function ResultPanels({ result }: Props) {
  const [activeTab, setActiveTab] = useState<TabId>("gaps");
  const roadmap = result.roadmap ?? [];
  const prepTopics = result.prepTopics ?? [];
  const resumeBullets = result.resumeBullets ?? [];
  const applicationStrategy = result.applicationStrategy ?? [];

  const tabs = [
    { id: "gaps" as const, count: result.gaps.length },
    { id: "roadmap" as const, count: roadmap.length },
    { id: "projects" as const, count: result.projects.length },
    { id: "prep" as const, count: prepTopics.length },
    { id: "resume" as const, count: resumeBullets.length },
    { id: "strategy" as const, count: applicationStrategy.length },
    { id: "strengths" as const, count: result.strengths.length },
    { id: "wins" as const, count: result.quickWins.length },
  ];

  return (
    <div className="grid gap-5 lg:grid-cols-[260px_minmax(0,1fr)]">
      <div className="rounded-[28px] border border-white/10 bg-black/24 p-2">
        {tabs.map((tab) => {
          const meta = tabMeta[tab.id];
          const Icon = meta.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`mb-1 flex w-full items-center justify-between rounded-2xl px-3 py-3 text-left transition-all duration-150 last:mb-0 ${
                activeTab === tab.id
                  ? "bg-white text-zinc-950 shadow-lg shadow-white/10"
                  : "text-zinc-400 hover:bg-white/[0.04] hover:text-white"
              }`}
            >
              <span className="flex items-center gap-2 text-sm font-medium">
                <Icon className="h-4 w-4" />
                {meta.label}
              </span>
              <span className={`rounded-full px-2 py-0.5 text-xs ${
                activeTab === tab.id ? "bg-zinc-950/10 text-zinc-800" : "bg-white/[0.06] text-zinc-500"
              }`}>
                {tab.count}
              </span>
            </button>
          );
        })}
      </div>

      <div className="min-h-[360px] rounded-[28px] border border-white/10 bg-black/24 p-4">
        {activeTab === "gaps" && (
          <div className="grid gap-3 animate-fade-in">
            {[...result.gaps]
              .sort((a, b) => (a.importance === "critical" ? -1 : 1) - (b.importance === "critical" ? -1 : 1))
              .map((gap, i) => (
                <article
                  key={i}
                  className={`rounded-[24px] border p-4 ${
                    gap.importance === "critical"
                      ? "border-rose-300/18 bg-rose-400/8"
                      : "border-white/10 bg-white/[0.03]"
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <span className={`mt-0.5 rounded-full px-2 py-1 text-[11px] font-bold uppercase tracking-[0.14em] ${
                      gap.importance === "critical"
                        ? "bg-rose-300/12 text-rose-200"
                        : "bg-zinc-800 text-zinc-300"
                    }`}>
                      {gap.importance}
                    </span>
                    <div>
                      <h4 className="font-semibold text-white">{gap.skill}</h4>
                      <p className="mt-1 text-sm leading-6 text-zinc-400">{gap.why}</p>
                    </div>
                  </div>
                </article>
              ))}
          </div>
        )}

        {activeTab === "roadmap" && (
          <div className="grid gap-3 animate-fade-in md:grid-cols-2">
            {roadmap.map((phase, i) => (
              <article key={i} className="rounded-[24px] border border-white/10 bg-white/[0.03] p-4">
                <div className="mb-4 flex items-center justify-between gap-3">
                  <h4 className="font-semibold text-white">{phase.phase}</h4>
                  <span className="rounded-full bg-[#e1ff5f]/12 px-2 py-1 text-xs font-medium text-[#e1ff5f]">
                    {phase.timeline}
                  </span>
                </div>
                <div className="space-y-2">
                  {phase.actions.map((action, j) => (
                    <p key={j} className="rounded-2xl border border-white/8 bg-black/20 p-3 text-sm leading-5 text-zinc-300">
                      {action}
                    </p>
                  ))}
                </div>
              </article>
            ))}
          </div>
        )}

        {activeTab === "projects" && (
          <div className="grid gap-4 animate-fade-in md:grid-cols-2">
            {result.projects.map((project, i) => (
              <article key={i} className="group rounded-[24px] border border-white/10 bg-white/[0.03] p-5 transition-all duration-150 hover:border-[#e1ff5f]/35 hover:bg-white/[0.05]">
                <div className="mb-3 flex items-start justify-between gap-3">
                  <h4 className="font-semibold text-white">{project.title}</h4>
                  <span className="rounded-full bg-cyan-300/12 px-2 py-1 text-xs font-medium text-cyan-200">
                    {project.effort}
                  </span>
                </div>
                <p className="text-sm leading-6 text-zinc-400">{project.description}</p>
                <div className="mt-4 flex flex-wrap gap-1.5">
                  {project.skillsCovered.map((skill, j) => (
                    <span key={j} className="rounded-full border border-white/10 bg-black/24 px-2 py-1 text-xs text-zinc-300">
                      {skill}
                    </span>
                  ))}
                </div>
              </article>
            ))}
          </div>
        )}

        {activeTab === "prep" && (
          <div className="space-y-3 animate-fade-in">
            {prepTopics.map((topic, i) => (
              <article key={i} className="rounded-[24px] border border-white/10 bg-white/[0.03] p-4">
                <div className="flex items-start gap-3">
                  <Priority priority={topic.priority} />
                  <div>
                    <h4 className="font-semibold text-white">{topic.topic}</h4>
                    <p className="mt-1 text-sm leading-6 text-zinc-400">{topic.reason}</p>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}

        {activeTab === "resume" && (
          <div className="space-y-2 animate-fade-in">
            {resumeBullets.map((bullet, i) => (
              <div key={i} className="flex gap-3 rounded-[22px] border border-white/10 bg-white/[0.03] p-4">
                <span className="mt-0.5 grid h-6 w-6 flex-shrink-0 place-items-center rounded-full bg-[#e1ff5f]/12 text-xs font-black text-[#e1ff5f]">
                  {i + 1}
                </span>
                <p className="text-sm leading-6 text-zinc-200">{bullet}</p>
              </div>
            ))}
          </div>
        )}

        {activeTab === "strategy" && (
          <div className="space-y-2 animate-fade-in">
            {applicationStrategy.map((step, i) => (
              <div key={i} className="flex gap-3 rounded-[22px] border border-white/10 bg-white/[0.03] p-4">
                <span className="grid h-7 w-7 flex-shrink-0 place-items-center rounded-full border border-[#e1ff5f]/30 text-xs font-black text-[#e1ff5f]">
                  {i + 1}
                </span>
                <p className="text-sm leading-6 text-zinc-200">{step}</p>
              </div>
            ))}
          </div>
        )}

        {activeTab === "strengths" && (
          <div className="grid gap-3 animate-fade-in md:grid-cols-2">
            {result.strengths.map((strength, i) => (
              <article key={i} className="rounded-[24px] border border-emerald-300/18 bg-emerald-400/7 p-4">
                <h4 className="font-semibold text-white">{strength.skill}</h4>
                <p className="mt-1 text-sm leading-6 text-zinc-400">{strength.evidence}</p>
              </article>
            ))}
          </div>
        )}

        {activeTab === "wins" && (
          <div className="grid gap-2 animate-fade-in md:grid-cols-2">
            {result.quickWins.map((win, i) => (
              <div key={i} className="flex gap-3 rounded-[22px] border border-amber-300/15 bg-amber-300/7 p-4">
                <Lightbulb className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-200" />
                <p className="text-sm leading-6 text-zinc-200">{win}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Priority({ priority }: { priority: "high" | "medium" | "low" }) {
  const classes = priority === "high"
    ? "bg-rose-300/12 text-rose-200"
    : priority === "medium"
      ? "bg-amber-300/12 text-amber-200"
      : "bg-zinc-800 text-zinc-300";
  return (
    <span className={`rounded-full px-2 py-1 text-[11px] font-bold uppercase tracking-[0.14em] ${classes}`}>
      {priority}
    </span>
  );
}
