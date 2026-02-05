#!/usr/bin/env bash
set -euo pipefail

APP_NAME="BypassSampleKinterApp"
APP_ID="BypassSampleKinterApp"
INSTALL_DIR="/opt/${APP_NAME}"
BIN_NAME="BypassSampleKinterApp"         # tên file chạy sau khi đóng gói (PyInstaller)
ICON_NAME="${APP_ID}.svg"

# ---- Input ----
# Dùng: ./install_bypass_app.sh BypassSampleKinterApp treasure-svgrepo-com.svg config.ini

SRC_BIN="${1:-}"
SRC_ICON="${2:-}"
SRC_CONFIG="${3:-}"
# ---------------
if [[ -z "${SRC_BIN}" ]]; then
  echo "Usage: $0 /path/to/${BIN_NAME} [optional_icon.png] [optional_config.ini]"
  exit 1
fi

if [[ ! -f "${SRC_BIN}" ]]; then
  echo "ERROR: binary not found: ${SRC_BIN}"
  exit 1
fi

if [[ ! -x "${SRC_BIN}" ]]; then
  echo "ERROR: binary is not executable. Run: chmod +x '${SRC_BIN}'"
  exit 1
fi


# Detect user (when running with sudo)
REAL_USER="${SUDO_USER:-$USER}"
REAL_HOME="$(getent passwd "${REAL_USER}" | cut -d: -f6)"

DESKTOP_DIR="${REAL_HOME}/Desktop"
USER_APPS_DIR="${REAL_HOME}/.local/share/applications"
USER_ICONS_DIR="${REAL_HOME}/.local/share/icons/hicolor/256x256/apps"
DESKTOP_FILE="${USER_APPS_DIR}/${APP_ID}.desktop"
DESKTOP_SHORTCUT="${DESKTOP_DIR}/${APP_NAME}.desktop"
TARGET_BIN="${INSTALL_DIR}/${BIN_NAME}"
TARGET_ICON="${USER_ICONS_DIR}/${ICON_NAME}"
TARGET_CONFIG="${INSTALL_DIR}/config.ini"

echo "==> Installing ${APP_NAME}"
echo "    User: ${REAL_USER}"
echo "    Home: ${REAL_HOME}"
echo "    Source binary: ${SRC_BIN}"

# ---- 1) Copy binary to /opt ----
echo "==> Copying binary to ${INSTALL_DIR}"
sudo mkdir -p "${INSTALL_DIR}"
sudo install -m 0755 "${SRC_BIN}" "${TARGET_BIN}"
# If config file provided, copy it too
if [[ -n "${SRC_CONFIG}" ]]; then
  if [[ ! -f "${SRC_CONFIG}" ]]; then
    echo "ERROR: config file not found: ${SRC_CONFIG}"
    exit 1
  fi
  echo "==> Installing config file from ${SRC_CONFIG}"
  sudo install -m 0644 "${SRC_CONFIG}" "${TARGET_CONFIG}"
fi

# ---- 2) Install icon ----
sudo -u "${REAL_USER}" mkdir -p "${USER_ICONS_DIR}"

if [[ -n "${SRC_ICON}" ]]; then
  if [[ ! -f "${SRC_ICON}" ]]; then
    echo "ERROR: icon not found: ${SRC_ICON}"
    exit 1
  fi
  echo "==> Installing icon from ${SRC_ICON}"
  sudo -u "${REAL_USER}" install -m 0644 "${SRC_ICON}" "${TARGET_ICON}"
else
  # Fallback: tạo icon placeholder bằng ImageMagick nếu có, không thì bỏ qua
  if command -v convert >/dev/null 2>&1; then
    echo "==> No icon provided. Creating placeholder icon (requires ImageMagick)."
    sudo -u "${REAL_USER}" convert -size 256x256 xc:transparent \
      -fill "#2E3440" -draw "roundrectangle 12,12 244,244 28,28" \
      -fill "#ECEFF4" -pointsize 22 -gravity center -annotate +0+0 "${APP_NAME}" \
      "${TARGET_ICON}"
  else
    echo "==> No icon provided and ImageMagick not found; launcher will use default icon."
    TARGET_ICON=""
  fi
