from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile


@dataclass(frozen=True)
class GameAsset:
    path: Path
    platform: str
    edition: str


def user_data_dir() -> Path:
    if platform.system() == "Darwin":
        return Path.home() / "Library" / "Application Support" / "KuloNiku FR"
    if platform.system() == "Windows":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "KuloNiku FR"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "kuloniku-fr"


def detect_asset(game: Path) -> GameAsset:
    game = game.expanduser().resolve()
    candidates: list[tuple[Path, str]] = []
    if game.is_file() and game.name == "resources.assets":
        candidates.append((game, "macos" if ".app" in str(game) else "windows"))
    elif game.suffix == ".app":
        candidates.append((game / "Contents/Resources/Data/resources.assets", "macos"))
    elif game.is_dir():
        for candidate in game.glob("*.app/Contents/Resources/Data/resources.assets"):
            candidates.append((candidate, "macos"))
        for candidate in game.glob("*_Data/resources.assets"):
            candidates.append((candidate, "windows"))
        if (game / "Contents/Resources/Data/resources.assets").exists():
            candidates.append((game / "Contents/Resources/Data/resources.assets", "macos"))

    existing = [(path, system) for path, system in candidates if path.is_file()]
    unique = list(dict.fromkeys(existing))
    if len(unique) != 1:
        raise FileNotFoundError(
            f"Un seul resources.assets était attendu dans {game}, {len(unique)} trouvé(s)."
        )
    path, system = unique[0]
    edition = "demo" if "demo" in str(path).lower() else "full"
    return GameAsset(path, system, edition)


def backup_asset(
    asset: GameAsset,
    sha256_fn,
    *,
    expected_sha256: str | None = None,
    pending: bool = False,
) -> tuple[Path, Path]:
    """Sauvegarde l'état actuel du jeu après avoir vérifié sa source.

    Une sauvegarde ``pending`` est créée avant une installation, mais reste
    invisible de ``latest_backup_for`` tant que l'appelant n'a pas confirmé le
    patch et retiré ce marqueur de son manifeste.
    """

    original_hash = sha256_fn(asset.path)
    if expected_sha256 is not None and original_hash != expected_sha256:
        raise RuntimeError(
            "Le fichier source a changé avant la création de la sauvegarde."
        )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_dir = user_data_dir() / "backups" / f"{stamp}-{original_hash[:12]}"
    backup_dir.mkdir(parents=True, exist_ok=False)
    backup_path = backup_dir / "resources.assets"
    shutil.copy2(asset.path, backup_path)
    if sha256_fn(backup_path) != original_hash:
        raise RuntimeError("La vérification SHA-256 de la sauvegarde a échoué.")
    manifest_path = backup_dir / "manifest.json"
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "target": str(asset.path.resolve()),
        "platform": asset.platform,
        "edition": asset.edition,
        "original_sha256": original_hash,
    }
    if pending:
        manifest["pending"] = True
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return backup_path, manifest_path


def atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def require_writable_asset(path: Path) -> None:
    if not os.access(path, os.W_OK) or not os.access(path.parent, os.W_OK):
        raise PermissionError(
            "Le fichier du jeu n’est pas accessible en écriture. "
            "Fermez KuloNiku et vérifiez les permissions de la bibliothèque Steam."
        )


def mac_app_for(asset_path: Path) -> Path | None:
    for parent in asset_path.parents:
        if parent.suffix == ".app":
            return parent
    return None


def resign_macos(asset_path: Path) -> None:
    app = mac_app_for(asset_path)
    if not app:
        return
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)


def backup_manifests() -> list[Path]:
    root = user_data_dir() / "backups"
    if not root.exists():
        return []
    return sorted(root.glob("*/manifest.json"), reverse=True)


def latest_backup_for(target: Path) -> tuple[Path, dict]:
    resolved = str(target.resolve())
    for manifest_path in backup_manifests():
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("target") == resolved and not manifest.get("pending", False):
            return manifest_path.parent / "resources.assets", manifest
    raise FileNotFoundError(f"Aucune sauvegarde trouvée pour {resolved}.")


def backup_for_patched_hash(target: Path, patched_sha256: str) -> tuple[Path, dict]:
    """Retourne la sauvegarde associée exactement au patch actuellement lu."""

    resolved = str(target.resolve())
    for manifest_path in backup_manifests():
        manifest = json.loads(manifest_path.read_text())
        if (
            manifest.get("target") == resolved
            and not manifest.get("pending", False)
            and manifest.get("patched_sha256") == patched_sha256
        ):
            return manifest_path.parent / "resources.assets", manifest
    raise FileNotFoundError(
        f"Aucune sauvegarde validée ne correspond au patch {patched_sha256}."
    )


def installation_state(
    current_hash: str, french_active: bool, manifest: dict | None
) -> str:
    """Classify the installed asset without modifying it."""
    if french_active:
        if manifest and manifest.get("patched_sha256") == current_hash:
            return "patched"
        return "patched_unknown"
    if manifest:
        if manifest.get("original_sha256") == current_hash:
            return "restored"
        return "game_updated"
    return "unpatched"
