import re

from app.schemas.analysis import AnalysisSignals

SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "algorithms": ("algorithms", "algorithmic"),
    "android": ("android",),
    "angular": ("angular",),
    "aws": ("aws", "amazon web services"),
    "azure": ("azure",),
    "c": ("c language",),
    "c#": ("c#", "c sharp"),
    "c++": ("c++", "cpp"),
    "cloud": (
        "cloud computing",
        "cloud infrastructure",
        "cloud platform",
        "cloud services",
    ),
    "computer vision": ("computer vision",),
    "css": ("css",),
    "data structures": ("data structures", "dsa"),
    "deep learning": ("deep learning",),
    "django": ("django",),
    "docker": ("docker",),
    "fastapi": ("fastapi",),
    "flask": ("flask",),
    "gcp": ("gcp", "google cloud"),
    "git": ("git",),
    "go": ("golang", "go language"),
    "graphql": ("graphql",),
    "html": ("html",),
    "iot": ("iot", "internet of things"),
    "java": ("java",),
    "javascript": ("javascript",),
    "kubernetes": ("kubernetes", "k8s"),
    "linux": ("linux",),
    "llm": ("llm", "large language model"),
    "machine learning": ("machine learning",),
    "mongodb": ("mongodb",),
    "multithreading": ("multithreading", "multi-threaded", "multithreaded"),
    "mysql": ("mysql",),
    "next.js": ("next.js", "nextjs"),
    "nlp": ("nlp", "natural language processing"),
    "node.js": ("node.js", "nodejs"),
    "postgresql": ("postgresql", "postgres"),
    "python": ("python",),
    "pytorch": ("pytorch",),
    "rag": ("rag", "retrieval augmented generation"),
    "react": ("react.js", "reactjs", "react framework", "react developer"),
    "redis": ("redis",),
    "rest": ("rest api", "restful"),
    "rust": ("rust",),
    "socket programming": ("socket programming", "sockets"),
    "spring boot": ("spring boot",),
    "sql": ("sql",),
    "system design": ("system design",),
    "tensorflow": ("tensorflow",),
    "typescript": ("typescript",),
    "vue": ("vue", "vue.js"),
    "web": (
        "web application",
        "web applications",
        "web developer",
        "web development",
        "web technologies",
    ),
    "5g": ("5g",),
}


def _contains_alias(text: str, alias: str) -> bool:
    pattern = rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])"
    return re.search(pattern, text) is not None


def _extract_skills(text: str) -> frozenset[str]:
    normalized = text.casefold()
    found: set[str] = set()
    for skill, aliases in SKILL_ALIASES.items():
        if any(_contains_alias(normalized, alias) for alias in aliases):
            found.add(skill)
    return frozenset(found)


def build_analysis_signals(jd_text: str, resume_text: str) -> AnalysisSignals:
    jd_skills = _extract_skills(jd_text)
    resume_skills = _extract_skills(resume_text)
    matched = tuple(sorted(jd_skills & resume_skills))
    missing = tuple(sorted(jd_skills - resume_skills))
    rough_match = round((len(matched) / len(jd_skills)) * 100, 1) if jd_skills else 0.0
    return AnalysisSignals(
        rough_match_percentage=rough_match,
        matched_skills=matched,
        missing_skills=missing,
    )
