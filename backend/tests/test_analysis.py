import json
from typing import Any

import httpx2 as httpx
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import Settings
from app.main import create_app
from app.providers.base import AnalysisProvider, AnalysisProviderError
from app.providers.openrouter import OpenRouterAnalysisProvider
from app.schemas.analysis import AnalysisPrompt, GroundedAnalysisDraft

INTERNAL_TOKEN = "test-internal-token"
RESUME_EVIDENCE = (
    "Built a FastAPI service with PostgreSQL for 500 student records using Python."
)
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
        "jdText": (
            "This internship requires Python, FastAPI, and PostgreSQL. "
            f"{JD_EVIDENCE}"
        ),
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
    }


def valid_draft_data() -> dict[str, Any]:
    return {
        "matchScore": 72,
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
        "applicationStrategy": [
            "Lead with the backend project and prepare its design trade-offs."
        ],
    }


def valid_draft() -> GroundedAnalysisDraft:
    return GroundedAnalysisDraft.model_validate(valid_draft_data())


def settings(*, provider_key: str | None = None) -> Settings:
    return Settings(
        internal_api_token=SecretStr(INTERNAL_TOKEN),
        openrouter_api_key=SecretStr(provider_key) if provider_key else None,
        openrouter_model="openrouter/free",
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
    assert result["matchScore"] == 72
    assert result["strengths"] == [
        {"skill": "FastAPI and PostgreSQL", "evidence": RESUME_EVIDENCE}
    ]
    assert result["projects"][0]["skillsCovered"] == ["Data structures"]
    assert result["resumeBullets"] == [RESUME_EVIDENCE]
    assert result["preAnalysis"] == {
        "roughMatchPercentage": 75.0,
        "totalMatched": 3,
        "totalMissing": 1,
    }
    assert result["analysisVersion"] == "grounded-v1"
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


def test_analysis_rejects_an_invented_resume_metric() -> None:
    data = valid_draft_data()
    data["resumeBullets"] = [
        {
            "text": "Built a FastAPI service that reduced latency by 40%.",
            "evidenceQuote": RESUME_EVIDENCE,
        }
    ]
    provider = FakeAnalysisProvider(GroundedAnalysisDraft.model_validate(data))

    response = post_analysis(provider, valid_request())

    assert response.status_code == 502


def test_analysis_rejects_a_score_far_from_deterministic_overlap() -> None:
    data = valid_draft_data()
    data["matchScore"] = 20
    provider = FakeAnalysisProvider(GroundedAnalysisDraft.model_validate(data))

    response = post_analysis(provider, valid_request())

    assert response.status_code == 502


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


def test_provider_errors_are_sanitized() -> None:
    provider = FakeAnalysisProvider(
        error=AnalysisProviderError("upstream leaked test-internal-token")
    )

    response = post_analysis(provider, valid_request())

    assert response.status_code == 502
    assert response.json() == {"detail": "AI analysis provider failed"}
    assert INTERNAL_TOKEN not in response.text


def test_ps2_track_uses_the_same_legacy_output_shape() -> None:
    provider = FakeAnalysisProvider(valid_draft())
    payload = valid_request()
    payload["track"] = "ps2"

    response = post_analysis(provider, payload)

    assert response.status_code == 200
    assert response.json()["matchScore"] == 72


def test_openrouter_adapter_requests_strict_structured_output() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["Authorization"]
        body = json.loads(request.content)
        captured["body"] = body
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": valid_draft().model_dump_json(by_alias=True)
                        }
                    }
                ]
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
    assert body["model"] == "openrouter/free"
    assert body["provider"] == {"require_parameters": True}
    response_format = body["response_format"]
    assert isinstance(response_format, dict)
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
