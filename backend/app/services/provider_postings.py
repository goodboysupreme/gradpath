import hashlib
import json
import math
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from ipaddress import ip_address
from typing import Annotated, Literal, cast
from urllib.parse import quote, unquote, urlsplit

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from app.schemas.domain import CareerTrack, OpportunityKind
from app.schemas.job_sources import SOURCE_SCHEMA_VERSIONS, JobSourceId
from app.schemas.provider_postings import (
    ParsedProviderBatch,
    ProviderAccountConfig,
    ProviderClassification,
    ProviderClassificationReason,
    ProviderClassificationStatus,
    ProviderEmploymentSignal,
    ProviderIssueCode,
    ProviderPayloadErrorCode,
    ProviderPosting,
    ProviderRecordFailure,
    ProviderRecordFailureCode,
    ProviderRegion,
    require_safe_https_url,
)

MAX_PROVIDER_PAYLOAD_BYTES = 16 * 1_024 * 1_024
MAX_PROVIDER_POSTINGS = 10_000
MAX_JSON_DEPTH = 32
MAX_JSON_NODES = 250_000
MAX_JSON_OBJECT_KEYS = 256
MAX_JSON_ARRAY_ITEMS = 10_000
MAX_JSON_KEY_CHARS = 256
MAX_DESCRIPTION_CHARS = 250_000
MAX_DESCRIPTION_BYTES = 1_024 * 1_024
MAX_RAW_RECORD_TEXT_BYTES = 1_024 * 1_024
MAX_HTML_FIELD_BYTES = 512 * 1_024
MAX_HTML_NODES = 50_000
MAX_HTML_DEPTH = 64
MAX_URL_CHARS = 4_096

ADAPTER_VERSIONS: Mapping[JobSourceId, str] = {
    JobSourceId.GREENHOUSE: "greenhouse-parser-v1",
    JobSourceId.LEVER: "lever-parser-v1",
    JobSourceId.ASHBY: "ashby-parser-v1",
    JobSourceId.SMARTRECRUITERS: "smartrecruiters-parser-v1",
}

_INTERN_TITLE = re.compile(r"\bintern(?:ship)?\b", re.IGNORECASE)
_FULL_TIME_TITLE = re.compile(r"\bfull[\s-]*time\b", re.IGNORECASE)
_BLOCKED_HTML_TAGS = frozenset(
    {
        "script",
        "style",
        "template",
        "noscript",
        "iframe",
        "object",
        "svg",
        "math",
    }
)
_BREAK_HTML_TAGS = frozenset(
    {
        "address",
        "article",
        "aside",
        "blockquote",
        "br",
        "dd",
        "div",
        "dl",
        "dt",
        "figcaption",
        "figure",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "tbody",
        "td",
        "th",
        "thead",
        "tr",
        "ul",
    }
)
_VOID_HTML_TAGS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)
_BIDI_CONTROLS = frozenset(
    {
        "\u061c",
        "\u200e",
        "\u200f",
        "\u202a",
        "\u202b",
        "\u202c",
        "\u202d",
        "\u202e",
        "\u2066",
        "\u2067",
        "\u2068",
        "\u2069",
    }
)
_HTTP_URL_ADAPTER = TypeAdapter(AnyHttpUrl)

StrictIdInt = Annotated[int, Field(strict=True, gt=0)]
StrictCount = Annotated[int, Field(strict=True, ge=0, le=10_000_000)]
StrictBool = Annotated[bool, Field(strict=True)]
ExternalIdText = Annotated[str, Field(strict=True, min_length=1, max_length=300)]
TitleText = Annotated[str, Field(strict=True, min_length=2, max_length=300)]
OrganizationText = Annotated[str, Field(strict=True, min_length=2, max_length=200)]
LocationText = Annotated[str, Field(strict=True, min_length=1, max_length=500)]
SignalText = Annotated[str, Field(strict=True, min_length=1, max_length=200)]
TimestampText = Annotated[str, Field(strict=True, min_length=10, max_length=100)]
UrlText = Annotated[str, Field(strict=True, min_length=8, max_length=MAX_URL_CHARS)]
OutboundUrlText = Annotated[str, Field(strict=True, max_length=MAX_URL_CHARS)]
RawText = Annotated[str, Field(strict=True, min_length=1, max_length=MAX_DESCRIPTION_CHARS)]
RawHtml = Annotated[str, Field(strict=True, min_length=1, max_length=512 * 1_024)]


