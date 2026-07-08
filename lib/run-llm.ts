import { createOpenAI } from "@ai-sdk/openai";
import { generateText } from "ai";
import {
  analysisResultSchema,
  buildUserPrompt,
  SYSTEM_PROMPT,
  type AnalysisResult,
  type PreAnalysis,
  type TargetContext,
} from "@/lib/analysis";

// Fast free default — full structured generateObject often fails/hangs on free models.
const DEFAULT_MODEL = "nvidia/nemotron-3-nano-30b-a3b:free";
const DEFAULT_FALLBACK = "openrouter/free";
const ATTEMPT_TIMEOUT_MS = 35_000;

function getClient() {
  const apiKey = process.env.OPENROUTER_API_KEY;
  if (!apiKey) {
    throw new Error("OPENROUTER_API_KEY is not configured.");
  }
  return createOpenAI({
    baseURL: "https://openrouter.ai/api/v1",
    apiKey,
    headers: {
      "HTTP-Referer": process.env.OPENROUTER_SITE_URL ?? "http://localhost:3000",
      "X-OpenRouter-Title": process.env.OPENROUTER_APP_NAME ?? "GradPath",
    },
    compatibility: "compatible",
  });
}

function modelsToTry(): string[] {
  const primary = process.env.OPENROUTER_MODEL?.trim() || DEFAULT_MODEL;
  const fallback = process.env.OPENROUTER_FALLBACK_MODEL?.trim() || DEFAULT_FALLBACK;
  // Cap retries — each model attempt is expensive and free tiers rate-limit hard.
  return [...new Set([primary, fallback])].slice(0, 2);
}

function extractJsonObject(raw: string): unknown {
  const fenced = raw.match(/```(?:json)?\s*([\s\S]*?)```/i);
  const candidate = (fenced?.[1] ?? raw).trim();
  const start = candidate.indexOf("{");
  const end = candidate.lastIndexOf("}");
  if (start === -1 || end === -1 || end <= start) {
    throw new Error("Model response did not contain a JSON object.");
  }
  return JSON.parse(candidate.slice(start, end + 1));
}

function softenAnalysis(value: unknown): AnalysisResult {
  const parsed = analysisResultSchema.safeParse(value);
  if (parsed.success) return parsed.data;

  const obj = (value && typeof value === "object" ? value : {}) as Record<string, unknown>;
  const asArray = (v: unknown) => (Array.isArray(v) ? v : []);
  const asString = (v: unknown, fallback = "") => (typeof v === "string" ? v : fallback);
  const asNumber = (v: unknown, fallback = 50) => {
    const n = typeof v === "number" ? v : Number(v);
    return Number.isFinite(n) ? Math.max(0, Math.min(100, Math.round(n))) : fallback;
  };

  const candidate = {
    matchScore: asNumber(obj.matchScore, 50),
    summary: asString(
      obj.summary,
      "Analysis completed with partial structure. Review the sections below and refine your resume/profile inputs for a stronger signal.",
    ).slice(0, 1200),
    strengths: asArray(obj.strengths).length
      ? asArray(obj.strengths)
      : [{ skill: "Baseline signal", evidence: "Provided resume/profile text was processed." }],
    gaps: asArray(obj.gaps).length
      ? asArray(obj.gaps)
      : [{ skill: "Role-specific depth", importance: "critical" as const, why: "Could not fully parse model gaps; re-run or paste a fuller JD." }],
    projects: asArray(obj.projects).length
      ? asArray(obj.projects)
      : [{
          title: "Targeted portfolio project",
          description: "Build a small project that maps to the biggest gap for this role.",
          skillsCovered: ["implementation"],
          effort: "1-2 weeks" as const,
        }],
    quickWins: asArray(obj.quickWins).length
      ? asArray(obj.quickWins).map(String)
      : ["Tighten resume bullets with metrics for the target role."],
    roadmap: asArray(obj.roadmap).length
      ? asArray(obj.roadmap)
      : [{ phase: "Week 1", timeline: "7 days", actions: ["Close one critical skill gap with a focused project."] }],
    resumeBullets: asArray(obj.resumeBullets).length
      ? asArray(obj.resumeBullets).map(String)
      : ["Built a project demonstrating core skills required by the target role."],
    prepTopics: asArray(obj.prepTopics).length
      ? asArray(obj.prepTopics)
      : [{ topic: "Core interviews for target role", priority: "high" as const, reason: "Highest leverage prep for campus screening." }],
    applicationStrategy: asArray(obj.applicationStrategy).length
      ? asArray(obj.applicationStrategy).map(String)
      : ["Apply with a role-aligned resume after closing one critical gap."],
  };

  return analysisResultSchema.parse(candidate);
}

const JSON_SYSTEM = `${SYSTEM_PROMPT}

OUTPUT FORMAT (mandatory):
Return ONLY one valid JSON object. No markdown fences, no preamble, no trailing commentary.
Required keys and shapes:
{
  "matchScore": 0-100 integer,
  "summary": string,
  "strengths": [{"skill": string, "evidence": string}],
  "gaps": [{"skill": string, "importance": "critical"|"nice-to-have", "why": string}],
  "projects": [{"title": string, "description": string, "skillsCovered": [string], "effort": "weekend"|"1-2 weeks"|"month"}],
  "quickWins": [string],
  "roadmap": [{"phase": string, "timeline": string, "actions": [string]}],
  "resumeBullets": [string],
  "prepTopics": [{"topic": string, "priority": "high"|"medium"|"low", "reason": string}],
  "applicationStrategy": [string]
}
Keep arrays non-empty. Keep summary under 700 characters.`;

async function tryGenerateTextJson(modelId: string, userPrompt: string): Promise<AnalysisResult> {
  const client = getClient();
  const { text } = await generateText({
    model: client(modelId),
    system: JSON_SYSTEM,
    prompt: userPrompt,
    temperature: 0.2,
    maxTokens: 2800,
    abortSignal: AbortSignal.timeout(ATTEMPT_TIMEOUT_MS),
    maxRetries: 0,
  });
  return softenAnalysis(extractJsonObject(text));
}

export async function runLlmAnalysis(
  jdText: string,
  resumeText: string,
  pre: PreAnalysis,
  target?: TargetContext,
): Promise<AnalysisResult> {
  const userPrompt = buildUserPrompt(jdText, resumeText, pre, target);
  const models = modelsToTry();
  const errors: string[] = [];

  for (const modelId of models) {
    try {
      return await tryGenerateTextJson(modelId, userPrompt);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      errors.push(`${modelId}: ${message}`);
      console.error("LLM attempt failed:", modelId, message);
    }
  }

  throw new Error(
    `AI analysis failed. ${errors.slice(-2).join(" | ")}`.slice(0, 600),
  );
}
