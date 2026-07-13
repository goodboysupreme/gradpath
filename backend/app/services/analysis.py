import re

from app.providers.base import AnalysisProvider
from app.schemas.analysis import (
    AnalysisPrompt,
    CitationOutputKind,
    CitationSource,
    GapResult,
    GroundingCitation,
    PreAnalysisSummary,
    ReadinessAnalysisRequest,
    ReadinessAnalysisResponse,
    ScoreConfidence,
    StrengthResult,
)
from app.services.preanalysis import build_analysis_signals
from app.services.redaction import redact_sensitive_text


class AnalysisGroundingError(RuntimeError):
    pass


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def _validate_quote(quote: str, source: str) -> None:
    if _normalize(quote) not in _normalize(source):
        raise AnalysisGroundingError("provider quote is absent from its source")


_SKILL_CONNECTORS = frozenset({"a", "an", "and", "in", "of", "or", "the", "using", "with"})


def _skill_tokens(value: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z0-9+#.]+", value.casefold())) - _SKILL_CONNECTORS


def _validate_skill_quote(skill: str, quote: str) -> None:
    skill_tokens = _skill_tokens(skill)
    if not skill_tokens or not skill_tokens.issubset(_skill_tokens(quote)):
        raise AnalysisGroundingError("provider skill label is unsupported by its quote")


def _project_closes_a_gap(project_skills: tuple[str, ...], gap_skills: tuple[str, ...]) -> bool:
    normalized_gap_skills = {_normalize(skill) for skill in gap_skills}
    return any(_normalize(skill) in normalized_gap_skills for skill in project_skills)


def _score_confidence(signal_count: int) -> ScoreConfidence:
    if signal_count == 0:
        return ScoreConfidence.INSUFFICIENT
    if signal_count < 3:
        return ScoreConfidence.LOW
    if signal_count < 5:
        return ScoreConfidence.MEDIUM
    return ScoreConfidence.HIGH


async def evaluate_readiness(
    payload: ReadinessAnalysisRequest,
    provider: AnalysisProvider,
) -> ReadinessAnalysisResponse:
    signals = build_analysis_signals(payload.jd_text, payload.resume_text)
    provider_payload = payload.model_copy(
        update={
            "jd_text": redact_sensitive_text(payload.jd_text),
            "resume_text": redact_sensitive_text(payload.resume_text),
        }
    )
    draft = await provider.generate(AnalysisPrompt(request=provider_payload, signals=signals))
    grounded_resume_text = provider_payload.resume_text
    grounded_jd_text = provider_payload.jd_text

    citations: list[GroundingCitation] = []
    strengths: list[StrengthResult] = []
    for index, strength in enumerate(draft.strengths):
        _validate_quote(strength.evidence_quote, grounded_resume_text)
        _validate_skill_quote(strength.skill, strength.evidence_quote)
        strengths.append(StrengthResult(skill=strength.skill, evidence=strength.evidence_quote))
        citations.append(
            GroundingCitation(
                output_kind=CitationOutputKind.STRENGTH,
                output_index=index,
                source=CitationSource.RESUME,
                quote=strength.evidence_quote,
            )
        )

    gaps: list[GapResult] = []
    for index, gap in enumerate(draft.gaps):
        _validate_quote(gap.jd_evidence_quote, grounded_jd_text)
        _validate_skill_quote(gap.skill, gap.jd_evidence_quote)
        gaps.append(GapResult(skill=gap.skill, importance=gap.importance, why=gap.why))
        citations.append(
            GroundingCitation(
                output_kind=CitationOutputKind.GAP,
                output_index=index,
                source=CitationSource.JD,
                quote=gap.jd_evidence_quote,
            )
        )

    gap_skills = tuple(gap.skill for gap in draft.gaps)
    if any(
        not _project_closes_a_gap(project.skills_covered, gap_skills) for project in draft.projects
    ):
        raise AnalysisGroundingError("suggested project does not address a returned gap")

    resume_bullets: list[str] = []
    for index, bullet in enumerate(draft.resume_bullets):
        _validate_quote(bullet.evidence_quote, grounded_resume_text)
        _validate_quote(bullet.text, bullet.evidence_quote)
        resume_bullets.append(bullet.text)
        citations.append(
            GroundingCitation(
                output_kind=CitationOutputKind.RESUME_BULLET,
                output_index=index,
                source=CitationSource.RESUME,
                quote=bullet.evidence_quote,
            )
        )

    return ReadinessAnalysisResponse(
        match_score=round(signals.rough_match_percentage),
        score_confidence=_score_confidence(signals.total_matched + signals.total_missing),
        summary=draft.summary,
        strengths=tuple(strengths),
        gaps=tuple(gaps),
        projects=draft.projects,
        quick_wins=draft.quick_wins,
        roadmap=draft.roadmap,
        resume_bullets=tuple(resume_bullets),
        prep_topics=draft.prep_topics,
        application_strategy=draft.application_strategy,
        pre_analysis=PreAnalysisSummary(
            rough_match_percentage=signals.rough_match_percentage,
            total_matched=signals.total_matched,
            total_missing=signals.total_missing,
        ),
        grounding=tuple(citations),
    )
