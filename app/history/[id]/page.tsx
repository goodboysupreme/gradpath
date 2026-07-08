import { auth } from "@/auth";
import { db } from "@/db";
import { analyses } from "@/db/schema";
import { eq, and } from "drizzle-orm";
import { ArrowLeft, Plus } from "lucide-react";
import Link from "next/link";
import { ScoreRing } from "@/components/score-ring";
import { ResultPanels } from "@/components/result-panels";
import type { AnalysisResult } from "@/lib/analysis";

export default async function HistoryDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const session = await auth();
  if (!session?.user?.id) {
    return <div className="min-h-screen bg-[#07080d] p-8 text-center text-zinc-400">Please sign in.</div>;
  }

  const { id } = await params;
  const [row] = await db
    .select()
    .from(analyses)
    .where(and(eq(analyses.id, id), eq(analyses.userId, session.user.id)))
    .limit(1);

  if (!row) {
    return (
      <div className="min-h-screen bg-[#07080d] p-8 text-center text-zinc-400">
        Analysis not found. <Link href="/history" className="text-[#e1ff5f]">Back</Link>
      </div>
    );
  }

  const result = row.result as AnalysisResult;
  const date = new Date(row.createdAt).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
  const target = [row.targetCompany, row.targetRole].filter(Boolean).join(" / ");

  return (
    <main className="min-h-screen overflow-hidden bg-[#07080d] text-zinc-100">
      <div className="app-grid-bg fixed inset-0 -z-10" />
      <div className="mx-auto w-full max-w-6xl px-4 py-5 sm:px-6 lg:px-8">
        <header className="mb-5 flex items-center justify-between rounded-[28px] border border-white/10 bg-zinc-950/78 px-4 py-3 shadow-2xl shadow-black/30 backdrop-blur-xl">
          <div className="flex items-center gap-3">
            <Link href="/history" className="grid h-10 w-10 place-items-center rounded-2xl border border-white/10 bg-white/[0.03] text-zinc-400 transition-all duration-150 hover:text-white" aria-label="Back to history">
              <ArrowLeft className="h-4 w-4" />
            </Link>
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.22em] text-zinc-500">{date}</p>
              <h1 className="text-lg font-semibold tracking-tight text-white sm:text-xl">{target || "Saved readiness run"}</h1>
            </div>
          </div>
          <Link href="/analyze" className="inline-flex items-center gap-2 rounded-2xl bg-[#e1ff5f] px-4 py-2 text-sm font-black text-zinc-950 transition-all duration-150 hover:scale-[1.01] hover:bg-[#f0ff99]">
            <Plus className="h-4 w-4" />
            New run
          </Link>
        </header>

        <section className="mb-5 rounded-[34px] border border-white/10 bg-zinc-950/78 p-5 shadow-2xl shadow-black/35 backdrop-blur-xl">
          <div className="flex flex-col gap-5 md:flex-row md:items-center">
            <ScoreRing score={result.matchScore} />
            <div className="flex-1">
              <p className="text-xs font-medium uppercase tracking-[0.22em] text-[#e1ff5f]">Summary</p>
              <p className="mt-3 text-sm leading-7 text-zinc-300">{result.summary}</p>
            </div>
          </div>
        </section>

        <div className="mb-5 grid gap-4 lg:grid-cols-2">
          <details className="rounded-[28px] border border-white/10 bg-zinc-950/78 p-4 shadow-xl shadow-black/20 backdrop-blur-xl">
            <summary className="cursor-pointer text-sm font-medium text-zinc-200">Role brief</summary>
            <pre className="mt-4 max-h-72 overflow-auto whitespace-pre-wrap rounded-2xl border border-white/10 bg-black/24 p-4 font-mono text-xs leading-5 text-zinc-400">{row.jdText}</pre>
          </details>

          <details className="rounded-[28px] border border-white/10 bg-zinc-950/78 p-4 shadow-xl shadow-black/20 backdrop-blur-xl">
            <summary className="cursor-pointer text-sm font-medium text-zinc-200">
              Resume or profile {row.resumeFilename ? `(${row.resumeFilename})` : ""}
            </summary>
            <pre className="mt-4 max-h-72 overflow-auto whitespace-pre-wrap rounded-2xl border border-white/10 bg-black/24 p-4 font-mono text-xs leading-5 text-zinc-400">{row.resumeText}</pre>
          </details>
        </div>

        <section className="rounded-[34px] border border-white/10 bg-zinc-950/82 p-5 shadow-2xl shadow-black/35 backdrop-blur-xl">
          <ResultPanels result={result} />
        </section>
      </div>
    </main>
  );
}
