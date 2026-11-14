#!/usr/bin/env bash
# One-shot install for a headless Ubuntu 24.04 container where GitHub release downloads are blocked
# (e.g. a Claude Code cloud session). Run as root:  bash install_cloud.sh
# - apt: fluidsynth + FluidR3 GM soundfont, poppler, squashfs-tools
# - MuseScore 4 from the Snap Store (the musescore snap + the Qt 6 it takes from the kf6-core24 snap), unpacked
#   under /opt/musescore and started through /usr/local/bin/mscore4 (headless)
# - the toolkit's Python venv (setup.sh --cpu)
# Idempotent: steps already done are skipped.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
OPT=/opt/musescore
export DEBIAN_FRONTEND=noninteractive

if ! command -v fluidsynth >/dev/null || ! command -v unsquashfs >/dev/null || ! command -v pdftoppm >/dev/null; then
  apt-get update -qq
  apt-get install -y -qq ffmpeg fluidsynth fluid-soundfont-gm poppler-utils squashfs-tools python3-venv \
    libegl1 libopengl0 libxkbcommon0 libnss3 >/dev/null
fi

snap_url() {  # latest stable amd64 download URL of a snap
  curl -fsS -m 30 -H 'Snap-Device-Series: 16' "https://api.snapcraft.io/v2/snaps/info/$1?architecture=amd64" |
    python3 -c 'import json,sys; d=json.load(sys.stdin)
print(next(c["download"]["url"] for c in d["channel-map"] if c["channel"]["name"]=="stable"))'
}
mkdir -p "$OPT"
if [ ! -x "$OPT/snap/usr/bin/mscore" ]; then
  curl -fsSL -m 3600 -o "$OPT/ms.snap" "$(snap_url musescore)"
  rm -rf "$OPT/snap"; unsquashfs -q -d "$OPT/snap" "$OPT/ms.snap" >/dev/null; rm -f "$OPT/ms.snap"
fi
if [ ! -e "$OPT/kf6/usr/lib/x86_64-linux-gnu/libQt6Core.so.6" ]; then
  curl -fsSL -m 3600 -o "$OPT/kf6.snap" "$(snap_url kf6-core24)"
  rm -rf "$OPT/kf6"
  unsquashfs -q -d "$OPT/kf6" "$OPT/kf6.snap" 'usr/lib/x86_64-linux-gnu/*' 'usr/share/qt6/*' >/dev/null
  rm -f "$OPT/kf6.snap"
fi
cat > /usr/local/bin/mscore4 <<'EOF'
#!/bin/bash
# MuseScore 4 (unpacked from the Snap Store) running headless. 4.7+ reads MU_QT_QPA_PLATFORM, not QT_QPA_PLATFORM.
S=/opt/musescore/snap; K=/opt/musescore/kf6
export LD_LIBRARY_PATH=$S/usr/lib:$S/usr/lib/x86_64-linux-gnu:$K/usr/lib/x86_64-linux-gnu:$K/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export QT_PLUGIN_PATH=$K/usr/lib/x86_64-linux-gnu/qt6/plugins
export QML2_IMPORT_PATH=$K/usr/lib/x86_64-linux-gnu/qt6/qml
export QT_QPA_PLATFORM=${QT_QPA_PLATFORM:-offscreen}
export MU_QT_QPA_PLATFORM=${MU_QT_QPA_PLATFORM:-offscreen}
export QT_QPA_PLATFORMTHEME=${QT_QPA_PLATFORMTHEME:-generic}
export LANG=${LANG:-C.UTF-8}
exec $S/usr/bin/mscore "$@"
EOF
chmod +x /usr/local/bin/mscore4
mscore4 --version

bash "$HERE/setup.sh" --cpu
