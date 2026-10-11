from pathlib import Path

import pytest

from kuloniku_fr.i2_asset import Language, LanguageSource, Pointer, Term
from kuloniku_fr.translation import (
    apply_french,
    lint_translation,
    source_character_limit,
    target_language_codes,
)


LAB_ASSET = Path("work/lab/game/resources.assets")


@pytest.mark.skipif(not LAB_ASSET.exists(), reason="copie de laboratoire absente")
def test_round_trip_real_i2_object():
    import UnityPy

    environment = UnityPy.load(str(LAB_ASSET))
    obj = next(obj for obj in environment.objects if obj.path_id == 3606)
    raw = obj.get_raw_data()
    source = LanguageSource.parse(raw)

    assert len(source.terms) == 12_211
    assert [language.code for language in source.languages] == [
        "en",
        "id",
        "es",
        "th",
        "zh-CN",
        "zh-TW",
        "de",
        "pt",
    ]
    assert source.serialize() == raw


@pytest.mark.skipif(not LAB_ASSET.exists(), reason="copie de laboratoire absente")
def test_append_french_keeps_languages_and_falls_back_to_english():
    import UnityPy

    environment = UnityPy.load(str(LAB_ASSET))
    obj = next(obj for obj in environment.objects if obj.path_id == 3606)
    source = LanguageSource.parse(obj.get_raw_data())
    original_codes = [language.code for language in source.languages]

    translated, fallback, unknown = apply_french(
        source, {"ACTION_SERVE": "Servir"}, slot_language=None
    )

    assert [language.code for language in source.languages] == [*original_codes, "fr"]
    assert translated == 1
    assert fallback == len(source.terms) - 1
    assert unknown == []
    serve = next(term for term in source.terms if term.key == "ACTION_SERVE")
    assert serve.translations[-1] == "Servir"
    assert serve.touch_translations == []
    other = next(term for term in source.terms if term.key != "ACTION_SERVE")
    assert other.translations[-1] == other.translations[0]
    reparsed = LanguageSource.parse(source.serialize())
    assert reparsed.languages[-1].code == "fr"


@pytest.mark.skipif(not LAB_ASSET.exists(), reason="copie de laboratoire absente")
def test_french_slot_keeps_supported_language_metadata():
    import UnityPy

    environment = UnityPy.load(str(LAB_ASSET))
    obj = next(obj for obj in environment.objects if obj.path_id == 3606)
    source = LanguageSource.parse(obj.get_raw_data())
    original_languages = [
        (language.name, language.code) for language in source.languages
    ]

    apply_french(
        source,
        {"SETTINGS_LANGUAGESELECTION": "Français", "ACTION_SERVE": "Servir"},
        slot_language="de",
    )

    assert [
        (language.name, language.code) for language in source.languages
    ] == original_languages
    german_index = [language.code for language in source.languages].index("de")
    selection = next(
        term for term in source.terms if term.key == "SETTINGS_LANGUAGESELECTION"
    )
    serve = next(term for term in source.terms if term.key == "ACTION_SERVE")
    assert selection.translations[german_index] == "Français"
    assert serve.translations[german_index] == "Servir"


@pytest.mark.skipif(not LAB_ASSET.exists(), reason="copie de laboratoire absente")
def test_lint_detects_length_and_preserves_tokens():
    import UnityPy

    environment = UnityPy.load(str(LAB_ASSET))
    obj = next(obj for obj in environment.objects if obj.path_id == 3606)
    source = LanguageSource.parse(obj.get_raw_data())
    term = next(term for term in source.terms if term.key == "ACTION_SERVE")
    warnings = lint_translation(term, "Une traduction volontairement beaucoup trop longue")
    assert any(warning.kind == "length" for warning in warnings)


def _source_with_native_french() -> LanguageSource:
    return LanguageSource(
        Pointer(0, 0),
        1,
        Pointer(0, 0),
        "Localization",
        0,
        0,
        0,
        [
            Term(
                "KNOWN",
                0,
                ["anglais {name}", "deutsch", "français natif", "technique"],
                b"\x01\x02\x03\x04",
                ["touch en", "touch de", "touch fr", "touch technique"],
            ),
            Term(
                "FALLBACK",
                0,
                ["english fallback", "deutsch", "français natif", "technique"],
                b"\x01\x02\x03\x04",
                [],
            ),
        ],
        0,
        0,
        "",
        [
            Language("English", "en", 0),
            Language("German", "de", 0),
            Language("French", "fr", 0),
            Language("Internal", "", 0),
        ],
        0,
        0,
        "",
        "",
        "",
        "",
        0,
        0,
        0,
        0.0,
        [],
    )


def test_native_french_is_patched_alongside_german_without_touching_technical_columns():
    source = _source_with_native_french()

    translated, fallback, unknown = apply_french(source, {"KNOWN": "Bonjour {name}"})

    assert (translated, fallback, unknown) == (1, 1, [])
    assert target_language_codes(source) == ("de", "fr")
    known, fallback_term = source.terms
    assert known.translations == ["anglais {name}", "Bonjour {name}", "Bonjour {name}", "technique"]
    assert known.touch_translations == ["touch en", "Bonjour {name}", "Bonjour {name}", "touch technique"]
    assert known.flags == b"\x01\x02\x03\x04"
    assert fallback_term.translations == ["english fallback", "english fallback", "english fallback", "technique"]
    assert fallback_term.flags == b"\x01\x02\x03\x04"


def test_legacy_slot_does_not_create_a_french_column_and_fallback_uses_en_code():
    source = _source_with_native_french()
    source.languages.pop(2)
    for term in source.terms:
        term.translations.pop(2)
        term.flags = term.flags[:3]
        if term.touch_translations:
            term.touch_translations.pop(2)

    apply_french(source, {})

    assert target_language_codes(source) == ("de",)
    assert [language.code for language in source.languages] == ["en", "de", ""]
    assert source.terms[1].translations == ["english fallback", "english fallback", "technique"]


def test_lint_uses_english_code_and_ignores_language_columns_without_a_code():
    source = _source_with_native_french()
    source.languages.insert(0, Language("Technical first", "", 0))
    for term in source.terms:
        term.translations.insert(0, "very long technical value that must be ignored")
    term = source.terms[0]

    warnings = lint_translation(term, "Bonjour {name}", source=source)

    assert not any(warning.kind == "tokens" for warning in warnings)
    assert source_character_limit(term, language_codes=[language.code for language in source.languages]) == len("anglais {name}")
