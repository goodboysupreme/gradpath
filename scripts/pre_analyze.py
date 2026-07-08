#!/usr/bin/env python3
"""
Resume ⇄ JD Pre-Analyzer (Deterministic)
==========================================
Runs BEFORE the LLM call. Extracts keywords, detects sections,
computes keyword overlap, identifies matched/missing skills, and
emits a JSON summary that shrinks the LLM's job.

Usage:
    python scripts/pre_analyze.py --jd <jd_text_or_file> --resume <resume_text_or_file>
    python scripts/pre_analyze.py --jd-file job.txt --resume-file resume.txt

Output: JSON to stdout (piped into the API route)

The Python script does NOT replace the LLM — it handles the mechanical
work (tokenization, keyword extraction, TF-IDF scoring, section detection)
so the LLM can focus on semantic reasoning, project generation, and nuance.
"""

import argparse
import json
import re
import sys
import math
import os
from collections import Counter
from pathlib import Path

# ── Skill taxonomy (deterministic, no ML) ───────────────────────

SKILL_TAXONOMY = {
    # Languages
    "python", "javascript", "typescript", "java", "go", "golang", "rust", "c++",
    "c#", "ruby", "php", "swift", "kotlin", "scala", "r", "matlab", "perl",
    "bash", "shell", "sql", "html", "css", "dart", "elixir", "haskell", "lua",

    # Frontend
    "react", "next.js", "nextjs", "vue", "vue.js", "nuxt", "angular", "svelte",
    "sveltekit", "solid", "jquery", "redux", "mobx", "zustand", "tailwind",
    "bootstrap", "sass", "scss", "less", "styled-components", "storybook",
    "three.js", "threejs", "d3", "d3.js", "chart.js", "framer-motion", "gsap",

    # Backend
    "node.js", "express", "fastify", "nestjs", "django", "flask", "fastapi",
    "spring", "spring boot", "rails", "laravel", "asp.net", "gin", "fiber",
    "graphql", "grpc", "rest", "websocket", "websockets", "trpc", "tRPC",

    # Databases
    "postgresql", "postgres", "mysql", "mongodb", "redis", "dynamodb",
    "cassandra", "elasticsearch", "supabase", "firebase", "firestore",
    "prisma", "drizzle", "typeorm", "sequelize", "sqlalchemy", "mongoose",
    "neon", "cockroachdb", "sqlite", "mariadb", "influxdb", "clickhouse",

    # Cloud / DevOps
    "aws", "gcp", "azure", "vercel", "netlify", "cloudflare", "docker",
    "kubernetes", "k8s", "terraform", "ansible", "helm", "ci/cd", "github actions",
    "gitlab ci", "jenkins", "circleci", "prometheus", "grafana", "datadog",
    "nginx", "apache", "caddy", "traefik", "linux", "unix",

    # AI / ML
    "machine learning", "deep learning", "nlp", "natural language processing",
    "computer vision", "llm", "llms", "transformers", "pytorch", "tensorflow",
    "keras", "scikit-learn", "sklearn", "pandas", "numpy", "scipy", "matplotlib",
    "seaborn", "jupyter", "huggingface", "langchain", "llamaindex", "openai",
    "anthropic", "rag", "fine-tuning", "fine tuning", "embedding", "embeddings",
    "vector database", "vector db", "pinecone", "weaviate", "chroma",
    "qdrant", "milvus", "tensorrt", "onnx",

    # Mobile
    "react native", "flutter", "ios", "android", "xcode", "swift ui",

    # Architecture / Patterns
    "microservices", "monolith", "serverless", "event-driven", "cqrs",
    "event sourcing", "ddd", "clean architecture", "hexagonal", "soa",
    "rest api", "api design", "rate limiting", "caching", "load balancing",
    "sharding", "replication", "message queue", "kafka", "rabbitmq",
    "redis pub/sub", "sqs", "sns", "eventbridge",

    # Testing
    "jest", "vitest", "pytest", "unittest", "cypress", "playwright",
    "selenium", "testing-library", "mocha", "chai", "junit", "integration testing",
    "e2e testing", "unit testing", "tdd", "test-driven development",

    # Tools / Practices
    "git", "github", "gitlab", "bitbucket", "jira", "confluence", "agile",
    "scrum", "kanban", "ci/cd pipeline", "code review", "pair programming",
    "devops", "sre", "observability", "logging", "monitoring", "alerting",

    # Security
    "oauth", "oauth2", "jwt", "saml", "sso", "rbac", "auth0", "clerk",
    "encryption", "hashing", "bcrypt", "argon2", "penetration testing",
    "security audit", "owasp", "cors", "helmet", "rate limit",

    # Data / Analytics
    "etl", "elt", "data pipeline", "airflow", "dbt", "spark", "hadoop",
    "kafka streams", "flink", "beam", "tableau", "power bi", "looker",
    "bigquery", "snowflake", "data warehouse", "data lake", "data mesh",

    # Soft / Other
    "leadership", "mentorship", "team lead", "product management",
    "stakeholder management", "communication", "presentation", "technical writing",
    "project management", "product sense", "system design", "technical design",
    "architecture review", "incident response", "on-call", "oncall",
}

