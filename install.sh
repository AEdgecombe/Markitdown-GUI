#!/usr/bin/env bash
#
# Install MarkItDown GUI into ~/.local (no system-wide writes except apt deps).
#
#   - installs the `markitdown` CLI via pipx (if missing)
#   - ensures python3-tk is present (apt)
#   - installs tkinterdnd2 (pip --user; non-fatal if it fails)
#   - copies the app, launcher, icon and .desktop entry into ~/.local
#   - refreshes the desktop + icon caches
#
set -euo pipefail

APP_ID="markitdown-gui"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

LIB_DIR="$HOME/.local/lib/$APP_ID"
BIN_DIR="$HOME/.local/bin"
LAUNCHER="$BIN_DIR/$APP_ID"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"

say()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*" >&2; }
ok()   { printf '\033[1;32m[✓]\033[0m %s\n' "$*"; }

# --------------------------------------------------------------------------- #
# 1. markitdown CLI via pipx
# --------------------------------------------------------------------------- #
if command -v markitdown >/dev/null 2>&1 || [ -x "$HOME/.local/bin/markitdown" ]; then
    ok "markitdown already installed."
else
    say "Installing markitdown CLI…"
    if ! command -v pipx >/dev/null 2>&1; then
        say "pipx not found — installing it."
        if command -v apt >/dev/null 2>&1; then
            sudo apt update && sudo apt install -y pipx
        else
            python3 -m pip install --user pipx
        fi
        python3 -m pipx ensurepath || true
    fi
    pipx install 'markitdown[all]'
    ok "markitdown installed."
fi

# --------------------------------------------------------------------------- #
# 2. python3-tk (apt)
# --------------------------------------------------------------------------- #
if python3 -c 'import tkinter' >/dev/null 2>&1; then
    ok "python3-tk already present."
else
    say "Installing python3-tk…"
    if command -v apt >/dev/null 2>&1; then
        sudo apt update && sudo apt install -y python3-tk
    else
        warn "apt not available; please install Tkinter for Python 3 manually."
    fi
fi

# --------------------------------------------------------------------------- #
# 3. tkinterdnd2 (optional, non-fatal)
# --------------------------------------------------------------------------- #
say "Installing tkinterdnd2 (drag-and-drop support; optional)…"
if python3 -m pip install --user tkinterdnd2 >/dev/null 2>&1; then
    ok "tkinterdnd2 installed."
else
    warn "Could not install tkinterdnd2 — drag-and-drop will be disabled, the file picker still works."
fi

# --------------------------------------------------------------------------- #
# 4. Copy app, launcher, icon, .desktop entry
# --------------------------------------------------------------------------- #
say "Installing application files…"
rm -rf "$LIB_DIR"
mkdir -p "$LIB_DIR" "$BIN_DIR" "$DESKTOP_DIR" "$ICON_DIR"
cp -r "$SRC_DIR/markitdown_gui" "$LIB_DIR/"

# Launcher
cat > "$LAUNCHER" <<EOF
#!/usr/bin/env bash
exec python3 -m markitdown_gui "\$@"
EOF
# Run from the install dir so the package is importable.
sed -i "1a export PYTHONPATH=\"$LIB_DIR:\${PYTHONPATH:-}\"" "$LAUNCHER"
chmod +x "$LAUNCHER"

# Icon (prefer the rendered PNG; generate it if only the SVG is present)
if [ -f "$SRC_DIR/assets/icon.png" ]; then
    cp "$SRC_DIR/assets/icon.png" "$ICON_DIR/$APP_ID.png"
elif [ -f "$SRC_DIR/assets/icon.svg" ]; then
    say "Rendering icon from SVG…"
    python3 "$SRC_DIR/scripts/generate_icon.py" "$ICON_DIR/$APP_ID.png" || \
        warn "Icon render failed; the app will still run without a custom icon."
fi

# .desktop entry
cp "$SRC_DIR/packaging/$APP_ID.desktop" "$DESKTOP_DIR/$APP_ID.desktop"

# --------------------------------------------------------------------------- #
# 5. Refresh caches
# --------------------------------------------------------------------------- #
say "Refreshing desktop and icon caches…"
update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true

ok "Installed."
echo
echo "Launch from your applications menu (MarkItDown) or run: $APP_ID"
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) warn "$BIN_DIR is not on your PATH. Add it, or run: $LAUNCHER" ;;
esac
