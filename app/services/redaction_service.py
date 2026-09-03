import re

_SECRET_PATTERN = re.compile(
    r"(?i)((?:api[_ -]?key|access[_ -]?key|password|passwd|pwd|token|secret|"
    r"密码|口令|令牌|密钥)\s*[:=：]\s*)[^\s,，;；&]+"
)
_BEARER_PATTERN = re.compile(r"(?i)(\bBearer\s+)[A-Za-z0-9._~+/=-]+")
_EMAIL_PATTERN = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_ID_NUMBER_PATTERN = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
_PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?86[\s-]?)?1[3-9]\d{9}(?!\d)")
_IPV4_PATTERN = re.compile(
    r"(?<![\w.])"
    r"(?:25[0-5]|2[0-4]\d|1?\d?\d)"
    r"(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}"
    r"(?![\w.])"
)
_MAC_PATTERN = re.compile(r"(?i)\b(?:[0-9A-F]{2}[:-]){5}[0-9A-F]{2}\b")
_WINDOWS_USER_PATTERN = re.compile(r"(?i)\b([A-Z]:\\Users\\)[^\\\s,，;；]+")


def redact_text(value: str) -> str:
    """Remove common credentials and direct identifiers before external transport."""

    redacted = _SECRET_PATTERN.sub(r"\1[SENSITIVE]", value)
    redacted = _BEARER_PATTERN.sub(r"\1[SENSITIVE]", redacted)
    redacted = _EMAIL_PATTERN.sub("[EMAIL]", redacted)
    redacted = _ID_NUMBER_PATTERN.sub("[ID_NUMBER]", redacted)
    redacted = _PHONE_PATTERN.sub("[PHONE]", redacted)
    redacted = _IPV4_PATTERN.sub("[IP_ADDRESS]", redacted)
    redacted = _MAC_PATTERN.sub("[MAC_ADDRESS]", redacted)
    return _WINDOWS_USER_PATTERN.sub(r"\1[USER]", redacted)


def redact_mapping(payload: dict[str, object]) -> dict[str, object]:
    """Return a redacted JSON-like copy without mutating persisted domain data."""

    return {key: _redact_value(value) for key, value in payload.items()}


def _redact_value(value: object) -> object:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _redact_value(item) for key, item in value.items()}
    return value
