#!/bin/bash
# Run Aesthetic Spruce on a workstation with a host LÖVE 11.5 (dev mode: windowed, fake device).
#
# Usage:
#   ./dev_launch.sh [WIDTH HEIGHT [INIT_SCREEN]]          interactive (keyboard: see input.lua)
#   AESTHETIC_AUTOBUILD=1 ./dev_launch.sh 1280 720          build a theme headlessly and exit
#   ROTATION=270 ./dev_launch.sh 960 720                    emulate a portrait-panel device
#   LOVE=/path/to/love ./dev_launch.sh                       pick a LÖVE binary explicitly
# Output goes to .dev/: Themes/<name>/, system.json ("theme" key), logs/, userdata/.
set -e

WIDTH=${1:-640}
HEIGHT=${2:-480}
INIT_SCREEN=${3:-splash}

if [ -n "$LOVE" ]; then
  LOVE_PATH="$LOVE"
elif command -v love >/dev/null 2>&1; then
  LOVE_PATH="love"
elif [ -x /Applications/love.app/Contents/MacOS/love ]; then
  LOVE_PATH=/Applications/love.app/Contents/MacOS/love
else
  echo "LÖVE 11.5 not found: install it or set LOVE=/path/to/love (an extracted AppImage works)" >&2
  exit 1
fi

SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$SOURCE_DIR/.dev"
mkdir -p "$ROOT_DIR/logs" "$ROOT_DIR/userdata/presets" "$ROOT_DIR/Themes"
[ -f "$ROOT_DIR/system.json" ] || echo '{"theme": "SPRUCE"}' > "$ROOT_DIR/system.json"
# love runs the src/ directory; assets/ must be reachable from inside it
[ -L "$SOURCE_DIR/src/assets" ] || ln -s ../assets "$SOURCE_DIR/src/assets"

export DEV=true
export WIDTH HEIGHT INIT_SCREEN
export ROTATION="${ROTATION:-0}"
export ROOT_DIR SOURCE_DIR
export THEME_PRESETS_DIR="$SOURCE_DIR/src/presets"
export SESSION_LOG_FILE="$ROOT_DIR/logs/$(date +%Y%m%d_%H%M%S).log"
export SPRUCE_THEMES_DIR="$ROOT_DIR/Themes"
export SPRUCE_SYSTEM_JSON="$ROOT_DIR/system.json"
export SPRUCE_PLATFORM="${SPRUCE_PLATFORM:-dev}"

echo "Aesthetic Spruce dev: ${WIDTH}x${HEIGHT} rot ${ROTATION}, screen ${INIT_SCREEN}, love=${LOVE_PATH}"
cd "$SOURCE_DIR"
"$LOVE_PATH" src 2>&1 | tee -a "$SESSION_LOG_FILE"
exit "${PIPESTATUS[0]}"
