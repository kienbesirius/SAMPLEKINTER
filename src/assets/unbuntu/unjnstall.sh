#!/usr/bin/env bash
set -euo pipefail

APP_NAME="BypassSampleKinterApp"
APP_ID="BypassSampleKinterApp"

INSTALL_DIR="/opt/${APP_NAME}"

# Detect user (when running with sudo)
REAL_USER="${SUDO_USER:-$USER}"
REAL_HOME="$(getent passwd "${REAL_USER}" | cut -d: -f6)"

USER_APPS_DIR="${REAL_HOME}/.local/share/applications"
DESKTOP_DIR="${REAL_HOME}/Desktop"

DESKTOP_FILE="${USER_APPS_DIR}/${APP_ID}.desktop"
DESKTOP_SHORTCUT="${DESKTOP_DIR}/${APP_NAME}.desktop"

# icon paths (support both png/svg + common dirs)
ICON_PNG_256="${REAL_HOME}/.local/share/icons/hicolor/256x256/apps/${APP_ID}.png"
ICON_SVG_SCALABLE="${REAL_HOME}/.local/share/icons/hicolor/scalable/apps/${APP_ID}.svg"
ICON_PNG_SCALABLE="${REAL_HOME}/.local/share/icons/hicolor/scalable/apps/${APP_ID}.png"  # in case someone saved png there

echo "==> Uninstalling ${APP_NAME}"
echo "    User: ${REAL_USER}"
echo "    Home: ${REAL_HOME}"

# 1) Remove installed app folder
if [[ -d "${INSTALL_DIR}" ]]; then
  echo "==> Removing install dir: ${INSTALL_DIR}"
  sudo rm -rf "${INSTALL_DIR}"
else
  echo "==> Install dir not found: ${INSTALL_DIR} (skip)"
fi

# 2) Remove .desktop launcher + desktop shortcut
echo "==> Removing launcher files"
rm -f "${DESKTOP_FILE}" || true
rm -f "${DESKTOP_SHORTCUT}" || true

# 3) Remove icons (try multiple locations)
echo "==> Removing icons"
rm -f "${ICON_PNG_256}" "${ICON_SVG_SCALABLE}" "${ICON_PNG_SCALABLE}" || true

# 4) Update desktop database (optional)
if command -v update-desktop-database >/dev/null 2>&1; then
  echo "==> Updating desktop database"
  sudo update-desktop-database "${USER_APPS_DIR}" >/dev/null 2>&1 || true
fi

# 5) Remove from GNOME favorites (best-effort)
if command -v gsettings >/dev/null 2>&1; then
  echo "==> Trying to remove from Favorites (GNOME Dock)..."
  DESKTOP_ID="${APP_ID}.desktop"

  FAVS="$(sudo -u "${REAL_USER}" gsettings get org.gnome.shell favorite-apps 2>/dev/null || echo "[]")"

  # Compute new favorites list safely with python (no bash bad substitution)
  NEW_FAVS="$(python3 - "${FAVS}" "${DESKTOP_ID}" <<'PY'
import ast, sys
s = sys.argv[1]
desktop_id = sys.argv[2]

try:
    lst = ast.literal_eval(s)
except Exception:
    lst = []

if not isinstance(lst, list):
    lst = []

lst = [x for x in lst if x != desktop_id]
print(lst)
PY
)"

  # Setting may fail if no GUI session DBUS; ignore errors.
  sudo -u "${REAL_USER}" gsettings set org.gnome.shell favorite-apps "${NEW_FAVS}" >/dev/null 2>&1 || true
  echo "    Favorites update attempted."
else
  echo "==> gsettings not found; skipping Favorites unpin."
fi

echo "✅ Uninstall done."
