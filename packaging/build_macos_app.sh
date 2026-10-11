#!/bin/bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 /path/to/KuloNiku-FR /path/to/package" >&2
  exit 2
fi

patcher="$1"
package_dir="$2"
app="$package_dir/KuloNiku FR.app"
contents="$app/Contents"
macos="$contents/MacOS"
resources="$contents/Resources"

if [[ ! -x "$patcher" ]]; then
  echo "Le moteur est absent ou non exécutable : $patcher" >&2
  exit 1
fi

mkdir -p "$macos" "$resources/translations"
architecture="$(uname -m)"
case "$architecture" in
  arm64|x86_64) patcher_name="KuloNiku-FR-$architecture" ;;
  *) echo "Architecture macOS non prise en charge : $architecture" >&2; exit 1 ;;
esac
minimum_macos="$(/usr/libexec/PlistBuddy -c 'Print :LSMinimumSystemVersion' packaging/macos/Info.plist)"

xcrun swiftc \
  -O \
  -target "$architecture-apple-macos$minimum_macos" \
  -framework Cocoa \
  packaging/macos/KuloNikuFRLauncher.swift \
  -o "$macos/KuloNiku FR"

cp packaging/macos/Info.plist "$contents/Info.plist"
cp packaging/icons/KuloNikuFR.icns "$resources/KuloNikuFR.icns"
version="$($patcher --version | awk '{print $2}')"
plutil -replace CFBundleShortVersionString -string "$version" "$contents/Info.plist"
plutil -replace CFBundleVersion -string "$version" "$contents/Info.plist"
cp "$patcher" "$resources/$patcher_name"
cp translations/fr.csv translations/source-hashes.csv translations/demo-overrides.csv translations/full-overrides.csv translations/native-approvals.csv translations/known-sources.json "$resources/translations/"
cp translations/review-overrides.csv translations/AGENT_BRIEF.md translations/NOTICE.md "$resources/translations/"
cp docs/TERMINOLOGY.md "$resources/translations/TERMINOLOGY.md"
cp README.md LICENSE SECURITY.md THIRD_PARTY_NOTICES.md "$resources/"

chmod +x "$macos/KuloNiku FR" "$resources/$patcher_name"
bash packaging/verify_macos_compatibility.sh "$macos/KuloNiku FR" "$architecture" "$minimum_macos"
bash packaging/verify_macos_compatibility.sh "$resources/$patcher_name" "$architecture" "$minimum_macos"
codesign --force --deep --sign - "$app"
codesign --verify --deep --strict "$app"
"$macos/KuloNiku FR" --self-test-updates

echo "Application créée : $app"
