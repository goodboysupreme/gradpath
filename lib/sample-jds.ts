export type RoleId =
  | "sde-intern"
  | "software-engineer"
  | "backend-engineer"
  | "frontend-engineer"
  | "ml-engineer"
  | "data-scientist"
  | "quant"
  | "product-manager";

export type SampleJd = {
  id: string;
  roleId: RoleId;
  company: string;
  title: string;
  location: string;
  body: string;
};

export type RoleOption = {
  id: RoleId;
  label: string;
  short: string;
};

export const ROLE_OPTIONS: RoleOption[] = [
  { id: "sde-intern", label: "SDE Intern", short: "SDE Intern" },
  { id: "software-engineer", label: "Software Engineer", short: "SDE" },
  { id: "backend-engineer", label: "Backend Engineer", short: "Backend" },
  { id: "frontend-engineer", label: "Frontend Engineer", short: "Frontend" },
  { id: "ml-engineer", label: "ML Engineer", short: "ML Eng" },
  { id: "data-scientist", label: "Data Scientist", short: "DS" },
  { id: "quant", label: "Quantitative Researcher", short: "Quant" },
  { id: "product-manager", label: "Product Manager", short: "PM" },
];

type CompanySeed = {
  name: string;
  location: string;
  blurb: string;
};

/** Publicly known firms that commonly hire for campus / new-grad roles. */
const COMPANIES: CompanySeed[] = [
  { name: "Google", location: "Bengaluru / Hyderabad / remote hybrid", blurb: "Build products used by billions. Strong emphasis on CS fundamentals, clean design, and scalable systems." },
  { name: "Microsoft", location: "Hyderabad / Bengaluru / Noida", blurb: "Cloud, productivity, and AI platforms. Values ownership, collaboration, and shipping production quality." },
  { name: "Amazon", location: "Bengaluru / Hyderabad", blurb: "Customer-obsessed engineering culture. Expect ownership, operational excellence, and high bar for code quality." },
  { name: "Meta", location: "Bengaluru / remote hybrid", blurb: "Social infrastructure at massive scale. Focus on impact, rapid iteration, and strong coding interviews." },
  { name: "Apple", location: "Hyderabad / Bengaluru", blurb: "Hardware-software integration and privacy-first products. High craft standards and attention to detail." },
  { name: "Uber", location: "Bengaluru / Hyderabad", blurb: "Marketplace and logistics systems. Real-time data, reliability, and mobile-first experiences." },
  { name: "Stripe", location: "Remote / Bengaluru", blurb: "Financial infrastructure for the internet. API design, reliability, and developer experience matter deeply." },
  { name: "Atlassian", location: "Bengaluru", blurb: "Collaboration tools for teams. Product sense, distributed systems, and clear communication." },
  { name: "Adobe", location: "Noida / Bengaluru", blurb: "Creative cloud and enterprise software. Full-stack product engineering with design-system rigor." },
  { name: "Salesforce", location: "Hyderabad / Bengaluru", blurb: "CRM platform at enterprise scale. Apex/Java/JS ecosystems, multi-tenant architecture, and cloud services." },
  { name: "Oracle", location: "Bengaluru / Hyderabad", blurb: "Cloud infrastructure and enterprise databases. Systems thinking, performance, and reliability." },
  { name: "LinkedIn", location: "Bengaluru", blurb: "Professional network and economic graph. Data-heavy products, recommendations, and large-scale services." },
  { name: "Flipkart", location: "Bengaluru", blurb: "India e-commerce at scale. High throughput systems, mobile apps, and supply-chain tech." },
  { name: "Swiggy", location: "Bengaluru", blurb: "Food and quick commerce logistics. Real-time routing, consumer apps, and experimentation culture." },
  { name: "Razorpay", location: "Bengaluru", blurb: "Payments and fintech APIs. Security, compliance, and high-availability payment rails." },
  { name: "CRED", location: "Bengaluru", blurb: "Fintech consumer product. Craft-focused engineering, mobile excellence, and growth systems." },
  { name: "Databricks", location: "Remote / Bengaluru", blurb: "Lakehouse platform for analytics and AI. Distributed data systems and developer tooling." },
  { name: "NVIDIA", location: "Bengaluru / Pune", blurb: "Accelerated computing and AI platforms. Performance, CUDA/ecosystem awareness, and systems depth." },
  { name: "Bloomberg", location: "Pune / remote hybrid", blurb: "Financial data and analytics terminal. Low-latency systems, correctness, and domain learning." },
  { name: "DE Shaw", location: "Hyderabad", blurb: "Technology-driven investment firm. Strong algorithms, software craftsmanship, and quantitative culture." },
];

