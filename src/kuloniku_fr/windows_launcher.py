from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from typing import Callable
import urllib.request
import webbrowser
from zipfile import BadZipFile, ZipFile

from . import __version__
from .installation import user_data_dir


REPOSITORY_URL = "https://github.com/Le-Moulin/KuloNiku-FR"
RELEASES_API_URL = "https://api.github.com/repos/Le-Moulin/KuloNiku-FR/releases?per_page=10"
STEAM_APP_ID = "3357960"
TRANSLATION_PACKAGE_FILES = {
    "fr.csv",
    "source-hashes.csv",
    "demo-overrides.csv",
    "known-sources.json",
}
OPTIONAL_TRANSLATION_FILES = {"full-overrides.csv", "native-approvals.csv"}
REVIEW_CONTEXT_FILES = {
    "review-overrides.csv",
    "TERMINOLOGY.md",
    "AGENT_BRIEF.md",
}


def engine_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    return environment


def decode_engine_output(output: bytes) -> str:
    try:
        return output.decode("utf-8")
    except UnicodeDecodeError:
        return output.decode("cp1252", errors="replace")


def version_tuple(version: str) -> tuple[int, ...]:
    """Return a comparable key for stable, alpha, beta and release-candidate versions."""
    match = re.search(
        r"(\d+)\.(\d+)\.(\d+)(?:[-.]?(alpha|beta|rc|a|b)(?:[.-]?(\d+))?)?",
        version.lower(),
    )
    if match is None:
        return (0, 0, 0, 3, 0)
    major, minor, patch = (int(match.group(index)) for index in range(1, 4))
    prerelease = match.group(4)
    stage = {
        "a": 0,
        "alpha": 0,
        "b": 1,
        "beta": 1,
        "rc": 2,
    }.get(prerelease, 3)
    prerelease_number = int(match.group(5) or 0)
    return (major, minor, patch, stage, prerelease_number)


def is_prerelease_version(version: str) -> bool:
    return version_tuple(version)[3] < 3


def available_update_kind(
    manifest: dict,
    *,
    edition: str,
    bundled_translation_hash: str,
    current_version: str = __version__,
) -> str | None:
    installer_available, translation_action = available_updates(
        manifest,
        edition=edition,
        bundled_translation_hash=bundled_translation_hash,
        current_version=current_version,
    )
    if installer_available:
        return "engine"
    if translation_action:
        return "translations"
    return None


