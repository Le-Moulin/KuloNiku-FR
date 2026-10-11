from argparse import Namespace
import csv

from kuloniku_fr.batching import (
    SOURCE_FIELDS,
    make_batches,
    make_update_batches,
    propagate_dialogue_backups,
)
from kuloniku_fr.cli import command_prepare_backups, command_prepare_update_batches


def row(key: str, english: str) -> dict[str, str]:
    return {
        "key": key,
        "english": english,
        "indonesian": english,
        "spanish": english,
        "thai": english,
        "chinese_simplified": english,
        "chinese_traditional": english,
        "german": english,
        "portuguese": english,
        "japanese": "",
        "native_french": "",
    }


def test_make_batches_excludes_done_empty_and_backup_rows():
    rows = [
        row("INGREDIENT_A", "A"),
        row("Dialogue/HERO_1", "Hello"),
        row("Dialogue (Backup)/HERO_1", "Hello"),
        row("EMPTY", ""),
    ]
    for field in rows[-1]:
        if field != "key":
            rows[-1][field] = ""

    batches = make_batches(rows, {"INGREDIENT_A"}, character_budget=100)

    assert [[item["key"] for item in batch.rows] for batch in batches] == [
        ["Dialogue/HERO_1"]
    ]


def test_propagate_only_exact_english_backup_pairs():
    rows = [
        row("Dialogue/HERO_1", "Hello"),
        row("Dialogue (Backup)/HERO_1", "Hello"),
        row("Dialogue/HERO_2", "New text"),
        row("Dialogue (Backup)/HERO_2", "Old text"),
    ]

    propagated, unresolved = propagate_dialogue_backups(
        rows, {"Dialogue/HERO_1": "Bonjour", "Dialogue/HERO_2": "Nouveau texte"}
    )

    assert propagated == {"Dialogue (Backup)/HERO_1": "Bonjour"}
    assert [item["key"] for item in unresolved] == ["Dialogue (Backup)/HERO_2"]


def test_prepare_backups_writes_exact_copy_and_review_batch(tmp_path):
    rows = [
        row("Dialogue/HERO_1", "Hello"),
        row("Dialogue (Backup)/HERO_1", "Hello"),
        row("Dialogue/HERO_2", "New text"),
        row("Dialogue (Backup)/HERO_2", "Old text"),
    ]
    source = tmp_path / "source.csv"
    with source.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=SOURCE_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    translations = tmp_path / "fr.csv"
    translations.write_text(
        "key,fr,status,notes\nDialogue/HERO_1,Bonjour,reviewed,\n"
        "Dialogue/HERO_2,Nouveau texte,reviewed,\n",
        encoding="utf-8",
    )
    source_dir = tmp_path / "backup-source"
    output_dir = tmp_path / "backup-output"
    manifest = tmp_path / "manifest.json"

    result = command_prepare_backups(
        Namespace(
            source=str(source),
            translations=str(translations),
            source_dir=str(source_dir),
            output_dir=str(output_dir),
            manifest=str(manifest),
            character_budget=80_000,
        )
    )

    assert result == 0
    assert (output_dir / "900-dialogue-backups-identiques.csv").read_text(
        encoding="utf-8"
    ).splitlines()[1].startswith("Dialogue (Backup)/HERO_1,Bonjour,reviewed,")
    assert (source_dir / "901-dialogue-backups-a-reviser.csv").exists()


def test_make_update_batches_selects_new_and_reference_language_changes_only():
    previous = [
        row("INGREDIENT_SAME", "Same"),
        row("INGREDIENT_EN_CHANGED", "Old English"),
        row("INGREDIENT_ID_CHANGED", "Same Indonesian"),
        row("Dialogue (Backup)/HERO_1", "Old backup"),
    ]
    previous[2]["indonesian"] = "Lama"
    current = [
        row("INGREDIENT_SAME", "Same"),
        row("INGREDIENT_EN_CHANGED", "New English"),
        row("INGREDIENT_ID_CHANGED", "Same Indonesian"),
        row("INGREDIENT_NEW", "New"),
        row("Dialogue (Backup)/HERO_1", "Changed backup"),
    ]
    current[1]["indonesian"] = "Old English"
    current[2]["indonesian"] = "Baru"
    translations = {
        "INGREDIENT_SAME": "Identique",
        "INGREDIENT_EN_CHANGED": "Ancien français",
        "INGREDIENT_ID_CHANGED": "Indonésien ancien",
        "Dialogue (Backup)/HERO_1": "Copie",
    }

    batches = make_update_batches(previous, current, translations, character_budget=1000)
    selected = {item["key"]: item for batch in batches for item in batch.rows}

    assert set(selected) == {
        "INGREDIENT_EN_CHANGED",
        "INGREDIENT_ID_CHANGED",
        "INGREDIENT_NEW",
    }
    updated_english = row("INGREDIENT_EN_CHANGED", "New English")
    updated_english["indonesian"] = "Old English"
    assert selected["INGREDIENT_EN_CHANGED"] == {
        **updated_english,
        "change": "english_changed",
        "previous_english": "Old English",
        "previous_indonesian": "Old English",
        "fr_previous": "Ancien français",
        "max_source_chars": len("New English"),
    }
    assert selected["INGREDIENT_ID_CHANGED"]["change"] == "indonesian_changed"
    assert selected["INGREDIENT_ID_CHANGED"]["previous_indonesian"] == "Lama"
    assert selected["INGREDIENT_ID_CHANGED"]["fr_previous"] == "Indonésien ancien"
    assert selected["INGREDIENT_NEW"]["change"] == "new"
    assert selected["INGREDIENT_NEW"]["fr_previous"] == ""


def test_prepare_update_batches_writes_previous_french_context(tmp_path):
    previous = [row("INGREDIENT_A", "Old")]
    current = [row("INGREDIENT_A", "New"), row("INGREDIENT_B", "Brand new")]
    current[0]["indonesian"] = "Old"
    previous_path = tmp_path / "previous.csv"
    current_path = tmp_path / "current.csv"
    for path, rows in ((previous_path, previous), (current_path, current)):
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=SOURCE_FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    translations = tmp_path / "fr.csv"
    translations.write_text(
        "key,fr,status,notes\nINGREDIENT_A,Ancienne version,reviewed,\n",
        encoding="utf-8",
    )
    source_dir = tmp_path / "update-source"
    output_dir = tmp_path / "update-output"
    manifest = tmp_path / "manifest.json"

    result = command_prepare_update_batches(
        Namespace(
            previous_source=str(previous_path),
            source=str(current_path),
            translations=str(translations),
            source_dir=str(source_dir),
            output_dir=str(output_dir),
            manifest=str(manifest),
            character_budget=80_000,
        )
    )

    assert result == 0
    rows = list(csv.DictReader((source_dir / "001-culinary-system-ingredient.csv").open(encoding="utf-8")))
    updated_a = row("INGREDIENT_A", "New")
    updated_a["indonesian"] = "Old"
    assert rows == [
        {
            **updated_a,
            "change": "english_changed",
            "previous_english": "Old",
            "previous_indonesian": "Old",
            "fr_previous": "Ancienne version",
            "max_source_chars": "3",
        },
        {
            **row("INGREDIENT_B", "Brand new"),
            "change": "new",
            "previous_english": "",
            "previous_indonesian": "",
            "fr_previous": "",
            "max_source_chars": "9",
        },
    ]
