"""Shared sanitization helpers for automation payloads."""

from typing import Any

SENSITIVE_KEYS = (
    "password",
    "token",
    "secret",
    "credentials",
    "auth",
    "api_key",
    "apikey",
    "access_key",
    "refresh_token",
    "private_key",
)


def redact_sensitive(
    data: Any,
    *,
    redacted_value: str = "***",
    redact_all: bool = False,
    redact_metadata: bool = False,
) -> Any:
    """Recursively redact sensitive values without mutating the input."""
    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            key_str = str(key)
            key_lower = key_str.lower()
            if redact_metadata and key_lower == "metadata":
                sanitized[key_str] = redact_sensitive(
                    value,
                    redacted_value=redacted_value,
                    redact_all=True,
                    redact_metadata=redact_metadata,
                )
            elif redact_all or any(term in key_lower for term in SENSITIVE_KEYS):
                sanitized[key_str] = redacted_value
            else:
                sanitized[key_str] = redact_sensitive(
                    value,
                    redacted_value=redacted_value,
                    redact_metadata=redact_metadata,
                )
        return sanitized

    if isinstance(data, list):
        return [
            redact_sensitive(
                item,
                redacted_value=redacted_value,
                redact_all=redact_all,
                redact_metadata=redact_metadata,
            )
            for item in data
        ]

    if redact_all:
        return redacted_value
    return data
