#!/usr/bin/env bash
#
# Uninstall MarkItDown GUI from ~/.local.
# Leaves the `markitdown` CLI and apt packages (python3-tk) untouched.
#
set -euo pipefail

APP_ID="markitdown-gui"

LIB_DIR="$HOME/.local/lib/$APP_ID"
LAUNCHER="$HOME/.local/bin/$APP_ID"
DESKTOP_FILE="$HOME/.local/share/applications/$APP_ID.desktop"
ICON_FILE="$HOME/.local/share/icons/hicolor/256x256/apps/$APP_ID.png"

ok() { printf '\033[1;32m[✓]\033[0m %s\n' "$*"; }

rm -rf "$LIB_DIR"        && ok "Removed $LIB_DIR"
rm -f  "$LAUNCHER"       && ok "Removed $LAUNCHER"
rm -f  "$DESKTOP_FILE"   && ok "Removed $DESKTOP_FILE"
rm -f  "$ICON_FILE"      && ok "Removed $ICON_FILE"

update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true

echo
ok "MarkItDown GUI uninstalled. The markitdown CLI was left intact."
echo "To remove the CLI too:  pipx uninstall markitdown"
