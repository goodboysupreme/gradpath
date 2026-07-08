import NextAuth from "next-auth";
import Google from "next-auth/providers/google";
import Credentials from "next-auth/providers/credentials";
import { DrizzleAdapter } from "@auth/drizzle-adapter";
import { eq } from "drizzle-orm";
import { getDb } from "@/db";
import { accounts, users } from "@/db/schema";

function allowedDomains() {
  const raw = process.env.BITS_ALLOWED_DOMAINS ?? "bits-pilani.ac.in";
  return raw.split(",").map((domain) => domain.trim().toLowerCase()).filter(Boolean);
}

function isBitsEmail(email?: string | null) {
  if (!email) return false;
  const domain = email.split("@").at(1)?.toLowerCase();
  if (!domain) return false;
  return allowedDomains().some((allowed) => domain === allowed || domain.endsWith(`.${allowed}`));
}

const devBypass = process.env.AUTH_DEV_BYPASS === "true";
const hasGoogle = Boolean(process.env.AUTH_GOOGLE_ID && process.env.AUTH_GOOGLE_SECRET);

export const { handlers, auth, signIn, signOut } = NextAuth({
  trustHost: true,
  adapter: process.env.DATABASE_URL
    ? DrizzleAdapter(getDb(), { usersTable: users, accountsTable: accounts })
    : undefined,
  session: { strategy: "jwt" },
  providers: [
    ...(hasGoogle
      ? [
          Google({
            clientId: process.env.AUTH_GOOGLE_ID!,
            clientSecret: process.env.AUTH_GOOGLE_SECRET!,
          }),
        ]
      : []),
    ...(devBypass
      ? [
          Credentials({
            id: "dev",
            name: "Dev bypass",
            credentials: {},
            async authorize() {
              if (process.env.AUTH_DEV_BYPASS !== "true") return null;

              const email = process.env.AUTH_DEV_EMAIL ?? "dev@bits-pilani.ac.in";
              const name = process.env.AUTH_DEV_NAME ?? "GradPath Dev";
              const db = getDb();

              const [existing] = await db
                .select()
                .from(users)
                .where(eq(users.email, email))
                .limit(1);

              if (existing) {
                return { id: existing.id, email: existing.email, name: existing.name ?? name };
              }

              const [created] = await db
                .insert(users)
                .values({ email, name })
                .returning();

              return { id: created.id, email: created.email, name: created.name ?? name };
            },
          }),
        ]
      : []),
  ],
  callbacks: {
    signIn: ({ account, profile, user }) => {
      if (account?.provider === "dev" && process.env.AUTH_DEV_BYPASS === "true") {
        return true;
      }
      const email = user.email ?? profile?.email;
      return isBitsEmail(email);
    },
    jwt: ({ token, user }) => {
      if (user) token.id = user.id;
      return token;
    },
    session: ({ session, token }) => {
      if (session.user) session.user.id = token.id as string;
      return session;
    },
  },
  pages: {
    signIn: "/",
  },
});
