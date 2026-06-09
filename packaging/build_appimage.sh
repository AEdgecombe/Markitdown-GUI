#!/usr/bin/env bash
#
# Build an AppImage for MarkItDown GUI.
#
# The AppImage bundles the GUI code and launches the host's python3. It expects
# python3-tk and the `markitdown` CLI to be available on the host (the latter
# via pipx install 'markitdown[all]'). appimagetool is downloaded on first run.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_ID="markitdown-gui"
VERSION="$(python3 -c "import re; print(re.search(r'__version__ = \"([^\"]+)\"', open('$ROOT/markitdown_gui/__init__.py').read()).group(1))")"
BUILD="$ROOT/packaging/build/appimage"
APPDIR="$BUILD/AppDir"
TOOLS="$ROOT/packaging/build/tools"

echo "==> Building ${APP_ID} ${VERSION} (AppImage)"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/lib/$APP_ID" \
         "$APPDIR/usr/bin" \
         "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/256x256/apps" \
         "$TOOLS"

# App payload
cp -r "$ROOT/markitdown_gui" "$APPDIR/usr/lib/$APP_ID/"

# Launcher used inside the AppImage
cat > "$APPDIR/usr/bin/$APP_ID" <<EOF
#!/usr/bin/env bash
HERE="\$(dirname "\$(readlink -f "\$0")")"
export PYTHONPATH="\$HERE/../lib/$APP_ID:\${PYTHONPATH:-}"
exec python3 -m markitdown_gui "\$@"
EOF
chmod 0755 "$APPDIR/usr/bin/$APP_ID"

# Icon
if [ ! -f "$ROOT/assets/icon.png" ]; then
    python3 "$ROOT/scripts/generate_icon.py" "$ROOT/assets/icon.png" || true
fi
cp "$ROOT/assets/icon.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/$APP_ID.png"
cp "$ROOT/assets/icon.png" "$APPDIR/$APP_ID.png"            # top-level icon
ln -sf "$APP_ID.png" "$APPDIR/.DirIcon"

# .desktop (top-level, required by AppImage)
cp "$ROOT/packaging/$APP_ID.desktop" "$APPDIR/$APP_ID.desktop"
cp "$ROOT/packaging/$APP_ID.desktop" "$APPDIR/usr/share/applications/$APP_ID.desktop"

# AppRun entry point
cat > "$APPDIR/AppRun" <<EOF
#!/usr/bin/env bash
HERE="\$(dirname "\$(readlink -f "\$0")")"
exec "\$HERE/usr/bin/$APP_ID" "\$@"
EOF
chmod 0755 "$APPDIR/AppRun"

# Fetch appimagetool if needed
TOOL="$TOOLS/appimagetool-x86_64.AppImage"
if [ ! -x "$TOOL" ]; then
    echo "==> Downloading appimagetool…"
    URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    if command -v curl >/dev/null 2>&1; then
        curl -fL "$URL" -o "$TOOL"
    else
        wget -O "$TOOL" "$URL"
    fi
    chmod +x "$TOOL"
fi

OUT="$ROOT/MarkItDown-${VERSION}-x86_64.AppImage"
ARCH=x86_64 "$TOOL" "$APPDIR" "$OUT"
echo "==> Built $OUT"
