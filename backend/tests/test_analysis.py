import json
from typing import Any, cast

import httpx2 as httpx
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import Settings
from app.main import create_app
from app.providers.base import AnalysisProvider, AnalysisProviderError
from app.providers.openrouter import OpenRouterAnalysisProvider
from app.schemas.analysis import AnalysisPrompt, GroundedAnalysisDraft
from app.services.preanalysis import build_analysis_signals

INTERNAL_TOKEN = "test-internal-token-that-is-long-enough"
RESUME_EVIDENCE = "Built a FastAPI service with PostgreSQL for 500 student records using Python."
JD_EVIDENCE = "Candidates must solve data structures problems in technical interviews."


class FakeAnalysisProvider:
    def __init__(
        self,
        draft: GroundedAnalysisDraft | None = None,
        error: AnalysisProviderError | None = None,
    ) -> None:
        self.draft = draft
        self.error = error
        self.prompts: list[AnalysisPrompt] = []

    async def generate(self, prompt: AnalysisPrompt) -> GroundedAnalysisDraft:
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        if self.draft is None:
            raise AssertionError("fake provider has no draft")
        return self.draft


def valid_request() -> dict[str, object]:
    return {
        "jdText": (f"This internship requires Python, FastAPI, and PostgreSQL. {JD_EVIDENCE}"),
        "resumeText": (
            "Projects\n"
            f"Campus API: {RESUME_EVIDENCE} "
            "Documented the API and deployed it for a student team."
        ),
        "targetCompany": "Samsung Research",
        "targetRole": "Developer Intern",
        "intakeMode": "resume",
        "season": "SI",
        "track": "si",
        "allowRemoteProcessing": True,
    }


def valid_draft_data() -> dict[str, Any]:
    return {
        "summary": (
            "The candidate has relevant backend evidence, while data structures remains the "
            "largest interview-readiness gap."
        ),
        "strengths": [
            {
                "skill": "FastAPI and PostgreSQL",
                "evidenceQuote": RESUME_EVIDENCE,
            }
        ],
        "gaps": [
            {
                "skill": "Data structures",
                "importance": "critical",
                "why": "The role explicitly tests data structures during technical interviews.",
                "jdEvidenceQuote": JD_EVIDENCE,
            }
        ],
        "projects": [
            {
                "title": "Algorithm practice tracker",
                "description": "Build a small tracker that records solved problems and patterns.",
                "skillsCovered": ["Data structures"],
                "effort": "weekend",
            }
        ],
        "quickWins": ["Move the backend project above less relevant coursework."],
        "roadmap": [
            {
                "phase": "Interview foundation",
                "timeline": "7 days",
                "actions": ["Practice arrays, trees, and graph traversal daily."],
            }
        ],
        "resumeBullets": [
            {
                "text": RESUME_EVIDENCE,
                "evidenceQuote": RESUME_EVIDENCE,
            }
        ],
        "prepTopics": [
            {
                "topic": "Data structures",
                "priority": "high",
                "reason": "It is an explicit technical interview requirement.",
            }
        ],
        "applicationStrategy": ["Lead with the backend project and prepare its design trade-offs."],
    }


def valid_draft() -> GroundedAnalysisDraft:
    return GroundedAnalysisDraft.model_validate(valid_draft_data())


def settings(*, provider_key: str | None = None) -> Settings:
    return Settings(
        internal_api_token=SecretStr(INTERNAL_TOKEN),
        openrouter_api_key=SecretStr(provider_key) if provider_key else None,
        openrouter_model="test/approved-model",
    )


def post_analysis(
    provider: AnalysisProvider,
    payload: dict[str, object],
    *,
    include_token: bool = True,
) -> httpx.Response:
    headers = {"X-GradPath-Internal-Token": INTERNAL_TOKEN} if include_token else {}
    with TestClient(create_app(settings=settings(), analysis_provider=provider)) as client:
        return client.post("/api/v1/analyses/evaluate", json=payload, headers=headers)


