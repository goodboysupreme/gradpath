import re

_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_URL_PATTERN = re.compile(
    r"\b(?:(?:https?://|www\.)\S+|(?:[A-Z0-9-]+\.)+(?:ai|com|dev|in|io|me|net|org)(?:/\S*)?)",
    re.IGNORECASE,
)
_STUDENT_ID_PATTERN = re.compile(r"\b20\d{2}[A-Z0-9]{5,12}\b", re.IGNORECASE)
_PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?91[\s.-]?)?(?:\d[\s.-]?){10}(?!\w)")
_PHONE_LINE_PATTERN = re.compile(r"(?im)^(\s*(?:contact(?:\s+number)?|mobile|phone)\s*[:\-]\s*).+$")
_NAME_LINE_PATTERN = re.compile(r"(?im)^(\s*(?:full\s+)?name\s*[:\-]\s*).+$")
_ADDRESS_LINE_PATTERN = re.compile(r"(?im)^(\s*(?:address|residence)\s*[:\-]\s*).+$")
_DOB_LINE_PATTERN = re.compile(r"(?im)^(\s*(?:date\s+of\s+birth|dob)\s*[:\-]\s*).+$")
_SOCIAL_HANDLE_PATTERN = re.compile(r"(?<![\w@])@[A-Z0-9_.-]{2,}", re.IGNORECASE)


def redact_sensitive_text(value: str) -> str:
    redacted = _EMAIL_PATTERN.sub("[REDACTED_EMAIL]", value)
    redacted = _URL_PATTERN.sub("[REDACTED_URL]", redacted)
    redacted = _STUDENT_ID_PATTERN.sub("[REDACTED_STUDENT_ID]", redacted)
    redacted = _PHONE_PATTERN.sub("[REDACTED_PHONE]", redacted)
    redacted = _PHONE_LINE_PATTERN.sub(r"\1[REDACTED_PHONE]", redacted)
    redacted = _NAME_LINE_PATTERN.sub(r"\1[REDACTED_NAME]", redacted)
    redacted = _ADDRESS_LINE_PATTERN.sub(r"\1[REDACTED_ADDRESS]", redacted)
    redacted = _DOB_LINE_PATTERN.sub(r"\1[REDACTED_DOB]", redacted)
    return _SOCIAL_HANDLE_PATTERN.sub("[REDACTED_SOCIAL_HANDLE]", redacted)