def available_updates(
    manifest: dict,
    *,
    edition: str | None = None,
    bundled_translation_hash: str | None = None,
    current_version: str = __version__,
) -> tuple[bool, str | None]:
    """Keep application and translation updates as independent decisions."""
    installer_available = version_tuple(str(manifest.get("version", "0"))) > version_tuple(
        current_version
    )
    if not edition or bundled_translation_hash is None:
        return installer_available, None

    remote_hash = manifest.get("translation_bundles", {}).get(edition)
    if not remote_hash or remote_hash == bundled_translation_hash:
        return installer_available, None

    package = manifest.get("translation_package")
    if not isinstance(package, dict) or package.get("bundles", {}).get(edition) != remote_hash:
        return installer_available, "unavailable"
    if version_tuple(str(package.get("minimum_patcher_version", "0"))) > version_tuple(
        current_version
    ):
        return installer_available, "installer_required"
    return installer_available, "download"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_translation_package(archive: Path, destination: Path, expected_sha256: str) -> Path:
    """Verify and extract only the public translation files from a release archive."""
    if sha256_file(archive) != expected_sha256.lower():
        raise ValueError("L’empreinte du paquet de traduction ne correspond pas.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".download-", dir=destination.parent))
    try:
        with ZipFile(archive) as bundle:
            names = {item.filename for item in bundle.infolist() if not item.is_dir()}
            if not TRANSLATION_PACKAGE_FILES.issubset(names):
                raise ValueError("Le paquet de traduction est incomplet.")
            for name in TRANSLATION_PACKAGE_FILES | OPTIONAL_TRANSLATION_FILES | REVIEW_CONTEXT_FILES | {"NOTICE.md"}:
                if name not in names:
                    continue
                target = temporary / name
                with bundle.open(name) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
        if destination.exists():
            shutil.rmtree(destination)
        temporary.replace(destination)
    except (BadZipFile, OSError, ValueError):
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination / "fr.csv"


def review_context_directory(active_translations: Path, bundled_translations: Path) -> Path:
    """Prefer updated review references, with bundled files as a safe fallback."""
    active_directory = active_translations.parent
    if all((active_directory / name).is_file() for name in REVIEW_CONTEXT_FILES):
        return active_directory
    return bundled_translations.parent


def default_review_workspace_output() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "KuloNiku FR" / "review-workspace" / "index.html"
    return user_data_dir() / "review-workspace" / "index.html"


def default_review_test_output() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "KuloNiku FR" / "review-test" / "fr.csv"
    return user_data_dir() / "review-test" / "fr.csv"


def review_workspace_arguments(
    engine: Path,
    game: Path,
    translations: Path,
    context_directory: Path,
    output: Path,
) -> list[str]:
    return [
        str(engine),
        "review-workspace",
        str(game),
        "--translations",
        str(translations),
        "--review-notes",
        str(context_directory / "review-overrides.csv"),
        "--terminology",
        str(context_directory / "TERMINOLOGY.md"),
        "--brief",
        str(context_directory / "AGENT_BRIEF.md"),
        "--output",
        str(output),
    ]


def prepare_review_test_arguments(
    engine: Path,
    game: Path,
    proposals: Path,
    translations: Path,
    output: Path,
) -> list[str]:
    return [
        str(engine),
        "prepare-review-test",
        str(game),
        str(proposals),
        "--translations",
        str(translations),
        "--output",
        str(output),
    ]


def latest_release_from_payload(
    payload: object,
    *,
    include_prereleases: bool,
) -> dict | None:
    """Return the newest usable GitHub release for the current update channel."""
    if not isinstance(payload, list):
        return None
    for release in payload:
        if not isinstance(release, dict):
            continue
        if release.get("prerelease", False) and not include_prereleases:
            continue
        if not isinstance(release.get("html_url"), str) or not isinstance(
            release.get("assets"), list
        ):
            continue
        return release
    return None


def parse_steam_library_paths(text: str) -> list[Path]:
    """Extract Steam library roots from either old or new VDF layouts."""
    paths: list[Path] = []
    for raw in re.findall(r'"path"\s+"((?:\\.|[^"\\])*)"', text, flags=re.IGNORECASE):
        decoded = raw.replace(r"\\", "\\")
        candidate = Path(decoded)
        if candidate not in paths:
            paths.append(candidate)
    return paths


def _registry_steam_roots() -> list[Path]:
    if os.name != "nt":
        return []
    import winreg

    roots: list[Path] = []
    keys = (
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
    )
    for hive, key_name, value_name in keys:
        try:
            with winreg.OpenKey(hive, key_name) as key:
                value, _ = winreg.QueryValueEx(key, value_name)
        except OSError:
            continue
        candidate = Path(value)
        if candidate not in roots:
            roots.append(candidate)
    return roots


def linux_steam_roots(home: Path | None = None) -> list[Path]:
    """Return standard native and Flatpak Steam roots, including mounted SD cards."""
    home = home or Path.home()
    candidates = [
        home / ".steam" / "steam",
        home / ".local" / "share" / "Steam",
        home / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam",
    ]

    mount_roots = [Path("/run/media") / home.name, Path("/run/media")]
    for mount_root in mount_roots:
        try:
            mounted = list(mount_root.iterdir())
        except OSError:
            continue
        for candidate in mounted:
            if (candidate / "steamapps").is_dir():
                candidates.append(candidate)

    unique: dict[str, Path] = {}
    for candidate in candidates:
        if not candidate.is_dir():
            continue
        try:
            normalized = candidate.resolve()
        except OSError:
            normalized = candidate.absolute()
        unique[os.path.normcase(str(normalized))] = normalized
    return list(unique.values())


def steam_library_roots() -> list[Path]:
    if sys.platform.startswith("linux"):
        roots = linux_steam_roots()
    elif os.name == "nt":
        roots = _registry_steam_roots()
        program_files = os.environ.get("PROGRAMFILES(X86)")
        if program_files:
            fallback = Path(program_files) / "Steam"
            if fallback not in roots:
                roots.append(fallback)
    else:
        roots = []

    for steam_root in list(roots):
        for relative in ("steamapps/libraryfolders.vdf", "config/libraryfolders.vdf"):
            configuration = steam_root / relative
            try:
                discovered = parse_steam_library_paths(
                    configuration.read_text(encoding="utf-8", errors="replace")
                )
            except OSError:
                continue
            for candidate in discovered:
                if candidate not in roots:
                    roots.append(candidate)
    return roots


def is_windows_game_folder(folder: Path) -> bool:
    try:
        assets = list(folder.glob("*_Data/resources.assets"))
    except OSError:
        return False
    return len(assets) == 1 and assets[0].is_file()


def installed_game_candidates(library_roots: list[Path] | None = None) -> list[Path]:
    """Find installed copies without recursively walking whole Steam libraries."""
    candidates: list[Path] = []
    for root in library_roots if library_roots is not None else steam_library_roots():
        steamapps = root / "steamapps"
        common = steamapps / "common"

        manifest = steamapps / f"appmanifest_{STEAM_APP_ID}.acf"
        try:
            manifest_text = manifest.read_text(encoding="utf-8", errors="replace")
            match = re.search(r'"installdir"\s+"([^"]+)"', manifest_text, re.IGNORECASE)
            if match:
                candidates.append(common / match.group(1).replace(r"\\", "\\"))
        except OSError:
            pass

        try:
            entries = list(common.iterdir())
        except OSError:
            continue
        candidates.extend(entry for entry in entries if "kuloniku" in entry.name.lower())

    unique: dict[str, Path] = {}
    for candidate in candidates:
        try:
            normalized = candidate.resolve()
        except OSError:
            normalized = candidate.absolute()
        if is_windows_game_folder(normalized):
            unique[os.path.normcase(str(normalized))] = normalized
    return sorted(
        unique.values(),
        key=lambda path: ("demo" in str(path).lower(), str(path).lower()),
    )


class LauncherPaths:
    def __init__(self, base: Path | None = None, *, linux_mode: bool | None = None):
        if base is None:
            base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path.cwd()
        if linux_mode is None:
            linux_mode = sys.platform.startswith("linux")
        self.linux_mode = linux_mode
        self.base = base
        self.resources = base / "resources"
        self.engine = self.resources / ("KuloNiku-FR" if linux_mode else "KuloNiku-FR.exe")
        self.translations = self.resources / "translations" / "fr.csv"
        self.review_context = self.resources / "translations"
        self.icon = self.resources / "KuloNikuFR.ico"

    def validate(self) -> list[str]:
        missing = []
        if not self.engine.is_file():
            missing.append(str(self.engine))
        for name in sorted(TRANSLATION_PACKAGE_FILES):
            path = self.review_context / name
            if not path.is_file():
                missing.append(str(path))
        for name in sorted(REVIEW_CONTEXT_FILES if not self.linux_mode else set()):
            path = self.review_context / name
            if not path.is_file():
                missing.append(str(path))
        return missing


class WindowsLauncher:
    def __init__(self, paths: LauncherPaths | None = None):
        import tkinter as tk
        from tkinter import ttk

        self.tk = tk
        self.ttk = ttk
        self.paths = paths or LauncherPaths()
        self.steam_deck_mode = self.paths.linux_mode
        self.active_translations = self.paths.translations
        self.game: Path | None = None
        self.simulation_succeeded = False
        self.restore_available = False
        self.busy = False
        self.release_url: str | None = None
        self.update_check_started = False
        self.release_data: tuple[dict, dict] | None = None
        self.pending_translation_context: tuple[str, str] | None = None
        self.translation_download_in_progress = False
        self.installer_update_required = False

        self.root = tk.Tk()
        self.root.title("KuloNiku FR")
        self.root.geometry("760x480")
        self.root.minsize(680, 440)
        try:
            self.root.iconbitmap(str(self.paths.icon))
        except tk.TclError:
            pass

        style = ttk.Style(self.root)
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("Status.TLabel", font=("Segoe UI", 15, "bold"))
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(18, 9))
        style.configure("Secondary.TButton", padding=(12, 7))

        outer = ttk.Frame(self.root, padding=24)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="KuloNiku FR", style="Title.TLabel").pack(anchor="w")

        status_frame = ttk.LabelFrame(outer, text=" État ", padding=18)
        status_frame.pack(fill="x", pady=(18, 0))
        status_row = ttk.Frame(status_frame)
        status_row.pack(fill="x")
        self.status_symbol = ttk.Label(status_row, text="●", font=("Segoe UI", 25), foreground="#c27c0e")
        self.status_symbol.pack(side="left", padx=(0, 14))
        status_text = ttk.Frame(status_row)
        status_text.pack(side="left", fill="x", expand=True)
        self.status_title = ttk.Label(status_text, text="Recherche de KuloNiku…", style="Status.TLabel")
        self.status_title.pack(anchor="w")
        self.status_message = ttk.Label(
            status_text,
            text="Recherche de l’installation Steam en cours.",
            wraplength=600,
            foreground="#505050",
        )
        self.status_message.pack(anchor="w", pady=(5, 0))

        self.update_frame = ttk.LabelFrame(outer, text=" Mise à jour de l’application ", padding=12)
        self.update_message = ttk.Label(
            self.update_frame,
            text="Une nouvelle version de KuloNiku FR est disponible.",
            foreground="#505050",
        )
        self.update_message.pack(side="left", fill="x", expand=True)
        self.release_button = ttk.Button(
            self.update_frame,
            text="Télécharger",
            style="Primary.TButton",
            command=self.open_release,
        )
        self.release_button.pack(side="right", padx=(12, 0))

        self.game_row = ttk.Frame(outer)
        self.game_row.pack(fill="x", pady=(18, 12))
        self.game_label = ttk.Label(self.game_row, text="Aucun jeu sélectionné", foreground="#505050")
        self.game_label.pack(side="left", fill="x", expand=True)
        self.choose_button = ttk.Button(self.game_row, text="Changer…", command=self.choose_game)
        self.choose_button.pack(side="right")

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(2, 8))
        self.install_button = ttk.Button(
            actions,
            text="Installer le français",
            style="Primary.TButton",
            command=self.install_french,
            state="disabled",
        )
        self.install_button.pack(side="left")
        self.restore_button = ttk.Button(
            actions,
            text="Restaurer l’original",
            style="Secondary.TButton",
            command=self.restore_original,
            state="disabled",
        )
        self.restore_button.pack(side="left", padx=(10, 0))
        self.analyze_button = ttk.Button(
            actions,
            text="Revérifier",
            style="Secondary.TButton",
            command=self.analyze,
            state="disabled",
        )
        self.analyze_button.pack(side="right")

        self.footer = ttk.Frame(outer)
        self.footer.pack(side="bottom", fill="x", pady=(12, 0))
        ttk.Label(self.footer, text=f"Version {__version__}", foreground="#707070").pack(side="left")
        ttk.Button(self.footer, text="Projet GitHub", command=lambda: webbrowser.open(REPOSITORY_URL)).pack(side="right")
        ttk.Button(self.footer, text="À propos", command=self.show_about).pack(side="right", padx=(0, 8))

        self.advanced_visible = False
        self.log_visible = False
        self.advanced_area = ttk.Frame(outer)
        self.advanced_area.pack(side="bottom", fill="x", pady=(8, 0))
        self.advanced_button = ttk.Button(
            self.advanced_area,
            text="Options avancées ▸",
            command=self.toggle_advanced,
        )
        self.advanced_button.pack(anchor="w")
        self.advanced_frame = ttk.Frame(self.advanced_area)
        utility_row = ttk.Frame(self.advanced_frame)
        utility_row.pack(fill="x")
        self.details_button = ttk.Button(
            utility_row, text="Journal de logs ▸", command=self.toggle_details
        )
        self.details_button.pack(side="left")
        self.review_button = ttk.Button(
            utility_row,
            text="Réviser et corriger les traductions",
            command=self.open_review_workspace,
            state="disabled",
        )
        if not self.steam_deck_mode:
            self.review_button.pack(side="left", padx=(8, 0))
        self.test_review_button = ttk.Button(
            utility_row,
            text="Importer mon fichier de correction",
            command=self.test_review_corrections,
            state="disabled",
        )
        if not self.steam_deck_mode:
            self.test_review_button.pack(side="left", padx=(8, 0))
        self.details_frame = ttk.Frame(self.advanced_frame)
        self.log = tk.Text(
            self.details_frame,
            height=10,
            wrap="word",
            state="disabled",
            font=("Consolas", 9),
            background="#f5f5f5",
        )
        self.log.pack(fill="both", expand=True, pady=(6, 0))

        self.root.after(80, self.select_default_installation)
        if not self.steam_deck_mode:
            self.root.after(120, self.check_latest_release)

    def set_status(self, title: str, message: str, kind: str = "warning") -> None:
        if self.installer_update_required:
            title = "Mise à jour de l’application requise"
            message = "Le nouveau français demande cette version de KuloNiku FR."
            kind = "warning"
        colors = {"good": "#188038", "info": "#1a73e8", "warning": "#c27c0e", "error": "#c5221f"}
        self.status_symbol.configure(foreground=colors[kind])
        self.status_title.configure(text=title)
        self.status_message.configure(text=message)

    def set_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.insert("1.0", text.strip())
        self.log.configure(state="disabled")

    def append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.configure(state="disabled")

    def show_about(self) -> None:
        from tkinter import messagebox

        messagebox.showinfo(
            "À propos de KuloNiku FR",
            f"KuloNiku FR {__version__}\n\n"
            "Patch français communautaire non officiel.\n\n"
            "Aucun fichier complet du jeu n’est distribué. Le patch est construit "
            "localement depuis votre propre installation.",
        )

    def open_release(self) -> None:
        if self.release_url:
            webbrowser.open(self.release_url)

    def check_latest_release(
        self,
        edition: str | None = None,
        bundled_translation_hash: str | None = None,
    ) -> None:
        if self.steam_deck_mode:
            return
        if edition is not None and bundled_translation_hash is not None:
            self.pending_translation_context = (edition, bundled_translation_hash)
        if self.release_data is not None:
            self.process_release_updates()
            return
        if self.update_check_started:
            return
        self.update_check_started = True

        def worker() -> None:
            try:
                headers = {
                    "Accept": "application/vnd.github+json",
                    "User-Agent": f"KuloNiku-FR/{__version__}",
                }
                request = urllib.request.Request(RELEASES_API_URL, headers=headers)
                with urllib.request.urlopen(request, timeout=8) as response:
                    release = latest_release_from_payload(
                        json.load(response),
                        include_prereleases=is_prerelease_version(__version__),
                    )
                if release is None:
                    return
                assets = release.get("assets", [])
                manifest_asset = next(
                    (asset for asset in assets if asset.get("name") == "update-manifest.json"),
                    None,
                )
                if not manifest_asset:
                    return
                manifest_request = urllib.request.Request(
                    manifest_asset["browser_download_url"], headers=headers
                )
                with urllib.request.urlopen(manifest_request, timeout=8) as response:
                    manifest = json.load(response)
                self.root.after(
                    0,
                    lambda: self.store_release_data(release, manifest),
                )
            except Exception as error:
                self.root.after(
                    0,
                    lambda message=str(error): self.append_log(
                        f"\n\nVérification GitHub indisponible : {message}"
                    ),
                )

        threading.Thread(target=worker, daemon=True).start()

    def store_release_data(self, release: dict, manifest: dict) -> None:
        self.release_data = (release, manifest)
        self.process_release_updates()

    def process_release_updates(self) -> None:
        if self.release_data is None:
            return
        release, manifest = self.release_data
        context = self.pending_translation_context
        edition, bundled_hash = context if context else (None, None)
        installer_available, translation_action = available_updates(
            manifest,
            edition=edition,
            bundled_translation_hash=bundled_hash,
        )
        version = str(manifest.get("version", ""))
        release_url = str(release["html_url"])
        if installer_available:
            self.show_available_installer(version, release_url)

        if translation_action == "installer_required":
            package = manifest.get("translation_package", {})
            minimum = str(package.get("minimum_patcher_version", version))
            self.show_available_installer(minimum, release_url, required=True)
        elif translation_action == "download" and edition is not None:
            self.download_translation_package(manifest, release, edition)
        elif translation_action == "unavailable":
            self.show_available_installer(version, release_url, package_unavailable=True)

    def show_available_installer(
        self,
        version: str,
        release_url: str,
        *,
        required: bool = False,
        package_unavailable: bool = False,
    ) -> None:
        self.release_url = release_url
        self.release_button.configure(text="Télécharger")
        self.update_message.configure(
            text=(
                f"KuloNiku FR {version} est disponible."
                if version
                else "Une mise à jour est disponible sur GitHub."
            )
        )
        if not self.update_frame.winfo_manager():
            self.update_frame.pack(fill="x", pady=(12, 0), before=self.game_row)
            self.refresh_window_geometry()
        if required:
            self.installer_update_required = True
            self.install_button.pack_forget()
            self.set_status(
                "Mise à jour de l’application requise",
                "Le nouveau français demande cette version de KuloNiku FR.",
                "warning",
            )
        elif package_unavailable:
            self.set_status(
                "Mise à jour disponible sur GitHub",
                "Le lot automatique est indisponible. Utilisez la nouvelle application.",
                "warning",
            )
        self.append_log(f"\n\nNouvelle version de l’application disponible : {version}.")

    def download_translation_package(self, manifest: dict, release: dict, edition: str) -> None:
        if self.translation_download_in_progress:
            return
        package = manifest.get("translation_package", {})
        asset_name = package.get("asset")
        expected_archive_hash = package.get("sha256")
        expected_bundle_hash = package.get("bundles", {}).get(edition)
        asset = next(
            (item for item in release.get("assets", []) if item.get("name") == asset_name),
            None,
        )
        if not asset or not expected_archive_hash or not expected_bundle_hash:
            self.show_available_installer(
                str(manifest.get("version", "")),
                str(release["html_url"]),
                package_unavailable=True,
            )
            return
        self.translation_download_in_progress = True
        self.append_log("\n\nTéléchargement de la mise à jour française…")

        def worker() -> None:
            cache_root = user_data_dir() / "translations"
            destination = cache_root / str(expected_archive_hash)
            candidate = destination / "fr.csv"
            try:
                cached_files = (
                    {path.name for path in destination.iterdir()} if destination.is_dir() else set()
                )
                if not TRANSLATION_PACKAGE_FILES.issubset(cached_files):
                    cache_root.mkdir(parents=True, exist_ok=True)
                    handle, temporary_name = tempfile.mkstemp(
                        prefix="translation-", suffix=".zip", dir=cache_root
                    )
                    os.close(handle)
                    archive = Path(temporary_name)
                    try:
                        request = urllib.request.Request(
                            asset["browser_download_url"],
                            headers={"User-Agent": f"KuloNiku-FR/{__version__}"},
                        )
                        with urllib.request.urlopen(request, timeout=30) as response, archive.open(
                            "wb"
                        ) as output:
                            shutil.copyfileobj(response, output)
                        candidate = extract_translation_package(
                            archive, destination, str(expected_archive_hash)
                        )
                    finally:
                        archive.unlink(missing_ok=True)
                self.root.after(
                    0,
                    lambda: self.validate_downloaded_translations(
                        candidate,
                        str(expected_bundle_hash),
                        edition,
                        str(release["html_url"]),
                    ),
                )
            except Exception as error:
                self.root.after(
                    0,
                    lambda message=str(error): self.translation_download_failed(
                        str(release["html_url"]), message
                    ),
                )

        threading.Thread(target=worker, daemon=True).start()

    def validate_downloaded_translations(
        self,
        candidate: Path,
        expected_bundle_hash: str,
        edition: str,
        release_url: str,
    ) -> None:
        if self.busy:
            self.root.after(
                250,
                lambda: self.validate_downloaded_translations(
                    candidate, expected_bundle_hash, edition, release_url
                ),
            )
            return
        if self.game is None:
            self.translation_download_in_progress = False
            return
        arguments = [
            str(self.paths.engine),
            "status",
            str(self.game),
            "--translations",
            str(candidate),
            "--json",
        ]

        def validated(code: int, output: str) -> None:
            self.set_busy(False)
            try:
                report = json.loads(output)
            except json.JSONDecodeError:
                report = {}
            if (
                code != 0
                or report.get("edition") != edition
                or report.get("available_bundle_sha256") != expected_bundle_hash
            ):
                shutil.rmtree(candidate.parent, ignore_errors=True)
                self.translation_download_failed(release_url, "validation logique impossible")
                return
            self.translation_download_in_progress = False
            self.active_translations = candidate
            self.append_log("\nTraduction téléchargée et vérifiée. Elle est prête à être appliquée.")
            self.analyze()

        self.run_async(arguments, validated)

    def translation_download_failed(self, release_url: str, message: str) -> None:
        self.translation_download_in_progress = False
        self.release_url = release_url
        self.release_button.configure(text="Voir sur GitHub")
        self.update_message.configure(text="Le téléchargement automatique est indisponible.")
        if not self.update_frame.winfo_manager():
            self.update_frame.pack(fill="x", pady=(12, 0), before=self.game_row)
            self.refresh_window_geometry()
        self.append_log(f"\nTéléchargement automatique indisponible : {message}.")

    def set_busy(self, busy: bool) -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.choose_button.configure(state=state)
        self.analyze_button.configure(state=state if self.game else "disabled")
        self.review_button.configure(state=state if self.game else "disabled")
        self.test_review_button.configure(state=state if self.game else "disabled")
        if busy:
            self.install_button.configure(state="disabled")
            self.restore_button.configure(state="disabled")
        else:
            self.restore_button.configure(state="normal" if self.restore_available else "disabled")

    def refresh_window_geometry(self) -> None:
        self.root.update_idletasks()
        height = max(480, self.root.winfo_reqheight())
        self.root.geometry(f"760x{height}")

    def toggle_advanced(self) -> None:
        self.advanced_visible = not self.advanced_visible
        if self.advanced_visible:
            self.advanced_frame.pack(fill="x", pady=(8, 0))
            self.advanced_button.configure(text="Options avancées ▾")
        else:
            self.advanced_frame.pack_forget()
            self.advanced_button.configure(text="Options avancées ▸")
        self.refresh_window_geometry()

    def toggle_details(self) -> None:
        self.log_visible = not self.log_visible
        if not self.log_visible:
            self.details_frame.pack_forget()
            self.details_button.configure(text="Journal de logs ▸")
        else:
            self.details_frame.pack(fill="both", expand=True, pady=(8, 0))
            self.details_button.configure(text="Journal de logs ▾")
        self.refresh_window_geometry()

    def select_default_installation(self) -> None:
        missing = self.paths.validate()
        if missing:
            self.set_log("Fichiers manquants :\n" + "\n".join(missing))
            self.set_status(
                "Installateur incomplet",
                (
                    "Retéléchargez l’AppImage Steam Deck."
                    if self.steam_deck_mode
                    else "Retéléchargez puis extrayez entièrement le paquet Windows."
                ),
                "error",
            )
            return
        candidates = installed_game_candidates()
        if candidates:
            self.set_game(candidates[0])
            self.analyze()
        else:
            self.set_status(
                "KuloNiku est introuvable automatiquement",
                "Cliquez sur « Changer… » et choisissez le dossier du jeu.",
            )
            self.set_log("Aucune installation KuloNiku valide n’a été trouvée dans les bibliothèques Steam.")

    def choose_game(self) -> None:
        from tkinter import filedialog

        selected = filedialog.askdirectory(title="Choisir le dossier KuloNiku")
        if not selected:
            return
        candidate = Path(selected)
        if not is_windows_game_folder(candidate):
            from tkinter import messagebox

            messagebox.showerror(
                "Dossier incorrect",
                "Choisissez le dossier contenant KuloNiku_Data (ou KuloNiku Demo_Data).",
            )
            return
        self.set_game(candidate)
        self.analyze()

    def set_game(self, game: Path) -> None:
        self.game = game
        self.simulation_succeeded = False
        edition = "Démo" if "demo" in str(game).lower() else "Jeu complet"
        origin = "Steam" if "steam" in str(game).lower() else "installation locale"
        self.game_label.configure(text=f"{edition} détecté · {origin}")
        self.analyze_button.configure(state="normal")
        if not self.steam_deck_mode:
            self.review_button.configure(state="normal")
            self.test_review_button.configure(state="normal")
        self.install_button.configure(state="disabled")

    def open_review_workspace(self) -> None:
        if not self.game or self.busy:
            return
        context_directory = review_context_directory(
            self.active_translations,
            self.paths.translations,
        )
        output = default_review_workspace_output()
        arguments = review_workspace_arguments(
            self.paths.engine,
            self.game,
            self.active_translations,
            context_directory,
            output,
        )
        self.set_status(
            "Préparation de l’espace de relecture…",
            "Les textes restent sur cet ordinateur et le jeu n’est pas modifié.",
            "info",
        )
        self.set_log("Création de l’espace de relecture en cours…")

        def workspace_ready(code: int, details: str) -> None:
            self.set_busy(False)
            self.set_log(details)
            if code != 0 or not output.is_file():
                self.set_status(
                    "Création impossible",
                    "Consultez les détails techniques pour identifier le problème.",
                    "error",
                )
                return
            webbrowser.open(output.resolve().as_uri())
            self.set_status(
                "Espace de relecture ouvert",
                "Vous pouvez explorer les textes et préparer des corrections dans votre navigateur.",
                "good",
            )

        self.run_async(arguments, workspace_ready)

    def test_review_corrections(self) -> None:
        from tkinter import filedialog, messagebox

        if not self.game or self.busy:
            return
        selected = filedialog.askopenfilename(
            title="Choisir les propositions exportées",
            filetypes=(("Propositions KuloNiku FR", "*.csv"), ("Tous les fichiers", "*.*")),
        )
        if not selected:
            return
        output = default_review_test_output()
        preparation = prepare_review_test_arguments(
            self.paths.engine,
            self.game,
            Path(selected),
            self.active_translations,
            output,
        )
        self.set_status(
            "Préparation du test…",
            "Le fichier est contrôlé avant toute modification du jeu.",
            "info",
        )
        self.set_log("Contrôle des corrections en cours…")

        def prepared(code: int, preparation_details: str) -> None:
            if code != 0 or not output.is_file():
                self.set_busy(False)
                self.set_log(preparation_details)
                self.set_status(
                    "Corrections non testables",
                    "Le fichier ne correspond pas aux textes actuels ou contient des marqueurs invalides.",
                    "error",
                )
                return
            simulation = [
                str(self.paths.engine),
                "install",
                str(self.game),
                "--translations",
                str(output),
            ]

            def simulated(simulation_code: int, simulation_details: str) -> None:
                details = preparation_details + "\n\n--- Simulation ---\n" + simulation_details
                self.set_busy(False)
                self.set_log(details)
                if simulation_code != 0:
                    self.set_status(
                        "Test indisponible",
                        "La simulation a échoué. Le jeu n’a pas été modifié.",
                        "error",
                    )
                    return
                if not messagebox.askokcancel(
                    "Tester les corrections",
                    "Installer ces corrections dans le jeu ?\n\n"
                    "La sauvegarde originale vérifiée sera créée ou conservée.",
                    icon="info",
                ):
                    self.set_status(
                        "Corrections prêtes à tester",
                        "Aucune modification n’a été effectuée.",
                        "info",
                    )
                    return
                self.set_status(
                    "Installation des corrections…",
                    "Ne fermez pas cette fenêtre.",
                    "info",
                )

                def installed(install_code: int, install_details: str) -> None:
                    self.set_busy(False)
                    self.set_log(details + "\n\n--- Installation ---\n" + install_details)
                    if install_code == 0:
                        self.restore_available = True
                        self.restore_button.configure(state="normal")
                        self.simulation_succeeded = False
                        self.install_button.configure(state="disabled")
                        self.set_status(
                            "Corrections installées pour test",
                            "Lancez le jeu et vérifiez les passages concernés.",
                            "good",
                        )
                        messagebox.showinfo(
                            "Corrections prêtes à tester",
                            "Lancez KuloNiku depuis Steam.\n\n"
                            "Vous pourrez restaurer l’original ou réinstaller la traduction publique ensuite.",
                        )
                    else:
                        self.set_status(
                            "Installation impossible",
                            "Le jeu reste protégé. Consultez les détails techniques.",
                            "error",
                        )

                self.run_async([*simulation, "--apply"], installed)

            self.run_async(simulation, simulated)

        self.run_async(preparation, prepared)

    def command(self, action: str, *, apply: bool = False, json_output: bool = False) -> list[str]:
        assert self.game is not None
        arguments = [str(self.paths.engine), action, str(self.game)]
        if action in {"status", "install"}:
            arguments.extend(["--translations", str(self.active_translations)])
        if json_output:
            arguments.append("--json")
        if apply:
            arguments.append("--apply")
        return arguments

    def run_async(self, arguments: list[str], callback: Callable[[int, str], None]) -> None:
        self.set_busy(True)

        def worker() -> None:
            try:
                flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                completed = subprocess.run(
                    arguments,
                    cwd=self.paths.base,
                    env=engine_environment(),
                    capture_output=True,
                    creationflags=flags,
                    timeout=600,
                    check=False,
                )
                output = decode_engine_output(completed.stdout + completed.stderr).strip()
                status = completed.returncode
            except Exception as error:
                status, output = 1, f"Impossible de lancer le moteur : {error}"
            self.root.after(0, lambda: callback(status, output))

        threading.Thread(target=worker, daemon=True).start()

    def analyze(self) -> None:
        if not self.game or self.busy:
            return
        self.simulation_succeeded = False
        self.install_button.configure(state="disabled")
        self.set_status("Vérification du jeu…", "Contrôle de la version, de la sauvegarde et des traductions.", "info")
        self.set_log("Analyse en cours…")

        def status_done(code: int, output: str) -> None:
            self.set_log(output)
            if code != 0:
                self.set_busy(False)
                self.set_status("Vérification impossible", "Le jeu n’a pas été modifié. Consultez les détails techniques.", "error")
                return
            try:
                report = json.loads(output)
                if report.get("schema_version") != 1:
                    raise ValueError("version de rapport incompatible")
            except (json.JSONDecodeError, ValueError) as error:
                self.set_busy(False)
                self.set_log(output + f"\n\nRapport invalide : {error}")
                self.set_status("Vérification impossible", "Le rapport du moteur est incompatible.", "error")
                return

            self.restore_available = bool(report.get("backup_available"))
            self.check_latest_release(
                str(report.get("edition", "full")),
                str(report.get("available_bundle_sha256", "")),
            )
            state = report.get("state")
            translation_state = report.get("translation_state")
            if state == "patched" and translation_state == "current":
                self.set_busy(False)
                self.install_button.configure(state="disabled", text="Traduction à jour")
                self.set_status("Installation propre et à jour", "La traduction installée correspond exactement à cette version.", "good")
            else:
                self.validate_install(report, output)

        self.run_async(self.command("status", json_output=True), status_done)

    def validate_install(self, report: dict, previous_output: str) -> None:
        is_update = report.get("state") in {"patched", "game_updated"}

        def simulation_done(code: int, output: str) -> None:
            self.set_busy(False)
            self.set_log(previous_output + "\n\n--- Simulation d’installation ---\n" + output)
            self.simulation_succeeded = code == 0
            self.install_button.configure(
                text="Mettre à jour le français" if is_update else "Installer le français",
                state="normal" if self.simulation_succeeded else "disabled",
            )
            if code != 0:
                self.set_status("Action indisponible", "La simulation a échoué. Aucune modification n’a été faite.", "error")
                return
            if report.get("source_recognition") == "unknown":
                self.set_status(
                    "Version récente, français disponible",
                    "Cette version du jeu n’a pas encore été testée. Les textes sans français compatible resteront en anglais.",
                    "info",
                )
            elif is_update:
                self.set_status("Mise à jour française disponible", "La sauvegarde originale vérifiée sera conservée.", "info")
            else:
                self.set_status("Prêt à installer le français", "Une sauvegarde vérifiée sera créée avant toute écriture.", "info")

        self.run_async(self.command("install"), simulation_done)

    def install_french(self) -> None:
        from tkinter import messagebox

        if not self.game or not self.simulation_succeeded or self.busy:
            return
        updating = self.install_button.cget("text").startswith("Mettre")
        prompt = (
            "Mettre à jour la traduction française ?\n\nLa sauvegarde originale vérifiée sera conservée."
            if updating
            else "Installer la traduction française ?\n\nUne sauvegarde vérifiée sera créée avant toute modification."
        )
        if not messagebox.askokcancel("KuloNiku FR", prompt, icon="info"):
            return
        self.set_status("Mise à jour en cours…" if updating else "Installation en cours…", "Ne fermez pas cette fenêtre.", "info")

        def done(code: int, output: str) -> None:
            self.set_busy(False)
            self.set_log(output)
            self.simulation_succeeded = False
            self.install_button.configure(state="disabled")
            if code == 0:
                self.restore_available = True
                self.restore_button.configure(state="normal")
                self.set_status("Installation propre et à jour", "La traduction et sa sauvegarde originale ont été vérifiées.", "good")
                messagebox.showinfo("Traduction installée", "Relancez le jeu depuis Steam et choisissez Français dans les paramètres.")
            else:
                self.set_status("Installation impossible", "Le jeu reste protégé. Consultez les détails techniques.", "error")
                messagebox.showerror("Installation impossible", "Aucun changement incomplet ne doit rester. Consultez le diagnostic.")

        self.run_async(self.command("install", apply=True), done)

    def restore_original(self) -> None:
        from tkinter import messagebox

        if not self.game or self.busy:
            return
        self.set_status("Vérification de la sauvegarde…", "Contrôle SHA-256 avant restauration.", "info")

        def simulation_done(code: int, output: str) -> None:
            self.set_busy(False)
            self.set_log(output)
            if code != 0:
                self.set_status("Restauration indisponible", "Aucune sauvegarde vérifiée n’a été trouvée.", "error")
                return
            if not messagebox.askokcancel(
                "Restaurer le fichier original ?",
                "La traduction française sera retirée. Vous pourrez la réinstaller plus tard.",
                icon="warning",
            ):
                self.analyze()
                return
            self.set_status("Restauration en cours…", "Le fichier original vérifié est remis en place.", "info")

            def restore_done(restore_code: int, restore_output: str) -> None:
                self.set_busy(False)
                self.set_log(restore_output)
                if restore_code == 0:
                    self.set_status("Fichier original restauré", "La vérification finale SHA-256 a réussi.", "good")
                    messagebox.showinfo("Restauration terminée", "Le jeu a retrouvé son fichier sauvegardé.")
                    self.analyze()
                else:
                    self.set_status("Restauration impossible", "Le jeu reste protégé. Consultez les détails techniques.", "error")

            self.run_async(self.command("restore", apply=True), restore_done)

        self.run_async(self.command("restore"), simulation_done)

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    paths = LauncherPaths()
    if "--self-test" in sys.argv:
        if paths.validate():
            return 1
        try:
            import tkinter

            interpreter = tkinter.Tcl()
            interpreter.eval("info patchlevel")
        except Exception:
            return 1
        return 0
    if os.name != "nt" and not sys.platform.startswith("linux"):
        print("Cette interface graphique est réservée à Windows et Linux.", file=sys.stderr)
        return 2
    WindowsLauncher(paths).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