def test_analysis_is_grounded_and_legacy_response_compatible() -> None:
    provider = FakeAnalysisProvider(valid_draft())

    response = post_analysis(provider, valid_request())

    assert response.status_code == 200
    result = response.json()
    assert {
        "matchScore",
        "summary",
        "strengths",
        "gaps",
        "projects",
        "quickWins",
        "roadmap",
        "resumeBullets",
        "prepTopics",
        "applicationStrategy",
        "preAnalysis",
    }.issubset(result)
    assert result["matchScore"] == 75
    assert result["scoreConfidence"] == "medium"
    assert result["strengths"] == [{"skill": "FastAPI and PostgreSQL", "evidence": RESUME_EVIDENCE}]
    assert result["projects"][0]["skillsCovered"] == ["Data structures"]
    assert result["resumeBullets"] == [RESUME_EVIDENCE]
    assert result["preAnalysis"] == {
        "roughMatchPercentage": 75.0,
        "totalMatched": 3,
        "totalMissing": 1,
    }
    assert result["analysisVersion"] == "grounded-v1"
    assert result["analysisNeedsConfirmation"] is True
    assert result["resumeBulletsNeedConfirmation"] is True
    assert result["grounding"] == [
        {
            "outputKind": "strength",
            "outputIndex": 0,
            "source": "resume",
            "quote": RESUME_EVIDENCE,
        },
        {
            "outputKind": "gap",
            "outputIndex": 0,
            "source": "jd",
            "quote": JD_EVIDENCE,
        },
        {
            "outputKind": "resume_bullet",
            "outputIndex": 0,
            "source": "resume",
            "quote": RESUME_EVIDENCE,
        },
    ]
    assert len(provider.prompts) == 1


def test_analysis_requires_internal_authentication() -> None:
    provider = FakeAnalysisProvider(valid_draft())

    response = post_analysis(provider, valid_request(), include_token=False)

    assert response.status_code == 401
    assert provider.prompts == []


def test_analysis_requires_explicit_remote_processing_consent() -> None:
    provider = FakeAnalysisProvider(valid_draft())
    payload = valid_request()
    del payload["allowRemoteProcessing"]

    response = post_analysis(provider, payload)

    assert response.status_code == 422
    assert provider.prompts == []


def test_analysis_fails_closed_when_internal_auth_is_not_configured() -> None:
    provider = FakeAnalysisProvider(valid_draft())
    unconfigured_settings = Settings(internal_api_token=None)

    with TestClient(
        create_app(settings=unconfigured_settings, analysis_provider=provider)
    ) as client:
        response = client.post(
            "/api/v1/analyses/evaluate",
            json=valid_request(),
            headers={"X-GradPath-Internal-Token": INTERNAL_TOKEN},
        )

    assert response.status_code == 503
    assert response.json() == {"detail": "Internal API authentication is not configured"}
    assert provider.prompts == []


def test_analysis_fails_closed_when_internal_auth_token_is_too_short() -> None:
    provider = FakeAnalysisProvider(valid_draft())
    insecure_settings = Settings(internal_api_token=SecretStr("short-token"))

    with TestClient(create_app(settings=insecure_settings, analysis_provider=provider)) as client:
        response = client.post(
            "/api/v1/analyses/evaluate",
            json=valid_request(),
            headers={"X-GradPath-Internal-Token": "short-token"},
        )

    assert response.status_code == 503
    assert response.json() == {"detail": "Internal API authentication is not configured"}
    assert provider.prompts == []


def test_analysis_rejects_short_or_unknown_input_before_provider() -> None:
    provider = FakeAnalysisProvider(valid_draft())
    payload = valid_request()
    payload["jdText"] = "too short"
    payload["inventedField"] = True

    response = post_analysis(provider, payload)

    assert response.status_code == 422
    assert provider.prompts == []


def test_analysis_rejects_an_unsupported_strength_quote() -> None:
    data = valid_draft_data()
    data["strengths"] = [
        {
            "skill": "Kubernetes",
            "evidenceQuote": "Deployed Kubernetes clusters across three regions.",
        }
    ]
    provider = FakeAnalysisProvider(GroundedAnalysisDraft.model_validate(data))

    response = post_analysis(provider, valid_request())

    assert response.status_code == 502
    assert response.json() == {"detail": "AI analysis was not grounded in supplied evidence"}


def test_analysis_rejects_an_unrelated_claim_with_a_valid_quote() -> None:
    data = valid_draft_data()
    data["strengths"] = [
        {
            "skill": "Google Kubernetes leadership",
            "evidenceQuote": RESUME_EVIDENCE,
        }
    ]
    provider = FakeAnalysisProvider(GroundedAnalysisDraft.model_validate(data))

    response = post_analysis(provider, valid_request())

    assert response.status_code == 502
    assert response.json() == {"detail": "AI analysis was not grounded in supplied evidence"}


def test_analysis_rejects_an_invented_resume_claim_even_with_a_reused_number() -> None:
    data = valid_draft_data()
    data["resumeBullets"] = [
        {
            "text": "Led a Kubernetes migration at Google for 500 customers.",
            "evidenceQuote": RESUME_EVIDENCE,
        }
    ]
    provider = FakeAnalysisProvider(GroundedAnalysisDraft.model_validate(data))

    response = post_analysis(provider, valid_request())

    assert response.status_code == 502


