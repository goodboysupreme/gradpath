/**
 * Season-aware sample JDs for BITS campus prep.
 *
 * Content is synthesized from patterns in public student/intern postings
 * (Google Careers SWE Intern Summer, Microsoft University / Explore,
 * Amazon SDE Intern, Meta student programs, India product cos).
 * NOT official employer postings — for practice / GradPath targeting only.
 */

export type SeasonId = "internship" | "placement" | "ps-conversion";

export type RoleId =
  | "sde-intern"
  | "software-engineer"
  | "backend-engineer"
  | "frontend-engineer"
  | "ml-engineer"
  | "data-scientist"
  | "quant"
  | "product-manager"
  | "explore-intern"
  | "ml-intern"
  | "data-intern"
  | "quant-intern"
  | "pm-intern";

export type SampleJd = {
  id: string;
  seasonId: SeasonId;
  roleId: RoleId;
  company: string;
  title: string;
  location: string;
  program: string;
  duration: string;
  level: "summer-intern" | "new-grad" | "ps-conversion";
  body: string;
  sourceNotes: string;
};

export type SeasonOption = {
  id: SeasonId;
  label: string;
  hint: string;
};

export type RoleOption = {
  id: RoleId;
  label: string;
  short: string;
  seasons: SeasonId[];
};

export const SEASON_OPTIONS: SeasonOption[] = [
  {
    id: "internship",
    label: "Internship season",
    hint: "Summer / off-cycle intern JDs (student, returning to campus)",
  },
  {
    id: "placement",
    label: "Placement season",
    hint: "New-grad / full-time campus hire JDs",
  },
  {
    id: "ps-conversion",
    label: "Practice School conversion",
    hint: "PS / intern-to-full-time conversion bar",
  },
];

export const ROLE_OPTIONS: RoleOption[] = [
  { id: "sde-intern", label: "SDE Intern (Summer)", short: "SDE Intern", seasons: ["internship"] },
  { id: "explore-intern", label: "Explore / Early Intern", short: "Explore", seasons: ["internship"] },
  { id: "ml-intern", label: "ML Intern (Summer)", short: "ML Intern", seasons: ["internship"] },
  { id: "data-intern", label: "Data Science Intern", short: "DS Intern", seasons: ["internship"] },
  { id: "quant-intern", label: "Quant Research Intern", short: "QR Intern", seasons: ["internship"] },
  { id: "pm-intern", label: "APM / PM Intern", short: "PM Intern", seasons: ["internship"] },
  { id: "software-engineer", label: "Software Engineer (New Grad)", short: "SDE FT", seasons: ["placement", "ps-conversion"] },
  { id: "backend-engineer", label: "Backend Engineer", short: "Backend", seasons: ["placement", "ps-conversion"] },
  { id: "frontend-engineer", label: "Frontend Engineer", short: "Frontend", seasons: ["placement", "ps-conversion"] },
  { id: "ml-engineer", label: "ML Engineer (New Grad)", short: "ML Eng", seasons: ["placement", "ps-conversion"] },
  { id: "data-scientist", label: "Data Scientist", short: "DS", seasons: ["placement", "ps-conversion"] },
  { id: "quant", label: "Quantitative Researcher", short: "Quant", seasons: ["placement", "ps-conversion"] },
  { id: "product-manager", label: "Associate Product Manager", short: "APM", seasons: ["placement", "ps-conversion"] },
];

export function seasonFromLabel(label: string): SeasonId | "" {
  const n = label.trim().toLowerCase();
  if (!n) return "";
  if (n.includes("internship")) return "internship";
  if (n.includes("placement")) return "placement";
  if (n.includes("practice") || n.includes("ps")) return "ps-conversion";
  return "";
}

export function seasonToProfileValue(season: SeasonId): string {
  if (season === "internship") return "Internship season";
  if (season === "placement") return "Placement season";
  return "Practice School conversion";
}

export function getRoleOptionsForSeason(season: SeasonId | ""): RoleOption[] {
  if (!season) return ROLE_OPTIONS;
  return ROLE_OPTIONS.filter((role) => role.seasons.includes(season));
}

type CompanySeed = {
  name: string;
  location: string;
  blurb: string;
  internProgram: string;
  internDuration: string;
  internFocus: string;
  placementNote: string;
};