type RoleBlueprint = {
  id: RoleId;
  title: string;
  about: string;
  responsibilities: string[];
  requirements: string[];
  niceToHave: string[];
  stack: string[];
  interviewFocus: string[];
};

const ROLE_BLUEPRINTS: RoleBlueprint[] = [
  {
    id: "sde-intern",
    title: "Software Development Engineer Intern",
    about: "Summer / internship track for students. You will ship features with a mentor on a production team.",
    responsibilities: [
      "Own a scoped feature or service improvement end-to-end with mentor support",
      "Write production-quality code, unit tests, and basic design docs",
      "Participate in code reviews, standups, and on-call shadowing where applicable",
      "Debug issues using logs, metrics, and local reproduction",
      "Present internship work in a final demo or write-up",
    ],
    requirements: [
      "Pursuing BE/BTech/MTech in CS or related field; available for full-time internship duration",
      "Strong DSA fundamentals (arrays, trees, graphs, DP) and comfort coding in one of Java/C++/Python/JS/TS",
      "Understanding of OOP, basic system design, and Git",
      "Ability to learn a large codebase quickly and communicate clearly",
      "At least one project, open-source contribution, or internship showing shipped code",
    ],
    niceToHave: [
      "Prior internship or open-source PRs",
      "Exposure to cloud (AWS/GCP/Azure), Docker, or CI/CD",
      "Hackathon wins or competitive programming experience",
    ],
    stack: ["Java", "Python", "TypeScript", "React", "SQL", "Git", "REST"],
    interviewFocus: ["DSA coding rounds", "resume projects deep-dive", "behavioral / ownership"],
  },
  {
    id: "software-engineer",
    title: "Software Engineer (New Grad / Entry)",
    about: "Full-time new-grad SWE role building product features and services used by millions.",
    responsibilities: [
      "Design, implement, and maintain product features across the stack as needed",
      "Improve reliability, performance, and observability of services you own",
      "Collaborate with PMs, designers, and other engineers on specs and trade-offs",
      "Write tests, review code, and participate in on-call rotations after ramp-up",
      "Document designs and share knowledge with the team",
    ],
    requirements: [
      "BE/BTech/MTech in CS or equivalent practical experience",
      "Strong problem-solving and coding skills (medium–hard DSA comfort)",
      "Solid grasp of data structures, algorithms, and complexity analysis",
      "Experience building non-trivial projects (web, mobile, systems, or ML productization)",
      "Clear written and verbal communication",
    ],
    niceToHave: [
      "Internship at a product company",
      "Familiarity with distributed systems basics (caching, queues, load balancing)",
      "Contributions to open source or production side projects",
    ],
    stack: ["Java", "Go", "Python", "TypeScript", "React", "PostgreSQL", "Kafka", "Kubernetes"],
    interviewFocus: ["multi-round coding", "system design intro", "behavioral"],
  },
  {
    id: "backend-engineer",
    title: "Backend Engineer",
    about: "Build and scale APIs, data pipelines, and services that power core product workflows.",
    responsibilities: [
      "Design and implement REST/gRPC APIs and domain services",
      "Model data in SQL/NoSQL stores and optimize queries under load",
      "Improve latency, throughput, and failure handling for critical paths",
      "Integrate message queues, caches, and third-party services",
      "Define SLOs, add metrics/tracing, and participate in incident response",
    ],
    requirements: [
      "Strong coding skills in Java, Go, Python, or Node.js",
      "Understanding of HTTP, authentication, and API design",
      "Hands-on SQL and schema design experience",
      "Knowledge of concurrency, caching, and basic distributed systems trade-offs",
      "Ability to write tests and reason about edge cases",
    ],
    niceToHave: [
      "Experience with Kafka/RabbitMQ, Redis, Postgres at scale",
      "Docker/Kubernetes deployment experience",
      "Prior work on payments, identity, or high-QPS services",
    ],
    stack: ["Java", "Go", "Python", "Node.js", "PostgreSQL", "Redis", "Kafka", "gRPC", "Docker"],
    interviewFocus: ["coding", "backend system design", "SQL / debugging"],
  },
  {
    id: "frontend-engineer",
    title: "Frontend Engineer",
    about: "Craft fast, accessible web UIs and design systems that feel polished on every device.",
    responsibilities: [
      "Build responsive UI with modern component frameworks",
      "Partner with design on interaction details, a11y, and visual quality",
      "Own performance budgets (LCP, INP, bundle size) for key pages",
      "Integrate frontend with backend APIs and manage client state thoughtfully",
      "Improve design-system components and developer ergonomics",
    ],
    requirements: [
      "Strong JavaScript/TypeScript fundamentals",
      "Production experience with React, Next.js, Vue, or similar",
      "Solid HTML/CSS, layout, and responsive design skills",
      "Understanding of browser performance and accessibility basics",
      "Portfolio or shipped projects demonstrating UI craft",
    ],
    niceToHave: [
      "Design system or component library work",
      "Animation (Framer Motion / CSS) and micro-interaction polish",
      "Experience with testing libraries and Storybook",
    ],
    stack: ["TypeScript", "React", "Next.js", "Tailwind", "CSS", "Jest", "Playwright"],
    interviewFocus: ["JS/TS coding", "UI system design", "portfolio deep-dive"],
  },
  {
    id: "ml-engineer",
    title: "Machine Learning Engineer",
    about: "Take models from notebooks to production: training pipelines, serving, and monitoring.",
    responsibilities: [
      "Train, evaluate, and iterate models for ranking, NLP, CV, or recommendations",
      "Build reliable training and inference pipelines",
      "Productionize models with latency, cost, and quality constraints",
      "Partner with data scientists and product on metrics and offline/online eval",
      "Monitor drift, failures, and model quality in production",
    ],
    requirements: [
      "Strong Python and solid CS fundamentals",
      "Applied ML experience (projects or internships) with PyTorch or TensorFlow",
      "Comfort with data wrangling (pandas, SQL) and experimental rigor",
      "Understanding of train/val/test leakage, metrics, and baselines",
      "Ability to write production-quality code, not just notebooks",
    ],
    niceToHave: [
      "Experience with feature stores, MLOps, or model serving (TorchServe, Triton, FastAPI)",
      "Distributed training or GPU optimization exposure",
      "LLM fine-tuning / RAG systems experience",
    ],
    stack: ["Python", "PyTorch", "TensorFlow", "scikit-learn", "SQL", "Docker", "FastAPI", "Spark"],
    interviewFocus: ["coding", "ML fundamentals", "applied case study"],
  },
  {
    id: "data-scientist",
    title: "Data Scientist",
    about: "Turn ambiguous business questions into experiments, models, and clear recommendations.",
    responsibilities: [
      "Define metrics, dashboards, and analytical frameworks for product areas",
      "Run A/B tests and causal analyses; communicate results to stakeholders",
      "Build predictive models and segmentation where they create product value",
      "Partner with engineering to instrument events and ensure data quality",
      "Present insights that drive roadmap and go-to-market decisions",
    ],
    requirements: [
      "Strong statistics and probability foundations",
      "Proficiency in Python or R and advanced SQL",
      "Experience with experimental design and hypothesis testing",
      "Ability to tell a clear story with data for non-technical audiences",
      "Projects showing end-to-end analysis (question → data → insight → action)",
    ],
    niceToHave: [
      "Causal inference, uplift modeling, or marketplace analytics",
      "Dashboarding (Looker, Tableau, Mode) experience",
      "Basic ML modeling for forecasting or classification",
    ],
    stack: ["Python", "SQL", "pandas", "scikit-learn", "R", "A/B testing", "Looker", "dbt"],
    interviewFocus: ["SQL", "stats / product sense", "case study"],
  },
  {
    id: "quant",
    title: "Quantitative Researcher / Quant Developer",
    about: "Research and implement data-driven trading or risk models in a technology-first firm.",
    responsibilities: [
      "Research signals, features, and models using large market or alternative datasets",
      "Implement research code that is correct, fast, and reproducible",
      "Backtest strategies carefully with realistic constraints and costs",
      "Collaborate with traders/engineers to productionize research",
      "Write clear research notes documenting assumptions and failure modes",
    ],
    requirements: [
      "Exceptional quantitative and problem-solving ability (math, stats, algorithms)",
      "Strong programming skills in Python and/or C++",
      "Comfort with probability, linear algebra, and statistical inference",
      "Evidence of research rigor (projects, papers, contests, or internships)",
      "Ability to work independently on open-ended problems",
    ],
    niceToHave: [
      "Prior work with time-series, market microstructure, or optimization",
      "Competitive programming or math olympiad background",
      "Experience with low-latency systems or large-scale data processing",
    ],
    stack: ["Python", "C++", "NumPy", "pandas", "SQL", "statistics", "Linux"],
    interviewFocus: ["brainteasers / probability", "coding", "research discussion"],
  },
  {
    id: "product-manager",
    title: "Associate / APM Product Manager",
    about: "Own problem discovery, prioritization, and delivery for a product surface with eng and design partners.",
    responsibilities: [
      "Identify user problems through research, data, and stakeholder input",
      "Write crisp PRDs and success metrics; drive alignment across teams",
      "Prioritize roadmap trade-offs under resource constraints",
      "Partner with eng/design from discovery through launch and iteration",
      "Run launches, measure outcomes, and propose next experiments",
    ],
    requirements: [
      "Strong analytical thinking and structured communication",
      "Comfort with product metrics, funnels, and basic SQL or spreadsheet analysis",
      "Evidence of ownership (startups, PORs, products, or complex projects)",
      "Ability to work with engineers and understand technical trade-offs at a high level",
      "Clear writing and stakeholder management skills",
    ],
    niceToHave: [
      "Prior internship in PM, consulting, or growth",
      "Shipped a consumer or B2B product (even campus-scale)",
      "Familiarity with design tools and user research methods",
    ],
    stack: ["SQL basics", "Amplitude/Mixpanel", "Figma familiarity", "PRDs", "A/B testing"],
    interviewFocus: ["product sense", "analytical case", "execution / behavioral"],
  },
];

