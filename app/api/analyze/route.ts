import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/auth";
import { db } from "@/db";
import { analyses, studentProfiles } from "@/db/schema";
import { extractResumeText, PdfError } from "@/lib/pdf";
import { runPreAnalysis } from "@/lib/pre-analysis";
import { analysisResultSchema, buildUserPrompt, SYSTEM_PROMPT, type PreAnalysis } from "@/lib/analysis";
import { resolveUserId } from "@/lib/guest-user";
import { sql, gte, and, eq } from "drizzle-orm";
import { generateObject } from "ai";
import { createOpenAI } from "@ai-sdk/openai";

export const runtime = "nodejs";
export const maxDuration = 90;

const DEFAULT_OPENROUTER_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free";
const DEFAULT_OPENROUTER_FALLBACK_MODEL = "openrouter/free";

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

function getLLMClient() {
  return createOpenAI({
    baseURL: "https://openrouter.ai/api/v1",
    apiKey: process.env.OPENROUTER_API_KEY!,
    headers: {
      "HTTP-Referer": process.env.OPENROUTER_SITE_URL ?? "http://localhost:3000",
      "X-OpenRouter-Title": process.env.OPENROUTER_APP_NAME ?? "GradPath",
    },
    compatibility: "compatible",
  });
}

async function getDailyLimit(userId: string): Promise<{ used: number; limit: number }> {
  const limit = parseInt(process.env.DAILY_LIMIT ?? "5", 10);
  const todayStart = new Date();
  todayStart.setUTCHours(0, 0, 0, 0);

  const rows = await db
    .select({ count: sql<number>`count(*)::int` })
    .from(analyses)
    .where(and(eq(analyses.userId, userId), gte(analyses.createdAt, todayStart)));

  return { used: rows[0]?.count ?? 0, limit };
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
  ].filter(Boolean).join("\n");
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
  // Auth temporarily open: use session user when present, else shared guest.
  const session = await auth().catch(() => null);
  const userId = await resolveUserId(session?.user?.id);

  // Only enforce daily limit for real signed-in users (not the shared guest).
  if (session?.user?.id) {
    const { used, limit } = await getDailyLimit(userId);
    if (used >= limit) {
      return NextResponse.json(
        { error: `Daily limit reached (${used}/${limit}). Try again tomorrow.` },
        { status: 429 },
      );
    }
  }

  let jdText = "";
  let resumeText = "";
  let resumeFilename: string | null = null;
  let targetCompany = "";
  let targetRole = "";
  let intakeMode = "resume";
  let studentContext: StudentContext = {};

  const contentType = req.headers.get("content-type") ?? "";

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
        return NextResponse.json({ error: "Add a job description or enter both target company and role." }, { status: 400 });
      }
      jdText = buildTargetBrief(targetCompany, targetRole);
    }

    if (intakeMode === "profile") {
      resumeText = buildProfileText(studentContext);
      resumeFilename = "student-profile";
    } else if (resumeFile) {
      try {
        const buffer = await resumeFile.arrayBuffer();
        const result = await extractResumeText(buffer, resumeFile.name);
        resumeText = result.text;
        resumeFilename = resumeFile.name;
      } catch (err) {
        const message = err instanceof PdfError ? err.message : "Failed to parse resume file.";
        return NextResponse.json({ error: message }, { status: 400 });
      }
    } else if (resumePaste) {
      resumeText = resumePaste;
      intakeMode = "paste";
    } else {
      return NextResponse.json({ error: "Upload a resume, paste resume text, or choose the no-resume guided profile." }, { status: 400 });
    }
  } else {
    const body = await req.json();
    jdText = body.jdText?.trim() ?? "";
    targetCompany = body.targetCompany?.trim() ?? "";
    targetRole = body.targetRole?.trim() ?? "";
    intakeMode = body.intakeMode?.trim() ?? "resume";
    studentContext = body.studentContext ?? {};
    resumeText = body.resumeText?.trim() ?? "";

    if (jdText.length < 50) {
      if (!targetCompany || !targetRole) {
        return NextResponse.json({ error: "Add a job description or enter both target company and role." }, { status: 400 });
      }
      jdText = buildTargetBrief(targetCompany, targetRole);
    }
    if (intakeMode === "profile") resumeText = buildProfileText(studentContext);
  }

  if (!isSupportedDegree(studentContext.degree)) {
    return NextResponse.json({ error: "This tool is restricted to BITS BE and MTech students. Select your program to continue." }, { status: 403 });
  }

  if (intakeMode === "profile") {
    const enoughProfile = [studentContext.degree, studentContext.branch, studentContext.skills, studentContext.projects, studentContext.courses]
      .filter((value) => value && value.trim().length > 0).length >= 3;
    if (!enoughProfile || resumeText.length < 80) {
      return NextResponse.json({ error: "Add degree, branch, skills, and at least one project/course detail for the guided profile." }, { status: 400 });
    }
  } else if (resumeText.length < 50) {
    return NextResponse.json({ error: "Resume text is too short (min 50 chars)." }, { status: 400 });
  }

  let pre: PreAnalysis;
  try {
    pre = await runPreAnalysis(jdText, resumeText);
  } catch (err) {
    console.error("Pre-analysis error:", err);
    pre = {
      jd_keywords: [], resume_keywords: [], matched_keywords: [], missing_keywords: [],
      jd_keyword_scores: {}, rough_match_percentage: 0,
      resume_sections_found: [], jd_sections_found: [],
      total_jd_keywords: 0, total_resume_keywords: 0, total_matched: 0, total_missing: 0,
    };
  }

  if (!process.env.OPENROUTER_API_KEY) {
    return NextResponse.json({ error: "OPENROUTER_API_KEY is not configured." }, { status: 500 });
  }

  const client = getLLMClient();
  const userPrompt = buildUserPrompt(jdText, resumeText, pre, {
    company: targetCompany,
    role: targetRole,
    intakeMode,
  });

  let result;
  try {
    result = await generateObject({
      model: client(process.env.OPENROUTER_MODEL ?? DEFAULT_OPENROUTER_MODEL),
      system: SYSTEM_PROMPT,
      prompt: userPrompt,
      schema: analysisResultSchema,
      temperature: 0.3,
      maxTokens: 3200,
    });
  } catch (primaryErr) {
    console.error("Primary LLM failed, trying fallback:", primaryErr);
    try {
      result = await generateObject({
        model: client(process.env.OPENROUTER_FALLBACK_MODEL ?? DEFAULT_OPENROUTER_FALLBACK_MODEL),
        system: SYSTEM_PROMPT,
        prompt: userPrompt,
        schema: analysisResultSchema,
        temperature: 0.3,
        maxTokens: 3200,
      });
    } catch (fallbackErr) {
      console.error("Fallback LLM also failed:", fallbackErr);
      return NextResponse.json({ error: "AI analysis failed. Please try again." }, { status: 502 });
    }
  }

  const analysis = result.object;

  try {
    await saveStudentProfile(userId, studentContext);
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
    console.error("DB insert error:", err);
    return NextResponse.json(
      { error: "Analysis complete but failed to save. Result not stored." },
      { status: 500 },
    );
  }
}
