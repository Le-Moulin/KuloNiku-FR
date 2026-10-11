from argparse import Namespace
import json
from pathlib import Path

from kuloniku_fr import cli
from kuloniku_fr.installation import GameAsset


class Language:
    def __init__(self, code: str):
        self.code = code


class Term:
    def __init__(self, key: str, translations: list[str]):
        self.key = key
        self.translations = translations


class Source:
    def __init__(self, french: bool):
        self.languages = [Language("en"), Language("id"), Language("de")]
        self.terms = [
            Term(
                "SETTINGS_LANGUAGESELECTION",
                ["English", "Indonesia", "Français" if french else "Deutsch"],
            )
        ]


def test_load_source_uses_bytes_to_avoid_windows_file_locks(monkeypatch, tmp_path: Path):
    asset = tmp_path / "resources.assets"
    asset.write_bytes(b"unity-asset")
    environment = object()

    class UnityObject:
        def get_raw_data(self):
            return b"i2"

    unity_object = UnityObject()

    monkeypatch.setattr(cli.UnityPy, "load", lambda value: (value, environment))
    monkeypatch.setattr(cli, "find_i2_object", lambda loaded: unity_object)

    class Parsed:
        def serialize(self):
            return b"i2"

    monkeypatch.setattr(cli.LanguageSource, "parse", lambda raw: Parsed())

    loaded, found, _ = cli.load_source(asset)

    assert loaded == (b"unity-asset", environment)
    assert found is unity_object


