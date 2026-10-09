#!/bin/bash
# Build the spruceOS app as an SD-card overlay plus two archives of it.
#
#   ./build.sh                 -> dist/sd-overlay/App/AestheticSpruce/   copy the App folder onto the card root
#                                 dist/AestheticSpruce_vX.Y.Z_sd-overlay.zip   same tree, for drag-and-drop from a PC
#                                 dist/AestheticSpruce_vX.Y.Z.7z              same tree, extractable on-device with 7zr
#   ./build.sh --deploy HOST   -> also rsync the app folder to HOST:/mnt/SDCARD/App/AestheticSpruce
#                                 (HOST like spruce@192.168.68.65; set RSYNC_RSH for a jump host)
#
# Every archive unpacks at the card root: App/AestheticSpruce/{config.json,launch.sh,aestheticspruce.png,.aesthetic/}.
set -euo pipefail
cd "$(dirname "$0")"

DEPLOY_HOST=""
while [ $# -gt 0 ]; do
  case "$1" in
    --deploy) DEPLOY_HOST="$2"; shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
done

MAJOR=$(awk '/^version.major =/ {print $3}' src/version.lua)
MINOR=$(awk '/^version.minor =/ {print $3}' src/version.lua)
PATCH=$(awk '/^version.patch =/ {print $3}' src/version.lua)
PRERELEASE=$(awk '/^version.prerelease =/ {print $3}' src/version.lua | tr -d '"')
VERSION="v${MAJOR}.${MINOR}.${PATCH}"
if [ -n "$PRERELEASE" ] && [ "$PRERELEASE" != "nil" ]; then
  VERSION="${VERSION}-${PRERELEASE}"
fi
echo "version: $VERSION"

DIST=dist
OVERLAY="$DIST/sd-overlay"
APP="$OVERLAY/App/AestheticSpruce"
SRC="$APP/.aesthetic"
rm -rf "$DIST"
mkdir -p "$SRC"

echo "== icons (host rasteriser) =="
python3 utils/generate_ui_icon_pngs.py --check >/dev/null 2>&1 || python3 utils/generate_ui_icon_pngs.py
python3 utils/check_lua_syntax.py

echo "== app files =="
cp spruce/config.json spruce/launch.sh "$APP/"
cp spruce/icon.png "$APP/aestheticspruce.png"
chmod +x "$APP/launch.sh"

echo "== source =="
rsync -a --exclude 'assets' --exclude 'scheme_templates' src/ "$SRC/"
rsync -a bin/ "$SRC/bin/"
rsync -a lib/ "$SRC/lib/"
chmod +x "$SRC/bin/love"

echo "== assets =="
mkdir -p "$SRC/assets/fonts" "$SRC/assets/icons/png" "$SRC/assets/images"
rsync -a --include='*/' --include='*.ttf' --include='OFL.txt' --include='LICENSE*' --exclude='*' assets/fonts/ "$SRC/assets/fonts/"
rsync -a assets/icons/png/ "$SRC/assets/icons/png/"
cp assets/icons/kenney_input_prompts/License.txt "$SRC/assets/icons/png/kenney_input_prompts/" 2>/dev/null || true
rsync -a assets/images/ "$SRC/assets/images/"
cp LICENSE "$SRC/LICENSE"
cp README.md "$SRC/README.md"

echo "== archives =="
# Homebrew's sevenzip ships 7zz, p7zip ships 7za: take whichever 7-Zip is installed
SEVENZIP="$(command -v 7z || command -v 7zz || command -v 7za || true)"
[ -n "$SEVENZIP" ] || { echo "no 7-Zip found: install sevenzip (7zz) or p7zip (7za)" >&2; exit 1; }
# -mf=off: no ARM64/BCJ executable filters; spruce's on-device p7zip 7zr cannot extract them
( cd "$OVERLAY" && rm -f "../AestheticSpruce_${VERSION}.7z" && "$SEVENZIP" a -t7z -bd -bso0 -m0=lzma2 -mx=5 -mf=off "../AestheticSpruce_${VERSION}.7z" App >/dev/null )
( cd "$OVERLAY" && rm -f "../AestheticSpruce_${VERSION}_sd-overlay.zip" && zip -9 -q -r "../AestheticSpruce_${VERSION}_sd-overlay.zip" App )
{
  echo "Aesthetic Spruce ${VERSION} - SD card overlay"
  echo
  echo "Copy the App folder onto the root of your spruceOS SD card (so that App/AestheticSpruce exists"
  echo "next to your other apps), then launch 'Aesthetic Spruce' from the Apps list."
  echo
  echo "Works on aarch64 spruceOS 4.3.x, 4.4.x and 4.5.x devices (TrimUI Smart Pro/Brick family, Miyoo Flip,"
  echo "Miniloong, Anbernic RG XX family, GKD Pixel2, RGB30, MagicX on 4.4.2+). Not for the Miyoo A30 or Mini."
  echo
  echo "Unofficial fork of Aesthetic by Jonathan Avila. Support the original author: https://ko-fi.com/F1F51COHHT"
} > "$OVERLAY/README.txt"
du -sh "$APP" "$DIST/AestheticSpruce_${VERSION}.7z" "$DIST/AestheticSpruce_${VERSION}_sd-overlay.zip"
( cd "$DIST" && sha256sum "AestheticSpruce_${VERSION}.7z" "AestheticSpruce_${VERSION}_sd-overlay.zip" > SHA256SUMS.txt && cat SHA256SUMS.txt )

if [ -n "$DEPLOY_HOST" ]; then
  echo "== deploy to $DEPLOY_HOST =="
  rsync -a --delete "$APP/" "$DEPLOY_HOST:/mnt/SDCARD/App/AestheticSpruce/"
fi
echo "done: $VERSION"