fi

# ---- 3) Create .desktop launcher (Applications menu) ----
echo "==> Creating launcher: ${DESKTOP_FILE}"
sudo -u "${REAL_USER}" mkdir -p "${USER_APPS_DIR}"

ICON_LINE="Icon=${TARGET_ICON}"
if [[ -z "${TARGET_ICON}" ]]; then
  ICON_LINE="Icon=utilities-terminal" # fallback icon
fi

sudo -u "${REAL_USER}" tee "${DESKTOP_FILE}" >/dev/null <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=${APP_NAME}
StartupWMClass=Bypasssamplekinterapp
Comment=Bypass tool (PyInstaller)
Exec=${TARGET_BIN}
Terminal=false
Categories=Utility;Development;
${ICON_LINE}
StartupNotify=true
EOF

sudo -u "${REAL_USER}" chmod 0644 "${DESKTOP_FILE}"

# ---- 4) Optional: put a shortcut on Desktop ----
if [[ -d "${DESKTOP_DIR}" ]]; then
  echo "==> Creating Desktop shortcut: ${DESKTOP_SHORTCUT}"
  sudo -u "${REAL_USER}" cp -f "${DESKTOP_FILE}" "${DESKTOP_SHORTCUT}"
  sudo -u "${REAL_USER}" chmod 0755 "${DESKTOP_SHORTCUT}" || true

  # GNOME/Nautilus: allow launching if needed (metadata may be required in some setups)
  if command -v gio >/dev/null 2>&1; then
    sudo -u "${REAL_USER}" gio set "${DESKTOP_SHORTCUT}" metadata::trusted true >/dev/null 2>&1 || true
  fi
fi

# ---- 5) Update desktop database ----
if command -v update-desktop-database >/dev/null 2>&1; then
  echo "==> Updating desktop database"
  sudo update-desktop-database "${USER_APPS_DIR}" >/dev/null 2>&1 || true
fi

# ---- 6) Optional: pin to Favorites (GNOME) ----
# Works on GNOME Shell with org.gnome.shell favorite-apps
if command -v gsettings >/dev/null 2>&1; then
  echo "==> Trying to add to Favorites (GNOME Dock)..."
  DESKTOP_ID="${APP_ID}.desktop"
  # read current favorites
  FAVS="$(sudo -u "${REAL_USER}" gsettings get org.gnome.shell favorite-apps 2>/dev/null || echo "[]")"
  if echo "${FAVS}" | grep -q "${DESKTOP_ID}"; then
    echo "    Already in favorites."
  else
    # append desktop id to list
        DESKTOP_ID="${APP_ID}.desktop"

    FAVS="$(sudo -u "${REAL_USER}" gsettings get org.gnome.shell favorite-apps 2>/dev/null || echo "[]")"
    if echo "${FAVS}" | grep -q "${DESKTOP_ID}"; then
      echo "    Already in favorites."
    else
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

if desktop_id not in lst:
    lst.append(desktop_id)

print(lst)
PY
)"
      sudo -u "${REAL_USER}" gsettings set org.gnome.shell favorite-apps "${NEW_FAVS}" >/dev/null 2>&1 || true
      echo "    Added to favorites (if supported)."
    fi

    sudo -u "${REAL_USER}" gsettings set org.gnome.shell favorite-apps "${NEW_FAVS}" >/dev/null 2>&1 || true
    echo "    Added to favorites (if supported by your desktop)."
  fi
else
  echo "==> gsettings not found; skipping Favorites pin."
fi

# ---- 7) Remove original run file (the one user executed / on Desktop) ----
echo "==> Removing original binary: ${SRC_BIN}"
rm -f "${SRC_BIN}" || true

echo "✅ Done."
echo "App installed to: ${TARGET_BIN}"
echo "Launcher: ${DESKTOP_FILE}"
echo "Desktop shortcut: ${DESKTOP_SHORTCUT}"

sudo mkdir -p "${INSTALL_DIR}/LOGS"
sudo chown -R "${REAL_USER}:${REAL_USER}" "${INSTALL_DIR}/LOGS"
sudo chmod 775 "${INSTALL_DIR}/LOGS"