/** 20 firms with public campus / intern hiring presence. */
const COMPANIES: CompanySeed[] = [
  {
    name: "Google",
    location: "Bengaluru / Hyderabad / US hybrid (role dependent)",
    blurb: "Build products used by billions. Interns join real engineering teams on production code paths.",
    internProgram: "Software Engineering Intern, Summer",
    internDuration: "10–14 weeks (typically May–Aug)",
    internFocus: "DSA depth, one strong language, Unix/Linux, software design; penultimate year preferred for main SWE intern track",
    placementNote: "New-grad SWE expects stronger systems exposure and internship track record",
  },
  {
    name: "Microsoft",
    location: "Hyderabad / Bengaluru / Noida",
    blurb: "Cloud, productivity, and AI platforms. University and Explore tracks for students.",
    internProgram: "University Software Engineering Intern / Explore (early years)",
    internDuration: "8 weeks (India Explore) or ~12 weeks (University intern)",
    internFocus: "CS fundamentals, collaboration, shipping with a pod/team; Explore mixes SWE+PM exposure for early years",
    placementNote: "Full-time university hire bar includes coding + design + collaboration signals",
  },
  {
    name: "Amazon",
    location: "Bengaluru / Hyderabad",
    blurb: "Customer-obsessed engineering. Interns own a slice of design → code → test under Leadership Principles.",
    internProgram: "Software Development Engineer Intern",
    internDuration: "12 weeks full-time (40 hrs/week)",
    internFocus: "One general-purpose language, DSA/OOP, enrolled in STEM degree, return to school after intern",
    placementNote: "SDE I new-grad emphasizes ownership, coding, and LP behavioral stories",
  },
  {
    name: "Meta",
    location: "Bengaluru / Menlo Park (program dependent)",
    blurb: "Social infrastructure at scale. Student programs emphasize impact and modern languages.",
    internProgram: "Software Engineer Intern (University)",
    internDuration: "~12 weeks summer",
    internFocus: "Enrolled BS/MS in CS-related field; Python/Java/C++; OOP; projects/internships preferred not always required",
    placementNote: "New-grad SWE expects demonstrated software experience and strong coding",
  },
  {
    name: "Apple",
    location: "Hyderabad / Bengaluru",
    blurb: "Hardware-software integration and privacy-first products. High craft bar even for interns.",
    internProgram: "Software Engineering Intern",
    internDuration: "12 weeks summer",
    internFocus: "Strong CS foundation, quality mindset, systems or app stack depending on team",
    placementNote: "New-grad roles often team-specific (platform, services, ML)",
  },
  {
    name: "Uber",
    location: "Bengaluru / Hyderabad",
    blurb: "Marketplace and logistics systems. Interns ship on real-time services and mobile backends.",
    internProgram: "Software Engineer Intern",
    internDuration: "10–12 weeks summer",
    internFocus: "Coding, distributed systems curiosity, product sense for marketplace problems",
    placementNote: "New-grad expects production internship or strong projects at scale thinking",
  },
  {
    name: "Stripe",
    location: "Remote / Bengaluru (role dependent)",
    blurb: "Financial infrastructure APIs. Interns work on reliability, API design, and developer experience.",
    internProgram: "Software Engineering Intern",
    internDuration: "12 weeks summer",
    internFocus: "Code quality, systems thinking, comfort with ambiguity, strong written communication",
    placementNote: "New-grad bar is high on craft and ownership",
  },
  {
    name: "Atlassian",
    location: "Bengaluru",
    blurb: "Collaboration tools for teams. Interns join squads shipping Jira/Confluence-scale products.",
    internProgram: "Software Engineer Intern",
    internDuration: "10–12 weeks",
    internFocus: "Full-stack or backend fundamentals, teamwork, iterative delivery",
    placementNote: "Graduate roles value product collaboration and clean engineering",
  },
  {
    name: "Adobe",
    location: "Noida / Bengaluru",
    blurb: "Creative Cloud and enterprise software. Interns contribute to product surfaces and services.",
    internProgram: "Product Intern / Software Development Intern",
    internDuration: "8–12 weeks summer",
    internFocus: "Solid coding, UI or backend track, design sensitivity for creative products",
    placementNote: "New-grad tracks often map to product engineering pods",
  },
  {
    name: "Salesforce",
    location: "Hyderabad / Bengaluru",
    blurb: "CRM platform at enterprise scale. Interns learn multi-tenant cloud software.",
    internProgram: "Software Engineering Intern",
    internDuration: "10–12 weeks",
    internFocus: "Java/JS comfort, OOP, databases, collaborative delivery",
    placementNote: "Associate SE roles emphasize platform thinking",
  },
  {
    name: "Oracle",
    location: "Bengaluru / Hyderabad",
    blurb: "Cloud infrastructure and databases. Internships lean systems and performance.",
    internProgram: "Software Intern",
    internDuration: "8–12 weeks",
    internFocus: "CS fundamentals, systems interest, SQL/languages",
    placementNote: "New-grad IC roles often cloud/database adjacent",
  },
  {
    name: "LinkedIn",
    location: "Bengaluru",
    blurb: "Economic graph products. Interns touch data-heavy services and member experiences.",
    internProgram: "Software Engineer Intern",
    internDuration: "12 weeks summer",
    internFocus: "DSA, distributed systems interest, Java/Python/Scala exposure helpful",
    placementNote: "New-grad expects strong coding + product impact stories",
  },
  {
    name: "Flipkart",
    location: "Bengaluru",
    blurb: "India e-commerce at scale. Heavy campus internship and PPO culture.",
    internProgram: "SDE Intern (Summer)",
    internDuration: "8–12 weeks (campus cycle dependent)",
    internFocus: "DSA interviews, Java/Python, projects, e-commerce systems curiosity",
    placementNote: "PPO conversion emphasizes intern delivery quality",
  },
  {
    name: "Swiggy",
    location: "Bengaluru",
    blurb: "Food and quick commerce logistics. Interns work near real-time consumer and logistics systems.",
    internProgram: "Software Development Intern",
    internDuration: "8–12 weeks",
    internFocus: "Coding, backend/mobile interest, product sense for consumer apps",
    placementNote: "FT hire values intern impact and ownership",
  },
  {
    name: "Razorpay",
    location: "Bengaluru",
    blurb: "Payments and fintech APIs. Interns learn high-availability and compliance-aware engineering.",
    internProgram: "Software Engineer Intern",
    internDuration: "8–12 weeks summer",
    internFocus: "Backend fundamentals, security awareness, clean APIs",
    placementNote: "New-grad expects production-minded coding",
  },
  {
    name: "CRED",
    location: "Bengaluru",
    blurb: "Fintech consumer product. Craft-focused engineering culture.",
    internProgram: "Software Intern",
    internDuration: "8–12 weeks",
    internFocus: "Strong coding, mobile/web craft, product polish",
    placementNote: "FT bar prioritizes quality and taste",
  },
  {
    name: "Databricks",
    location: "Remote / Bengaluru",
    blurb: "Lakehouse platform for analytics and AI. Interns touch data systems and developer tooling.",
    internProgram: "Software Engineering Intern",
    internDuration: "12 weeks summer",
    internFocus: "Strong CS, distributed data interest, Python/Scala/Java",
    placementNote: "New-grad roles are systems-heavy",
  },
  {
    name: "NVIDIA",
    location: "Bengaluru / Pune",
    blurb: "Accelerated computing and AI platforms. Internships often systems/ML adjacent.",
    internProgram: "Software / Deep Learning Intern",
    internDuration: "8–12 weeks",
    internFocus: "C++/Python, algorithms, CUDA/ML interest depending on team",
    placementNote: "FT roles often specialized (systems, DL frameworks, tooling)",
  },
  {
    name: "Bloomberg",
    location: "Pune / remote hybrid",
    blurb: "Financial data and analytics terminal. Interns value correctness and low-latency thinking.",
    internProgram: "Software Engineering Intern",
    internDuration: "10–12 weeks",
    internFocus: "C++/Python/Java, DSA, systems curiosity",
    placementNote: "New-grad expects strong fundamentals and domain learning agility",
  },
  {
    name: "DE Shaw",
    location: "Hyderabad",
    blurb: "Technology-driven investment firm. High bar internships in software and research.",
    internProgram: "Software Developer Intern / Research Intern",
    internDuration: "8–12 weeks summer",
    internFocus: "Exceptional algorithms, clean code, math/CS depth",
    placementNote: "FT quant/tech roles are extremely competitive",
  },
];

