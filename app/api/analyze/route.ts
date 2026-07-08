import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db";
import { analyses, studentProfiles } from "@/db/schema";
import { extractResumeText, PdfError } from "@/lib/pdf";
import { runPreAnalysis } from "@/lib/pre-analysis";
import { type PreAnalysis } from "@/lib/analysis";
import { ensureGuestUser } from "@/lib/guest-user";
import { runLlmAnalysis } from "@/lib/run-llm";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 60;

type StudentContext = {
  fullName?: string;
  degree?: string;
  branch?: string;
  campus?: string;
  graduationYear?: string;
  cgpa?: string;
  courses?: string;
  skills?: string;
  projects?: string;
  internships?: string;
  achievements?: string;
  links?: string;
  preferredDomains?: string;
};

function jsonError(error: string, status: number, extra?: Record<string, unknown>) {
  return NextResponse.json({ error, ...extra }, { status });
}

function parseContext(raw: FormDataEntryValue | null): StudentContext {
  if (typeof raw !== "string" || !raw.trim()) return {};
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function textLine(label: string, value?: string) {
  const trimmed = value?.trim();
  return trimmed ? `${label}: ${trimmed}` : null;
}

function buildProfileText(context: StudentContext) {
  return [
    textLine("Name", context.fullName),
    textLine("Degree", context.degree),
    textLine("Branch", context.branch),
    textLine("Campus", context.campus),
    textLine("Graduation year", context.graduationYear),
    textLine("CGPA", context.cgpa),
    textLine("Relevant courses", context.courses),
    textLine("Skills", context.skills),
    textLine("Projects", context.projects),
    textLine("Internships or work experience", context.internships),
    textLine("Achievements", context.achievements),
    textLine("Links", context.links),
    textLine("Preferred domains", context.preferredDomains),
  ]
    .filter(Boolean)
    .join("\n");
}

function buildTargetBrief(company: string, role: string) {
  return [
    `Target company: ${company}`,
    `Target role: ${role}`,
    "Analyze readiness for this company-role target using typical campus placement expectations, technical screening, resume shortlisting, projects, coursework, and interview preparation.",
  ].join("\n");
}

function isSupportedDegree(degree?: string) {
  const normalized = degree?.trim().toLowerCase();
  return normalized === "be" || normalized === "b.e." || normalized === "mtech" || normalized === "m.tech";
}

async function saveStudentProfile(userId: string, context: StudentContext) {
  if (!Object.values(context).some((value) => typeof value === "string" && value.trim())) return;
  await db
    .insert(studentProfiles)
    .values({
      userId,
      fullName: context.fullName || null,
      degree: context.degree || null,
      branch: context.branch || null,
      campus: context.campus || null,
      graduationYear: context.graduationYear ? Number.parseInt(context.graduationYear, 10) || null : null,
      cgpa: context.cgpa || null,
      courses: context.courses || null,
      skills: context.skills || null,
      projects: context.projects || null,
      internships: context.internships || null,
      achievements: context.achievements || null,
      links: context.links || null,
      preferredDomains: context.preferredDomains || null,
      updatedAt: new Date(),
    })
    .onConflictDoUpdate({
      target: studentProfiles.userId,
      set: {
        fullName: context.fullName || null,
        degree: context.degree || null,
        branch: context.branch || null,
        campus: context.campus || null,
        graduationYear: context.graduationYear ? Number.parseInt(context.graduationYear, 10) || null : null,
        cgpa: context.cgpa || null,
        courses: context.courses || null,
        skills: context.skills || null,
        projects: context.projects || null,
        internships: context.internships || null,
        achievements: context.achievements || null,
        links: context.links || null,
        preferredDomains: context.preferredDomains || null,
        updatedAt: new Date(),
      },
    });
}

export async function POST(req: NextRequest) {
  try {
    if (!process.env.OPENROUTER_API_KEY) {
      return jsonError("OPENROUTER_API_KEY is not configured on the server.", 500);
    }
    if (!process.env.DATABASE_URL) {
      return jsonError("DATABASE_URL is not configured on the server.", 500);
    }

    let userId: string;
    try {
      userId = await ensureGuestUser();
    } catch (err) {
      console.error("Guest user bootstrap failed:", err);
      return jsonError(
        `Database connection failed while creating guest user: ${err instanceof Error ? err.message : "unknown error"}`,
        500,
      );
    }

    let jdText = "";
    let resumeText = "";
    let resumeFilename: string | null = null;
    let targetCompany = "";
    let targetRole = "";
    let intakeMode = "resume";
    let studentContext: StudentContext = {};

    const contentType = req.headers.get("content-type") ?? "";

    try {
      if (contentType.includes("multipart/form-data")) {
        const formData = await req.formData();
        jdText = (formData.get("jd") as string)?.trim() ?? "";
        targetCompany = (formData.get("targetCompany") as string)?.trim() ?? "";
        targetRole = (formData.get("targetRole") as string)?.trim() ?? "";
        intakeMode = ((formData.get("intakeMode") as string)?.trim() || "resume").toLowerCase();
        resumeFilename = (formData.get("resumeFilename") as string) ?? null;
        studentContext = parseContext(formData.get("studentContext"));
        const resumeFile = formData.get("resumeFile") as File | null;
        const resumePaste = (formData.get("resumeText") as string)?.trim() ?? "";

        if (jdText.length < 50) {
          if (!targetCompany || !targetRole) {
            return jsonError("Add a job description or enter both target company and role.", 400);
          }
          jdText = buildTargetBrief(targetCompany, targetRole);
        }

        if (intakeMode === "profile") {
          resumeText = buildProfileText(studentContext);
          resumeFilename = "student-profile";
        } else if (resumeFile && typeof resumeFile === "object" && "arrayBuffer" in resumeFile) {
          try {
            const buffer = await resumeFile.arrayBuffer();
            const result = await extractResumeText(buffer, resumeFile.name || "resume.pdf");
            resumeText = result.text;
            resumeFilename = resumeFile.name || "resume.pdf";
          } catch (err) {
            const message = err instanceof PdfError ? err.message : "Failed to parse resume file.";
            return jsonError(message, 400);
          }
        } else if (resumePaste) {
          resumeText = resumePaste;
          intakeMode = "paste";
        } else {
          return jsonError("Upload a resume, paste resume text, or choose the no-resume guided profile.", 400);
        }
      } else {
        const body = await req.json();
        const asText = (value: unknown) => (typeof value === "string" ? value : value == null ? "" : String(value)).trim();
        jdText = asText(body.jdText ?? body.jd);
        targetCompany = asText(body.targetCompany);
        targetRole = asText(body.targetRole);
        intakeMode = asText(body.intakeMode) || "resume";
        studentContext = body.studentContext && typeof body.studentContext === "object" ? body.studentContext : {};
        resumeText = asText(body.resumeText);

        if (jdText.length < 50) {
          if (!targetCompany || !targetRole) {
            return jsonError("Add a job description or enter both target company and role.", 400);
          }
          jdText = buildTargetBrief(targetCompany, targetRole);
        }
        if (intakeMode === "profile") resumeText = buildProfileText(studentContext);
      }
    } catch (err) {
      console.error("Request parse error:", err);
      return jsonError(
        `Could not read request body: ${err instanceof Error ? err.message : "unknown error"}`,
        400,
      );
    }

    // Default program if omitted (open mode).
    if (!studentContext.degree) {
      studentContext = { ...studentContext, degree: "BE" };
    }

    if (!isSupportedDegree(studentContext.degree)) {
      return jsonError("Select program BE or MTech to continue.", 403);
    }

    if (intakeMode === "profile") {
      const enoughProfile = [studentContext.degree, studentContext.branch, studentContext.skills, studentContext.projects, studentContext.courses]
        .filter((value) => value && value.trim().length > 0).length >= 3;
      if (!enoughProfile || resumeText.length < 80) {
        return jsonError("Add degree, branch, skills, and at least one project/course detail for the guided profile.", 400);
      }
    } else if (resumeText.length < 50) {
      return jsonError("Resume text is too short (min 50 chars). If PDF upload failed, paste resume text instead.", 400);
    }

    let pre: PreAnalysis;
    try {
      pre = await runPreAnalysis(jdText, resumeText);
    } catch (err) {
      console.error("Pre-analysis error:", err);
      pre = {
        jd_keywords: [],
        resume_keywords: [],
        matched_keywords: [],
        missing_keywords: [],
        jd_keyword_scores: {},
        rough_match_percentage: 0,
        resume_sections_found: [],
        jd_sections_found: [],
        total_jd_keywords: 0,
        total_resume_keywords: 0,
        total_matched: 0,
        total_missing: 0,
      };
    }

    let analysis;
    try {
      analysis = await runLlmAnalysis(jdText, resumeText, pre, {
        company: targetCompany,
        role: targetRole,
        intakeMode,
        season:
          typeof studentContext.preferredDomains === "string"
            ? studentContext.preferredDomains
            : undefined,
      });
    } catch (err) {
      console.error("LLM analysis failed:", err);
      return jsonError(
        err instanceof Error ? err.message : "AI analysis failed. Please try again.",
        502,
      );
    }

    try {
      await saveStudentProfile(userId, studentContext);
    } catch (err) {
      console.warn("Profile save skipped:", err);
    }

    try {
      const [inserted] = await db
        .insert(analyses)
        .values({
          userId,
          targetCompany: targetCompany || null,
          targetRole: targetRole || null,
          intakeMode,
          jdText,
          resumeText,
          resumeFilename,
          studentContext,
          result: analysis,
          matchScore: analysis.matchScore,
        })
        .returning({ id: analyses.id });

      return NextResponse.json({
        id: inserted.id,
        targetCompany,
        targetRole,
        intakeMode,
        ...analysis,
        preAnalysis: {
          roughMatchPercentage: pre.rough_match_percentage,
          totalMatched: pre.total_matched,
          totalMissing: pre.total_missing,
        },
      });
    } catch (err) {
      console.error("DB insert error (returning unsaved analysis):", err);
      // Still return the analysis so the UI is usable if DB write fails.
      return NextResponse.json({
        id: "unsaved",
        targetCompany,
        targetRole,
        intakeMode,
        ...analysis,
        warning: "Analysis completed but was not saved to history.",
        preAnalysis: {
          roughMatchPercentage: pre.rough_match_percentage,
          totalMatched: pre.total_matched,
          totalMissing: pre.total_missing,
        },
      });
    }
  } catch (err) {
    console.error("Unhandled /api/analyze error:", err);
    return jsonError(
      `Server error: ${err instanceof Error ? err.message : "unknown failure"}`,
      500,
    );
  }
}

/** Lightweight health check for env wiring. */
export async function GET() {
  const checks = {
    ok: true,
    openrouter: Boolean(process.env.OPENROUTER_API_KEY),
    database: Boolean(process.env.DATABASE_URL),
    model: process.env.OPENROUTER_MODEL || "nvidia/nemotron-3-nano-30b-a3b:free",
  };

  if (!checks.openrouter || !checks.database) {
    return NextResponse.json({ ...checks, ok: false }, { status: 500 });
  }

  try {
    const guestId = await ensureGuestUser();
    return NextResponse.json({ ...checks, dbReachable: true, guestId });
  } catch (err) {
    return NextResponse.json(
      {
        ...checks,
        ok: false,
        dbReachable: false,
        error: err instanceof Error ? err.message : "db error",
      },
      { status: 500 },
    );
  }
}
