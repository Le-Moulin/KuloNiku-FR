"""Language-aware extraction and approvals for French shipped by the game."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from .i2_asset import LanguageSource, Term
from .translation import tokens


LANGUAGE_FIELDS = {
    "en": "english", "id": "indonesian", "es": "spanish", "th": "thai",
    "zh-CN": "chinese_simplified", "zh-TW": "chinese_traditional",
    "de": "german", "pt": "portuguese", "ja": "japanese", "fr": "native_french",
}
SOURCE_FIELDS = ["key", *LANGUAGE_FIELDS.values()]


def source_value(source: LanguageSource, term: Term, code: str) -> str:
    index = next((i for i, language in enumerate(source.languages) if language.code == code), None)
    return term.translations[index] if index is not None and index < len(term.translations) else ""


def source_row(source: LanguageSource, term: Term) -> dict[str, str]:
    return {"key": term.key, **{field: source_value(source, term, code) for code, field in LANGUAGE_FIELDS.items()}}


def source_limit(source: LanguageSource, term: Term) -> int:
    return max((len(term.translations[i]) for i, language in enumerate(source.languages)
                if language.code and i < len(term.translations)), default=0)


def reference_digest(english: str, indonesian: str) -> str:
    return hashlib.sha256((english + "\0" + indonesian).encode("utf-8")).hexdigest()


def text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def native_technical_errors(english: str, french: str) -> list[str]:
    errors = []
    if tokens(english) != tokens(french):
        errors.append("tokens")
    if english.count("\n") != french.count("\n") or english.count("\r") != french.count("\r"):
        errors.append("newlines")
    return errors


def approved_native(source: LanguageSource, approvals_path: Path) -> dict[str, str]:
    if not approvals_path.exists():
        return {}
    with approvals_path.open(newline="", encoding="utf-8") as stream:
        approvals = list(csv.DictReader(stream))
    by_key = {term.key: term for term in source.terms}
    accepted = {}
    for row in approvals:
        term = by_key.get(row.get("key", ""))
        if term is None or row.get("status") != "reviewed":
            continue
        english = source_value(source, term, "en")
        native = source_value(source, term, "fr")
        if (native.strip() and row.get("source_hash") == reference_digest(english, source_value(source, term, "id"))
                and row.get("native_fr_sha256") == text_digest(native)
                and not native_technical_errors(english, native)):
            accepted[term.key] = native
    return accepted
