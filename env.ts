import { existsSync, readFileSync } from "fs";
import { join } from "path";

/** Read .env.local if present (dev only) */
function tryEnvFile() {
  const envPath = join(process.cwd(), ".env.local");
  if (existsSync(envPath)) {
    const content = readFileSync(envPath, "utf-8");
    for (const line of content.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) continue;
      const eqIdx = trimmed.indexOf("=");
      if (eqIdx === -1) continue;
      const key = trimmed.slice(0, eqIdx).trim();
      const value = trimmed.slice(eqIdx + 1).trim().replace(/^["']|["']$/g, "");
      if (!process.env[key]) process.env[key] = value;
    }
  }
}

tryEnvFile();

/** Next.js + Auth.js required envs */
export const env = {
  AUTH_SECRET: process.env.AUTH_SECRET!,
  AUTH_GOOGLE_ID: process.env.AUTH_GOOGLE_ID!,
  AUTH_GOOGLE_SECRET: process.env.AUTH_GOOGLE_SECRET!,
  DATABASE_URL: process.env.DATABASE_URL!,
  OPENROUTER_API_KEY: process.env.OPENROUTER_API_KEY!,
  OPENROUTER_MODEL: process.env.OPENROUTER_MODEL ?? "nvidia/nemotron-3-ultra-550b-a55b:free",
  OPENROUTER_FALLBACK_MODEL: process.env.OPENROUTER_FALLBACK_MODEL ?? "openrouter/free",
  OPENROUTER_SITE_URL: process.env.OPENROUTER_SITE_URL ?? "http://localhost:3000",
  OPENROUTER_APP_NAME: process.env.OPENROUTER_APP_NAME ?? "GradPath",
  DAILY_LIMIT: parseInt(process.env.DAILY_LIMIT ?? "5", 10),
  BITS_ALLOWED_DOMAINS: process.env.BITS_ALLOWED_DOMAINS ?? "bits-pilani.ac.in",
} as const;