# Normalize variants → canonical name
CANONICAL_MAP = {
    "golang": "go",
    "nextjs": "next.js",
    "vue.js": "vue",
    "threejs": "three.js",
    "d3.js": "d3",
    "k8s": "kubernetes",
    "postgres": "postgresql",
    "sklearn": "scikit-learn",
    "fine tuning": "fine-tuning",
    "vector db": "vector database",
    "trpc": "tRPC",
    "rest api": "rest",
    "test-driven development": "tdd",
    "ci/cd pipeline": "ci/cd",
    "oncall": "on-call",
    "natural language processing": "nlp",
}

# Resume sections to detect
RESUME_SECTIONS = [
    "experience", "work experience", "professional experience", "employment",
    "education", "skills", "technical skills", "projects", "personal projects",
    "open source", "certifications", "certificates", "awards", "publications",
    "summary", "objective", "profile", "about", "contact", "interests",
    "languages", "volunteer", "leadership",
]

# JD sections to detect
JD_SECTIONS = [
    "requirements", "qualifications", "must have", "must-have", "nice to have",
    "nice-to-have", "preferred", "preferred qualifications", "responsibilities",
    "what you'll do", "what you will do", "about the role", "about the team",
    "about us", "benefits", "perks", "compensation", "salary", "tech stack",
    "technology stack", "who you are", "ideal candidate", "minimum requirements",
    "bonus", "bonus points", "tech requirements",
]

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "must", "shall", "can", "need",
    "this", "that", "these", "those", "i", "you", "he", "she", "it", "we",
    "they", "them", "their", "his", "her", "its", "our", "your", "my",
    "me", "him", "us", "as", "if", "then", "than", "so", "no", "not",
    "yes", "all", "any", "each", "every", "some", "such", "own", "other",
    "into", "through", "during", "before", "after", "above", "below",
    "up", "down", "out", "off", "over", "under", "again", "further",
    "once", "here", "there", "when", "where", "why", "how", "what",
    "which", "who", "whom", "also", "very", "just", "only", "more",
    "most", "able", "about", "across", "after", "among", "between",
    "etc", "eg", "ie", "ex", "including", "via", "per", "vs", "versus",
    "using", "used", "use", "uses", "using", "work", "working", "worked",
    "role", "team", "company", "candidate", "candidates", "you'll", "you will",
    "we're", "we are", "looking", "join", "build", "help", "helping",
    "strong", "good", "great", "excellent", "ability", "experience",
    "years", "year", "plus", "minimum", "maximum", "required", "require",
    "requires", "requirement", "requirements", "preferred", "nice",
    "have", "having", "must", "should", "will", "responsible",
    "responsibilities", "duties", "duty", "task", "tasks",
}


def read_input(arg: str | None, file_arg: str | None) -> str:
    """Read from --file arg, or treat --arg as text / filename"""
    if file_arg:
        path = Path(file_arg)
        if not path.exists():
            print(f"Error: file not found: {file_arg}", file=sys.stderr)
            sys.exit(1)
        return path.read_text(encoding="utf-8", errors="replace")
    if arg:
        # Could be a filename or raw text
        if len(arg) < 200 and "." in arg and Path(arg).exists():
            return Path(arg).read_text(encoding="utf-8", errors="replace")
        return arg
    return ""


def extract_skills(text: str) -> dict[str, int]:
    """Extract known skills from text. Returns {canonical_skill: occurrences}."""
    text_lower = text.lower()
    found: dict[str, int] = {}

    for skill in SKILL_TAXONOMY:
        # Word boundary match for single-word skills
        # For multi-word, just check substring presence
        if " " in skill or "." in skill or "-" in skill:
            count = text_lower.count(skill)
            if count > 0:
                canonical = CANONICAL_MAP.get(skill, skill)
                found[canonical] = found.get(canonical, 0) + count
        else:
            # Use regex word boundary for single words
            pattern = r"\b" + re.escape(skill) + r"\b"
            matches = re.findall(pattern, text_lower)
            if matches:
                canonical = CANONICAL_MAP.get(skill, skill)
                found[canonical] = found.get(canonical, 0) + len(matches)

    return found


