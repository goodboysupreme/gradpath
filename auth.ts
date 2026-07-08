import NextAuth from "next-auth";
import Google from "next-auth/providers/google";
import { DrizzleAdapter } from "@auth/drizzle-adapter";
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

export const { handlers, auth, signIn, signOut } = NextAuth({
  adapter: process.env.DATABASE_URL
    ? DrizzleAdapter(getDb(), { usersTable: users, accountsTable: accounts })
    : undefined,
  session: { strategy: "jwt" },
  providers: [
    Google({
      clientId: process.env.AUTH_GOOGLE_ID!,
      clientSecret: process.env.AUTH_GOOGLE_SECRET!,
    }),
  ],
  callbacks: {
    signIn: ({ profile, user }) => {
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
