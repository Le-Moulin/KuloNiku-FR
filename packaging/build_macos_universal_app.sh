#!/bin/bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 /path/to/arm64/KuloNiku-FR /path/to/x86_64/KuloNiku-FR /path/to/package" >&2
  exit 2
fi

arm_patcher="$1"
intel_patcher="$2"
package_dir="$3"
app="$package_dir/KuloNiku FR.app"
contents="$app/Contents"
macos="$contents/MacOS"
resources="$contents/Resources"
launcher_build="$package_dir/launcher-build"

for patcher in "$arm_patcher" "$intel_patcher"; do
  if [[ ! -f "$patcher" ]]; then
    echo "Le moteur est absent : $patcher" >&2
    exit 1
  fi
done

mkdir -p "$macos" "$resources/translations" "$launcher_build"
chmod +x "$arm_patcher" "$intel_patcher"
minimum_macos="$(/usr/libexec/PlistBuddy -c 'Print :LSMinimumSystemVersion' packaging/macos/Info.plist)"

xcrun swiftc \
  -O \
  -target "arm64-apple-macos$minimum_macos" \
  -framework Cocoa \
  packaging/macos/KuloNikuFRLauncher.swift \
  -o "$launcher_build/KuloNiku FR-arm64"

xcrun swiftc \
  -O \
  -target "x86_64-apple-macos$minimum_macos" \
  -framework Cocoa \
  packaging/macos/KuloNikuFRLauncher.swift \
  -o "$launcher_build/KuloNiku FR-x86_64"

lipo -create \
  "$launcher_build/KuloNiku FR-arm64" \
  "$launcher_build/KuloNiku FR-x86_64" \
  -output "$macos/KuloNiku FR"
lipo "$macos/KuloNiku FR" -verify_arch arm64 x86_64

cp packaging/macos/Info.plist "$contents/Info.plist"
cp packaging/icons/KuloNikuFR.icns "$resources/KuloNikuFR.icns"
cp "$arm_patcher" "$resources/KuloNiku-FR-arm64"
cp "$intel_patcher" "$resources/KuloNiku-FR-x86_64"
cp translations/fr.csv translations/source-hashes.csv translations/demo-overrides.csv translations/full-overrides.csv translations/native-approvals.csv translations/known-sources.json "$resources/translations/"
cp translations/review-overrides.csv translations/AGENT_BRIEF.md translations/NOTICE.md "$resources/translations/"
cp docs/TERMINOLOGY.md "$resources/translations/TERMINOLOGY.md"
cp README.md LICENSE SECURITY.md THIRD_PARTY_NOTICES.md "$resources/"

arm_version="$(arch -arm64 "$resources/KuloNiku-FR-arm64" --version | awk '{print $2}')"
intel_version="$(arch -x86_64 "$resources/KuloNiku-FR-x86_64" --version | awk '{print $2}')"
if [[ "$arm_version" != "$intel_version" ]]; then
  echo "Les moteurs macOS n’ont pas la même version : $arm_version / $intel_version" >&2
  exit 1
fi
plutil -replace CFBundleShortVersionString -string "$arm_version" "$contents/Info.plist"
plutil -replace CFBundleVersion -string "$arm_version" "$contents/Info.plist"

chmod +x \
  "$macos/KuloNiku FR" \
  "$resources/KuloNiku-FR-arm64" \
  "$resources/KuloNiku-FR-x86_64"
bash packaging/verify_macos_compatibility.sh "$macos/KuloNiku FR" arm64 "$minimum_macos"
bash packaging/verify_macos_compatibility.sh "$macos/KuloNiku FR" x86_64 "$minimum_macos"
bash packaging/verify_macos_compatibility.sh "$resources/KuloNiku-FR-arm64" arm64 "$minimum_macos"
bash packaging/verify_macos_compatibility.sh "$resources/KuloNiku-FR-x86_64" x86_64 "$minimum_macos"
codesign --force --deep --sign - "$app"
codesign --verify --deep --strict "$app"
"$macos/KuloNiku FR" --self-test-updates

echo "Application macOS universelle créée : $app"