type RoleSeasonBlueprint = {
  id: RoleId;
  seasons: SeasonId[];
  titleFor: (company: CompanySeed, season: SeasonId) => string;
  programFor: (company: CompanySeed, season: SeasonId) => string;
  durationFor: (company: CompanySeed, season: SeasonId) => string;
  level: SampleJd["level"];
  about: string;
  responsibilities: string[];
  minimumQualifications: string[];
  preferredQualifications: string[];
  whatYouWillLearn: string[];
  interviewLoop: string[];
  stack: string[];
  sourceNotes: string;
};

const ROLE_SEASON_BLUEPRINTS: RoleSeasonBlueprint[] = [
  {
    id: "sde-intern",
    seasons: ["internship"],
    titleFor: (c) => `Software Engineering Intern, Summer — ${c.name}`,
    programFor: (c) => c.internProgram,
    durationFor: (c) => c.internDuration,
    level: "summer-intern",
    about:
      "This is a full-time SUMMER INTERNSHIP for enrolled students who will return to university after the program. You are not expected to have years of industry seniority. You are expected to write real production code with a mentor, pass coding interviews focused on data structures and algorithms, and ship a scoped project in ~10–14 weeks.",
    responsibilities: [
      "Join an engineering team and take ownership of a well-scoped feature, service improvement, or tool under mentor guidance",
      "Design, implement, test, and document code that can be merged to production within the internship window",
      "Participate in code reviews, standups, design discussions, and (where offered) light on-call shadowing",
      "Debug using logs, metrics, unit tests, and local reproduction; raise blockers early",
      "Present end-of-internship demo / write-up covering problem, design, impact, and next steps",
      "Collaborate with PMs/designers/other engineers as a student engineer — not as a senior IC",
    ],
    minimumQualifications: [
      "Currently pursuing a Bachelor's or Master's (or dual degree) in Computer Science or a related technical field",
      "Must be able to return to degree program after the internship (student status required)",
      "Experience with one or more general-purpose languages: Java, C/C++, Python, JavaScript/TypeScript, Go, etc.",
      "Coursework or project experience with data structures, algorithms, and basic software design",
      "Comfort working in Unix/Linux-style environments and using Git",
      "Available full-time for the published summer window (typically 40 hours/week for 10–14 weeks)",
    ],
    preferredQualifications: [
      "Penultimate year of study for flagship SWE intern tracks (company-dependent)",
      "Prior projects, open-source, hackathons, or a previous internship demonstrating shipped code",
      "Exposure to web services, mobile, distributed systems, ML, security, or systems programming",
      "Competitive programming / strong DSA practice (arrays, trees, graphs, DP, complexity analysis)",
      "Clear communication and ability to learn a large codebase quickly",
    ],
    whatYouWillLearn: [
      "How production code is reviewed, tested, and rolled out at scale",
      "Working inside a large monorepo/service ecosystem with mentors and code owners",
      "Translating a product/tech problem into a 10–12 week deliverable",
    ],
    interviewLoop: [
      "Online assessment or recruiter screen (company-dependent)",
      "1–2 coding interviews (DSA, medium-level problem solving)",
      "Sometimes a project deep-dive or light behavioral / leadership principles round",
      "No expectation of multi-year staff-level system design for pure intern loops",
    ],
    stack: ["Java", "C++", "Python", "TypeScript", "Git", "Linux", "SQL", "REST"],
    sourceNotes:
      "Patterned on public Google SWE Intern Summer min/preferred quals, Amazon SDE Intern basic quals (enrolled STEM, language + DSA/OOP, 12-week full-time), Meta university intern enrollment + language signals.",
  },
  {
    id: "explore-intern",
    seasons: ["internship"],
    titleFor: (c) => `Explore / Early Career Engineering Intern — ${c.name}`,
    programFor: (c) => (c.name === "Microsoft" ? "Explore Microsoft" : `${c.name} Early Intern / STEP-style program`),
    durationFor: (c) => (c.name === "Microsoft" ? "8 weeks (India Explore) / 12 weeks (US-style)" : "8–12 weeks summer"),
    level: "summer-intern",
    about:
      "Early-year summer internship (typically 1st/2nd year or STEP-style). Lower expectation of deep production history; higher emphasis on learning velocity, fundamentals, and finishing a pod project. Not a senior hire JD.",
    responsibilities: [
      "Work in a small pod on a design → build → quality project for a product group",
      "Learn software development lifecycle with structured mentorship",
      "For Explore-style programs: gain exposure across engineering (and sometimes PM) disciplines",
      "Ship a demo-able project by the end of the short summer window",
      "Build professional skills: collaboration, feedback, documentation",
    ],
    minimumQualifications: [
      "Enrolled in an undergraduate CS/EE/related program (often first or second year for Explore tracks)",
      "Basic programming ability in at least one language",
      "Curiosity about software products and willingness to learn in a team setting",
      "Available for the full program duration without conflicting full-time work",
    ],
    preferredQualifications: [
      "Personal projects, course projects, or coding club experience",
      "Interest in both building and understanding product problems",
      "Strong communication and growth mindset",
    ],
    whatYouWillLearn: [
      "How large product groups plan and deliver software",
      "Pair programming, code review culture, and iterative delivery",
      "Whether SWE (or PM-adjacent) tracks fit your long-term direction",
    ],
    interviewLoop: [
      "Coding fundamentals screen",
      "Behavioral / collaboration interview",
      "Sometimes a simple project discussion",
    ],
    stack: ["Python", "Java", "JavaScript", "Git", "basic web or systems intro"],
    sourceNotes: "Patterned on public Microsoft Explore descriptions (early-year, pod project, 8–12 weeks) and Google STEP-style early engineering intern framing.",
  },
  {
    id: "ml-intern",
    seasons: ["internship"],
    titleFor: (c) => `Machine Learning / AI Intern, Summer — ${c.name}`,
    programFor: (c) => `${c.name} ML / Applied Science Intern (Summer)`,
    durationFor: () => "10–12 weeks summer",
    level: "summer-intern",
    about:
      "Summer research-or-applied ML internship for students. You will run experiments, write training/eval code, and partner with engineers — not own multi-year model platforms solo.",
    responsibilities: [
      "Implement baselines and experiments for ranking, NLP, CV, recommendations, or LLM-adjacent tasks",
      "Write reproducible training/eval scripts; track metrics carefully",
      "Collaborate with full-time ML engineers/scientists on a scoped summer milestone",
      "Document findings; present results in an intern showcase",
      "Help productionize a small piece when the team is ready (feature, offline eval, simple service)",
    ],
    minimumQualifications: [
      "Pursuing BS/MS/PhD in CS, EE, Math, Statistics, or related field; returning to school after internship",
      "Strong Python and solid linear algebra / probability / ML coursework",
      "Hands-on experience with PyTorch or TensorFlow via courses or projects",
      "Ability to read papers/docs and implement methods carefully",
    ],
    preferredQualifications: [
      "Projects involving real datasets, ablations, and clear metrics",
      "Exposure to data wrangling (pandas, SQL) and experiment tracking",
      "Interest in LLMs, retrieval, or classical ML depending on team",
    ],
    whatYouWillLearn: [
      "How industrial ML experiments are scoped for a summer",
      "Eval rigor, leakage pitfalls, and communication of uncertainty",
      "Interface between research ideas and production constraints",
    ],
    interviewLoop: [
      "Coding (Python + DSA basics)",
      "ML fundamentals / applied case",
      "Project deep-dive",
    ],
    stack: ["Python", "PyTorch", "NumPy", "pandas", "SQL", "scikit-learn"],
    sourceNotes: "Synthesized from public student ML/applied science intern patterns at large tech firms (experimentation, Python, returning student).",
  },
  {
    id: "data-intern",
    seasons: ["internship"],
    titleFor: (c) => `Data Science Intern, Summer — ${c.name}`,
    programFor: (c) => `${c.name} Data Science / Analytics Intern`,
    durationFor: () => "10–12 weeks summer",
    level: "summer-intern",
    about:
      "Summer DS intern role: analytics, experimentation support, and lightweight modeling — scoped for a student timeline, not principal-scientist ownership.",
    responsibilities: [
      "Define metrics and pull data with SQL / Python for a product question",
      "Support A/B test analysis or exploratory analysis under mentorship",
      "Build dashboards or notebooks that stakeholders can reuse",
      "Present insights and recommended next experiments at internship end",
    ],
    minimumQualifications: [
      "Enrolled in a quantitative degree program; return to school after internship",
      "SQL + Python (or R) proficiency from coursework/projects",
      "Statistics fundamentals: hypothesis testing, confidence intervals, bias",
      "Clear written and verbal communication",
    ],
    preferredQualifications: [
      "Course projects with real messy data",
      "Familiarity with experimentation or causal thinking",
      "Dashboarding exposure (Looker/Tableau/Mode optional)",
    ],
    whatYouWillLearn: [
      "How product analytics decisions are made in industry",
      "Stakeholder communication and metric design",
    ],
    interviewLoop: ["SQL", "stats reasoning", "case / product sense light"],
    stack: ["SQL", "Python", "pandas", "statistics", "A/B testing basics"],
    sourceNotes: "Public campus DS intern patterns: SQL-first, stats, student enrollment, summer length.",
  },
  {
    id: "quant-intern",
    seasons: ["internship"],
    titleFor: (c) => `Quantitative Research / Trading Tech Intern — ${c.name}`,
    programFor: (c) => `${c.name} Quant / Software Research Intern`,
    durationFor: () => "8–12 weeks summer",
    level: "summer-intern",
    about:
      "High-bar summer quant/tech internship. Expect probability, algorithms, and coding — still an intern scope, not a PM of a trading desk.",
    responsibilities: [
      "Research a scoped signal/feature or implement research tooling",
      "Write correct, tested code for data analysis or simulation",
      "Present research notes with assumptions and failure modes",
      "Collaborate with full-time researchers/engineers",
    ],
    minimumQualifications: [
      "Strong math/CS background; currently enrolled in a degree program",
      "Excellent programming in Python and/or C++",
      "Probability, statistics, and algorithms depth",
      "Available for intensive full-time summer internship",
    ],
    preferredQualifications: [
      "Contest math/CP background",
      "Prior research or finance-curious projects",
      "Experience with large datasets or performance-sensitive code",
    ],
    whatYouWillLearn: [
      "Research hygiene and reproducibility",
      "How quant tech teams evaluate ideas quickly",
    ],
    interviewLoop: ["Probability / brainteasers", "Coding", "Research discussion"],
    stack: ["Python", "C++", "NumPy", "statistics", "Linux"],
    sourceNotes: "Patterned on public tech/quant intern hiring signals at firms like DE Shaw and trading tech cultures.",
  },
  {
    id: "pm-intern",
    seasons: ["internship"],
    titleFor: (c) => `Product Management Intern, Summer — ${c.name}`,
    programFor: (c) => `${c.name} APM / PM Intern`,
    durationFor: () => "10–12 weeks summer",
    level: "summer-intern",
    about:
      "Summer PM internship for students. You will ship a scoped product bet with eng/design partners — not own a multi-year portfolio as a senior PM.",
    responsibilities: [
      "Clarify user problem, success metrics, and scope for a summer-sized initiative",
      "Write crisp specs / PRD sections and align stakeholders",
      "Partner with engineering on trade-offs and weekly execution",
      "Run lightweight research or data checks; present outcomes at the end",
    ],
    minimumQualifications: [
      "Currently enrolled undergraduate or master's student returning to school",
      "Evidence of leadership, product sense, or complex project ownership (clubs, startups, PORs)",
      "Analytical comfort (spreadsheets/SQL basics helpful)",
      "Excellent communication",
    ],
    preferredQualifications: [
      "Prior internship in product, consulting, or growth",
      "Technical literacy to talk to engineers",
      "Shipped something users touched (even campus-scale)",
    ],
    whatYouWillLearn: [
      "How PMs scope for a quarter vs a summer",
      "Metric definition and stakeholder management",
    ],
    interviewLoop: ["Product sense", "Analytical case", "Behavioral"],
    stack: ["PRDs", "metrics", "basic SQL", "Figma familiarity"],
    sourceNotes: "Public APM/PM intern patterns: enrolled student, summer length, product sense + execution — not staff PM scope.",
  },
  {
    id: "software-engineer",
    seasons: ["placement", "ps-conversion"],
    titleFor: (c, season) =>
      season === "ps-conversion"
        ? `Software Engineer I (PS / Intern Conversion Track) — ${c.name}`
        : `Software Engineer (New Grad / University Graduate) — ${c.name}`,
    programFor: (c, season) =>
      season === "ps-conversion" ? `${c.name} PPO / Intern Conversion` : `${c.name} University Graduate SWE`,
    durationFor: () => "Full-time",
    level: "new-grad",
    about:
      "Full-time new-grad or conversion role. Higher bar than summer intern: sustained ownership, stronger system design signal, and (for conversion) proof you delivered during internship/PS.",
    responsibilities: [
      "Design, implement, and maintain production features/services",
      "Improve reliability, performance, and observability for owned surfaces",
      "Participate fully in code review, on-call (after ramp), and planning",
      "Write design docs for medium-sized projects",
      "Mentor interns later; model high engineering standards",
    ],
    minimumQualifications: [
      "BE/BTech/MTech in CS or equivalent practical experience; graduating into full-time eligibility",
      "Strong coding and DSA; able to clear multi-round coding interviews",
      "Demonstrated projects or internships with non-trivial software ownership",
      "Solid communication and collaboration skills",
    ],
    preferredQualifications: [
      "Prior SWE internship at a product company (strongly preferred for conversion)",
      "Exposure to distributed systems basics, cloud, or large codebases",
      "Open-source or production side projects",
    ],
    whatYouWillLearn: [
      "Longer-horizon ownership than a summer intern project",
      "Operational excellence and cross-team collaboration",
    ],
    interviewLoop: ["Multiple coding rounds", "System design intro", "Behavioral / leadership principles"],
    stack: ["Java", "Go", "Python", "TypeScript", "SQL", "Kafka", "Kubernetes"],
    sourceNotes: "New-grad SWE patterns vs intern: full-time eligibility, stronger design/ownership, conversion emphasizes intern impact.",
  },
  {
    id: "backend-engineer",
    seasons: ["placement", "ps-conversion"],
    titleFor: (c) => `Backend Engineer (New Grad) — ${c.name}`,
    programFor: (c) => `${c.name} University Backend / Platform Graduate`,
    durationFor: () => "Full-time",
    level: "new-grad",
    about: "Full-time backend-focused new-grad role building APIs and services — not a 12-week intern scoped ticket list.",
    responsibilities: [
      "Build and maintain REST/gRPC services and data models",
      "Own latency, correctness, and failure modes for critical paths",
      "Work with queues, caches, and datastores under review",
      "Participate in on-call after ramp-up",
    ],
    minimumQualifications: [
      "Strong coding in Java/Go/Python/Node",
      "SQL and API design fundamentals",
      "Understanding of concurrency and basic distributed systems trade-offs",
      "Graduating into full-time work authorization/eligibility",
    ],
    preferredQualifications: [
      "Internship on backend systems",
      "Kafka/Redis/Postgres production exposure",
      "Docker/K8s familiarity",
    ],
    whatYouWillLearn: ["Service ownership at scale", "SLOs and operational excellence"],
    interviewLoop: ["Coding", "Backend design", "SQL/debugging"],
    stack: ["Java", "Go", "PostgreSQL", "Redis", "Kafka", "Docker"],
    sourceNotes: "Campus FT backend hiring patterns at product companies.",
  },
  {
    id: "frontend-engineer",
    seasons: ["placement", "ps-conversion"],
    titleFor: (c) => `Frontend Engineer (New Grad) — ${c.name}`,
    programFor: (c) => `${c.name} University Frontend Graduate`,
    durationFor: () => "Full-time",
    level: "new-grad",
    about: "Full-time frontend new-grad role focused on product UI quality, performance, and accessibility.",
    responsibilities: [
      "Ship polished UI with modern frameworks",
      "Partner with design on interaction quality and a11y",
      "Own client performance budgets on key surfaces",
      "Integrate APIs and manage client state thoughtfully",
    ],
    minimumQualifications: [
      "Strong JavaScript/TypeScript",
      "React/Next (or equivalent) project experience",
      "Solid HTML/CSS and responsive design",
      "Portfolio or shipped UI work",
    ],
    preferredQualifications: ["Design systems", "Testing/Storybook", "Internship on product UI"],
    whatYouWillLearn: ["Production frontend craft", "Design-eng collaboration"],
    interviewLoop: ["JS/TS coding", "UI architecture", "Portfolio"],
    stack: ["TypeScript", "React", "Next.js", "CSS", "Playwright"],
    sourceNotes: "Campus FT frontend patterns.",
  },
  {
    id: "ml-engineer",
    seasons: ["placement", "ps-conversion"],
    titleFor: (c) => `ML Engineer (New Grad) — ${c.name}`,
    programFor: (c) => `${c.name} University ML / Applied Science Graduate`,
    durationFor: () => "Full-time",
    level: "new-grad",
    about: "Full-time ML engineer new-grad: productionization expectations higher than a summer research intern.",
    responsibilities: [
      "Train/eval models and help ship them with latency/cost constraints",
      "Build pipelines and monitoring with engineering partners",
      "Own offline/online metrics for a model surface over time",
    ],
    minimumQualifications: [
      "Strong Python + ML fundamentals",
      "PyTorch/TF project or internship experience",
      "Ability to write production-quality code beyond notebooks",
      "Full-time eligibility on graduation",
    ],
    preferredQualifications: ["MLOps exposure", "Prior ML internship", "Distributed training familiarity"],
    whatYouWillLearn: ["Production ML lifecycle", "Eval and monitoring discipline"],
    interviewLoop: ["Coding", "ML fundamentals", "Applied case"],
    stack: ["Python", "PyTorch", "SQL", "Docker", "FastAPI"],
    sourceNotes: "FT ML new-grad vs ML intern: longer ownership, production bar.",
  },
  {
    id: "data-scientist",
    seasons: ["placement", "ps-conversion"],
    titleFor: (c) => `Data Scientist (New Grad) — ${c.name}`,
    programFor: (c) => `${c.name} University Data Science Graduate`,
    durationFor: () => "Full-time",
    level: "new-grad",
    about: "Full-time DS role: ongoing product analytics ownership beyond a single summer study.",
    responsibilities: [
      "Own metrics and decision support for a product area",
      "Design and analyze experiments",
      "Build models/segmentations where they create product value",
      "Partner with eng on instrumentation quality",
    ],
    minimumQualifications: [
      "Strong stats + SQL + Python/R",
      "Experimentation literacy",
      "Clear storytelling with data",
      "Full-time eligibility",
    ],
    preferredQualifications: ["DS internship", "Causal inference exposure", "Dashboarding"],
    whatYouWillLearn: ["Roadmap influence with data", "Cross-functional leadership"],
    interviewLoop: ["SQL", "Stats", "Product case"],
    stack: ["SQL", "Python", "pandas", "experimentation", "Looker/dbt optional"],
    sourceNotes: "Campus FT DS hiring patterns.",
  },
  {
    id: "quant",
    seasons: ["placement", "ps-conversion"],
    titleFor: (c) => `Quantitative Researcher / Quant Developer (New Grad) — ${c.name}`,
    programFor: (c) => `${c.name} New Grad Quant / Tech`,
    durationFor: () => "Full-time",
    level: "new-grad",
    about: "Full-time quant/tech new-grad bar — significantly higher than intern exploratory projects.",
    responsibilities: [
      "Research and implement models/tools with production constraints",
      "Write high-correctness code; communicate research clearly",
      "Iterate with senior researchers under performance pressure",
    ],
    minimumQualifications: [
      "Exceptional quantitative ability",
      "Strong Python/C++",
      "Probability, stats, algorithms depth",
      "Evidence of research or contest excellence",
    ],
    preferredQualifications: ["Prior quant intern", "Publications or strong research thesis", "Low-latency systems interest"],
    whatYouWillLearn: ["Research-to-production loop", "Risk-aware evaluation"],
    interviewLoop: ["Math/probability", "Coding", "Research"],
    stack: ["Python", "C++", "statistics", "Linux"],
    sourceNotes: "FT quant hiring bar vs intern.",
  },
  {
    id: "product-manager",
    seasons: ["placement", "ps-conversion"],
    titleFor: (c) => `Associate Product Manager / APM — ${c.name}`,
    programFor: (c) => `${c.name} APM / University PM`,
    durationFor: () => "Full-time rotational or direct",
    level: "new-grad",
    about: "Full-time APM/new-grad PM — multi-quarter ownership, not a summer-only feature.",
    responsibilities: [
      "Own problem discovery and prioritization for a product surface",
      "Drive specs, metrics, and launches with eng/design",
      "Manage stakeholders and iterate after launch",
    ],
    minimumQualifications: [
      "Analytical + communication excellence",
      "Evidence of ownership and product judgment",
      "Comfort with metrics and technical trade-offs",
      "Full-time eligibility",
    ],
    preferredQualifications: ["PM internship", "Shipped products", "Technical degree or literacy"],
    whatYouWillLearn: ["Long-term roadmap craft", "Org navigation"],
    interviewLoop: ["Product sense", "Analytical", "Execution/behavioral"],
    stack: ["PRDs", "metrics", "SQL basics", "A/B testing"],
    sourceNotes: "APM FT vs PM intern scope.",
  },
];

