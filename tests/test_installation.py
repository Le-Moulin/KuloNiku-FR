from pathlib import Path

import pytest

from kuloniku_fr import installation
from kuloniku_fr.installation import (
    GameAsset,
    atomic_copy,
    backup_asset,
    backup_for_patched_hash,
    detect_asset,
    installation_state,
    latest_backup_for,
    require_writable_asset,
    user_data_dir,
)


def test_detect_windows_asset(tmp_path: Path):
    asset = tmp_path / "KuloNiku_Data" / "resources.assets"
    asset.parent.mkdir()
    asset.write_bytes(b"test")

    detected = detect_asset(tmp_path)

    assert detected.path == asset.resolve()
    assert detected.platform == "windows"
    assert detected.edition == "full"


def test_detect_refuses_ambiguous_assets(tmp_path: Path):
    for name in ("A_Data", "B_Data"):
        path = tmp_path / name / "resources.assets"
        path.parent.mkdir()
        path.write_bytes(b"test")

    with pytest.raises(FileNotFoundError):
        detect_asset(tmp_path)


@pytest.mark.parametrize(
    ("current_hash", "french_active", "manifest", "expected"),
    [
        ("patched", True, {"patched_sha256": "patched"}, "patched"),
        ("other", True, {"patched_sha256": "patched"}, "patched_unknown"),
        ("original", False, {"original_sha256": "original"}, "restored"),
        ("steam-update", False, {"original_sha256": "original"}, "game_updated"),
        ("new", False, None, "unpatched"),
    ],
)
def test_installation_state(current_hash, french_active, manifest, expected):
    assert installation_state(current_hash, french_active, manifest) == expected


def test_linux_user_data_uses_xdg(monkeypatch, tmp_path: Path):
    xdg_data = tmp_path / "xdg-data"
    monkeypatch.setattr(installation.platform, "system", lambda: "Linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg_data))

    assert user_data_dir() == xdg_data / "kuloniku-fr"


def test_unwritable_game_file_has_a_clear_error(monkeypatch, tmp_path: Path):
    asset = tmp_path / "resources.assets"
    asset.write_bytes(b"game")
    monkeypatch.setattr(installation.os, "access", lambda path, mode: False)

    with pytest.raises(PermissionError, match="n’est pas accessible en écriture"):
        require_writable_asset(asset)


def test_linux_backup_and_restore_round_trip(monkeypatch, tmp_path: Path):
    from hashlib import sha256

    xdg_data = tmp_path / "xdg-data"
    asset_path = tmp_path / "KuloNiku_Data" / "resources.assets"
    asset_path.parent.mkdir()
    asset_path.write_bytes(b"original")
    monkeypatch.setattr(installation.platform, "system", lambda: "Linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg_data))
    digest = lambda path: sha256(path.read_bytes()).hexdigest()

    backup, manifest = backup_asset(GameAsset(asset_path, "windows", "full"), digest)
    asset_path.write_bytes(b"patched")
    atomic_copy(backup, asset_path)

    assert backup.is_relative_to(xdg_data / "kuloniku-fr" / "backups")
    assert manifest.is_file()
    assert asset_path.read_bytes() == b"original"
    assert digest(asset_path) == digest(backup)


def test_pending_backup_is_not_selected_until_the_patch_is_committed(monkeypatch, tmp_path: Path):
    from hashlib import sha256
    import json

    xdg_data = tmp_path / "xdg-data"
    asset_path = tmp_path / "KuloNiku_Data" / "resources.assets"
    asset_path.parent.mkdir()
    asset_path.write_bytes(b"legacy-original")
    monkeypatch.setattr(installation.platform, "system", lambda: "Linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg_data))
    digest = lambda path: sha256(path.read_bytes()).hexdigest()

    legacy_backup, legacy_manifest_path = backup_asset(
        GameAsset(asset_path, "windows", "full"), digest
    )
    legacy_manifest = json.loads(legacy_manifest_path.read_text())
    legacy_manifest["patched_sha256"] = "legacy-patch"
    legacy_manifest_path.write_text(json.dumps(legacy_manifest))

    asset_path.write_bytes(b"new-source")
    pending_backup, pending_manifest_path = backup_asset(
        GameAsset(asset_path, "windows", "full"),
        digest,
        expected_sha256=digest(asset_path),
        pending=True,
    )

    selected, manifest = latest_backup_for(asset_path)
    assert selected == legacy_backup
    assert manifest["patched_sha256"] == "legacy-patch"
    assert json.loads(pending_manifest_path.read_text())["pending"] is True
    assert pending_backup.exists()


def test_backup_rejects_a_changed_source_before_copying(monkeypatch, tmp_path: Path):
    from hashlib import sha256

    xdg_data = tmp_path / "xdg-data"
    asset_path = tmp_path / "resources.assets"
    asset_path.write_bytes(b"current")
    monkeypatch.setattr(installation.platform, "system", lambda: "Linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg_data))
    digest = lambda path: sha256(path.read_bytes()).hexdigest()

    with pytest.raises(RuntimeError, match="a changé"):
        backup_asset(
            GameAsset(asset_path, "windows", "full"),
            digest,
            expected_sha256="different",
        )

    assert not (xdg_data / "kuloniku-fr" / "backups").exists()


def test_backup_can_be_selected_by_its_exact_patched_hash(monkeypatch, tmp_path: Path):
    from hashlib import sha256
    import json

    xdg_data = tmp_path / "xdg-data"
    asset_path = tmp_path / "resources.assets"
    asset_path.write_bytes(b"original")
    monkeypatch.setattr(installation.platform, "system", lambda: "Linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg_data))
    digest = lambda path: sha256(path.read_bytes()).hexdigest()
    backup, manifest_path = backup_asset(GameAsset(asset_path, "windows", "full"), digest)
    manifest = json.loads(manifest_path.read_text())
    manifest["patched_sha256"] = "exact-patch"
    manifest_path.write_text(json.dumps(manifest))

    selected, selected_manifest = backup_for_patched_hash(asset_path, "exact-patch")

    assert selected == backup
    assert selected_manifest["original_sha256"] == digest(backup)
