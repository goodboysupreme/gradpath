from fastapi.testclient import TestClient


def samsung_coverage_payload() -> dict[str, object]:
    return {
        "requirements": [
            {
                "id": "dsa",
                "statement": "Ability to solve problems using algorithms and data structures",
                "priority": "required",
            },
            {
                "id": "voice",
                "statement": "Evidence relevant to voice intelligence",
                "priority": "required",
                "group_id": "coe",
            },
            {
                "id": "web",
                "statement": "Evidence relevant to server technology or web",
                "priority": "required",
                "group_id": "coe",
            },
        ],
        "groups": [
            {
                "id": "coe",
                "label": "At least one Samsung R&D centre of excellence",
                "operator": "any_of",
                "priority": "required",
                "requirement_ids": ["voice", "web"],
                "minimum_satisfied": 1,
            }
        ],
        "evidence_claims": [
            {
                "id": "project-web",
                "kind": "project",
                "statement": "Built and deployed a web service with FastAPI",
            }
        ],
        "matches": [
            {
                "requirement_id": "web",
                "evidence_claim_ids": ["project-web"],
                "confidence": 0.95,
                "verified": True,
            }
        ],
    }


def test_any_of_group_suppresses_unmatched_alternatives(client: TestClient) -> None:
    response = client.post("/api/v1/coverage/evaluate", json=samsung_coverage_payload())

    assert response.status_code == 200
    result = response.json()
    assert result["group_results"] == [
        {
            "group_id": "coe",
            "status": "supported",
            "supported_requirement_ids": ["web"],
        }
    ]
    assert result["actionable_gap_ids"] == ["dsa"]
    assert result["summary"]["required_missing"] == 1


def test_low_confidence_evidence_requires_confirmation(client: TestClient) -> None:
    payload = samsung_coverage_payload()
    payload["matches"] = [
        {
            "requirement_id": "web",
            "evidence_claim_ids": ["project-web"],
            "confidence": 0.6,
            "verified": False,
        }
    ]

    response = client.post("/api/v1/coverage/evaluate", json=payload)

    assert response.status_code == 200
    result = response.json()
    assert result["group_results"][0]["status"] == "needs_confirmation"
    assert result["actionable_gap_ids"] == ["dsa", "group:coe"]


def test_match_cannot_reference_unknown_evidence(client: TestClient) -> None:
    payload = samsung_coverage_payload()
    payload["matches"] = [
        {
            "requirement_id": "web",
            "evidence_claim_ids": ["invented-claim"],
            "confidence": 0.99,
            "verified": True,
        }
    ]

    response = client.post("/api/v1/coverage/evaluate", json=payload)

    assert response.status_code == 422


def test_requirement_group_rejects_dangling_members(client: TestClient) -> None:
    payload = samsung_coverage_payload()
    payload["groups"] = [
        {
            "id": "coe",
            "label": "At least one Samsung R&D centre of excellence",
            "operator": "any_of",
            "priority": "required",
            "requirement_ids": ["voice", "nonexistent"],
            "minimum_satisfied": 1,
        }
    ]

    response = client.post("/api/v1/coverage/evaluate", json=payload)

    assert response.status_code == 422


def test_requirement_group_rejects_duplicate_members(client: TestClient) -> None:
    payload = samsung_coverage_payload()
    payload["requirements"] = [
        {
            "id": "voice",
            "statement": "Evidence relevant to voice intelligence",
            "priority": "required",
        },
        {
            "id": "web",
            "statement": "Evidence relevant to server technology or web",
            "priority": "required",
            "group_id": "coe",
        },
    ]
    payload["groups"] = [
        {
            "id": "coe",
            "label": "At least two Samsung R&D centre capabilities",
            "operator": "any_of",
            "priority": "required",
            "requirement_ids": ["web", "web"],
            "minimum_satisfied": 2,
        }
    ]

    response = client.post("/api/v1/coverage/evaluate", json=payload)

    assert response.status_code == 422


def test_all_of_group_rejects_a_partial_threshold(client: TestClient) -> None:
    payload = samsung_coverage_payload()
    payload["groups"] = [
        {
            "id": "coe",
            "label": "Every required Samsung R&D capability",
            "operator": "all_of",
            "priority": "required",
            "requirement_ids": ["voice", "web"],
            "minimum_satisfied": 1,
        }
    ]

    response = client.post("/api/v1/coverage/evaluate", json=payload)

    assert response.status_code == 422


def test_request_rejects_excessive_requirement_collections(client: TestClient) -> None:
    payload = {
        "requirements": [
            {
                "id": f"requirement_{index}",
                "statement": f"Requirement number {index}",
                "priority": "required",
            }
            for index in range(251)
        ]
    }

    response = client.post("/api/v1/coverage/evaluate", json=payload)

    assert response.status_code == 422
