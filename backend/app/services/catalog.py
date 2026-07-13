from typing import Literal

from app.schemas.catalog import (
    CapabilitiesResponse,
    ResumeSection,
    ResumeTemplateDefinition,
    TrackCapability,
)
from app.schemas.domain import CareerTrack

type SectionSpec = tuple[
    str,
    str,
    Literal["inline", "list", "table"],
    tuple[str, ...],
    bool,
]


def capabilities() -> CapabilitiesResponse:
    return CapabilitiesResponse(
        tracks=(
            TrackCapability(
                id=CareerTrack.SI,
                workflow="application",
                supports_preferences=False,
                supports_continuous_evaluation=False,
            ),
            TrackCapability(
                id=CareerTrack.PS2,
                workflow="allotment",
                supports_preferences=True,
                supports_continuous_evaluation=True,
            ),
            TrackCapability(
                id=CareerTrack.PLACEMENT,
                workflow="application",
                supports_preferences=False,
                supports_continuous_evaluation=False,
            ),
            TrackCapability(
                id=CareerTrack.OFF_CAMPUS,
                workflow="application",
                supports_preferences=False,
                supports_continuous_evaluation=False,
            ),
        ),
        resume_template_ids=("bits-superset-v1",),
    )


def get_resume_template(template_id: str) -> ResumeTemplateDefinition:
    if template_id != "bits-superset-v1":
        raise KeyError(template_id)
    section_specs: tuple[SectionSpec, ...] = (
        (
            "academic_details",
            "Academic Details",
            "table",
            ("course", "institute", "board", "score", "year"),
            True,
        ),
        ("subjects_electives", "Subjects / Electives", "inline", (), False),
        ("technical_proficiency", "Technical Proficiency", "inline", (), False),
        ("work_experience", "Work Experience", "list", (), False),
        ("internships", "Internships", "list", (), False),
        ("projects", "Projects", "list", (), False),
        ("positions_of_responsibility", "Position of Responsibility", "list", (), False),
        ("extracurricular_activities", "Extra Curricular Activities", "list", (), False),
        ("awards_recognitions", "Awards and Recognitions", "list", (), False),
        (
            "certifications",
            "Certifications",
            "table",
            ("certification", "certifying_authority"),
            False,
        ),
        ("competitions", "Competitions", "list", (), False),
        ("conferences_workshops", "Conferences and Workshops", "list", (), False),
        ("test_scores", "Test Scores", "table", ("test_name", "date_of_exam", "score"), False),
        ("patents", "Patents", "list", (), False),
        ("publications", "Publications", "list", (), False),
        ("scholarships", "Scholarships", "list", (), False),
        ("volunteer_experience", "Volunteer Experience", "list", (), False),
        ("languages_known", "Languages Known", "list", (), False),
    )
    sections = tuple(
        ResumeSection(
            key=key,
            label=label,
            layout=layout,
            columns=columns,
            required=required,
        )
        for key, label, layout, columns, required in section_specs
    )
    return ResumeTemplateDefinition(
        id="bits-superset-v1",
        name="BITS Superset One-Page Resume",
        version="1",
        page_size="A4",
        max_pages=1,
        includes_photo=True,
        institutional_layout=True,
        header_fields=(
            "full_name",
            "course",
            "graduation_year",
            "email",
            "mobile",
            "cgpa",
        ),
        sections=sections,
    )
