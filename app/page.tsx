import Link from "next/link";
import { ArrowRight, GraduationCap, History, Target } from "lucide-react";

export default function LandingPage() {
  return (
    <main className="min-h-screen overflow-hidden bg-[#07080d] text-zinc-100">
      <div className="app-grid-bg fixed inset-0 -z-10" />
      <div className="mx-auto flex min-h-screen w-full max-w-[1400px] flex-col px-4 py-4 sm:px-6 lg:px-8">
        <nav className="mb-5 flex items-center justify-between rounded-[28px] border border-white/10 bg-zinc-950/78 px-4 py-3 shadow-2xl shadow-black/30 backdrop-blur-xl">
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-2xl bg-[#e1ff5f] text-sm font-black text-zinc-950">GP</span>
            <div>
              <span className="block text-lg font-semibold leading-tight text-white">GradPath</span>
              <span className="text-xs text-zinc-500">BITS placement readiness</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/history" className="hidden items-center gap-2 rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-2 text-sm text-zinc-300 transition-all duration-150 hover:border-white/20 hover:text-white sm:flex">
              <History className="h-4 w-4" />
              History
            </Link>
            <Link href="/analyze" className="flex items-center gap-2 rounded-2xl bg-[#e1ff5f] px-4 py-2 text-sm font-black text-zinc-950 transition-all duration-150 hover:scale-[1.01] hover:bg-[#f0ff99]">
              Open console
            </Link>
          </div>
        </nav>

        <section className="grid flex-1 gap-5 lg:grid-cols-[minmax(0,1fr)_420px]">
          <div className="rounded-[38px] border border-white/10 bg-zinc-950/78 p-6 shadow-2xl shadow-black/35 backdrop-blur-xl sm:p-8 lg:p-10">
            <div className="mb-12 inline-flex items-center gap-2 rounded-full border border-[#e1ff5f]/25 bg-[#e1ff5f]/8 px-3 py-1 text-xs font-medium text-[#e1ff5f]">
              <GraduationCap className="h-3.5 w-3.5" />
              BE and MTech · open access
            </div>
            <h1 className="max-w-4xl text-5xl font-black leading-[0.95] tracking-[-0.04em] text-white sm:text-7xl lg:text-8xl">
              Point at a company. Get the path.
            </h1>
            <p className="mt-7 max-w-2xl text-lg leading-8 text-zinc-400">
              Company, role, resume or no resume. GradPath turns that into gaps, projects, prep topics, bullets, and a placement-season attack plan.
            </p>
            <div className="mt-10 flex flex-wrap gap-3">
              <Link href="/analyze" className="group inline-flex items-center gap-2 rounded-2xl bg-[#e1ff5f] px-6 py-4 text-sm font-black text-zinc-950 transition-all duration-150 hover:scale-[1.01] hover:bg-[#f0ff99]">
                Open console
                <ArrowRight className="h-4 w-4 transition-transform duration-150 group-hover:translate-x-0.5" />
              </Link>
              <Link href="/history" className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-white/[0.03] px-6 py-4 text-sm font-medium text-zinc-300 transition-all duration-150 hover:border-white/20 hover:text-white">
                <History className="h-4 w-4" />
                History
              </Link>
            </div>
          </div>

          <aside className="grid gap-5">
            <div className="rounded-[34px] border border-white/10 bg-zinc-950/78 p-6 shadow-xl shadow-black/25 backdrop-blur-xl">
              <div className="mb-5 flex items-center justify-between">
                <p className="text-xs font-medium uppercase tracking-[0.22em] text-zinc-500">Signal stack</p>
                <Target className="h-5 w-5 text-[#e1ff5f]" />
              </div>
              <div className="space-y-3">
                {[
                  ["01", "Target company and role"],
                  ["02", "Resume or guided student profile"],
                  ["03", "Role brief or JD"],
                  ["04", "Action plan and interview prep"],
                ].map(([index, label]) => (
                  <div key={index} className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.03] p-3">
                    <span className="grid h-8 w-8 place-items-center rounded-xl bg-[#e1ff5f]/12 text-xs font-black text-[#e1ff5f]">{index}</span>
                    <span className="text-sm text-zinc-300">{label}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-[34px] border border-white/10 bg-zinc-950/78 p-6 shadow-xl shadow-black/25 backdrop-blur-xl">
              <p className="text-xs font-medium uppercase tracking-[0.22em] text-zinc-500">Access</p>
              <p className="mt-4 text-2xl font-semibold tracking-tight text-white">No sign-in required</p>
              <p className="mt-3 text-sm leading-6 text-zinc-400">
                Auth is paused for now. Jump straight into the console — BITS gate can come back later.
              </p>
            </div>
          </aside>
        </section>
      </div>
    </main>
  );
}