function bullets(lines: string[]) {
  return lines.map((line) => `• ${line}`).join("\n");
}

function buildSampleJd(role: RoleBlueprint, company: CompanySeed, index: number): SampleJd {
  const title = `${role.title} — ${company.name}`;
  const body = [
    `${title}`,
    `Company: ${company.name}`,
    `Location: ${company.location}`,
    ``,
    `About the company`,
    company.blurb,
    ``,
    `About the role`,
    role.about,
    ``,
    `What you will do`,
    bullets(role.responsibilities),
    ``,
    `Minimum qualifications`,
    bullets(role.requirements),
    ``,
    `Preferred qualifications`,
    bullets(role.niceToHave),
    ``,
    `Common tech / tools for this role`,
    role.stack.join(", "),
    ``,
    `Interview focus (typical)`,
    bullets(role.interviewFocus),
    ``,
    `Notes`,
    `Sample JD synthesized from common public campus / new-grad posting patterns for ${role.title} roles at companies similar to ${company.name}. Not an official job posting from ${company.name}. Use as a realistic target brief for placement prep.`,
  ].join("\n");

  return {
    id: `${role.id}-${index + 1}`,
    roleId: role.id,
    company: company.name,
    title: role.title,
    location: company.location,
    body,
  };
}

function buildAllSamples(): Record<RoleId, SampleJd[]> {
  const out = {} as Record<RoleId, SampleJd[]>;
  for (const role of ROLE_BLUEPRINTS) {
    out[role.id] = COMPANIES.map((company, index) => buildSampleJd(role, company, index));
  }
  return out;
}

export const SAMPLE_JDS_BY_ROLE = buildAllSamples();

export function getSamplesForRole(roleId: RoleId | ""): SampleJd[] {
  if (!roleId) return [];
  return SAMPLE_JDS_BY_ROLE[roleId] ?? [];
}

export function findRoleIdByLabel(label: string): RoleId | "" {
  const normalized = label.trim().toLowerCase();
  if (!normalized) return "";
  const exact = ROLE_OPTIONS.find((role) => role.label.toLowerCase() === normalized || role.short.toLowerCase() === normalized);
  if (exact) return exact.id;
  const partial = ROLE_OPTIONS.find(
    (role) => normalized.includes(role.short.toLowerCase()) || role.label.toLowerCase().includes(normalized),
  );
  return partial?.id ?? "";
}
