#!/bin/bash
# Sync the iCamVideo theme onto a mounted iPod's .rockbox install.
#
# Only copies files that belong to this theme (themes/iCamVideo.cfg, wps/iCamVideo.*,
# backdrops/iCamVideo_Backdrop.bmp, the two iLike .fnt files, icons/blank-10.bmp).
# fonts/, icons/, wps/, backdrops/, themes/ are shared across every theme on the
# device, so this must never wipe or glob those directories - only touch the
# iCamVideo-owned paths listed below. Update this list if the theme's file set
# changes (new bitmap, renamed font, etc).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DEFAULT_IPOD_ROOT="/Volumes/JUANCHO'S I"
IPOD_ROOT="${1:-$DEFAULT_IPOD_ROOT}"
RB="$IPOD_ROOT/.rockbox"
if [ ! -d "$RB" ]; then
    echo "$RB does not exist. Is the iPod mounted? Pass its mount path as an argument to override." >&2
    exit 1
fi

echo "Syncing iCamVideo theme to $RB"

copy() {
    local src="$1" dst="$2"
    mkdir -p "$(dirname "$dst")"
    cp -v "$src" "$dst"
}

copy "$REPO_DIR/themes/iCamVideo.cfg"                  "$RB/themes/iCamVideo.cfg"

copy "$REPO_DIR/wps/iCamVideo.wps"                     "$RB/wps/iCamVideo.wps"
copy "$REPO_DIR/wps/iCamVideo.sbs"                     "$RB/wps/iCamVideo.sbs"
copy "$REPO_DIR/wps/iCamVideo.fms"                     "$RB/wps/iCamVideo.fms"
copy "$REPO_DIR/wps/iCamVideo-no-clock-WPS.txt"        "$RB/wps/iCamVideo-no-clock-WPS.txt"
copy "$REPO_DIR/wps/iCamVideo-no-clock-FMS.txt"        "$RB/wps/iCamVideo-no-clock-FMS.txt"

mkdir -p "$RB/wps/iCamVideo"
for f in "$REPO_DIR"/wps/iCamVideo/*.bmp; do
    copy "$f" "$RB/wps/iCamVideo/$(basename "$f")"
done

copy "$REPO_DIR/backdrops/iCamVideo_Backdrop.bmp"      "$RB/backdrops/iCamVideo_Backdrop.bmp"

copy "$REPO_DIR/fonts/18 iLike.fnt"                    "$RB/fonts/18 iLike.fnt"
copy "$REPO_DIR/fonts/24 iLike.fnt"                    "$RB/fonts/24 iLike.fnt"

copy "$REPO_DIR/icons/blank-10.bmp"                    "$RB/icons/blank-10.bmp"

echo "Done."