def extract_keywords_tfidf(text: str, top_n: int = 40) -> list[tuple[str, float]]:
    """
    Simple TF-based keyword extraction (no IDF corpus, just TF with
    stopword removal and length filtering). Good enough for pre-analysis.
    """
    # Tokenize
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9+#.]{1,30}", text.lower())
    # Filter stopwords + short tokens
    filtered = [
        t for t in tokens
        if t not in STOPWORDS and len(t) >= 2 and not t.isdigit()
    ]

    # Bigrams for multi-word terms
    bigrams = [
        f"{filtered[i]} {filtered[i+1]}"
        for i in range(len(filtered) - 1)
        if filtered[i] not in STOPWORDS and filtered[i+1] not in STOPWORDS
    ]

    # Count
    tf_uni = Counter(filtered)
    tf_bi = Counter(bigrams)

    # Score: unigrams weight 1, bigrams weight 1.5 (capture more specific terms)
    scored: list[tuple[str, float]] = []
    for term, count in tf_uni.items():
        scored.append((term, count))
    for term, count in tf_bi.items():
        # Only keep bigrams that appear at least twice or contain a known skill
        if count >= 2 or any(s in term for s in SKILL_TAXONOMY):
            scored.append((term, count * 1.5))

    # Sort by score desc, then alphabetical for stability
    scored.sort(key=lambda x: (-x[1], x[0]))
    return scored[:top_n]


def detect_sections(text: str, section_list: list[str]) -> list[str]:
    """Detect which sections are present in the text (case-insensitive)."""
    text_lower = text.lower()
    found: list[str] = []
    for section in section_list:
        # Look for section headers — line starts with the section name
        # or it's a heading-like pattern (all caps, or followed by colon/newline)
        pattern = r"(?:^|\n)\s*[" + re.escape(section[0].upper() + section[0].lower()) + r"]" + re.escape(section[1:]) + r"\s*[:\n]"
        if re.search(pattern, text_lower, re.IGNORECASE):
            found.append(section)
        elif section in text_lower and section in section_list[:10]:
            # Fallback: just substring for common sections
            found.append(section)
    return list(set(found))


def compute_keyword_overlap(
    jd_skills: dict[str, int],
    resume_skills: dict[str, int],
) -> tuple[list[str], list[str], list[str], float]:
    """
    Compute overlap between JD skills and resume skills.
    Returns: (matched, missing, extra_in_resume, percentage)
    """
    jd_set = set(jd_skills.keys())
    resume_set = set(resume_skills.keys())

    matched = sorted(jd_set & resume_set)
    missing = sorted(jd_set - resume_set)
    extra = sorted(resume_set - jd_set)

    if not jd_set:
        return matched, missing, extra, 0.0

    # Weight by JD frequency — critical skills mentioned more in JD
    total_weight = sum(jd_skills.values())
    matched_weight = sum(jd_skills[k] for k in matched)
    percentage = round((matched_weight / total_weight) * 100, 1) if total_weight else 0.0

    return matched, missing, extra, percentage


def run_pre_analysis(jd_text: str, resume_text: str) -> dict:
    """Main pre-analysis function."""
    # 1. Extract skills from both
    jd_skills = extract_skills(jd_text)
    resume_skills = extract_skills(resume_text)

    # 2. Extract TF-IDF-ish keywords
    jd_kw = extract_keywords_tfidf(jd_text, top_n=40)
    resume_kw = extract_keywords_tfidf(resume_text, top_n=40)

    # 3. Compute overlap
    matched, missing, extra, rough_pct = compute_keyword_overlap(jd_skills, resume_skills)

    # 4. Score individual JD keywords by frequency (how critical)
    jd_keyword_scores: dict[str, float] = {}
    total_jd = sum(jd_skills.values()) if jd_skills else 1
    for skill, count in sorted(jd_skills.items(), key=lambda x: -x[1]):
        jd_keyword_scores[skill] = round(count / total_jd, 4)

    # 5. Detect sections
    resume_sections = detect_sections(resume_text, RESUME_SECTIONS)
    jd_sections = detect_sections(jd_text, JD_SECTIONS)

    return {
        "jd_keywords": [kw[0] for kw in jd_kw],
        "resume_keywords": [kw[0] for kw in resume_kw],
        "matched_keywords": matched,
        "missing_keywords": missing,
        "extra_resume_keywords": extra,
        "jd_keyword_scores": jd_keyword_scores,
        "rough_match_percentage": rough_pct,
        "resume_sections_found": resume_sections,
        "jd_sections_found": jd_sections,
        "total_jd_keywords": len(jd_skills),
        "total_resume_keywords": len(resume_skills),
        "total_matched": len(matched),
        "total_missing": len(missing),
    }


def main():
    parser = argparse.ArgumentParser(description="Pre-analyze JD vs Resume")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--jd", type=str, help="JD text or filename")
    group.add_argument("--jd-file", type=str, help="File containing JD text")
    group2 = parser.add_mutually_exclusive_group()
    group2.add_argument("--resume", type=str, help="Resume text or filename")
    group2.add_argument("--resume-file", type=str, help="File containing resume text")
    parser.add_argument("--output", "-o", type=str, help="Output file (default: stdout)")
    args = parser.parse_args()

    jd_text = read_input(args.jd, args.jd_file)
    resume_text = read_input(args.resume, args.resume_file)

    if not jd_text or not resume_text:
        print("Error: both JD and resume text are required", file=sys.stderr)
        sys.exit(1)

    result = run_pre_analysis(jd_text, resume_text)

    output = json.dumps(result, indent=2, ensure_ascii=False)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Pre-analysis saved to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
