import { pgTable, text, timestamp, integer, jsonb, uuid, primaryKey, uniqueIndex } from "drizzle-orm/pg-core";

// Auth.js tables

export const users = pgTable("users", {
  id: uuid("id").primaryKey().defaultRandom(),
  name: text("name"),
  email: text("email").notNull().unique(),
  emailVerified: timestamp("email_verified", { mode: "date" }),
  image: text("image"),
});

export const accounts = pgTable(
  "accounts",
  {
    userId: uuid("user_id")
      .notNull()
      .references(() => users.id, { onDelete: "cascade" }),
    type: text("type").notNull(),
    provider: text("provider").notNull(),
    providerAccountId: text("provider_account_id").notNull(),
    refresh_token: text("refresh_token"),
    access_token: text("access_token"),
    expires_at: integer("expires_at"),
    token_type: text("token_type"),
    scope: text("scope"),
    id_token: text("id_token"),
    session_state: text("session_state"),
  },
  (acc) => ({
    compoundKey: primaryKey({
      columns: [acc.provider, acc.providerAccountId],
    }),
  }),
);

// Analyses table

export const analyses = pgTable("analyses", {
  id: uuid("id").primaryKey().defaultRandom(),
  userId: uuid("user_id")
    .notNull()
    .references(() => users.id, { onDelete: "cascade" }),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  targetCompany: text("target_company"),
  targetRole: text("target_role"),
  intakeMode: text("intake_mode"),
  jdText: text("jd_text").notNull(),
  resumeText: text("resume_text").notNull(),
  resumeFilename: text("resume_filename"),
  studentContext: jsonb("student_context"),
  result: jsonb("result").notNull(),
  matchScore: integer("match_score").notNull(),
});

export const studentProfiles = pgTable(
  "student_profiles",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    userId: uuid("user_id")
      .notNull()
      .references(() => users.id, { onDelete: "cascade" }),
    updatedAt: timestamp("updated_at").defaultNow().notNull(),
    fullName: text("full_name"),
    degree: text("degree"),
    branch: text("branch"),
    campus: text("campus"),
    graduationYear: integer("graduation_year"),
    cgpa: text("cgpa"),
    courses: text("courses"),
    skills: text("skills"),
    projects: text("projects"),
    internships: text("internships"),
    achievements: text("achievements"),
    links: text("links"),
    preferredDomains: text("preferred_domains"),
  },
  (table) => ({
    userIdIdx: uniqueIndex("student_profiles_user_id_idx").on(table.userId),
  }),
);
