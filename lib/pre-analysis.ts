import { spawn } from "child_process";
import { writeFileSync, mkdtempSync, readFileSync, rmSync } from "fs";
import { join } from "path";
import { tmpdir } from "os";
import type { PreAnalysis } from "./analysis";

/**
 * Calls the Python pre-processor script to do deterministic keyword extraction,
 * skill matching, and rough overlap scoring BEFORE the LLM call.
 *
 * This reduces the LLM's job: it gets pre-extracted keywords + a rough score
 * so it can focus on semantic reasoning, project generation, and nuance.
 *
 * Falls back gracefully — if Python isn't available, we do a minimal
 * keyword extraction in JS and proceed.
 */
export async function runPreAnalysis(jdText: string, resumeText: string): Promise<PreAnalysis> {
  try {
    const result = await callPython(jdText, resumeText);
    return result;
  } catch (err) {
    console.warn("Python pre-analysis failed, using JS fallback:", err);
    return jsFallback(jdText, resumeText);
  }
}

async function callPython(jdText: string, resumeText: string): Promise<PreAnalysis> {
  return new Promise((resolve, reject) => {
    const scriptPath = join(process.cwd(), "scripts", "pre_analyze.py");
    const input = JSON.stringify({ jd_text: jdText, resume_text: resumeText });
    // We pass input via a temp file to avoid stdin encoding issues on Windows
    const tmpDir = mkdtempSync(join(tmpdir(), "preanalyze-"));
    const inputPath = join(tmpDir, "input.json");
    const outputPath = join(tmpDir, "output.json");
    writeFileSync(inputPath, input, "utf-8");

    // Try python, python3, and py in order
    const py = process.platform === "win32" ? "python" : "python3";

    const child = spawn(
      py,
      [scriptPath, "--jd-file", inputPath, "--resume-file", inputPath, "-o", outputPath],
      { stdio: ["ignore", "pipe", "pipe"] },
    );

    // Wait — we passed the same file for both jd and resume. That's wrong.
    // Instead, let's use stdin approach with a wrapper.
    child.kill();

    // Restart with proper approach: separate files
    const jdPath = join(tmpDir, "jd.txt");
    const resumePath = join(tmpDir, "resume.txt");
    writeFileSync(jdPath, jdText, "utf-8");
    writeFileSync(resumePath, resumeText, "utf-8");

    const child2 = spawn(
      py,
      [scriptPath, "--jd-file", jdPath, "--resume-file", resumePath, "-o", outputPath],
      { stdio: ["ignore", "pipe", "pipe"] },
    );

    let stderr = "";
    child2.stderr.on("data", (d) => { stderr += d.toString(); });

    child2.on("close", (code) => {
      try {
        if (code !== 0) {
          reject(new Error(`Python exited ${code}: ${stderr}`));
          return;
        }
        const output = readFileSync(outputPath, "utf-8");
        const result = JSON.parse(output) as PreAnalysis;
        // Validate
        if (!result || typeof result.rough_match_percentage !== "number") {
          reject(new Error("Invalid pre-analysis output"));
          return;
        }
        resolve(result);
      } catch (e) {
        reject(e);
      } finally {
        rmSync(tmpDir, { recursive: true, force: true });
      }
    });

    child2.on("error", (e) => {
      rmSync(tmpDir, { recursive: true, force: true });
      reject(e);
    });
  });
}

// ── JS Fallback (minimal) ───────────────────────────────────────

const SKILL_LIST = [
  "python", "javascript", "typescript", "java", "go", "rust", "c++", "c#",
  "react", "next.js", "vue", "angular", "node.js", "express", "django",
  "flask", "fastapi", "postgresql", "mysql", "mongodb", "redis", "docker",
  "kubernetes", "aws", "gcp", "azure", "graphql", "rest", "grpc",
  "machine learning", "deep learning", "pytorch", "tensorflow", "nlp",
  "ci/cd", "git", "linux", "tailwind", "prisma", "drizzle", "auth.js",
  "vercel", "supabase", "firebase", "neon", "llm", "rag", "openai",
];

function jsFallback(jdText: string, resumeText: string): PreAnalysis {
  const jdLower = jdText.toLowerCase();
  const resumeLower = resumeText.toLowerCase();

  const jdSkills: Record<string, number> = {};
  const resumeSkills: Record<string, number> = {};

  for (const skill of SKILL_LIST) {
    const jdCount = jdLower.split(skill).length - 1;
    const resumeCount = resumeLower.split(skill).length - 1;
    if (jdCount > 0) jdSkills[skill] = jdCount;
    if (resumeCount > 0) resumeSkills[skill] = resumeCount;
  }

  const jdSet = new Set(Object.keys(jdSkills));
  const resumeSet = new Set(Object.keys(resumeSkills));
  const matched = [...jdSet].filter((s) => resumeSet.has(s)).sort();
  const missing = [...jdSet].filter((s) => !resumeSet.has(s)).sort();

  const totalWeight = Object.values(jdSkills).reduce((a, b) => a + b, 0);
  const matchedWeight = matched.reduce((sum, s) => sum + jdSkills[s], 0);
  const roughPct = totalWeight ? Math.round((matchedWeight / totalWeight) * 1000) / 10 : 0;

  const jdKeywordScores: Record<string, number> = {};
  for (const [skill, count] of Object.entries(jdSkills).sort((a, b) => b[1] - a[1])) {
    jdKeywordScores[skill] = Math.round((count / (totalWeight || 1)) * 10000) / 10000;
  }

  return {
    jd_keywords: Object.keys(jdSkills),
    resume_keywords: Object.keys(resumeSkills),
    matched_keywords: matched,
    missing_keywords: missing,
    jd_keyword_scores: jdKeywordScores,
    rough_match_percentage: roughPct,
    resume_sections_found: [],
    jd_sections_found: [],
    total_jd_keywords: jdSet.size,
    total_resume_keywords: resumeSet.size,
    total_matched: matched.length,
    total_missing: missing.length,
  };
}
