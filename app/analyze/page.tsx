"use client";

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Building2,
  CheckCircle2,
  ClipboardList,
  FileText,
  GraduationCap,
  History,
  Loader2,
  MapPin,
  Sparkles,
  Target,
  Upload,
  UserRound,
} from "lucide-react";
import { ScoreRing } from "@/components/score-ring";
import { UsageBadge } from "@/components/usage-badge";
import { ResultPanels } from "@/components/result-panels";
import type { AnalysisResult } from "@/lib/analysis";

interface AnalyzeResponse extends AnalysisResult {
  id: string;
  targetCompany?: string;
  targetRole?: string;
  intakeMode?: string;
  preAnalysis?: {
    roughMatchPercentage: number;
    totalMatched: number;
    totalMissing: number;
  };
}

type ResumeMode = "upload" | "paste" | "profile";

type StudentProfile = {
  fullName: string;
  degree: string;
  branch: string;
  campus: string;
  graduationYear: string;
  cgpa: string;
  courses: string;
  skills: string;
  projects: string;
  internships: string;
  achievements: string;
  links: string;
  preferredDomains: string;
};

const emptyProfile: StudentProfile = {
  fullName: "",
  degree: "BE",
  branch: "",
  campus: "Pilani",
  graduationYear: "",
  cgpa: "",
  courses: "",
  skills: "",
  projects: "",
  internships: "",
  achievements: "",
  links: "",
  preferredDomains: "",
};

const intakeModes = [
  { id: "upload" as const, label: "Resume file", icon: Upload },
  { id: "paste" as const, label: "Resume text", icon: FileText },
  { id: "profile" as const, label: "No resume", icon: UserRound },
];

const MAX_RESUME_FILE_BYTES = 5 * 1024 * 1024;
const SUPPORTED_RESUME_EXTENSIONS = [".pdf", ".png", ".jpg", ".jpeg", ".bmp"];

function isSupportedResumeFile(file: File) {
  const name = file.name.toLowerCase();
  return SUPPORTED_RESUME_EXTENSIONS.some((extension) => name.endsWith(extension));
}