def test_analysis_redacts_contact_data_before_remote_processing() -> None:
    provider = FakeAnalysisProvider(valid_draft())
    payload = valid_request()
    payload["resumeText"] = (
        f"{payload['resumeText']}\n"
        "Email: student@example.com\n"
        "Phone: +91 98765 43210\n"
        "BITS ID: 2024A7PS1234P\n"
        "Portfolio: https://example.com/student\n"
        "LinkedIn: linkedin.com/in/student"
    )

    response = post_analysis(provider, payload)

    assert response.status_code == 200
    outbound_resume = provider.prompts[0].request.resume_text
    assert "student@example.com" not in outbound_resume
    assert "98765" not in outbound_resume
    assert "2024A7PS1234P" not in outbound_resume
    assert "https://example.com/student" not in outbound_resume
    assert "linkedin.com/in/student" not in outbound_resume
    assert "[REDACTED_EMAIL]" in outbound_resume


def test_redacted_evidence_is_validated_and_returned_without_original_pii() -> None:
    original_evidence = (
        "Published a FastAPI project portfolio at https://example.com/student for reviewers."
    )
    redacted_evidence = "Published a FastAPI project portfolio at [REDACTED_URL] for reviewers."
    payload = valid_request()
    payload["resumeText"] = f"Projects\n{original_evidence} Additional context for this profile."
    data = valid_draft_data()
    data["strengths"] = [{"skill": "FastAPI", "evidenceQuote": redacted_evidence}]
    data["resumeBullets"] = [{"text": redacted_evidence, "evidenceQuote": redacted_evidence}]
    provider = FakeAnalysisProvider(GroundedAnalysisDraft.model_validate(data))

    response = post_analysis(provider, payload)

    assert response.status_code == 200
    assert "https://example.com/student" not in response.text
    assert "[REDACTED_URL]" in response.text


def test_unrecognized_niche_jd_gets_a_server_controlled_insufficient_score() -> None:
    jd_evidence = "Candidates must practice ontological lattice reconciliation during interviews."
    resume_evidence = (
        "Catalogued archival specimens with consistent metadata for a campus collection."
    )
    payload = valid_request()
    payload["jdText"] = f"Specialist internship. {jd_evidence}"
    payload["resumeText"] = f"Selected experience. {resume_evidence}"
    data = valid_draft_data()
    data["strengths"] = [{"skill": "Metadata", "evidenceQuote": resume_evidence}]
    data["gaps"] = [
        {
            "skill": "Ontological lattice",
            "importance": "critical",
            "why": "This specialist method is the central stated interview requirement.",
            "jdEvidenceQuote": jd_evidence,
        }
    ]
    data["projects"] = [
        {
            "title": "Lattice reconciliation sandbox",
            "description": "Build a small sandbox to compare reconciliation approaches.",
            "skillsCovered": ["Ontological lattice"],
            "effort": "weekend",
        }
    ]
    data["resumeBullets"] = [{"text": resume_evidence, "evidenceQuote": resume_evidence}]
    provider = FakeAnalysisProvider(GroundedAnalysisDraft.model_validate(data))

    response = post_analysis(provider, payload)

    assert response.status_code == 200
    assert response.json()["matchScore"] == 0
    assert response.json()["scoreConfidence"] == "insufficient"


def test_preanalysis_ignores_ambiguous_nontechnical_aliases() -> None:
    signals = build_analysis_signals(
        "Our vision is to react quickly to the rest of the web and cloud market.",
        "Our vision is to react quickly to the rest of the web and cloud market.",
    )

    assert signals.rough_match_percentage == 0
    assert signals.matched_skills == ()
    assert signals.missing_skills == ()


def test_preanalysis_canonicalizes_aws_without_double_counting_web() -> None:
    signals = build_analysis_signals(
        "The engineer will deploy services on Amazon Web Services.",
        "Deployed production services using AWS.",
    )

    assert signals.rough_match_percentage == 100
    assert signals.matched_skills == ("aws",)
    assert signals.missing_skills == ()


def test_analysis_rejects_projects_that_do_not_close_a_gap() -> None:
    data = valid_draft_data()
    data["projects"] = [
        {
            "title": "Design portfolio",
            "description": "Create a polished visual design portfolio.",
            "skillsCovered": ["Graphic design"],
            "effort": "weekend",
        }
    ]
    provider = FakeAnalysisProvider(GroundedAnalysisDraft.model_validate(data))

    response = post_analysis(provider, valid_request())

    assert response.status_code == 502