function bullets(lines: string[]) {
  return lines.map((line) => `• ${line}`).join("\n");
}

function levelLabel(level: SampleJd["level"]) {
  if (level === "summer-intern") return "SUMMER INTERNSHIP (student, returns to campus)";
  if (level === "ps-conversion") return "PS / INTERN CONVERSION → FULL-TIME";
  return "FULL-TIME NEW GRAD / UNIVERSITY HIRE";
}

function buildBody(
  role: RoleSeasonBlueprint,
  company: CompanySeed,
  season: SeasonId,
  title: string,
  program: string,
  duration: string,
): string {
  const seasonBanner =
    season === "internship"
      ? "SEASON CONTEXT: Internship hiring (Summer). Optimize for student internship bar — not senior FT seniority."
      : season === "placement"
        ? "SEASON CONTEXT: Placement / full-time campus hiring. Optimize for new-grad FT bar."
        : "SEASON CONTEXT: Practice School / intern conversion. Emphasize delivery proof from PS/intern + FT readiness.";

  const companySpecific =
    season === "internship"
      ? `Company intern focus: ${company.internFocus}`
      : `Company FT note: ${company.placementNote}`;

  return [
    title,
    `Company: ${company.name}`,
    `Program: ${program}`,
    `Level: ${levelLabel(role.level === "new-grad" && season === "ps-conversion" ? "ps-conversion" : role.level)}`,
    `Duration / commitment: ${duration}`,
    `Location: ${company.location}`,
    ``,
    seasonBanner,
    ``,
    `About ${company.name}`,
    company.blurb,
    companySpecific,
    ``,
    `Role summary`,
    role.about,
    ``,
    `What you will do`,
    bullets(role.responsibilities),
    ``,
    `Minimum qualifications`,
    bullets(role.minimumQualifications),
    ``,
    `Preferred qualifications`,
    bullets(role.preferredQualifications),
    ``,
    `What you will learn`,
    bullets(role.whatYouWillLearn),
    ``,
    `Typical interview loop`,
    bullets(role.interviewLoop),
    ``,
    `Common tools / stack signals`,
    role.stack.join(", "),
    ``,
    `Eligibility reminder`,
    season === "internship"
      ? "Applicants must usually be enrolled students who intend to return to their degree program after the internship. This is not a disguised senior IC role."
      : season === "ps-conversion"
        ? "Conversion candidates are evaluated on intern/PS delivery quality plus FT coding/design bar."
        : "Applicants should be eligible for full-time employment upon graduation (campus hire cycle).",
    ``,
    `Notes for GradPath users`,
    `Sample JD synthesized from common PUBLIC student/intern/new-grad posting patterns for companies like ${company.name}. Not an official ${company.name} job posting. Use for placement/internship readiness practice only.`,
    `Sources consulted for patterns: public Google Careers intern pages & SWE Intern Summer qualification lists; Microsoft University/Explore program pages; Amazon SDE Intern basic qualifications (enrolled STEM, language + DSA/OOP, ~12-week full-time); Meta student/university program enrollment guidance.`,
  ].join("\n");
}

