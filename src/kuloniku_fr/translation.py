from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re
from typing import Iterable

from .i2_asset import LanguageSource, Term


TOKEN_PATTERN = re.compile(
    r"\[[^\[\]]+\]|\{[^{}]+\}|<[^<>]+>|%(?:\d+\$)?[-+#0']*\d*(?:\.\d+)?[diuoxXfFeEgGaAcsp]|\\[nrt]"
)


@dataclass(frozen=True)
class TranslationWarning:
    key: str
    kind: str
    message: str


def tokens(value: str) -> Counter[str]:
    return Counter(TOKEN_PATTERN.findall(value))


def source_character_limit(
    term: Term,
    *,
    source_language_count: int | None = None,
    language_codes: Iterable[str] | None = None,
) -> int:
    """Retourne la longueur maximale parmi les langues humaines de la source.

    Certaines versions embarquent des colonnes techniques après les langues I2.
    ``source_language_count`` permet aux appelants qui connaissent la table des
    langues de les exclure, sans modifier les anciens appels qui ne disposent
    que d'un :class:`Term`.
    """

    translations = term.translations
    if language_codes is not None:
        translations = [
            value
            for value, code in zip(term.translations, language_codes)
            if code
        ]
    elif source_language_count is not None:
        translations = translations[:source_language_count]
    return max((len(value) for value in translations if value), default=0)


def _language_index(source: LanguageSource, code: str) -> int:
    try:
        return [language.code for language in source.languages].index(code)
    except ValueError as exc:
        raise ValueError(f"Langue source absente : {code}") from exc


def target_language_codes(
    source: LanguageSource, slot_language: str | None = "de"
) -> tuple[str, ...]:
    """Indique les codes qui recevront le français lors d'une installation.

    Le menu historique expose l'emplacement allemand. Une version récente peut
    aussi contenir une colonne française native : elle est alors remplie en
    parallèle, sans créer cette colonne sur les anciennes versions. ``None``
    garde le mode expérimental qui ajoute une colonne ``fr``.
    """

    codes = [language.code for language in source.languages]
    if slot_language is None:
        return ("fr",)
    if slot_language not in codes:
        raise ValueError(f"Emplacement de langue absent : {slot_language}")
    return (slot_language, "fr") if "fr" in codes and slot_language != "fr" else (slot_language,)


def lint_translation(
    term: Term,
    french: str,
    *,
    source: LanguageSource | None = None,
    source_language_count: int | None = None,
) -> list[TranslationWarning]:
    warnings: list[TranslationWarning] = []
    if source is None:
        english = term.translations[0] if term.translations else ""
    else:
        english_index = _language_index(source, "en")
        english = (
            term.translations[english_index]
            if english_index < len(term.translations)
            else ""
        )
    expected_tokens = tokens(english)
    actual_tokens = tokens(french)
    if expected_tokens != actual_tokens:
        warnings.append(
            TranslationWarning(
                term.key,
                "tokens",
                f"marqueurs différents : attendu {dict(expected_tokens)}, obtenu {dict(actual_tokens)}",
            )
        )

    language_codes = (
        [language.code for language in source.languages] if source is not None else None
    )
    limit = source_character_limit(
        term,
        source_language_count=source_language_count,
        language_codes=language_codes,
    )
    if limit and len(french) > limit:
        warnings.append(
            TranslationWarning(
                term.key,
                "length",
                f"{len(french)} caractères, maximum observé dans les langues source : {limit}",
            )
        )
    return warnings


def apply_french(
    source: LanguageSource,
    translations: dict[str, str],
    *,
    slot_language: str | None = "de",
) -> tuple[int, int, list[str]]:
    """Injecte le français dans un emplacement reconnu par le menu du jeu.

    Toutes les clés françaises absentes reçoivent la version anglaise de la version
    installée. Une mise à jour du jeu peut donc ajouter de nouvelles clés sans rendre
    le patch inutilisable.

    KuloNiku filtre son menu avec une liste codée séparément. Le nom et le code de
    l'emplacement doivent donc rester inchangés. ``None`` conserve un mode
    expérimental d'ajout, utile pour l'analyse mais non proposé par l'installateur.
    """

    codes = [language.code for language in source.languages]
    target_codes = target_language_codes(source, slot_language)
    english_index = _language_index(source, "en")
    appended = slot_language is None and "fr" not in codes
    if appended:
        from .i2_asset import Language

        source.languages.append(Language("French", "fr", 0))
        codes.append("fr")

    target_indices = [_language_index(source, code) for code in target_codes]

    known_keys = {term.key for term in source.terms}
    unknown_keys = sorted(set(translations) - known_keys)
    translated = 0
    fallback = 0
    for term in source.terms:
        english = (
            term.translations[english_index]
            if english_index < len(term.translations)
            else ""
        )
        value = translations.get(term.key, english)
        if term.key in translations:
            translated += 1
        else:
            fallback += 1

        for target_index in target_indices:
            while len(term.translations) <= target_index:
                term.translations.append(english)
            term.translations[target_index] = value

        # Une liste tactile vide signifie « fonctionnalité non utilisée » dans
        # cet asset. Ne pas la matérialiser artificiellement.
        if term.touch_translations:
            for target_index in target_indices:
                while len(term.touch_translations) <= target_index:
                    term.touch_translations.append(english)
                term.touch_translations[target_index] = value

        # I2 conserve un octet d'état par langue dans cette table.
        if appended and len(term.flags) < len(source.languages):
            term.flags += b"\0" * (len(source.languages) - len(term.flags))

    return translated, fallback, unknown_keys
