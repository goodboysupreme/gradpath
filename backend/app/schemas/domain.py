from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AnyHttpUrl, AwareDatetime, Field, model_validator

from app.schemas.base import ContractModel


class CareerTrack(StrEnum):
    SI = "si"
    PS2 = "ps2"
    PLACEMENT = "placement"
    OFF_CAMPUS = "off_campus"


class OpportunityKind(StrEnum):
    INTERNSHIP = "internship"
    STATION_PROJECT = "station_project"
    JOB = "job"


class AccessLevel(StrEnum):
    USER_PRIVATE = "user_private"
    CAMPUS_RESTRICTED = "campus_restricted"
    PUBLIC = "public"


class ProgramCycle(ContractModel):
    track: CareerTrack
    campus: str = Field(min_length=2, max_length=80)
    academic_year: str = Field(pattern=r"^\d{4}-\d{2}$")
    term: str = Field(min_length=2, max_length=40)
    policy_version: str = Field(min_length=3, max_length=100)

    @model_validator(mode="after")
    def academic_year_is_consecutive(self) -> "ProgramCycle":
        start_text, end_text = self.academic_year.split("-")
        start_year = int(start_text)
        expected_end = (start_year + 1) % 100
        if int(end_text) != expected_end:
            raise ValueError("academic_year must contain consecutive years")
        return self


class BaseRouteListing(ContractModel):
    access_level: AccessLevel
    organization: str = Field(min_length=2, max_length=200)
    title: str = Field(min_length=2, max_length=300)


class SIListing(BaseRouteListing):
    track: Literal[CareerTrack.SI] = CareerTrack.SI
    opportunity_kind: Literal[OpportunityKind.INTERNSHIP] = OpportunityKind.INTERNSHIP
    application_deadline: AwareDatetime


class PS2Listing(BaseRouteListing):
    track: Literal[CareerTrack.PS2] = CareerTrack.PS2
    opportunity_kind: Literal[OpportunityKind.STATION_PROJECT] = OpportunityKind.STATION_PROJECT
    station_id: str = Field(min_length=2, max_length=100)
    project_id: str = Field(min_length=2, max_length=100)
    semester: str = Field(min_length=2, max_length=40)


class PlacementListing(BaseRouteListing):
    track: Literal[CareerTrack.PLACEMENT] = CareerTrack.PLACEMENT
    opportunity_kind: Literal[OpportunityKind.JOB] = OpportunityKind.JOB
    application_deadline: AwareDatetime


class OffCampusListing(BaseRouteListing):
    track: Literal[CareerTrack.OFF_CAMPUS] = CareerTrack.OFF_CAMPUS
    opportunity_kind: Literal[OpportunityKind.INTERNSHIP, OpportunityKind.JOB]
    source_url: AnyHttpUrl


RouteListing = Annotated[
    SIListing | PS2Listing | PlacementListing | OffCampusListing,
    Field(discriminator="track"),
]
