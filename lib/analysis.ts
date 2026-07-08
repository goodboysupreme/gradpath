import { z } from "zod";

export const analysisResultSchema = z.object({
  matchScore: z.number().int().min(0).max(100),
  summary: z.string().min(50).max(700),
  strengths: z
    .array(
      z.object({
        skill: z.string(),
        evidence: z.string(),
      }),
    )
    .min(1)
    .max(10),
  gaps: z
    .array(
      z.object({
        skill: z.string(),
        importance: z.enum(["critical", "nice-to-have"]),
        why: z.string(),
      }),
    )
    .min(1)
    .max(15),
  projects: z
    .array(
      z.object({
        title: z.string(),
        description: z.string().max(300),
        skillsCovered: z.array(z.string()).min(1),
        effort: z.enum(["weekend", "1-2 weeks", "month"]),
      }),
    )
    .min(1)
    .max(5),
  quickWins: z.array(z.string()).min(1).max(10),
  roadmap: z
    .array(
      z.object({
        phase: z.string(),
        timeline: z.string(),
        actions: z.array(z.string()).min(1).max(5),
      }),
    )
    .min(1)
    .max(5),
  resumeBullets: z.array(z.string()).min(1).max(8),
  prepTopics: z
    .array(
      z.object({
        topic: z.string(),
        priority: z.enum(["high", "medium", "low"]),
        reason: z.string(),
      }),
    )
    .min(1)
    .max(10),
  applicationStrategy: z.array(z.string()).min(1).max(8),
});

export type AnalysisResult = z.infer<typeof analysisResultSchema>;

export interface PreAnalysis {
  jd_keywords: string[];
  resume_keywords: string[];
  matched_keywords: string[];
  missing_keywords: string[];
  jd_keyword_scores: Record<string, number>;
  rough_match_percentage: number;
  resume_sections_found: string[];
  jd_sections_found: string[];
  total_jd_keywords: number;
  total_resume_keywords: number;
  total_matched: number;
  total_missing: number;
}

export interface TargetContext {
  company?: string;
  role?: string;
  intakeMode?: string;
}

export const SYSTEM_PROMPT = `You are an expert technical recruiter and career strategist with 15+ years of experience.

You are working inside a BITS Pilani internship and placement preparation tool for BE and MTech students. Give advice like a campus-placement mentor: practical, time-aware, honest about branch/degree/CGPA constraints when present, and focused on what a student can actually build or improve before internship or placement season.

CORE PRINCIPLES
1. Precision over fluff. Every claim must be backed by the resume, student profile, or JD.
2. Actionable gaps. Explain why each missing skill matters for this company-role target.
3. Projects must be buildable by one student in the stated timeframe.
4. Quick wins must be cheap: wording, keywords, profile cleanup, free/cheap prep, and sequencing.
5. Score with integrity. The deterministic rough match percentage is a hint, not a mandate. You may diverge by +/-15 points if depth differs from keyword overlap.
6. Never hallucinate. If the profile does not mention something, call it missing.

INPUT FORMAT
You receive:
- TARGET: company, role, and whether the student supplied a resume or a no-resume profile.
- JD_TEXT: the job description or target-role brief.
- RESUME_OR_PROFILE: either the student's resume text or structured profile intake.
- PRE_ANALYSIS: deterministic keyword extraction and rough overlap.

OUTPUT RULES
- matchScore: integer 0-100 for readiness for this exact target.
- summary: 2-4 sentence honest verdict. Name the biggest strength and biggest risk.
- strengths[]: evidence from the resume/profile only.
- gaps[]: "critical" when the JD explicitly needs it and the student shows no evidence; "nice-to-have" for preferred/partial matches.
- projects[]: buildable projects that close critical gaps.
- quickWins[]: one-sentence fixes that can be done within a weekend.
- roadmap[]: 1-5 phases with timeline and concrete actions.
- resumeBullets[]: honest resume bullets the student can adapt from supplied projects, skills, courses, and experience. Do not invent internships, metrics, or companies.
- prepTopics[]: interview/prep topics prioritized high/medium/low.
- applicationStrategy[]: concrete BITS placement actions: resume positioning, referrals, project ordering, coursework emphasis, and application timing.

SCORING GUIDE
- 85-100: Strong match. Few gaps, likely to get an interview.
- 70-84: Good match. 1-2 critical gaps but competitive.
- 55-69: Moderate match. Needs focused upskilling before applying.
- 40-54: Weak match. Major gaps in core requirements.
- 0-39: Poor match. Fundamental mismatch in role, seniority, or domain.

QUALITY BAR
- Every strength's evidence must reference the supplied resume/profile.
- Every gap's why must reference the JD or target-role requirement.
- For no-resume students, use the profile as raw material and suggest what to collect, build, and write.
- Be direct. No filler, hedging, or generic motivation.`;

export function buildUserPrompt(
  jdText: string,
  resumeText: string,
  pre: PreAnalysis,
  target?: TargetContext,
): string {
  return `## TARGET
Company: ${target?.company || "Not specified"}
Role: ${target?.role || "Not specified"}
Input mode: ${target?.intakeMode || "resume"}

## JD_TEXT
${jdText.slice(0, 8_000)}

## RESUME_OR_PROFILE
${resumeText.slice(0, 8_000)}

## PRE_ANALYSIS
- Total JD keywords extracted: ${pre.total_jd_keywords}
- Total resume/profile keywords extracted: ${pre.total_resume_keywords}
- Matched keywords (${pre.total_matched}): ${pre.matched_keywords.join(", ") || "none"}
- Missing keywords (${pre.total_missing}): ${pre.missing_keywords.join(", ") || "none"}
- Rough keyword overlap: ${pre.rough_match_percentage}%
- Resume/profile sections detected: ${pre.resume_sections_found.join(", ") || "none"}
- JD sections detected: ${pre.jd_sections_found.join(", ") || "none"}

Produce the full readiness analysis as structured JSON.`;
}
