#!/usr/bin/env bash
#
# Build a simple .deb for MarkItDown GUI.
# The package installs the app under /usr/lib and a launcher under /usr/bin.
# It depends on python3 + python3-tk; the markitdown CLI is installed
# separately by the user (pipx install 'markitdown[all]').
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_ID="markitdown-gui"
VERSION="$(python3 -c "import re,sys; print(re.search(r'__version__ = \"([^\"]+)\"', open('$ROOT/markitdown_gui/__init__.py').read()).group(1))")"
ARCH="all"
BUILD="$ROOT/packaging/build/deb"
PKG="$BUILD/${APP_ID}_${VERSION}_${ARCH}"

echo "==> Building ${APP_ID} ${VERSION} (.deb)"
rm -rf "$PKG"
mkdir -p "$PKG/DEBIAN" \
         "$PKG/usr/lib/$APP_ID" \
         "$PKG/usr/bin" \
         "$PKG/usr/share/applications" \
         "$PKG/usr/share/icons/hicolor/256x256/apps" \
         "$PKG/usr/share/doc/$APP_ID"

# App payload
cp -r "$ROOT/markitdown_gui" "$PKG/usr/lib/$APP_ID/"

# Launcher
cat > "$PKG/usr/bin/$APP_ID" <<EOF
#!/usr/bin/env bash
export PYTHONPATH="/usr/lib/$APP_ID:\${PYTHONPATH:-}"
exec python3 -m markitdown_gui "\$@"
EOF
chmod 0755 "$PKG/usr/bin/$APP_ID"

# Icon (render if needed)
if [ ! -f "$ROOT/assets/icon.png" ]; then
    python3 "$ROOT/scripts/generate_icon.py" "$ROOT/assets/icon.png" || true
fi
[ -f "$ROOT/assets/icon.png" ] && \
    cp "$ROOT/assets/icon.png" "$PKG/usr/share/icons/hicolor/256x256/apps/$APP_ID.png"

# .desktop
cp "$ROOT/packaging/$APP_ID.desktop" "$PKG/usr/share/applications/$APP_ID.desktop"

# Docs
cp "$ROOT/LICENSE" "$PKG/usr/share/doc/$APP_ID/copyright"
cp "$ROOT/NOTICE"  "$PKG/usr/share/doc/$APP_ID/NOTICE"

# Control file
cat > "$PKG/DEBIAN/control" <<EOF
Package: $APP_ID
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Depends: python3 (>= 3.10), python3-tk
Recommends: pipx
Maintainer: Alexander Edgecombe <alexander.edgecombe01@gmail.com>
Description: Desktop GUI for the markitdown document-to-Markdown converter
 A thin Tkinter front-end that converts documents to Markdown by shelling out
 to Microsoft's markitdown CLI. Install the engine separately with
 'pipx install markitdown[all]'.
EOF

# postinst/postrm: refresh caches
cat > "$PKG/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
gtk-update-icon-cache -f -t /usr/share/icons/hicolor >/dev/null 2>&1 || true
EOF
cp "$PKG/DEBIAN/postinst" "$PKG/DEBIAN/postrm"
chmod 0755 "$PKG/DEBIAN/postinst" "$PKG/DEBIAN/postrm"

# Build
if ! command -v dpkg-deb >/dev/null 2>&1; then
    echo "dpkg-deb not found; install dpkg-dev." >&2
    exit 1
fi
dpkg-deb --build --root-owner-group "$PKG"
OUT="$ROOT/${APP_ID}_${VERSION}_${ARCH}.deb"
mv "$PKG.deb" "$OUT"
echo "==> Built $OUT"
