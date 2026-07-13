from fastapi.testclient import TestClient


def test_capabilities_keep_ps2_as_a_distinct_allotment_route(client: TestClient) -> None:
    response = client.get("/api/v1/capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert [track["id"] for track in payload["tracks"]] == [
        "si",
        "ps2",
        "placement",
        "off_campus",
    ]
    ps2 = next(track for track in payload["tracks"] if track["id"] == "ps2")
    assert ps2 == {
        "id": "ps2",
        "workflow": "allotment",
        "supports_preferences": True,
        "supports_continuous_evaluation": True,
    }
    assert payload["resume_template_ids"] == ["bits-superset-v1"]


def test_bits_template_matches_the_supplied_one_page_structure(client: TestClient) -> None:
    response = client.get("/api/v1/resume-templates/bits-superset-v1")

    assert response.status_code == 200
    template = response.json()
    assert template["id"] == "bits-superset-v1"
    assert template["page_size"] == "A4"
    assert template["max_pages"] == 1
    assert template["includes_photo"] is True
    assert template["institutional_layout"] is True
    assert template["header_fields"] == [
        "full_name",
        "course",
        "graduation_year",
        "email",
        "mobile",
        "cgpa",
    ]
    assert [section["key"] for section in template["sections"]] == [
        "academic_details",
        "subjects_electives",
        "technical_proficiency",
        "work_experience",
        "internships",
        "projects",
        "positions_of_responsibility",
        "extracurricular_activities",
        "awards_recognitions",
        "certifications",
        "competitions",
        "conferences_workshops",
        "test_scores",
        "patents",
        "publications",
        "scholarships",
        "volunteer_experience",
        "languages_known",
    ]
    academic = template["sections"][0]
    assert academic["layout"] == "table"
    assert academic["columns"] == ["course", "institute", "board", "score", "year"]


def test_unknown_resume_template_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/resume-templates/unknown-template")

    assert response.status_code == 404
    assert response.json() == {"detail": "Resume template not found"}
