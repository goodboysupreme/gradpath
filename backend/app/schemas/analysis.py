from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.schemas.base import CamelContractModel, ContractModel
from app.schemas.domain import CareerTrack

SkillLabel = Annotated[str, Field(min_length=2, max_length=160)]
AdviceText = Annotated[str, Field(min_length=2, max_length=500)]
BulletText = Annotated[str, Field(min_length=8, max_length=500)]


class IntakeMode(StrEnum):
    RESUME = "resume"
    UPLOAD = "upload"
    PASTE = "paste"
    PROFILE = "profile"


class GapImportance(StrEnum):
    CRITICAL = "critical"
    NICE_TO_HAVE = "nice-to-have"


class ProjectEffort(StrEnum):
    WEEKEND = "weekend"
    ONE_TO_TWO_WEEKS = "1-2 weeks"
    MONTH = "month"


class PrepPriority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CitationSource(StrEnum):
    RESUME = "resume"
    JD = "jd"


class CitationOutputKind(StrEnum):
    STRENGTH = "strength"
    GAP = "gap"
    RESUME_BULLET = "resume_bullet"


class ScoreConfidence(StrEnum):
    INSUFFICIENT = "insufficient"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReadinessAnalysisRequest(CamelContractModel):
    jd_text: str = Field(min_length=50, max_length=30_000)
    resume_text: str = Field(min_length=50, max_length=30_000)
    target_company: str | None = Field(default=None, max_length=200)
    target_role: str | None = Field(default=None, max_length=200)
    intake_mode: IntakeMode = IntakeMode.RESUME
    season: str | None = Field(default=None, max_length=100)
    track: CareerTrack | None = None
    allow_remote_processing: Literal[True]

    @model_validator(mode="after")
    def profile_has_enough_context(self) -> "ReadinessAnalysisRequest":
        if self.intake_mode is IntakeMode.PROFILE and len(self.resume_text) < 80:
            raise ValueError("profile text must contain at least 80 characters")
        return self


class PreAnalysisSummary(CamelContractModel):
    rough_match_percentage: float = Field(ge=0, le=100)
    total_matched: int = Field(ge=0)
    total_missing: int = Field(ge=0)


class AnalysisSignals(CamelContractModel):
    rough_match_percentage: float = Field(ge=0, le=100)
    matched_skills: tuple[str, ...]
    missing_skills: tuple[str, ...]

    @property
    def total_matched(self) -> int:
        return len(self.matched_skills)

    @property
    def total_missing(self) -> int:
        return len(self.missing_skills)


class AnalysisPrompt(ContractModel):
    request: ReadinessAnalysisRequest
    signals: AnalysisSignals


class StrengthResult(CamelContractModel):
    skill: SkillLabel
    evidence: str = Field(min_length=8, max_length=1_000)


class GapResult(CamelContractModel):
    skill: SkillLabel
    importance: GapImportance
    why: str = Field(min_length=8, max_length=1_000)


class SuggestedProject(CamelContractModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=500)
    skills_covered: tuple[SkillLabel, ...] = Field(min_length=1, max_length=10)
    effort: ProjectEffort


class RoadmapPhase(CamelContractModel):
    phase: str = Field(min_length=2, max_length=120)
    timeline: str = Field(min_length=2, max_length=120)
    actions: tuple[AdviceText, ...] = Field(min_length=1, max_length=5)


class PrepTopic(CamelContractModel):
    topic: str = Field(min_length=2, max_length=160)
    priority: PrepPriority
    reason: str = Field(min_length=8, max_length=500)


class GroundedStrength(CamelContractModel):
    skill: SkillLabel
    evidence_quote: str = Field(min_length=8, max_length=1_000)


class GroundedGap(CamelContractModel):
    skill: SkillLabel
    importance: GapImportance
    why: str = Field(min_length=8, max_length=1_000)
    jd_evidence_quote: str = Field(min_length=8, max_length=1_000)


class GroundedResumeBullet(CamelContractModel):
    text: BulletText
    evidence_quote: str = Field(min_length=8, max_length=1_000)


class GroundedAnalysisDraft(CamelContractModel):
    summary: str = Field(min_length=20, max_length=1_200)
    strengths: tuple[GroundedStrength, ...] = Field(min_length=1, max_length=10)
    gaps: tuple[GroundedGap, ...] = Field(min_length=1, max_length=15)
    projects: tuple[SuggestedProject, ...] = Field(min_length=1, max_length=5)
    quick_wins: tuple[AdviceText, ...] = Field(min_length=1, max_length=10)
    roadmap: tuple[RoadmapPhase, ...] = Field(min_length=1, max_length=5)
    resume_bullets: tuple[GroundedResumeBullet, ...] = Field(min_length=1, max_length=8)
    prep_topics: tuple[PrepTopic, ...] = Field(min_length=1, max_length=10)
    application_strategy: tuple[AdviceText, ...] = Field(min_length=1, max_length=8)


class GroundingCitation(CamelContractModel):
    output_kind: CitationOutputKind
    output_index: int = Field(ge=0)
    source: CitationSource
    quote: str = Field(min_length=8, max_length=1_000)


class ReadinessAnalysisResponse(CamelContractModel):
    match_score: int = Field(ge=0, le=100)
    score_confidence: ScoreConfidence
    summary: str = Field(min_length=20, max_length=1_200)
    strengths: tuple[StrengthResult, ...] = Field(min_length=1, max_length=10)
    gaps: tuple[GapResult, ...] = Field(min_length=1, max_length=15)
    projects: tuple[SuggestedProject, ...] = Field(min_length=1, max_length=5)
    quick_wins: tuple[AdviceText, ...] = Field(min_length=1, max_length=10)
    roadmap: tuple[RoadmapPhase, ...] = Field(min_length=1, max_length=5)
    resume_bullets: tuple[BulletText, ...] = Field(min_length=1, max_length=8)
    prep_topics: tuple[PrepTopic, ...] = Field(min_length=1, max_length=10)
    application_strategy: tuple[AdviceText, ...] = Field(min_length=1, max_length=8)
    pre_analysis: PreAnalysisSummary
    grounding: tuple[GroundingCitation, ...]
    analysis_version: Literal["grounded-v1"] = "grounded-v1"
    analysis_needs_confirmation: Literal[True] = True
    resume_bullets_need_confirmation: Literal[True] = True
