from types import SimpleNamespace
import csv

from kuloniku_fr.i2_asset import Language, Term
from kuloniku_fr.localization import (
    SOURCE_FIELDS, approved_native, native_technical_errors, reference_digest,
    source_limit, source_row, text_digest,
)
from kuloniku_fr.translation import tokens


def source():
    return SimpleNamespace(
        languages=[Language("Indonesian", "id", 0), Language("English", "en", 0),
                   Language("French", "fr", 0), Language("Notes", "", 0)],
        terms=[Term("HELLO", 0, ["Halo [NAME]", "Hello [NAME]", "Bonjour [NAME]", "x" * 1000], b"", [])],
    )


def write_approval(path, *, french="Bonjour [NAME]", english="Hello [NAME]", status="reviewed"):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["key", "source_hash", "native_fr_sha256", "status"])
        writer.writeheader()
        writer.writerow(dict(key="HELLO", source_hash=reference_digest(english, "Halo [NAME]"),
                             native_fr_sha256=text_digest(french), status=status))


def test_extraction_uses_language_codes_and_omits_technical_columns():
    value = source()
    row = source_row(value, value.terms[0])
    assert list(row) == SOURCE_FIELDS
    assert row["english"] == "Hello [NAME]"
    assert row["native_french"] == "Bonjour [NAME]"
    assert source_limit(value, value.terms[0]) == len("Bonjour [NAME]")


def test_native_approval_requires_both_exact_text_and_reference(tmp_path):
    path = tmp_path / "native-approvals.csv"
    value = source()
    write_approval(path)
    assert approved_native(value, path) == {"HELLO": "Bonjour [NAME]"}
    value.terms[0].translations[2] = "Salut [NAME]"
    assert approved_native(value, path) == {}
    value = source()
    value.terms[0].translations[1] = "Hi [NAME]"
    assert approved_native(value, path) == {}


def test_native_approval_cannot_override_missing_variables(tmp_path):
    value = source()
    value.terms[0].translations[2] = "Bonjour"
    path = tmp_path / "native-approvals.csv"
    write_approval(path, french="Bonjour")
    assert approved_native(value, path) == {}
    assert native_technical_errors("First\nSecond", "Premier Deuxième") == ["newlines"]


def test_native_pending_is_not_applied(tmp_path):
    path = tmp_path / "native-approvals.csv"
    write_approval(path, status="pending")
    assert approved_native(source(), path) == {}


def test_percent_in_prose_is_not_a_printf_placeholder():
    assert tokens("Cooks [X]% slower") == tokens("Cuit [X]% plus lentement")
    assert tokens("100% of customers") == tokens("100% des clients")
    assert tokens("Value: %02d / %1$s") == {"%02d": 1, "%1$s": 1}
