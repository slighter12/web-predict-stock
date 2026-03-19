from __future__ import annotations


def clean_required_text(value: str) -> str:
    return value.strip()


def clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