class ProviderPayloadError(ValueError):
    def __init__(self, code: ProviderPayloadErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


class _DuplicateJsonKey(ValueError):
    pass


class _InvalidJson(ValueError):
    pass


class _StructureLimitExceeded(ValueError):
    pass


class _RecordParseFailure(ValueError):
    def __init__(self, code: ProviderRecordFailureCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(slots=True)
class _JsonFrame:
    kind: Literal["array", "object"]
    item_count: int = 0
    expecting_value: bool = False


class _WireModel(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)


class _GreenhouseMeta(_WireModel):
    total: StrictCount


class _GreenhouseEnvelope(_WireModel):
    jobs: Annotated[list[object], Field(max_length=MAX_PROVIDER_POSTINGS)]
    meta: _GreenhouseMeta


class _GreenhouseLocation(_WireModel):
    name: LocationText


class _GreenhouseIdentity(_WireModel):
    id: StrictIdInt


class _GreenhouseRecord(_WireModel):
    id: StrictIdInt
    title: TitleText
    content: RawHtml
    absolute_url: OutboundUrlText | None = None
    location: _GreenhouseLocation | None = None
    updated_at: TimestampText | None = None
    first_published: TimestampText | None = None
    application_deadline: TimestampText | None = None
    company_name: OrganizationText | None = None


class _LeverCategories(_WireModel):
    commitment: SignalText | None = None
    location: LocationText | None = None


class _LeverListSection(_WireModel):
    text: Annotated[str, Field(strict=True, min_length=1, max_length=200)]
    content: RawHtml


def _empty_lever_sections() -> list[_LeverListSection]:
    return []


class _LeverIdentity(_WireModel):
    id: ExternalIdText


class _LeverRecord(_WireModel):
    id: ExternalIdText
    text: TitleText
    categories: _LeverCategories | None = None
    opening_plain: RawText | None = Field(default=None, alias="openingPlain")
    description_body_plain: RawText | None = Field(default=None, alias="descriptionBodyPlain")
    description_plain: RawText | None = Field(default=None, alias="descriptionPlain")
    additional_plain: RawText | None = Field(default=None, alias="additionalPlain")
    lists: Annotated[list[_LeverListSection], Field(max_length=64)] = Field(
        default_factory=_empty_lever_sections
    )
    hosted_url: OutboundUrlText | None = Field(default=None, alias="hostedUrl")
    apply_url: OutboundUrlText | None = Field(default=None, alias="applyUrl")


class _AshbyEnvelope(_WireModel):
    api_version: Annotated[str, Field(strict=True, min_length=1, max_length=20)] = Field(
        alias="apiVersion"
    )
    jobs: Annotated[list[object], Field(max_length=MAX_PROVIDER_POSTINGS)]


class _AshbyIdentity(_WireModel):
    job_url: UrlText = Field(alias="jobUrl")


class _AshbyRecord(_WireModel):
    id: ExternalIdText | None = None
    title: TitleText
    location: LocationText | None = None
    is_listed: StrictBool = Field(alias="isListed")
    description_plain: RawText = Field(alias="descriptionPlain")
    published_at: TimestampText | None = Field(default=None, alias="publishedAt")
    employment_type: SignalText | None = Field(default=None, alias="employmentType")
    job_url: UrlText = Field(alias="jobUrl")
    apply_url: OutboundUrlText | None = Field(default=None, alias="applyUrl")


class _SmartCompany(_WireModel):
    name: OrganizationText | None = None


class _SmartLocation(_WireModel):
    city: LocationText | None = None
    region: LocationText | None = None
    country: LocationText | None = None


class _SmartEmploymentType(_WireModel):
    label: SignalText | None = None


class _SmartIdentity(_WireModel):
    id: ExternalIdText


class _SmartSummary(_WireModel):
    id: ExternalIdText
    name: TitleText
    company: _SmartCompany | None = None
    released_date: TimestampText | None = Field(default=None, alias="releasedDate")
    location: _SmartLocation | None = None
    employment_type: _SmartEmploymentType | None = Field(default=None, alias="typeOfEmployment")
    ref: OutboundUrlText | None = None


class _SmartListEnvelope(_WireModel):
    total_found: StrictCount = Field(alias="totalFound")
    content: Annotated[list[object], Field(max_length=MAX_PROVIDER_POSTINGS)]


class _SmartSection(_WireModel):
    title: Annotated[str, Field(strict=True, min_length=1, max_length=200)] | None = None
    text: RawHtml


class _SmartSections(_WireModel):
    company_description: _SmartSection | None = Field(default=None, alias="companyDescription")
    job_description: _SmartSection = Field(alias="jobDescription")
    qualifications: _SmartSection | None = None
    additional_information: _SmartSection | None = Field(
        default=None,
        alias="additionalInformation",
    )


class _SmartJobAd(_WireModel):
    sections: _SmartSections


class _SmartDetail(_WireModel):
    id: ExternalIdText
    active: StrictBool
    apply_url: OutboundUrlText | None = Field(default=None, alias="applyUrl")
    job_ad: _SmartJobAd = Field(alias="jobAd")


class _SafeHtmlTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._blocked_tags: list[str] = []
        self._open_tags: list[str] = []
        self._nodes = 0

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        del attrs
        self._touch_node()
        normalized_tag = tag.casefold()
        if self._blocked_tags:
            if normalized_tag in _BLOCKED_HTML_TAGS:
                self._blocked_tags.append(normalized_tag)
                self._check_depth()
            return
        if normalized_tag in _BLOCKED_HTML_TAGS:
            self._blocked_tags.append(normalized_tag)
            self._check_depth()
            return
        if normalized_tag not in _VOID_HTML_TAGS:
            self._open_tags.append(normalized_tag)
            self._check_depth()
        if normalized_tag in _BREAK_HTML_TAGS:
            self.parts.append("\n")

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        del attrs
        self._touch_node()
        if not self._blocked_tags and tag.casefold() in _BREAK_HTML_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        self._touch_node()
        normalized_tag = tag.casefold()
        if self._blocked_tags:
            if normalized_tag in self._blocked_tags:
                match_index = (
                    len(self._blocked_tags) - 1 - self._blocked_tags[::-1].index(normalized_tag)
                )
                del self._blocked_tags[match_index:]
            return
        if normalized_tag in _BREAK_HTML_TAGS:
            self.parts.append("\n")
        if normalized_tag in _VOID_HTML_TAGS or normalized_tag not in self._open_tags:
            return
        match_index = len(self._open_tags) - 1 - self._open_tags[::-1].index(normalized_tag)
        del self._open_tags[match_index:]

    def handle_data(self, data: str) -> None:
        self._touch_node()
        if not self._blocked_tags:
            self.parts.append(data)

    def handle_comment(self, data: str) -> None:
        del data
        self._touch_node()

    def handle_decl(self, decl: str) -> None:
        del decl
        self._touch_node()

    def unknown_decl(self, data: str) -> None:
        del data
        self._touch_node()

    def _touch_node(self) -> None:
        self._nodes += 1
        if self._nodes > MAX_HTML_NODES:
            raise _RecordParseFailure(ProviderRecordFailureCode.INVALID_CRITICAL_FIELD)

    def _check_depth(self) -> None:
        if len(self._open_tags) + len(self._blocked_tags) > MAX_HTML_DEPTH:
            raise _RecordParseFailure(ProviderRecordFailureCode.INVALID_CRITICAL_FIELD)


def parse_greenhouse_snapshot(
    config: ProviderAccountConfig,
    payload: bytes,
    *,
    observed_at: datetime,
) -> ParsedProviderBatch:
    _require_provider(config, JobSourceId.GREENHOUSE)
    _require_aware(observed_at)
    decoded = _decode_provider_json(payload)
    try:
        envelope = _GreenhouseEnvelope.model_validate(decoded)
    except ValidationError:
        raise ProviderPayloadError(ProviderPayloadErrorCode.INVALID_ENVELOPE) from None
    if envelope.meta.total != len(envelope.jobs):
        raise ProviderPayloadError(ProviderPayloadErrorCode.INVALID_ENVELOPE)

    postings: list[ProviderPosting] = []
    failures: list[ProviderRecordFailure] = []
    seen_ids: set[str] = set()
    for index, raw_record in enumerate(envelope.jobs):
        try:
            identity_record = _GreenhouseIdentity.model_validate(raw_record)
            external_id = str(identity_record.id)
            _claim_identity(external_id, seen_ids)
            record = _GreenhouseRecord.model_validate(raw_record)
            description = _sanitize_html(record.content)
            _validate_description(description)
            public_url, public_issue = _optional_outbound_url(
                record.absolute_url,
                ProviderIssueCode.UNSAFE_PUBLIC_LISTING_URL,
            )
            issues = (public_issue,) if public_issue is not None else ()
            published_at = _parse_timestamp(record.first_published)
            updated_at = _parse_timestamp(record.updated_at)
            deadline = _parse_timestamp(record.application_deadline)
            title = _required_inline(record.title, 2, 300)
            classification = _classify(title, None)
            provider_ref = _trusted_url(
                "https://boards-api.greenhouse.io/v1/boards/"
                f"{quote(config.source_account, safe='-._~')}/jobs/{external_id}"
            )
            posting = _build_posting(
                config=config,
                organization_name=record.company_name,
                external_id=external_id,
                provider_record_ref=provider_ref,
                public_listing_url=public_url,
                application_url=None,
                title=title,
                description=description,
                location=_optional_inline(
                    record.location.name if record.location is not None else None,
                    2,
                    200,
                ),
                published_at=published_at,
                updated_at=updated_at,
                application_deadline=deadline,
                employment_signal=None,
                classification=classification,
                issues=issues,
                observed_at=observed_at,
            )
        except ValidationError:
            failures.append(
                _record_failure(
                    config,
                    index,
                    raw_record,
                    ProviderRecordFailureCode.INVALID_CRITICAL_FIELD,
                )
            )
        except _RecordParseFailure as error:
            failures.append(_record_failure(config, index, raw_record, error.code))
        else:
            postings.append(posting)
    return _batch(config, envelope.meta.total, envelope.jobs, postings, failures)


def parse_lever_page(
    config: ProviderAccountConfig,
    payload: bytes,
    *,
    observed_at: datetime,
) -> ParsedProviderBatch:
    _require_provider(config, JobSourceId.LEVER)
    _require_aware(observed_at)
    decoded = _decode_provider_json(payload)
    if not isinstance(decoded, list):
        raise ProviderPayloadError(ProviderPayloadErrorCode.INVALID_ENVELOPE)
    records = cast(list[object], decoded)
    if len(records) > MAX_PROVIDER_POSTINGS:
        raise ProviderPayloadError(ProviderPayloadErrorCode.INVALID_ENVELOPE)

    postings: list[ProviderPosting] = []
    failures: list[ProviderRecordFailure] = []
    seen_ids: set[str] = set()
    for index, raw_record in enumerate(records):
        try:
            identity_record = _LeverIdentity.model_validate(raw_record)
            external_id = _opaque_external_id(identity_record.id)
            _claim_identity(external_id, seen_ids)
            record = _LeverRecord.model_validate(raw_record)
            description = _lever_description(record)
            signal = _employment_signal(
                "categories.commitment",
                record.categories.commitment if record.categories is not None else None,
            )
            title = _required_inline(record.text, 2, 300)
            classification = _classify(title, signal)
            public_url, public_issue = _optional_outbound_url(
                record.hosted_url,
                ProviderIssueCode.UNSAFE_PUBLIC_LISTING_URL,
            )
            application_url, application_issue = _optional_outbound_url(
                record.apply_url,
                ProviderIssueCode.UNSAFE_APPLICATION_URL,
            )
            issues = tuple(
                issue for issue in (public_issue, application_issue) if issue is not None
            )
            api_host = (
                "api.eu.lever.co" if config.lever_region is ProviderRegion.EU else "api.lever.co"
            )
            provider_ref = _trusted_url(
                f"https://{api_host}/v0/postings/"
                f"{quote(config.source_account, safe='-._~')}/"
                f"{quote(external_id, safe='-._~')}"
            )
            posting = _build_posting(
                config=config,
                organization_name=None,
                external_id=external_id,
                provider_record_ref=provider_ref,
                public_listing_url=public_url,
                application_url=application_url,
                title=title,
                description=description,
                location=_optional_inline(
                    record.categories.location if record.categories is not None else None,
                    2,
                    200,
                ),
                published_at=None,
                updated_at=None,
                application_deadline=None,
                employment_signal=signal,
                classification=classification,
                issues=issues,
                observed_at=observed_at,
            )
        except ValidationError:
            failures.append(
                _record_failure(
                    config,
                    index,
                    raw_record,
                    ProviderRecordFailureCode.INVALID_CRITICAL_FIELD,
                )
            )
        except _RecordParseFailure as error:
            failures.append(_record_failure(config, index, raw_record, error.code))
        else:
            postings.append(posting)
    return _batch(config, None, records, postings, failures)


def parse_ashby_snapshot(
    config: ProviderAccountConfig,
    payload: bytes,
    *,
    observed_at: datetime,
) -> ParsedProviderBatch:
    _require_provider(config, JobSourceId.ASHBY)
    _require_aware(observed_at)
    decoded = _decode_provider_json(payload)
    try:
        envelope = _AshbyEnvelope.model_validate(decoded)
    except ValidationError:
        raise ProviderPayloadError(ProviderPayloadErrorCode.INVALID_ENVELOPE) from None
    if envelope.api_version != "1":
        raise ProviderPayloadError(ProviderPayloadErrorCode.UNSUPPORTED_SCHEMA_VERSION)

    postings: list[ProviderPosting] = []
    failures: list[ProviderRecordFailure] = []
    seen_ids: set[str] = set()
    for index, raw_record in enumerate(envelope.jobs):
        try:
            identity_record = _AshbyIdentity.model_validate(raw_record)
            observed_url = _ashby_identity_url(identity_record.job_url, config.source_account)
            identity = _canonical_outbound_url(observed_url)
            _claim_identity(identity, seen_ids)
            public_url = _trusted_url(identity)
            record = _AshbyRecord.model_validate(raw_record)
            external_id = _opaque_external_id(record.id) if record.id is not None else None
            _ensure_raw_text_budget(record.description_plain)
            description = _normalize_multiline(record.description_plain)
            _validate_description(description)
            application_url, application_issue = _optional_outbound_url(
                record.apply_url,
                ProviderIssueCode.UNSAFE_APPLICATION_URL,
            )
            issues = (application_issue,) if application_issue is not None else ()
            signal = _employment_signal("employmentType", record.employment_type)
            rejection = (
                ProviderClassificationReason.POSTING_UNLISTED if not record.is_listed else None
            )
            title = _required_inline(record.title, 2, 300)
            classification = _classify(title, signal, rejection=rejection)
            posting = _build_posting(
                config=config,
                organization_name=None,
                external_id=external_id,
                provider_record_ref=public_url,
                public_listing_url=public_url,
                application_url=application_url,
                title=title,
                description=description,
                location=_optional_inline(record.location, 2, 200),
                published_at=_parse_timestamp(record.published_at),
                updated_at=None,
                application_deadline=None,
                employment_signal=signal,
                classification=classification,
                issues=issues,
                observed_at=observed_at,
            )
        except ValidationError:
            failures.append(
                _record_failure(
                    config,
                    index,
                    raw_record,
                    ProviderRecordFailureCode.INVALID_CRITICAL_FIELD,
                )
            )
        except _RecordParseFailure as error:
            failures.append(_record_failure(config, index, raw_record, error.code))
        else:
            postings.append(posting)
    return _batch(config, len(envelope.jobs), envelope.jobs, postings, failures)


def parse_smartrecruiters_page(
    config: ProviderAccountConfig,
    payload: bytes,
    details_by_id: Mapping[str, bytes],
    *,
    observed_at: datetime,
) -> ParsedProviderBatch:
    _require_provider(config, JobSourceId.SMARTRECRUITERS)
    _require_aware(observed_at)
    if len(payload) + sum(len(detail) for detail in details_by_id.values()) > (
        MAX_PROVIDER_PAYLOAD_BYTES
    ):
        raise ProviderPayloadError(ProviderPayloadErrorCode.PAYLOAD_TOO_LARGE)
    decoded = _decode_provider_json(payload)
    try:
        envelope = _SmartListEnvelope.model_validate(decoded)
    except ValidationError:
        raise ProviderPayloadError(ProviderPayloadErrorCode.INVALID_ENVELOPE) from None

    postings: list[ProviderPosting] = []
    failures: list[ProviderRecordFailure] = []
    seen_ids: set[str] = set()
    for index, raw_summary in enumerate(envelope.content):
        try:
            identity_summary = _SmartIdentity.model_validate(raw_summary)
            external_id = _opaque_external_id(identity_summary.id)
            _claim_identity(external_id, seen_ids)
            summary = _SmartSummary.model_validate(raw_summary)
            detail_payload = details_by_id.get(external_id)
            if detail_payload is None:
                raise ProviderPayloadError(ProviderPayloadErrorCode.DETAIL_MISSING)
            decoded_detail = _decode_provider_json(detail_payload)
            try:
                detail = _SmartDetail.model_validate(decoded_detail)
            except ValidationError:
                raise _RecordParseFailure(
                    ProviderRecordFailureCode.INVALID_CRITICAL_FIELD
                ) from None
            detail_id = _opaque_external_id(detail.id)
            if detail_id != external_id:
                raise ProviderPayloadError(ProviderPayloadErrorCode.DETAIL_ID_MISMATCH)
            description = _smartrecruiters_description(detail.job_ad.sections)
            application_url, application_issue = _optional_outbound_url(
                detail.apply_url,
                ProviderIssueCode.UNSAFE_APPLICATION_URL,
            )
            issues = (application_issue,) if application_issue is not None else ()
            signal = _employment_signal(
                "typeOfEmployment.label",
                (summary.employment_type.label if summary.employment_type is not None else None),
            )
            rejection = ProviderClassificationReason.POSTING_INACTIVE if not detail.active else None
            title = _required_inline(summary.name, 2, 300)
            classification = _classify(title, signal, rejection=rejection)
            provider_ref = _trusted_url(
                "https://api.smartrecruiters.com/v1/companies/"
                f"{quote(config.source_account, safe='-._~')}/postings/"
                f"{quote(external_id, safe='-._~')}"
            )
            if summary.ref is not None:
                try:
                    observed_ref = _safe_outbound_url(summary.ref)
                except ValueError:
                    raise _RecordParseFailure(
                        ProviderRecordFailureCode.INVALID_CRITICAL_FIELD
                    ) from None
                if str(observed_ref) != str(provider_ref):
                    raise _RecordParseFailure(ProviderRecordFailureCode.INVALID_CRITICAL_FIELD)
            posting = _build_posting(
                config=config,
                organization_name=(summary.company.name if summary.company is not None else None),
                external_id=external_id,
                provider_record_ref=provider_ref,
                public_listing_url=None,
                application_url=application_url,
                title=title,
                description=description,
                location=_smart_location(summary.location),
                published_at=_parse_timestamp(summary.released_date),
                updated_at=None,
                application_deadline=None,
                employment_signal=signal,
                classification=classification,
                issues=issues,
                observed_at=observed_at,
            )
        except ValidationError:
            failures.append(
                _record_failure(
                    config,
                    index,
                    raw_summary,
                    ProviderRecordFailureCode.INVALID_CRITICAL_FIELD,
                )
            )
        except _RecordParseFailure as error:
            failures.append(_record_failure(config, index, raw_summary, error.code))
        else:
            postings.append(posting)
    return _batch(
        config,
        envelope.total_found,
        envelope.content,
        postings,
        failures,
    )


def _decode_provider_json(payload: bytes) -> object:
    if len(payload) > MAX_PROVIDER_PAYLOAD_BYTES:
        raise ProviderPayloadError(ProviderPayloadErrorCode.PAYLOAD_TOO_LARGE)
    try:
        text = payload.decode("utf-8")
        _preflight_json_structure(text)
        decoded = cast(
            object,
            json.loads(
                text,
                object_pairs_hook=_strict_object,
                parse_constant=_reject_json_constant,
            ),
        )
    except _DuplicateJsonKey:
        raise ProviderPayloadError(ProviderPayloadErrorCode.DUPLICATE_JSON_KEY) from None
    except _StructureLimitExceeded:
        raise ProviderPayloadError(ProviderPayloadErrorCode.STRUCTURE_LIMIT_EXCEEDED) from None
    except RecursionError:
        raise ProviderPayloadError(ProviderPayloadErrorCode.STRUCTURE_LIMIT_EXCEEDED) from None
    except (UnicodeDecodeError, json.JSONDecodeError, _InvalidJson, ValueError):
        raise ProviderPayloadError(ProviderPayloadErrorCode.INVALID_JSON) from None
    _validate_json_structure(decoded)
    return decoded


def _preflight_json_structure(value: str) -> None:
    frames: list[_JsonFrame] = []
    in_string = False
    escaped = False
    in_scalar = False
    nodes = 0

    for character in value:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue

        if in_scalar:
            if character not in " \t\r\n,]}:":
                continue
            in_scalar = False

        if character in " \t\r\n":
            continue
        if character == '"':
            if _begin_json_value(frames):
                nodes += 1
            in_string = True
        elif character in "[{":
            if _begin_json_value(frames):
                nodes += 1
            frames.append(
                _JsonFrame(
                    kind="array" if character == "[" else "object",
                    expecting_value=character == "[",
                )
            )
            if len(frames) > MAX_JSON_DEPTH:
                raise _StructureLimitExceeded
        elif character in "]}":
            expected_kind = "array" if character == "]" else "object"
            if not frames or frames[-1].kind != expected_kind:
                raise _InvalidJson
            frames.pop()
        elif character == ",":
            if frames:
                frames[-1].expecting_value = frames[-1].kind == "array"
        elif character == ":":
            if frames and frames[-1].kind == "object":
                frames[-1].item_count += 1
                if frames[-1].item_count > MAX_JSON_OBJECT_KEYS:
                    raise _StructureLimitExceeded
                frames[-1].expecting_value = True
        else:
            if _begin_json_value(frames):
                nodes += 1
            in_scalar = True

        if nodes > MAX_JSON_NODES:
            raise _StructureLimitExceeded

    if in_string or frames:
        raise _InvalidJson


def _begin_json_value(frames: list[_JsonFrame]) -> bool:
    if not frames:
        return True
    frame = frames[-1]
    if frame.kind == "object":
        if not frame.expecting_value:
            return False
        frame.expecting_value = False
        return True
    if frame.expecting_value:
        frame.item_count += 1
        if frame.item_count > MAX_JSON_ARRAY_ITEMS:
            raise _StructureLimitExceeded
        frame.expecting_value = False
    return True


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    if len(pairs) > MAX_JSON_OBJECT_KEYS:
        raise _StructureLimitExceeded
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    del value
    raise _InvalidJson


def _validate_json_structure(value: object) -> None:
    stack: list[tuple[object, int]] = [(value, 1)]
    nodes = 0
    while stack:
        current, depth = stack.pop()
        nodes += 1
        if nodes > MAX_JSON_NODES or depth > MAX_JSON_DEPTH:
            raise ProviderPayloadError(ProviderPayloadErrorCode.STRUCTURE_LIMIT_EXCEEDED)
        if isinstance(current, dict):
            current_mapping = cast(dict[object, object], current)
            if len(current_mapping) > MAX_JSON_OBJECT_KEYS:
                raise ProviderPayloadError(ProviderPayloadErrorCode.STRUCTURE_LIMIT_EXCEEDED)
            for key, child in current_mapping.items():
                if not isinstance(key, str) or not _valid_json_string(key, MAX_JSON_KEY_CHARS):
                    raise ProviderPayloadError(ProviderPayloadErrorCode.INVALID_JSON)
                stack.append((child, depth + 1))
        elif isinstance(current, list):
            current_items = cast(list[object], current)
            if len(current_items) > MAX_JSON_ARRAY_ITEMS:
                raise ProviderPayloadError(ProviderPayloadErrorCode.STRUCTURE_LIMIT_EXCEEDED)
            stack.extend((child, depth + 1) for child in current_items)
        elif isinstance(current, str):
            if not _valid_json_string(current, None):
                raise ProviderPayloadError(ProviderPayloadErrorCode.INVALID_JSON)
        elif isinstance(current, float) and not math.isfinite(current):
            raise ProviderPayloadError(ProviderPayloadErrorCode.INVALID_JSON)


def _valid_json_string(value: str, max_chars: int | None) -> bool:
    if max_chars is not None and len(value) > max_chars:
        return False
    return not any(0xD800 <= ord(character) <= 0xDFFF for character in value)


def _require_provider(config: ProviderAccountConfig, expected: JobSourceId) -> None:
    if config.provider is not expected:
        raise ProviderPayloadError(ProviderPayloadErrorCode.INVALID_ENVELOPE)


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ProviderPayloadError(ProviderPayloadErrorCode.INVALID_ENVELOPE)


def _claim_identity(identity: str, seen: set[str]) -> None:
    canonical = identity.casefold()
    if canonical in seen:
        raise ProviderPayloadError(ProviderPayloadErrorCode.DUPLICATE_POSTING_ID)
    seen.add(canonical)


def _opaque_external_id(value: str) -> str:
    if (
        value != value.strip()
        or any(character.isspace() for character in value)
        or any(
            character in _BIDI_CONTROLS or unicodedata.category(character).startswith("C")
            for character in value
        )
    ):
        raise _RecordParseFailure(ProviderRecordFailureCode.INVALID_CRITICAL_FIELD)
    return value


def _record_failure(
    config: ProviderAccountConfig,
    index: int,
    raw_record: object,
    code: ProviderRecordFailureCode,
) -> ProviderRecordFailure:
    return ProviderRecordFailure(
        record_index=index,
        reason_code=code,
        snapshot_fingerprint=_fingerprint(
            "gradpath.provider.record-failure",
            {
                "adapterVersion": ADAPTER_VERSIONS[config.provider],
                "provider": config.provider.value,
                "record": raw_record,
                "sourceAccount": config.source_account.casefold(),
            },
        ),
    )


def _batch(
    config: ProviderAccountConfig,
    provider_total: int | None,
    raw_records: list[object],
    postings: list[ProviderPosting],
    failures: list[ProviderRecordFailure],
) -> ParsedProviderBatch:
    try:
        return ParsedProviderBatch(
            provider=config.provider,
            source_account=config.source_account,
            provider_total=provider_total,
            records_seen=len(raw_records),
            postings=tuple(postings),
            record_failures=tuple(failures),
        )
    except ValidationError:
        raise ProviderPayloadError(ProviderPayloadErrorCode.INVALID_ENVELOPE) from None


def _build_posting(
    *,
    config: ProviderAccountConfig,
    organization_name: str | None,
    external_id: str | None,
    provider_record_ref: AnyHttpUrl,
    public_listing_url: AnyHttpUrl | None,
    application_url: AnyHttpUrl | None,
    title: str,
    description: str,
    location: str | None,
    published_at: datetime | None,
    updated_at: datetime | None,
    application_deadline: datetime | None,
    employment_signal: ProviderEmploymentSignal | None,
    classification: ProviderClassification,
    issues: tuple[ProviderIssueCode, ...],
    observed_at: datetime,
) -> ProviderPosting:
    organization = _required_inline(
        config.employer_display_name if organization_name is None else organization_name,
        2,
        200,
    )
    snapshot_fingerprint = _fingerprint(
        "gradpath.provider.semantic-snapshot",
        {
            "adapterVersion": ADAPTER_VERSIONS[config.provider],
            "applicationDeadline": _timestamp_text(application_deadline),
            "applicationUrl": _url_text(application_url),
            "classification": {
                "opportunityKind": (
                    classification.opportunity_kind.value
                    if classification.opportunity_kind is not None
                    else None
                ),
                "reasonCode": (
                    classification.reason_code.value
                    if classification.reason_code is not None
                    else None
                ),
                "status": classification.status.value,
                "tracks": [track.value for track in classification.tracks],
            },
            "description": description,
            "employmentSignal": (
                {
                    "field": employment_signal.field,
                    "value": employment_signal.value,
                }
                if employment_signal is not None
                else None
            ),
            "externalId": (None if config.provider is JobSourceId.ASHBY else external_id),
            "issues": [issue.value for issue in issues],
            "location": location,
            "organization": organization,
            "permissionBasis": config.permission_basis.value,
            "provider": config.provider.value,
            "providerRecordRef": str(provider_record_ref),
            "publicListingUrl": _url_text(public_listing_url),
            "publishedAt": _timestamp_text(published_at),
            "schemaVersion": SOURCE_SCHEMA_VERSIONS[config.provider],
            "sourceAccount": config.source_account.casefold(),
            "title": title,
            "updatedAt": _timestamp_text(updated_at),
        },
    )
    try:
        return ProviderPosting(
            provider=config.provider,
            source_account=config.source_account,
            organization=organization,
            external_id=external_id,
            provider_record_ref=provider_record_ref,
            public_listing_url=public_listing_url,
            application_url=application_url,
            title=title,
            description=description,
            location=location,
            published_at=published_at,
            updated_at=updated_at,
            application_deadline=application_deadline,
            employment_signal=employment_signal,
            classification=classification,
            issues=issues,
            schema_version=SOURCE_SCHEMA_VERSIONS[config.provider],
            adapter_version=ADAPTER_VERSIONS[config.provider],
            observed_at=observed_at,
            snapshot_fingerprint=snapshot_fingerprint,
        )
    except ValidationError:
        raise _RecordParseFailure(ProviderRecordFailureCode.INVALID_CRITICAL_FIELD) from None


def _classify(
    title: str,
    signal: ProviderEmploymentSignal | None,
    *,
    rejection: ProviderClassificationReason | None = None,
) -> ProviderClassification:
    if rejection is not None:
        return ProviderClassification(
            status=ProviderClassificationStatus.REJECTED,
            tracks=(),
            opportunity_kind=None,
            reason_code=rejection,
        )
    if signal is None:
        return ProviderClassification(
            status=ProviderClassificationStatus.NEEDS_REVIEW,
            tracks=(),
            opportunity_kind=None,
            reason_code=ProviderClassificationReason.EMPLOYMENT_SIGNAL_MISSING,
        )
    normalized_signal = "".join(
        character for character in signal.value.casefold() if character.isalnum()
    )
    if normalized_signal in {"intern", "internship"}:
        opportunity_kind = OpportunityKind.INTERNSHIP
    elif normalized_signal == "fulltime":
        opportunity_kind = OpportunityKind.JOB
    else:
        return ProviderClassification(
            status=ProviderClassificationStatus.NEEDS_REVIEW,
            tracks=(),
            opportunity_kind=None,
            reason_code=ProviderClassificationReason.EMPLOYMENT_SIGNAL_UNSUPPORTED,
        )
    title_conflicts = (
        opportunity_kind is OpportunityKind.JOB and _INTERN_TITLE.search(title) is not None
    ) or (
        opportunity_kind is OpportunityKind.INTERNSHIP
        and _FULL_TIME_TITLE.search(title) is not None
    )
    if title_conflicts:
        return ProviderClassification(
            status=ProviderClassificationStatus.NEEDS_REVIEW,
            tracks=(),
            opportunity_kind=None,
            reason_code=ProviderClassificationReason.EMPLOYMENT_SIGNAL_CONFLICT,
        )
    return ProviderClassification(
        status=ProviderClassificationStatus.ACCEPTED,
        tracks=(CareerTrack.OFF_CAMPUS,),
        opportunity_kind=opportunity_kind,
        reason_code=None,
    )


def _employment_signal(field: str, value: str | None) -> ProviderEmploymentSignal | None:
    if value is None:
        return None
    normalized = _optional_inline(value, 1, 200)
    if normalized is None:
        return None
    try:
        return ProviderEmploymentSignal(field=field, value=normalized)
    except ValidationError:
        raise _RecordParseFailure(ProviderRecordFailureCode.INVALID_CRITICAL_FIELD) from None


def _lever_description(record: _LeverRecord) -> str:
    raw_values: list[str | None] = [
        record.opening_plain,
        record.description_body_plain,
        record.description_plain,
        record.additional_plain,
    ]
    raw_values.extend(section.content for section in record.lists)
    raw_values.extend(section.text for section in record.lists)
    _ensure_raw_text_budget(*raw_values)

    blocks: list[str] = []
    components = (record.opening_plain, record.description_body_plain)
    if any(value is not None and _normalize_multiline(value) for value in components):
        blocks.extend(_normalize_multiline(value) for value in components if value is not None)
    elif record.description_plain is not None:
        blocks.append(_normalize_multiline(record.description_plain))
    for section in record.lists:
        blocks.append(_normalize_multiline(section.text))
        blocks.append(_sanitize_html(section.content))
    if record.additional_plain is not None:
        blocks.append(_normalize_multiline(record.additional_plain))
    description = _join_unique_blocks(blocks)
    _validate_description(description)
    return description


def _smartrecruiters_description(sections: _SmartSections) -> str:
    ordered_sections = (
        ("Company Description", sections.company_description),
        ("Job Description", sections.job_description),
        ("Qualifications", sections.qualifications),
        ("Additional Information", sections.additional_information),
    )
    _ensure_raw_text_budget(
        *(section.text if section is not None else None for _, section in ordered_sections)
    )
    blocks = [
        f"{heading}\n{_sanitize_html(section.text)}"
        for heading, section in ordered_sections
        if section is not None
    ]
    description = _join_unique_blocks(blocks)
    _validate_description(description)
    return description


def _sanitize_html(value: str) -> str:
    if len(value.encode("utf-8")) > MAX_HTML_FIELD_BYTES:
        raise _RecordParseFailure(ProviderRecordFailureCode.INVALID_CRITICAL_FIELD)
    parser = _SafeHtmlTextExtractor()
    try:
        parser.feed(value)
        parser.close()
    except _RecordParseFailure:
        raise
    except Exception:
        raise _RecordParseFailure(ProviderRecordFailureCode.INVALID_CRITICAL_FIELD) from None
    return _normalize_multiline("".join(parser.parts))


def _ensure_raw_text_budget(*values: str | None) -> None:
    total = sum(len(value.encode("utf-8")) for value in values if value is not None)
    if total > MAX_RAW_RECORD_TEXT_BYTES:
        raise _RecordParseFailure(ProviderRecordFailureCode.INVALID_CRITICAL_FIELD)


def _validate_description(value: str) -> None:
    if (
        len(value) < 50
        or len(value) > MAX_DESCRIPTION_CHARS
        or len(value.encode("utf-8")) > MAX_DESCRIPTION_BYTES
    ):
        raise _RecordParseFailure(ProviderRecordFailureCode.INVALID_CRITICAL_FIELD)


def _join_unique_blocks(values: list[str]) -> str:
    blocks: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _normalize_multiline(value)
        canonical = normalized.casefold()
        if normalized and canonical not in seen:
            seen.add(canonical)
            blocks.append(normalized)
    return "\n\n".join(blocks)


def _normalize_multiline(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).replace("\r\n", "\n").replace("\r", "\n")
    cleaned: list[str] = []
    for character in normalized:
        if character in _BIDI_CONTROLS:
            continue
        if character in {"\n", "\t"}:
            cleaned.append(character)
            continue
        if unicodedata.category(character).startswith("C"):
            continue
        cleaned.append(character)
    return "\n".join(
        line for raw_line in "".join(cleaned).split("\n") if (line := " ".join(raw_line.split()))
    )


def _required_inline(value: str, min_length: int, max_length: int) -> str:
    normalized = " ".join(_normalize_multiline(value).split())
    if not min_length <= len(normalized) <= max_length:
        raise _RecordParseFailure(ProviderRecordFailureCode.INVALID_CRITICAL_FIELD)
    return normalized


def _optional_inline(
    value: str | None,
    min_length: int,
    max_length: int,
) -> str | None:
    if value is None:
        return None
    normalized = " ".join(_normalize_multiline(value).split())
    if not normalized:
        return None
    if not min_length <= len(normalized) <= max_length:
        raise _RecordParseFailure(ProviderRecordFailureCode.INVALID_CRITICAL_FIELD)
    return normalized


def _parse_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    if value != value.strip():
        raise _RecordParseFailure(ProviderRecordFailureCode.INVALID_CRITICAL_FIELD)
    candidate = f"{value[:-1]}+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        raise _RecordParseFailure(ProviderRecordFailureCode.INVALID_CRITICAL_FIELD) from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _RecordParseFailure(ProviderRecordFailureCode.INVALID_CRITICAL_FIELD)
    return parsed


def _optional_outbound_url(
    value: str | None,
    issue: ProviderIssueCode,
) -> tuple[AnyHttpUrl | None, ProviderIssueCode | None]:
    if value is None:
        return None, None
    try:
        return _safe_outbound_url(value), None
    except ValueError:
        return None, issue


def _safe_outbound_url(value: str) -> AnyHttpUrl:
    if (
        len(value) > MAX_URL_CHARS
        or value != value.strip()
        or "\\" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ValueError("unsafe outbound URL")
    decoded = unquote(value)
    if "\\" in decoded or any(
        ord(character) < 32 or ord(character) == 127 for character in decoded
    ):
        raise ValueError("unsafe outbound URL")
    try:
        parsed = urlsplit(value)
        port = parsed.port
        host = parsed.hostname
    except ValueError:
        raise ValueError("unsafe outbound URL") from None
    if (
        parsed.scheme.casefold() != "https"
        or host is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or port not in {None, 443}
    ):
        raise ValueError("unsafe outbound URL")
    try:
        normalized_host = host.encode("idna").decode("ascii").casefold().rstrip(".")
    except UnicodeError:
        raise ValueError("unsafe outbound URL") from None
    if normalized_host == "localhost" or normalized_host.endswith(
        (".localhost", ".local", ".internal", ".home.arpa")
    ):
        raise ValueError("unsafe outbound URL")
    try:
        address = ip_address(normalized_host.strip("[]"))
    except ValueError:
        pass
    else:
        if not address.is_global:
            raise ValueError("unsafe outbound URL")
    try:
        validated = _HTTP_URL_ADAPTER.validate_python(value)
        return require_safe_https_url(validated)
    except (ValidationError, ValueError):
        raise ValueError("unsafe outbound URL") from None


def _ashby_identity_url(value: str, source_account: str) -> AnyHttpUrl:
    try:
        url = _safe_outbound_url(value)
    except ValueError:
        raise _RecordParseFailure(ProviderRecordFailureCode.INVALID_IDENTITY_URL) from None
    if url.host is None or url.host.casefold().rstrip(".") != "jobs.ashbyhq.com" or url.query:
        raise _RecordParseFailure(ProviderRecordFailureCode.INVALID_IDENTITY_URL)
    segments = tuple(
        _required_inline(unquote(segment), 1, 300)
        for segment in (url.path or "").split("/")
        if segment
    )
    if (
        len(segments) < 2
        or segments[0].casefold() != source_account.casefold()
        or any(segment in {".", ".."} for segment in segments)
    ):
        raise _RecordParseFailure(ProviderRecordFailureCode.INVALID_IDENTITY_URL)
    return url


def _canonical_outbound_url(value: AnyHttpUrl) -> str:
    if value.host is None:
        raise _RecordParseFailure(ProviderRecordFailureCode.INVALID_IDENTITY_URL)
    segments = [
        quote(_required_inline(unquote(segment), 1, 300), safe="-._~")
        for segment in (value.path or "").split("/")
        if segment
    ]
    return f"https://{value.host.casefold()}/{'/'.join(segments)}"


def _trusted_url(value: str) -> AnyHttpUrl:
    try:
        return _HTTP_URL_ADAPTER.validate_python(value)
    except ValidationError:
        raise ProviderPayloadError(ProviderPayloadErrorCode.INVALID_ENVELOPE) from None


def _smart_location(value: _SmartLocation | None) -> str | None:
    if value is None:
        return None
    parts: list[str] = []
    seen: set[str] = set()
    for candidate in (value.city, value.region, value.country):
        normalized = _optional_inline(candidate, 1, 100)
        if normalized is not None and normalized.casefold() not in seen:
            seen.add(normalized.casefold())
            parts.append(normalized)
    if not parts:
        return None
    location = ", ".join(parts)
    if len(location) > 200:
        raise _RecordParseFailure(ProviderRecordFailureCode.INVALID_CRITICAL_FIELD)
    return location


def _url_text(value: AnyHttpUrl | None) -> str | None:
    return str(value) if value is not None else None


def _timestamp_text(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _fingerprint(domain: str, payload: Mapping[str, object]) -> str:
    try:
        encoded = json.dumps(
            {"domain": domain, "payload": payload},
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError):
        raise ProviderPayloadError(ProviderPayloadErrorCode.INVALID_ENVELOPE) from None
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


__all__ = [
    "MAX_PROVIDER_PAYLOAD_BYTES",
    "ProviderPayloadError",
    "parse_ashby_snapshot",
    "parse_greenhouse_snapshot",
    "parse_lever_page",
    "parse_smartrecruiters_page",
]