export default function AnalyzePage() {
  const router = useRouter();
  const [targetCompany, setTargetCompany] = useState("");
  const [targetRole, setTargetRole] = useState("");
  const [jdText, setJdText] = useState("");
  const [resumeText, setResumeText] = useState("");
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [resumeFilename, setResumeFilename] = useState<string | null>(null);
  const [resumeMode, setResumeMode] = useState<ResumeMode>("upload");
  const [profile, setProfile] = useState<StudentProfile>(emptyProfile);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [usage, setUsage] = useState<{ used: number; limit: number } | null>(null);
  const [dragging, setDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const updateProfile = (key: keyof StudentProfile, value: string) => {
    setProfile((current) => ({ ...current, [key]: value }));
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (!file) return;
    if (file.size > MAX_RESUME_FILE_BYTES) {
      setError("Keep the resume file under 5MB.");
      return;
    }
    if (isSupportedResumeFile(file)) {
      setResumeFile(file);
      setResumeFilename(file.name);
      setError(null);
    } else {
      setError("Drop a PDF, PNG, JPG, JPEG, or BMP resume.");
    }
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (file.size > MAX_RESUME_FILE_BYTES) {
        setError("Keep the resume file under 5MB.");
        return;
      }
      if (!isSupportedResumeFile(file)) {
        setError("Upload a PDF, PNG, JPG, JPEG, or BMP resume.");
        return;
      }
      setResumeFile(file);
      setResumeFilename(file.name);
      setError(null);
    }
  };

  const profileReady = [profile.degree, profile.branch, profile.skills, profile.projects || profile.courses]
    .filter((value) => value.trim().length > 0).length >= 4;
  const hasTarget = targetCompany.trim().length > 1 && targetRole.trim().length > 1;
  const hasBrief = jdText.trim().length >= 50 || hasTarget;
  const hasResumeInput =
    resumeMode === "profile"
      ? profileReady
      : resumeMode === "upload"
        ? !!resumeFile
        : resumeText.trim().length >= 50;
  const canSubmit = hasBrief && hasResumeInput && !loading;

  const targetCompleteness = Math.round(([targetCompany, targetRole, jdText].filter((value) => value.trim().length > 0).length / 3) * 100);
  const inputCompleteness = resumeMode === "profile"
    ? Math.min(100, Math.round(([profile.branch, profile.cgpa, profile.skills, profile.projects, profile.courses, profile.links].filter((value) => value.trim().length > 0).length / 6) * 100))
    : hasResumeInput ? 100 : 35;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setError(null);
    setResult(null);
    setLoading(true);

    try {
      const formData = new FormData();
      formData.append("targetCompany", targetCompany);
      formData.append("targetRole", targetRole);
      formData.append("jd", jdText);
      formData.append("intakeMode", resumeMode === "profile" ? "profile" : resumeMode);
      formData.append("studentContext", JSON.stringify(profile));

      if (resumeMode === "upload" && resumeFile) {
        formData.append("resumeFile", resumeFile);
        formData.append("resumeFilename", resumeFile.name);
      }
      if (resumeMode === "paste") {
        formData.append("resumeText", resumeText);
      }

      const res = await fetch("/api/analyze", { method: "POST", body: formData });
      const data = await res.json();

      if (!res.ok) {
        setError(data.error || "Analysis failed.");
        if (res.status === 429 && usage) setUsage({ used: usage.limit, limit: usage.limit });
        return;
      }

      setResult(data);
      setUsage((current) => current ? { used: current.used + 1, limit: current.limit } : { used: 1, limit: 5 });
    } catch {
      setError("Network error. Try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen overflow-hidden bg-[#07080d] text-zinc-100">
      <div className="app-grid-bg fixed inset-0 -z-10" />
      <div className="mx-auto flex min-h-screen w-full max-w-[1500px] flex-col px-4 py-4 sm:px-6 lg:px-8">
        <header className="mb-5 flex items-center justify-between rounded-[28px] border border-white/10 bg-zinc-950/78 px-4 py-3 shadow-2xl shadow-black/30 backdrop-blur-xl">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => router.push("/")}
              className="grid h-10 w-10 place-items-center rounded-2xl border border-white/10 bg-white/[0.03] text-zinc-400 transition-all duration-150 hover:border-white/20 hover:text-white"
              aria-label="Back"
            >
              <ArrowLeft className="h-4 w-4" />
            </button>
            <div>
              <div className="flex items-center gap-2">
                <span className="grid h-8 w-8 place-items-center rounded-xl bg-[#e1ff5f] text-xs font-black text-zinc-950">GP</span>
                <h1 className="text-base font-semibold tracking-tight text-white sm:text-lg">GradPath</h1>
              </div>
              <p className="mt-0.5 text-xs text-zinc-500">BITS placement readiness console</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {usage && <UsageBadge used={usage.used} limit={usage.limit} />}
            <button
              type="button"
              onClick={() => router.push("/history")}
              className="hidden items-center gap-2 rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-2 text-sm text-zinc-300 transition-all duration-150 hover:border-[#e1ff5f]/40 hover:text-white sm:flex"
            >
              <History className="h-4 w-4" />
              History
            </button>
          </div>
        </header>

        <form onSubmit={handleSubmit} className="grid flex-1 gap-5 xl:grid-cols-[330px_minmax(0,1fr)_360px]">
          <aside className="space-y-4">
            <section className="rounded-[30px] border border-white/10 bg-zinc-950/78 p-5 shadow-xl shadow-black/25 backdrop-blur-xl">
              <div className="mb-5 flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.22em] text-[#e1ff5f]">Target</p>
                  <h2 className="mt-1 text-2xl font-semibold tracking-tight text-white">Company path</h2>
                </div>
                <Target className="h-6 w-6 text-[#e1ff5f]" />
              </div>

              <label className="group mb-3 block">
                <span className="mb-2 flex items-center gap-2 text-xs font-medium text-zinc-400">
                  <Building2 className="h-3.5 w-3.5" />
                  Company
                </span>
                <input
                  value={targetCompany}
                  onChange={(e) => setTargetCompany(e.target.value)}
                  placeholder="Google, Microsoft, DE Shaw"
                  className="w-full rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-white outline-none transition-all duration-150 placeholder:text-zinc-600 focus:border-[#e1ff5f]/50 focus:ring-4 focus:ring-[#e1ff5f]/10"
                />
              </label>

              <label className="group mb-3 block">
                <span className="mb-2 flex items-center gap-2 text-xs font-medium text-zinc-400">
                  <Target className="h-3.5 w-3.5" />
                  Role
                </span>
                <input
                  value={targetRole}
                  onChange={(e) => setTargetRole(e.target.value)}
                  placeholder="SDE Intern, Quant, ML Engineer"
                  className="w-full rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-white outline-none transition-all duration-150 placeholder:text-zinc-600 focus:border-[#e1ff5f]/50 focus:ring-4 focus:ring-[#e1ff5f]/10"
                />
              </label>

              <div className="mb-3 grid grid-cols-2 gap-3">
                <label className="block">
                  <span className="mb-2 flex items-center gap-2 text-xs font-medium text-zinc-400">
                    <GraduationCap className="h-3.5 w-3.5" />
                    Program
                  </span>
                  <select
                    value={profile.degree}
                    onChange={(e) => updateProfile("degree", e.target.value)}
                    className="w-full rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-white outline-none transition-all duration-150 focus:border-[#e1ff5f]/50 focus:ring-4 focus:ring-[#e1ff5f]/10"
                  >
                    <option value="BE">BE</option>
                    <option value="MTech">MTech</option>
                  </select>
                </label>

                <label className="block">
                  <span className="mb-2 flex items-center gap-2 text-xs font-medium text-zinc-400">
                    <MapPin className="h-3.5 w-3.5" />
                    Campus
                  </span>
                  <select
                    value={profile.campus}
                    onChange={(e) => updateProfile("campus", e.target.value)}
                    className="w-full rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-white outline-none transition-all duration-150 focus:border-[#e1ff5f]/50 focus:ring-4 focus:ring-[#e1ff5f]/10"
                  >
                    <option value="Pilani">Pilani</option>
                    <option value="Goa">Goa</option>
                    <option value="Hyderabad">Hyderabad</option>
                  </select>
                </label>
              </div>

              <label className="block">
                <span className="mb-2 flex items-center gap-2 text-xs font-medium text-zinc-400">
                  <GraduationCap className="h-3.5 w-3.5" />
                  Season
                </span>
                <select
                  value={profile.preferredDomains}
                  onChange={(e) => updateProfile("preferredDomains", e.target.value)}
                  className="w-full rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-white outline-none transition-all duration-150 focus:border-[#e1ff5f]/50 focus:ring-4 focus:ring-[#e1ff5f]/10"
                >
                  <option value="">Select focus</option>
                  <option value="Internship season">Internship season</option>
                  <option value="Placement season">Placement season</option>
                  <option value="Practice School conversion">Practice School conversion</option>
                </select>
              </label>
            </section>

            <section className="rounded-[30px] border border-white/10 bg-zinc-950/78 p-5 shadow-xl shadow-black/25 backdrop-blur-xl">
              <p className="text-xs font-medium uppercase tracking-[0.22em] text-zinc-500">Readiness feed</p>
              <div className="mt-5 space-y-4">
                <ProgressRow label="Target lock" value={targetCompleteness} tone="lime" />
                <ProgressRow label="Student signal" value={inputCompleteness} tone="cyan" />
                <ProgressRow label="Brief depth" value={Math.min(100, Math.max(24, Math.round((jdText.length / 800) * 100)))} tone="amber" />
              </div>
            </section>
          </aside>

          <section className="min-w-0 rounded-[34px] border border-white/10 bg-zinc-950/78 p-4 shadow-2xl shadow-black/35 backdrop-blur-xl sm:p-5">
            <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className="text-xs font-medium uppercase tracking-[0.22em] text-zinc-500">Workspace</p>
                <h2 className="mt-1 text-3xl font-semibold tracking-tight text-white">Build the signal pack</h2>
              </div>
              <div className="grid grid-cols-3 gap-1 rounded-2xl border border-white/10 bg-black/30 p-1">
                {intakeModes.map((mode) => {
                  const Icon = mode.icon;
                  return (
                    <button
                      key={mode.id}
                      type="button"
                      onClick={() => setResumeMode(mode.id)}
                      className={`flex items-center justify-center gap-2 rounded-xl px-3 py-2 text-xs font-medium transition-all duration-150 ${
                        resumeMode === mode.id
                          ? "bg-white text-zinc-950 shadow-lg shadow-white/10"
                          : "text-zinc-400 hover:bg-white/[0.04] hover:text-white"
                      }`}
                    >
                      <Icon className="h-3.5 w-3.5" />
                      <span className="hidden sm:inline">{mode.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="grid gap-4 lg:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)]">
              <section className="rounded-[26px] border border-white/10 bg-black/24 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <label className="text-sm font-medium text-zinc-200">Role brief</label>
                  <span className="rounded-full border border-white/10 px-2 py-1 text-[11px] text-zinc-500">{jdText.length} chars</span>
                </div>
                <textarea
                  value={jdText}
                  onChange={(e) => setJdText(e.target.value)}
                  placeholder="Paste the JD. Company + role is enough for a first pass."
                  className="min-h-[430px] w-full resize-none rounded-[22px] border border-white/10 bg-[#090a10] p-4 text-sm leading-6 text-zinc-100 outline-none transition-all duration-150 placeholder:text-zinc-600 focus:border-[#e1ff5f]/50 focus:ring-4 focus:ring-[#e1ff5f]/10"
                />
              </section>

              <section className="rounded-[26px] border border-white/10 bg-black/24 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <label className="text-sm font-medium text-zinc-200">
                    {resumeMode === "profile" ? "Student profile" : "Resume source"}
                  </label>
                  {hasResumeInput ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-400/10 px-2 py-1 text-[11px] text-emerald-300">
                      <CheckCircle2 className="h-3 w-3" />
                      Ready
                    </span>
                  ) : (
                    <span className="rounded-full border border-white/10 px-2 py-1 text-[11px] text-zinc-500">Waiting</span>
                  )}
                </div>

                {resumeMode === "upload" && (
                  <div
                    onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                    onDragLeave={() => setDragging(false)}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                    className={`grid min-h-[430px] cursor-pointer place-items-center rounded-[22px] border border-dashed p-6 text-center transition-all duration-150 ${
                      dragging
                        ? "border-[#e1ff5f] bg-[#e1ff5f]/8"
                        : "border-white/15 bg-[#090a10] hover:border-[#e1ff5f]/50 hover:bg-white/[0.03]"
                    }`}
                  >
                    {resumeFilename ? (
                      <div>
                        <div className="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-3xl bg-[#e1ff5f] text-zinc-950">
                          <FileText className="h-7 w-7" />
                        </div>
                        <div className="text-sm font-medium text-white">{resumeFilename}</div>
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); setResumeFile(null); setResumeFilename(null); }}
                          className="mt-3 text-xs text-rose-300 transition-colors duration-150 hover:text-rose-200"
                        >
                          Remove file
                        </button>
                      </div>
                    ) : (
                      <div>
                        <div className="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-3xl border border-white/10 bg-white/[0.03] text-[#e1ff5f]">
                          <Upload className="h-7 w-7" />
                        </div>
                        <div className="text-sm font-medium text-white">Drop PDF or image resume</div>
                        <div className="mt-1 text-xs text-zinc-500">PDF text parser + open-source OCR, max 5MB</div>
                      </div>
                    )}
                    <input ref={fileInputRef} type="file" accept=".pdf,.png,.jpg,.jpeg,.bmp" onChange={handleFileSelect} className="hidden" />
                  </div>
                )}

                {resumeMode === "paste" && (
                  <textarea
                    value={resumeText}
                    onChange={(e) => setResumeText(e.target.value)}
                    placeholder="Paste resume text."
                    className="min-h-[430px] w-full resize-none rounded-[22px] border border-white/10 bg-[#090a10] p-4 text-sm leading-6 text-zinc-100 outline-none transition-all duration-150 placeholder:text-zinc-600 focus:border-[#e1ff5f]/50 focus:ring-4 focus:ring-[#e1ff5f]/10"
                  />
                )}

                {resumeMode === "profile" && (
                  <div className="max-h-[430px] overflow-y-auto pr-1">
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                      <Field value={profile.fullName} onChange={(value) => updateProfile("fullName", value)} placeholder="Name" />
                      <label className="block">
                        <span className="sr-only">Degree</span>
                        <select value={profile.degree} onChange={(e) => updateProfile("degree", e.target.value)} className="field-control">
                          <option value="BE">BE</option>
                          <option value="MTech">MTech</option>
                        </select>
                      </label>
                      <Field value={profile.branch} onChange={(value) => updateProfile("branch", value)} placeholder="Branch" />
                      <label className="block">
                        <span className="sr-only">Campus</span>
                        <select value={profile.campus} onChange={(e) => updateProfile("campus", e.target.value)} className="field-control">
                          <option value="Pilani">Pilani</option>
                          <option value="Goa">Goa</option>
                          <option value="Hyderabad">Hyderabad</option>
                        </select>
                      </label>
                      <Field value={profile.graduationYear} onChange={(value) => updateProfile("graduationYear", value)} placeholder="Graduation year" />
                      <Field value={profile.cgpa} onChange={(value) => updateProfile("cgpa", value)} placeholder="CGPA" />
                    </div>
                    <Textarea value={profile.skills} onChange={(value) => updateProfile("skills", value)} placeholder="Skills, tools, DSA comfort..." />
                    <Textarea value={profile.projects} onChange={(value) => updateProfile("projects", value)} placeholder="Projects, stack, outcome..." tall />
                    <Textarea value={profile.courses} onChange={(value) => updateProfile("courses", value)} placeholder="Relevant courses, labs, electives..." />
                    <Textarea value={profile.internships} onChange={(value) => updateProfile("internships", value)} placeholder="Internships, PS, PORs, freelance work..." />
                    <Textarea value={profile.achievements} onChange={(value) => updateProfile("achievements", value)} placeholder="Achievements, hackathons, competitions..." />
                    <Field value={profile.links} onChange={(value) => updateProfile("links", value)} placeholder="GitHub, LinkedIn, portfolio links" />
                  </div>
                )}
              </section>
            </div>
          </section>

          <aside className="space-y-4">
            <section className="rounded-[30px] border border-white/10 bg-zinc-950/78 p-5 shadow-xl shadow-black/25 backdrop-blur-xl">
              <div className="mb-5 flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.22em] text-zinc-500">Launch</p>
                  <h2 className="mt-1 text-2xl font-semibold tracking-tight text-white">Readiness run</h2>
                </div>
                <Sparkles className="h-6 w-6 text-[#e1ff5f]" />
              </div>
              <button
                type="submit"
                disabled={!canSubmit}
                className="group flex w-full items-center justify-center gap-2 rounded-2xl bg-[#e1ff5f] px-5 py-4 text-sm font-black text-zinc-950 shadow-lg shadow-[#e1ff5f]/10 transition-all duration-150 hover:scale-[1.01] hover:bg-[#f0ff99] disabled:scale-100 disabled:cursor-not-allowed disabled:bg-zinc-800 disabled:text-zinc-500 disabled:shadow-none"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4 transition-transform duration-150 group-hover:rotate-12" />}
                {loading ? "Running analysis" : "Generate plan"}
              </button>
              {error && (
                <div className="mt-4 rounded-2xl border border-rose-400/20 bg-rose-400/10 p-3 text-sm text-rose-200">
                  {error}
                </div>
              )}
            </section>

            <section className="rounded-[30px] border border-white/10 bg-zinc-950/78 p-5 shadow-xl shadow-black/25 backdrop-blur-xl">
              <p className="text-xs font-medium uppercase tracking-[0.22em] text-zinc-500">Run order</p>
              <div className="mt-5 space-y-3">
                <Step active={hasTarget} label="Target locked" />
                <Step active={hasBrief} label="Brief available" />
                <Step active={hasResumeInput} label="Student signal ready" />
                <Step active={!!result} label="Plan generated" />
              </div>
            </section>

            {result && !loading && (
              <section className="rounded-[30px] border border-white/10 bg-zinc-950/78 p-5 shadow-xl shadow-black/25 backdrop-blur-xl">
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <p className="text-xs font-medium uppercase tracking-[0.22em] text-zinc-500">Score</p>
                    <h2 className="mt-1 text-2xl font-semibold tracking-tight text-white">Match pulse</h2>
                  </div>
                  <ScoreRing score={result.matchScore} compact />
                </div>
                {result.preAnalysis && (
                  <div className="grid grid-cols-3 gap-2">
                    <Metric label="Overlap" value={`${result.preAnalysis.roughMatchPercentage}%`} />
                    <Metric label="Matched" value={String(result.preAnalysis.totalMatched)} />
                    <Metric label="Missing" value={String(result.preAnalysis.totalMissing)} />
                  </div>
                )}
              </section>
            )}
          </aside>
        </form>

        {loading && (
          <div className="mt-5 grid gap-4 xl:grid-cols-[1fr_1fr_1fr]">
            <div className="h-28 rounded-[28px] border border-white/10 bg-white/[0.03] animate-pulse" />
            <div className="h-28 rounded-[28px] border border-white/10 bg-white/[0.03] animate-pulse" />
            <div className="h-28 rounded-[28px] border border-white/10 bg-white/[0.03] animate-pulse" />
          </div>
        )}

        {result && !loading && (
          <section className="mt-5 rounded-[34px] border border-white/10 bg-zinc-950/82 p-5 shadow-2xl shadow-black/35 backdrop-blur-xl">
            <div className="mb-5 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className="text-xs font-medium uppercase tracking-[0.22em] text-[#e1ff5f]">
                  {[result.targetCompany, result.targetRole].filter(Boolean).join(" / ") || "Readiness"}
                </p>
                <h2 className="mt-2 text-3xl font-semibold tracking-tight text-white">Actionable placement plan</h2>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-400">{result.summary}</p>
              </div>
              <div className="hidden lg:block">
                <ScoreRing score={result.matchScore} />
              </div>
            </div>
            <ResultPanels result={result} />
          </section>
        )}
      </div>
    </main>
  );
}

function ProgressRow({ label, value, tone }: { label: string; value: number; tone: "lime" | "cyan" | "amber" }) {
  const color = tone === "lime" ? "bg-[#e1ff5f]" : tone === "cyan" ? "bg-cyan-300" : "bg-amber-300";
  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-xs">
        <span className="text-zinc-400">{label}</span>
        <span className="font-medium text-zinc-200">{value}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-white/[0.06]">
        <div className={`h-full rounded-full ${color} transition-all duration-300`} style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

function Step({ active, label }: { active: boolean; label: string }) {
  return (
    <div className="flex items-center gap-3">
      <div className={`grid h-7 w-7 place-items-center rounded-full border transition-all duration-150 ${
        active ? "border-[#e1ff5f]/40 bg-[#e1ff5f]/12 text-[#e1ff5f]" : "border-white/10 bg-white/[0.03] text-zinc-600"
      }`}>
        {active ? <CheckCircle2 className="h-4 w-4" /> : <ClipboardList className="h-4 w-4" />}
      </div>
      <span className={active ? "text-sm text-zinc-200" : "text-sm text-zinc-500"}>{label}</span>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
      <div className="text-lg font-semibold text-white">{value}</div>
      <div className="mt-1 text-[11px] uppercase tracking-[0.16em] text-zinc-500">{label}</div>
    </div>
  );
}

function Field({ value, onChange, placeholder }: { value: string; onChange: (value: string) => void; placeholder: string }) {
  return (
    <label className="block">
      <span className="sr-only">{placeholder}</span>
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className="field-control" />
    </label>
  );
}

function Textarea({ value, onChange, placeholder, tall = false }: { value: string; onChange: (value: string) => void; placeholder: string; tall?: boolean }) {
  return (
    <label className="mt-3 block">
      <span className="sr-only">{placeholder}</span>
      <textarea value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className={`field-control resize-none ${tall ? "h-24" : "h-20"}`} />
    </label>
  );
}
