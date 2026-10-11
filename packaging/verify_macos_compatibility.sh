#!/bin/bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 /path/to/binary architecture minimum-macos" >&2
  exit 2
fi

binary="$1"
architecture="$2"
minimum="$3"
xcrun lipo "$binary" -verify_arch "$architecture"
# Inspect every slice: Info.plist alone does not control the binary's minimum OS.
build_info="$(xcrun vtool -show-build "$binary")"
if ! awk -v maximum="$minimum" '
  function newer(version, limit, a, b, i) {
    split(version, a, "."); split(limit, b, ".")
    for (i = 1; i <= 3; i++) {
      if (a[i] + 0 > b[i] + 0) return 1
      if (a[i] + 0 < b[i] + 0) return 0
    }
    return 0
  }
  $1 == "minos" || ($1 == "version" && legacy) {
    found++; if (newer($2, maximum)) invalid = 1
    legacy = 0
  }
  $1 == "cmd" { legacy = ($2 == "LC_VERSION_MIN_MACOSX") }
  END { exit (!found || invalid) }
' <<< "$build_info"; then
  echo "Binaire incompatible avec macOS $minimum : $binary" >&2
  echo "$build_info" >&2
  exit 1
fi
