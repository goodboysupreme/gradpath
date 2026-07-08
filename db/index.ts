import { neon } from "@neondatabase/serverless";
import { drizzle, type NeonHttpDatabase } from "drizzle-orm/neon-http";
import * as schema from "./schema";

type DB = NeonHttpDatabase<typeof schema>;

const globalForDb = globalThis as unknown as { db?: DB };

export function getDb(): DB {
  const url = process.env.DATABASE_URL;
  if (!url) {
    throw new Error("DATABASE_URL is not set. Configure it in .env.local or your deployment environment.");
  }
  if (!globalForDb.db) {
    globalForDb.db = drizzle(neon(url), { schema });
  }
  return globalForDb.db;
}

const dbProxy: DB = new Proxy({} as DB, {
  get(_target, prop) {
    return Reflect.get(getDb(), prop);
  },
});

export const db = dbProxy;
