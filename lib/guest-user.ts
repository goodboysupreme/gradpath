import { eq } from "drizzle-orm";
import { getDb } from "@/db";
import { users } from "@/db/schema";

const GUEST_EMAIL = "guest@gradpath.local";
const GUEST_NAME = "Guest";

/** Shared anonymous user for open (no-auth) mode. */
export async function ensureGuestUser(): Promise<string> {
  const db = getDb();
  const [existing] = await db
    .select({ id: users.id })
    .from(users)
    .where(eq(users.email, GUEST_EMAIL))
    .limit(1);

  if (existing) return existing.id;

  const [created] = await db
    .insert(users)
    .values({ email: GUEST_EMAIL, name: GUEST_NAME })
    .returning({ id: users.id });

  return created.id;
}

export async function resolveUserId(sessionUserId?: string | null): Promise<string> {
  if (sessionUserId) return sessionUserId;
  return ensureGuestUser();
}
