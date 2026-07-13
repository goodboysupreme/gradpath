import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas.domain import ProgramCycle, RouteListing


def test_program_cycle_is_versioned_and_immutable() -> None:
    cycle = ProgramCycle(
        track="ps2",
        campus="pilani",
        academic_year="2026-27",
        term="semester_1",
        policy_version="ps2-2026-27-draft-1",
    )

    assert cycle.track.value == "ps2"
    with pytest.raises(ValidationError):
        cycle.term = "semester_2"


def test_program_cycle_rejects_an_ambiguous_academic_year() -> None:
    with pytest.raises(ValidationError):
        ProgramCycle(
            track="si",
            campus="pilani",
            academic_year="2026",
            term="summer",
            policy_version="si-2026-draft-1",
        )


def test_ps2_listing_requires_station_project_and_semester_fields() -> None:
    adapter = TypeAdapter(RouteListing)
    listing = adapter.validate_python(
        {
            "track": "ps2",
            "opportunity_kind": "station_project",
            "access_level": "campus_restricted",
            "organization": "Samsung Research",
            "title": "Developer Project",
            "station_id": "station-srib",
            "project_id": "project-developer",
            "semester": "semester_1",
        }
    )

    assert listing.track.value == "ps2"
    assert listing.project_id == "project-developer"


def test_ps2_listing_cannot_be_reduced_to_a_generic_jd() -> None:
    adapter = TypeAdapter(RouteListing)

    with pytest.raises(ValidationError):
        adapter.validate_python(
            {
                "track": "ps2",
                "opportunity_kind": "station_project",
                "access_level": "campus_restricted",
                "organization": "Samsung Research",
                "title": "Developer Project",
            }
        )


def test_si_listing_rejects_a_station_project_kind() -> None:
    adapter = TypeAdapter(RouteListing)

    with pytest.raises(ValidationError):
        adapter.validate_python(
            {
                "track": "si",
                "opportunity_kind": "station_project",
                "access_level": "campus_restricted",
                "organization": "Example",
                "title": "Summer Intern",
                "application_deadline": "2026-09-01T12:00:00Z",
            }
        )
