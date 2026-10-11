#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 4 ]]; then
  echo "Usage: $0 ENGINE GUI APPIMAGETOOL OUTPUT_DIR" >&2
  exit 2
fi

engine="$1"
gui="$2"
appimagetool="$3"
output_dir="$4"
appdir="$output_dir/KuloNikuFR.AppDir"
artifact="$output_dir/KuloNiku-FR-Steam-Deck-x86_64.AppImage"

rm -rf "$appdir"
mkdir -p \
  "$appdir/usr/bin/resources/translations" \
  "$appdir/usr/share/applications" \
  "$appdir/usr/share/icons/hicolor/scalable/apps"

install -m 755 "$engine" "$appdir/usr/bin/resources/KuloNiku-FR"
install -m 755 "$gui" "$appdir/usr/bin/KuloNiku-FR-GUI"
install -m 755 packaging/steam-deck/AppRun "$appdir/AppRun"
install -m 644 packaging/steam-deck/KuloNikuFR.desktop "$appdir/KuloNikuFR.desktop"
install -m 644 packaging/steam-deck/KuloNikuFR.desktop \
  "$appdir/usr/share/applications/KuloNikuFR.desktop"
install -m 644 packaging/icons/KuloNikuFR.svg "$appdir/KuloNikuFR.svg"
install -m 644 packaging/icons/KuloNikuFR.svg \
  "$appdir/usr/share/icons/hicolor/scalable/apps/KuloNikuFR.svg"
ln -s KuloNikuFR.svg "$appdir/.DirIcon"

for name in fr.csv source-hashes.csv demo-overrides.csv full-overrides.csv native-approvals.csv known-sources.json; do
  install -m 644 "translations/$name" "$appdir/usr/bin/resources/translations/$name"
done
install -m 644 LICENSE SECURITY.md THIRD_PARTY_NOTICES.md "$appdir/usr/bin/resources/"

mkdir -p "$output_dir"
rm -f "$artifact"
ARCH=x86_64 "$appimagetool" "$appdir" "$artifact"
(
  cd "$output_dir"
  sha256sum KuloNiku-FR-Steam-Deck-x86_64.AppImage \
    > KuloNiku-FR-Steam-Deck-x86_64.AppImage.sha256
)