function buildAllSamples(): SampleJd[] {
  const samples: SampleJd[] = [];

  for (const role of ROLE_SEASON_BLUEPRINTS) {
    for (const season of role.seasons) {
      COMPANIES.forEach((company, index) => {
        const title = role.titleFor(company, season);
        const program = role.programFor(company, season);
        const duration = role.durationFor(company, season);
        const level: SampleJd["level"] =
          season === "internship" ? "summer-intern" : season === "ps-conversion" ? "ps-conversion" : "new-grad";

        samples.push({
          id: `${season}-${role.id}-${index + 1}`,
          seasonId: season,
          roleId: role.id,
          company: company.name,
          title,
          location: company.location,
          program,
          duration,
          level,
          body: buildBody(role, company, season, title, program, duration),
          sourceNotes: role.sourceNotes,
        });
      });
    }
  }

  return samples;
}

const ALL_SAMPLES = buildAllSamples();

export function getSamplesForRole(roleId: RoleId | "", seasonId?: SeasonId | ""): SampleJd[] {
  if (!roleId) return [];
  return ALL_SAMPLES.filter((sample) => {
    if (sample.roleId !== roleId) return false;
    if (seasonId && sample.seasonId !== seasonId) return false;
    return true;
  });
}

export function countSamplesForSeason(seasonId: SeasonId): number {
  return ALL_SAMPLES.filter((sample) => sample.seasonId === seasonId).length;
}

export function findRoleIdByLabel(label: string): RoleId | "" {
  const normalized = label.trim().toLowerCase();
  if (!normalized) return "";
  const exact = ROLE_OPTIONS.find(
    (role) => role.label.toLowerCase() === normalized || role.short.toLowerCase() === normalized,
  );
  if (exact) return exact.id;
  const partial = ROLE_OPTIONS.find(
    (role) => normalized.includes(role.short.toLowerCase()) || role.label.toLowerCase().includes(normalized),
  );
  return partial?.id ?? "";
}