def test_install_updates_directly_from_verified_original(monkeypatch, tmp_path: Path):
    asset_path = tmp_path / "KuloNiku_Data" / "resources.assets"
    asset_path.parent.mkdir()
    asset_path.write_bytes(b"patched-old")

    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    backup_path = backup_dir / "resources.assets"
    backup_path.write_bytes(b"original")
    manifest_path = backup_dir / "manifest.json"
    manifest = {
        "original_sha256": cli.sha256(backup_path),
        "patched_sha256": cli.sha256(asset_path),
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    monkeypatch.setattr(
        cli,
        "detect_asset",
        lambda game: GameAsset(asset_path, "windows", "full"),
    )
    monkeypatch.setattr(cli, "latest_backup_for", lambda target: (backup_path, manifest))
    monkeypatch.setattr(
        cli,
        "load_source",
        lambda path: (None, None, Source(french=Path(path).read_bytes() != b"original")),
    )
    monkeypatch.setattr(
        cli,
        "load_resolved_french",
        lambda *args, **kwargs: ({"SETTINGS_LANGUAGESELECTION": "Français"}, 0, 0),
    )

    def fake_build(args):
        Path(args.output).write_bytes(b"patched-new")
        return 0

    monkeypatch.setattr(cli, "command_build", fake_build)
    monkeypatch.setattr(cli, "resign_macos", lambda path: None)
    monkeypatch.setattr(cli, "translation_bundle_hash", lambda *args, **kwargs: "bundle")

    result = cli.command_install(
        Namespace(
            game=str(tmp_path),
            translations=str(tmp_path / "fr.csv"),
            source_hashes=None,
            compatibility_overrides=None,
            apply=True,
        )
    )

    assert result == 0
    assert asset_path.read_bytes() == b"patched-new"
    assert backup_path.read_bytes() == b"original"
    updated_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert updated_manifest["original_sha256"] == cli.sha256(backup_path)
    assert updated_manifest["patched_sha256"] == cli.sha256(asset_path)
    assert updated_manifest["translation_bundle_sha256"] == "bundle"


def test_status_reports_current_translation_and_backup(monkeypatch, tmp_path: Path):
    asset_path = tmp_path / "KuloNiku_Data" / "resources.assets"
    asset_path.parent.mkdir()
    asset_path.write_bytes(b"patched")
    translations = tmp_path / "fr.csv"
    translations.write_text("key,fr\n", encoding="utf-8")
    manifest = {
        "patched_sha256": cli.sha256(asset_path),
        "translation_bundle_sha256": "bundle-current",
        "patcher_version": "0.1.0",
    }

    monkeypatch.setattr(
        cli,
        "detect_asset",
        lambda game: GameAsset(asset_path, "windows", "full"),
    )
    monkeypatch.setattr(cli, "load_source", lambda path: (None, None, Source(french=True)))
    monkeypatch.setattr(
        cli,
        "latest_backup_for",
        lambda target: (tmp_path / "backup" / "resources.assets", manifest),
    )
    monkeypatch.setattr(
        cli,
        "translation_bundle_hash",
        lambda *args, **kwargs: "bundle-current",
    )

    report = cli.status_report(
        Namespace(
            game=str(tmp_path),
            translations=str(translations),
            source_hashes=None,
            compatibility_overrides=None,
        )
    )

    assert report["state"] == "patched"
    assert report["translation_state"] == "current"
    assert report["backup_available"] is True
    assert report["schema_version"] == 1
    assert report["source_recognition"] == "unavailable"


def test_source_recognition_marks_unlisted_game_without_blocking(tmp_path: Path):
    translations = tmp_path / "fr.csv"
    translations.write_text("key,fr\n", encoding="utf-8")
    (tmp_path / "known-sources.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "editions": {
                    "full": [
                        {
                            "game_version": "older",
                            "source_profile_sha256": "not-the-current-profile",
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    assert cli.source_recognition(Source(french=False), translations, "full") == "unknown"


def test_status_detects_a_real_steam_replacement_from_the_asset_hash(monkeypatch, tmp_path: Path):
    asset_path = tmp_path / "KuloNiku_Data" / "resources.assets"
    asset_path.parent.mkdir()
    asset_path.write_bytes(b"new-steam-version")
    translations = tmp_path / "fr.csv"
    translations.write_text("key,fr\n", encoding="utf-8")
    manifest = {
        "original_sha256": "old-original",
        "patched_sha256": "old-patched",
        "translation_bundle_sha256": "bundle-current",
    }

    monkeypatch.setattr(
        cli,
        "detect_asset",
        lambda game: GameAsset(asset_path, "windows", "full"),
    )
    monkeypatch.setattr(cli, "load_source", lambda path: (None, None, Source(french=False)))
    monkeypatch.setattr(
        cli,
        "latest_backup_for",
        lambda target: (tmp_path / "backup" / "resources.assets", manifest),
    )
    monkeypatch.setattr(cli, "translation_bundle_hash", lambda *args, **kwargs: "bundle-current")

    report = cli.status_report(
        Namespace(
            game=str(tmp_path),
            translations=str(translations),
            source_hashes=None,
            compatibility_overrides=None,
        )
    )

    assert report["state"] == "game_updated"
    assert report["translation_state"] == "not_installed"


def test_native_french_does_not_trigger_old_patch_update(monkeypatch, tmp_path: Path, capsys):
    path = tmp_path / "resources.assets"
    path.write_bytes(b"new-steam-version")
    native = Source(french=False)
    native.languages.append(Language("fr"))
    native.terms[0].translations.append("English")
    old_manifest = {"patched_sha256": "old-patched", "original_sha256": "old-source"}
    monkeypatch.setattr(cli, "detect_asset", lambda _: GameAsset(path, "windows", "full"))
    monkeypatch.setattr(cli, "load_source", lambda _: (None, None, native))
    monkeypatch.setattr(cli, "latest_backup_for", lambda _: (tmp_path / "old-backup", old_manifest))
    monkeypatch.setattr(cli, "load_resolved_french", lambda *a, **kw: ({"SETTINGS_LANGUAGESELECTION": "Français"}, 0, 0))
    monkeypatch.setattr(cli, "backup_asset", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("simulation wrote a backup")))
    assert cli.command_install(Namespace(game=str(tmp_path), translations=str(tmp_path / "fr.csv"), apply=False)) == 0
    assert path.read_bytes() == b"new-steam-version"
    assert "de, fr" in capsys.readouterr().out


def test_new_steam_patch_creates_its_own_restorable_backup(monkeypatch, tmp_path: Path):
    from kuloniku_fr import installation
    path = tmp_path / "KuloNiku_Data" / "resources.assets"
    path.parent.mkdir()
    path.write_bytes(b"new-steam-version")
    data = tmp_path / "user-data"
    monkeypatch.setattr(installation, "user_data_dir", lambda: data)
    monkeypatch.setattr(cli, "detect_asset", lambda _: GameAsset(path, "windows", "full"))

    def load(p):
        native = Source(french=Path(p).read_bytes() == b"patched-new")
        native.languages.append(Language("fr"))
        native.terms[0].translations.append("Français" if Path(p).read_bytes() == b"patched-new" else "English")
        return None, None, native

    monkeypatch.setattr(cli, "load_source", load)
    monkeypatch.setattr(cli, "load_resolved_french", lambda *a, **kw: ({"SETTINGS_LANGUAGESELECTION": "Français"}, 0, 0))
    monkeypatch.setattr(cli, "command_build", lambda args: Path(args.output).write_bytes(b"patched-new"))
    monkeypatch.setattr(cli, "translation_bundle_hash", lambda *a, **kw: "bundle")
    monkeypatch.setattr(cli, "resign_macos", lambda _: None)
    args = Namespace(game=str(tmp_path), translations=str(tmp_path / "fr.csv"), apply=True)
    cli.command_install(args)
    backup, manifest = installation.latest_backup_for(path)
    assert backup.read_bytes() == b"new-steam-version"
    assert manifest["pending"] is False
    assert manifest["target_languages"] == ["de", "fr"]
    cli.command_restore(args)
    assert path.read_bytes() == b"new-steam-version"


def test_failed_install_does_not_activate_backup(monkeypatch, tmp_path: Path):
    import pytest
    from kuloniku_fr import installation
    path = tmp_path / "resources.assets"
    path.write_bytes(b"source")
    monkeypatch.setattr(installation, "user_data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr(cli, "detect_asset", lambda _: GameAsset(path, "windows", "full"))
    monkeypatch.setattr(cli, "load_source", lambda p: (None, None, Source(french=Path(p).read_bytes() == b"candidate")))
    monkeypatch.setattr(cli, "load_resolved_french", lambda *a, **kw: ({"SETTINGS_LANGUAGESELECTION": "Français"}, 0, 0))
    monkeypatch.setattr(cli, "command_build", lambda a: Path(a.output).write_bytes(b"candidate"))
    calls = []

    def resign(_):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("signature failed")

    monkeypatch.setattr(cli, "resign_macos", resign)
    with pytest.raises(RuntimeError, match="signature failed"):
        cli.command_install(Namespace(game=str(tmp_path), translations=str(tmp_path / "fr.csv"), apply=True))
    assert path.read_bytes() == b"source"
    with pytest.raises(FileNotFoundError):
        installation.latest_backup_for(path)


def test_restore_cannot_downgrade_a_steam_update(monkeypatch, tmp_path: Path):
    import pytest
    path = tmp_path / "resources.assets"
    path.write_bytes(b"new-steam")
    monkeypatch.setattr(cli, "detect_asset", lambda _: GameAsset(path, "windows", "full"))
    monkeypatch.setattr(cli, "latest_backup_for", lambda _: (tmp_path / "old", {"original_sha256": "old", "patched_sha256": "old-patch"}))
    with pytest.raises(RuntimeError, match="ancienne version"):
        cli.command_restore(Namespace(game=str(tmp_path), apply=True))
    assert path.read_bytes() == b"new-steam"


def test_source_changed_during_build_is_not_overwritten(monkeypatch, tmp_path: Path):
    import pytest
    from kuloniku_fr import installation
    path = tmp_path / "resources.assets"
    path.write_bytes(b"source")
    monkeypatch.setattr(installation, "user_data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr(cli, "detect_asset", lambda _: GameAsset(path, "windows", "full"))
    monkeypatch.setattr(cli, "load_source", lambda p: (None, None, Source(french=False)))
    monkeypatch.setattr(cli, "load_resolved_french", lambda *a, **kw: ({"SETTINGS_LANGUAGESELECTION": "Français"}, 0, 0))

    def build(args):
        Path(args.output).write_bytes(b"candidate")
        path.write_bytes(b"concurrent-steam-update")

    monkeypatch.setattr(cli, "command_build", build)
    with pytest.raises(RuntimeError, match="pendant la préparation"):
        cli.command_install(Namespace(game=str(tmp_path), translations=str(tmp_path / "fr.csv"), apply=True))
    assert path.read_bytes() == b"concurrent-steam-update"
    with pytest.raises(FileNotFoundError):
        installation.latest_backup_for(path)


def test_restore_failure_keeps_the_previous_patch(monkeypatch, tmp_path: Path):
    import pytest
    path = tmp_path / "resources.assets"
    path.write_bytes(b"patched")
    backup = tmp_path / "backup"
    backup.write_bytes(b"original")
    manifest = {"original_sha256": cli.sha256(backup), "patched_sha256": cli.sha256(path)}
    monkeypatch.setattr(cli, "detect_asset", lambda _: GameAsset(path, "windows", "full"))
    monkeypatch.setattr(cli, "latest_backup_for", lambda _: (backup, manifest))
    calls = []

    def resign(_):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("signature failed")

    monkeypatch.setattr(cli, "resign_macos", resign)
    with pytest.raises(RuntimeError, match="signature failed"):
        cli.command_restore(Namespace(game=str(tmp_path), apply=True))
    assert path.read_bytes() == b"patched"
