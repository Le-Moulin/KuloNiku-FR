from kuloniku_fr.cli import reference_hash, resolve_french_for_source
from kuloniku_fr.i2_asset import Language, LanguageSource, Pointer, Term


def source_with(*terms: Term) -> LanguageSource:
    return LanguageSource(
        game_object=Pointer(0, 0),
        enabled=1,
        script=Pointer(0, 0),
        name="I2Languages",
        agrees_scene=0,
        agrees_plugins=0,
        google_live_sync_up_to_date=0,
        terms=list(terms),
        case_insensitive_terms=0,
        missing_translation_mode=0,
        app_name_term="",
        languages=[Language("English", "en", 0), Language("Indonesian", "id", 0)],
        ignore_device_language=0,
        allow_unloading_languages=0,
        google_web_service_url="",
        google_spreadsheet_key="",
        google_spreadsheet_name="",
        google_last_updated_version="",
        google_update_frequency=0,
        google_editor_check_frequency=0,
        google_update_synchronization=0,
        google_update_delay=0.0,
        assets=[],
    )


def term(key: str, english: str, indonesian: str) -> Term:
    return Term(key, 0, [english, indonesian], b"", [])


def test_source_hash_rejects_stale_translation_and_keeps_current_one():
    source = source_with(term("SAME", "Same", "Sama"), term("CHANGED", "New", "Baru"))
    translations = {"SAME": "Identique", "CHANGED": "Ancien sens"}
    hashes = {
        "SAME": reference_hash("Same", "Sama"),
        "CHANGED": reference_hash("Old", "Lama"),
    }

    resolved, rejected, applied = resolve_french_for_source(source, translations, hashes)

    assert resolved == {"SAME": "Identique"}
    assert rejected == 1
    assert applied == 0


def test_demo_override_is_selected_only_for_its_exact_source():
    demo_hash = reference_hash("Old demo meaning", "Arti demo lama")
    overrides = {("SHARED", demo_hash): "Sens propre à la démo"}
    translations = {"SHARED": "Sens de la version complète"}
    full_hashes = {"SHARED": reference_hash("Full meaning", "Arti penuh")}

    demo = source_with(term("SHARED", "Old demo meaning", "Arti demo lama"))
    resolved, rejected, applied = resolve_french_for_source(
        demo, translations, full_hashes, overrides
    )
    assert resolved == {"SHARED": "Sens propre à la démo"}
    assert rejected == 1
    assert applied == 1

    unknown_update = source_with(term("SHARED", "Third meaning", "Arti ketiga"))
    resolved, rejected, applied = resolve_french_for_source(
        unknown_update, translations, full_hashes, overrides
    )
    assert resolved == {}
    assert rejected == 1
    assert applied == 0