def test_analysis_does_not_treat_javascript_as_a_java_gap_match() -> None:
    java_evidence = "Candidates must build production services using Java."
    payload = valid_request()
    payload["jdText"] = f"{payload['jdText']} {java_evidence}"
    data = valid_draft_data()
    data["gaps"] = [
        {
            "skill": "Java",
            "importance": "critical",
            "why": "Java is an explicit implementation requirement for this role.",
            "jdEvidenceQuote": java_evidence,
        }
    ]
    data["projects"] = [
        {
            "title": "JavaScript service",
            "description": "Build a small service using the JavaScript runtime ecosystem.",
            "skillsCovered": ["JavaScript"],
            "effort": "weekend",
        }
    ]
    provider = FakeAnalysisProvider(GroundedAnalysisDraft.model_validate(data))

    response = post_analysis(provider, payload)

    assert response.status_code == 502


def test_provider_errors_are_sanitized() -> None:
    provider = FakeAnalysisProvider(
        error=AnalysisProviderError("upstream leaked test-internal-token")
    )

    response = post_analysis(provider, valid_request())

    assert response.status_code == 502
    assert response.json() == {"detail": "AI analysis provider failed"}
    assert INTERNAL_TOKEN not in response.text


def test_missing_provider_configuration_returns_503() -> None:
    provider = OpenRouterAnalysisProvider(settings())

    response = post_analysis(provider, valid_request())

    assert response.status_code == 503
    assert response.json() == {"detail": "AI analysis provider is not configured"}


def test_missing_approved_model_configuration_returns_503() -> None:
    provider_settings = settings(provider_key="test-provider-key").model_copy(
        update={"openrouter_model": None}
    )
    provider = OpenRouterAnalysisProvider(provider_settings)

    response = post_analysis(provider, valid_request())

    assert response.status_code == 503
    assert response.json() == {"detail": "AI analysis provider is not configured"}


def test_malformed_provider_output_returns_a_sanitized_502() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "not valid JSON"}}]},
        )

    provider = OpenRouterAnalysisProvider(
        settings(provider_key="test-provider-key"),
        transport=httpx.MockTransport(handler),
    )

    response = post_analysis(provider, valid_request())

    assert response.status_code == 502
    assert response.json() == {"detail": "AI analysis provider failed"}


def test_provider_output_rejects_oversized_inner_text() -> None:
    data = valid_draft_data()
    data["quickWins"] = ["x" * 501]

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(data)}}]},
        )

    provider = OpenRouterAnalysisProvider(
        settings(provider_key="test-provider-key"),
        transport=httpx.MockTransport(handler),
    )

    response = post_analysis(provider, valid_request())

    assert response.status_code == 502
    assert response.json() == {"detail": "AI analysis provider failed"}


def test_provider_response_rejects_an_oversized_envelope() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "x" * 256_001}}]},
        )

    provider = OpenRouterAnalysisProvider(
        settings(provider_key="test-provider-key"),
        transport=httpx.MockTransport(handler),
    )

    response = post_analysis(provider, valid_request())

    assert response.status_code == 502
    assert response.json() == {"detail": "AI analysis provider failed"}


def test_ps2_track_uses_the_same_legacy_output_shape() -> None:
    provider = FakeAnalysisProvider(valid_draft())
    payload = valid_request()
    payload["track"] = "ps2"

    response = post_analysis(provider, payload)

    assert response.status_code == 200
    assert response.json()["matchScore"] == 75


def test_openrouter_adapter_requests_strict_structured_output() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["Authorization"]
        body = json.loads(request.content)
        captured["body"] = body
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": valid_draft().model_dump_json(by_alias=True)}}]
            },
        )

    transport = httpx.MockTransport(handler)
    provider = OpenRouterAnalysisProvider(
        settings(provider_key="test-provider-key"),
        transport=transport,
    )

    response = post_analysis(provider, valid_request())

    assert response.status_code == 200
    assert captured["authorization"] == "Bearer test-provider-key"
    body = captured["body"]
    assert isinstance(body, dict)
    typed_body = cast(dict[str, Any], body)
    assert typed_body["model"] == "test/approved-model"
    assert typed_body["provider"] == {
        "require_parameters": True,
        "data_collection": "deny",
        "zdr": True,
    }
    response_format = cast(dict[str, Any], typed_body["response_format"])
    assert response_format["type"] == "json_schema"
    json_schema = cast(dict[str, Any], response_format["json_schema"])
    assert json_schema["strict"] is True
