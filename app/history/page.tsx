import { auth } from "@/auth";
import { db } from "@/db";
import { analyses } from "@/db/schema";
import { resolveUserId } from "@/lib/guest-user";
import { desc, eq } from "drizzle-orm";
import { ArrowLeft, FileClock, Plus } from "lucide-react";
import Link from "next/link";

export default async function HistoryPage() {
  const session = await auth().catch(() => null);
  const userId = await resolveUserId(session?.user?.id);

  const rows = await db
    .select({
      id: analyses.id,
      createdAt: analyses.createdAt,
      matchScore: analyses.matchScore,
      targetCompany: analyses.targetCompany,
      targetRole: analyses.targetRole,
      jdText: analyses.jdText,
      resumeFilename: analyses.resumeFilename,
    })
    .from(analyses)
    .where(eq(analyses.userId, userId))
    .orderBy(desc(analyses.createdAt))
    .limit(50);

  return (
    <main className="min-h-screen overflow-hidden bg-[#07080d] text-zinc-100">
      <div className="app-grid-bg fixed inset-0 -z-10" />
      <div className="mx-auto w-full max-w-6xl px-4 py-5 sm:px-6 lg:px-8">
        <header className="mb-5 flex items-center justify-between rounded-[28px] border border-white/10 bg-zinc-950/78 px-4 py-3 shadow-2xl shadow-black/30 backdrop-blur-xl">
          <div className="flex items-center gap-3">
            <Link href="/analyze" className="grid h-10 w-10 place-items-center rounded-2xl border border-white/10 bg-white/[0.03] text-zinc-400 transition-all duration-150 hover:text-white" aria-label="Back to console">
              <ArrowLeft className="h-4 w-4" />
            </Link>
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.22em] text-[#e1ff5f]">Archive</p>
              <h1 className="text-xl font-semibold tracking-tight text-white">Readiness history</h1>
            </div>
          </div>
          <Link href="/analyze" className="inline-flex items-center gap-2 rounded-2xl bg-[#e1ff5f] px-4 py-2 text-sm font-black text-zinc-950 transition-all duration-150 hover:scale-[1.01] hover:bg-[#f0ff99]">
            <Plus className="h-4 w-4" />
            New run
          </Link>
        </header>

        {rows.length === 0 ? (
          <section className="grid min-h-[420px] place-items-center rounded-[34px] border border-white/10 bg-zinc-950/78 p-8 text-center shadow-2xl shadow-black/35 backdrop-blur-xl">
            <div>
              <div className="mx-auto mb-5 grid h-16 w-16 place-items-center rounded-3xl border border-white/10 bg-white/[0.03] text-[#e1ff5f]">
                <FileClock className="h-7 w-7" />
              </div>
              <h2 className="text-2xl font-semibold text-white">No runs yet</h2>
              <Link href="/analyze" className="mt-5 inline-flex rounded-2xl bg-[#e1ff5f] px-5 py-3 text-sm font-black text-zinc-950 transition-all duration-150 hover:bg-[#f0ff99]">
                Start first run
              </Link>
            </div>
          </section>
        ) : (
          <section className="grid gap-3">
            {rows.map((row) => {
              const jdSnippet = row.jdText.slice(0, 110) + "...";
              const target = [row.targetCompany, row.targetRole].filter(Boolean).join(" / ");
              const date = new Date(row.createdAt).toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
                year: "numeric",
              });
              const scoreTone =
                row.matchScore >= 85 ? "text-emerald-300 border-emerald-300/20 bg-emerald-400/8"
                : row.matchScore >= 70 ? "text-[#e1ff5f] border-[#e1ff5f]/20 bg-[#e1ff5f]/8"
                : row.matchScore >= 55 ? "text-amber-200 border-amber-300/20 bg-amber-300/8"
                : "text-rose-200 border-rose-300/20 bg-rose-400/8";

              return (
                <Link
                  key={row.id}
                  href={`/history/${row.id}`}
                  className="group rounded-[28px] border border-white/10 bg-zinc-950/78 p-4 shadow-xl shadow-black/20 backdrop-blur-xl transition-all duration-150 hover:border-[#e1ff5f]/35 hover:bg-zinc-900/80"
                >
                  <div className="flex items-center gap-4">
                    <div className={`grid h-16 w-16 flex-shrink-0 place-items-center rounded-3xl border text-2xl font-black ${scoreTone}`}>
                      {row.matchScore}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="mb-1 text-xs font-medium uppercase tracking-[0.16em] text-zinc-500">
                        {date}{row.resumeFilename ? ` | ${row.resumeFilename}` : ""}
                      </div>
                      <div className="truncate text-base font-semibold text-white">{target || jdSnippet}</div>
                      {target ? <div className="mt-1 truncate text-sm text-zinc-500">{jdSnippet}</div> : null}
                    </div>
                  </div>
                </Link>
              );
            })}
          </section>
        )}
      </div>
    </main>
  );
}
