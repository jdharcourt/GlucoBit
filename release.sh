#!/usr/bin/env bash
# ─────────────────────────────────────────────
# GlucoBit OTA Release Script
# Usage:
#   ./release.sh          → bump patch  (1.1.3 → 1.1.4)
#   ./release.sh minor    → bump minor  (1.1.3 → 1.2.0)
#   ./release.sh major    → bump major  (1.1.3 → 2.0.0)
#   ./release.sh 1.2.5    → exact version
# ─────────────────────────────────────────────
set -euo pipefail

DEVICE="/Volumes/CIRCUITPY"
REPO="jdharcourt/GlucoBit"

# ── 1. Read & bump version ───────────────────
CURRENT=$(cat "$DEVICE/app/version.txt" | tr -d '[:space:]')
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT"

BUMP="${1:-patch}"
case "$BUMP" in
  major) MAJOR=$((MAJOR+1)); MINOR=0; PATCH=0 ;;
  minor) MINOR=$((MINOR+1)); PATCH=0 ;;
  patch) PATCH=$((PATCH+1)) ;;
  *.*.*)
    IFS='.' read -r MAJOR MINOR PATCH <<< "$BUMP" ;;
  *)
    echo "Usage: $0 [major|minor|patch|X.Y.Z]" >&2; exit 1 ;;
esac

NEW_VERSION="$MAJOR.$MINOR.$PATCH"
echo "📦  $CURRENT  →  $NEW_VERSION"

# ── 2. Update version.txt on device ─────────
printf '%s' "$NEW_VERSION" > "$DEVICE/app/version.txt"
echo "✅  Updated app/version.txt"

# ── 3. Stage files in a temp dir ─────────────
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

cp "$DEVICE/app/main.py"      "$TMP/main.py"
cp "$DEVICE/app/ble.py"       "$TMP/ble.py"
cp "$DEVICE/app/version.txt"  "$TMP/version.txt"
cp "$DEVICE/ota.py"           "$TMP/ota.py"

# ── 4. Build release.json manifest ───────────
cat > "$TMP/release.json" <<JSON
{
  "version": "$NEW_VERSION",
  "files": {
    "app/main.py":      "main.py",
    "app/ble.py":       "ble.py",
    "app/version.txt":  "version.txt",
    "ota.py":           "ota.py"
  }
}
JSON
echo "✅  Built release.json"

# ── 5. Publish to GitHub ──────────────────────
echo "🚀  Creating GitHub release v$NEW_VERSION ..."
gh release create "v$NEW_VERSION" \
  --repo "$REPO" \
  --title "v$NEW_VERSION" \
  --notes "OTA release v$NEW_VERSION" \
  "$TMP/release.json" \
  "$TMP/main.py" \
  "$TMP/ble.py" \
  "$TMP/version.txt" \
  "$TMP/ota.py"

echo ""
echo "✅  Done! Release v$NEW_VERSION is live."
echo "    Device will pick it up on next OTA check."
