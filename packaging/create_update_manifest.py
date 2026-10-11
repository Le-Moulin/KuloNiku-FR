"""Create the small, public update descriptor shipped with GitHub releases."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from kuloniku_fr import TRANSLATION_PACKAGE_MINIMUM_PATCHER_VERSION, __version__
from kuloniku_fr.cli import translation_bundle_hash


def main() -> None:
    translations = Path("translations/fr.csv")
    source_hashes = Path("translations/source-hashes.csv")
    overrides = Path("translations/demo-overrides.csv")
    known_sources = Path("translations/known-sources.json")
    review_notes = Path("translations/review-overrides.csv")
    agent_brief = Path("translations/AGENT_BRIEF.md")
    terminology = Path("docs/TERMINOLOGY.md")
    notice = Path("translations/NOTICE.md")
    package_dir = Path("package")
    package_dir.mkdir(parents=True, exist_ok=True)
    archive = package_dir / "translations.zip"
    with ZipFile(archive, "w", compression=ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in (
            translations,
            source_hashes,
            overrides,
            known_sources,
            review_notes,
            agent_brief,
            terminology,
            notice,
        ):
            info = ZipInfo(path.name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            bundle.writestr(info, path.read_bytes(), compresslevel=9)

    with ZipFile(archive, "a", compression=ZIP_DEFLATED, compresslevel=9) as bundle:
        for name in ("full-overrides.csv", "native-approvals.csv"):
            path = translations.with_name(name)
            if path.exists():
                info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                bundle.writestr(info, path.read_bytes(), compresslevel=9)

    archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
    bundle_hashes = {
        edition: translation_bundle_hash(
            translations,
            edition=edition,
            source_hashes=str(source_hashes),
            compatibility_overrides=str(overrides) if edition == "demo" else None,
        )
        for edition in ("full", "demo")
    }
    manifest = {
        "schema": 2,
        "version": __version__,
        "translation_bundles": bundle_hashes,
        "translation_package": {
            "version": __version__,
            "asset": archive.name,
            "sha256": archive_hash,
            "minimum_patcher_version": TRANSLATION_PACKAGE_MINIMUM_PATCHER_VERSION,
            "bundles": bundle_hashes,
        },
    }
    (package_dir / "update-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
