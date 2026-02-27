#!/usr/bin/env bash
set -euo pipefail

# =========================
# Install checkfixtureapp
# =========================
APP_NAME="checkfixtureapp"
APP_ID="checkfixtureapp"
INSTALL_DIR="/opt/${APP_ID}"
BIN_NAME="checkfixtureapp"          # file binary sau khi PyInstaller (Linux: no .exe)
ICON_BASENAME="${APP_ID}"           # sẽ lưu thành ~/.local/share/icons/.../checkfixtureapp.png|svg
DESKTOP_FILE_NAME="${APP_ID}.desktop"
# ---- Input ----
# Dùng: ./install_check_fixture.sh checkfixture delphi-svgrepo-com.svg config.ini

# Watchdog (optional): bạn nói bind py theo src rồi -> đặt ở /opt/<app>/src/watchdog/watchdog_service.py
WATCHDOG_REL="src/watchdog/watchdog_service.py"

usage() {
  echo "Usage:"
  echo "  $0 /path/to/${BIN_NAME} /path/to/icon.(png|svg) /path/to/config.ini [optional_src_dir]"
  echo ""
  echo "Examples:"
  echo "  sudo $0 ./dist/${BIN_NAME} ./assets/icon.svg ./config.ini ./src"
}

SRC_BIN="${1:-}"
SRC_ICON="${2:-}"
SRC_CONFIG="${3:-}"
SRC_DIR="${4:-}"   # optional: folder src/ để copy vào /opt/<app>/src (chứa watchdog .py)

if [[ -z "${SRC_BIN}" || -z "${SRC_ICON}" || -z "${SRC_CONFIG}" ]]; then
  usage
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

if [[ ! -f "${SRC_ICON}" ]]; then
  echo "ERROR: icon not found: ${SRC_ICON}"
  exit 1
fi

if [[ ! -f "${SRC_CONFIG}" ]]; then
  echo "ERROR: config.ini not found: ${SRC_CONFIG}"
  exit 1
fi

# Detect real user (when running with sudo)
REAL_USER="${SUDO_USER:-$USER}"
REAL_HOME="$(getent passwd "${REAL_USER}" | cut -d: -f6)"

USER_APPS_DIR="${REAL_HOME}/.local/share/applications"
USER_ICONS_DIR="${REAL_HOME}/.local/share/icons/hicolor/256x256/apps"
DESKTOP_FILE="${USER_APPS_DIR}/${DESKTOP_FILE_NAME}"
DESKTOP_SHORTCUT="${REAL_HOME}/Desktop/${APP_NAME}.desktop"

TARGET_BIN="${INSTALL_DIR}/${BIN_NAME}"
TARGET_CONFIG="${INSTALL_DIR}/config.ini"
TARGET_LOGS="${INSTALL_DIR}/LOGS"

# icon target keep original extension
ICON_EXT="${SRC_ICON##*.}"
TARGET_ICON="${USER_ICONS_DIR}/${ICON_BASENAME}.${ICON_EXT}"

echo "==> Installing ${APP_NAME}"
echo "    Real user : ${REAL_USER}"
echo "    Home      : ${REAL_HOME}"
echo "    Install   : ${INSTALL_DIR}"
echo "    Binary    : ${SRC_BIN}"
echo "    Icon      : ${SRC_ICON}"
echo "    Config    : ${SRC_CONFIG}"
if [[ -n "${SRC_DIR}" ]]; then
  echo "    Src dir   : ${SRC_DIR}"
fi

# 1) Copy binary + config to /opt
echo "==> Copying to ${INSTALL_DIR}"
sudo mkdir -p "${INSTALL_DIR}"
sudo install -m 0755 "${SRC_BIN}" "${TARGET_BIN}"
sudo install -m 0644 "${SRC_CONFIG}" "${TARGET_CONFIG}"

# optional: copy src/ for watchdog .py
if [[ -n "${SRC_DIR}" ]]; then
  if [[ ! -d "${SRC_DIR}" ]]; then
    echo "ERROR: optional_src_dir is not a directory: ${SRC_DIR}"
    exit 1
  fi
  echo "==> Copying src/ to ${INSTALL_DIR}/src"
  sudo rm -rf "${INSTALL_DIR}/src"
  sudo mkdir -p "${INSTALL_DIR}/src"
  sudo cp -a "${SRC_DIR}/." "${INSTALL_DIR}/src/"
fi

# 2) Logs dir writable by real user
echo "==> Preparing logs folder: ${TARGET_LOGS}"
sudo mkdir -p "${TARGET_LOGS}"
sudo chown -R "${REAL_USER}:${REAL_USER}" "${TARGET_LOGS}"
sudo chmod 775 "${TARGET_LOGS}"

# 3) Install icon (per-user)
echo "==> Installing icon to ${TARGET_ICON}"
sudo -u "${REAL_USER}" mkdir -p "${USER_ICONS_DIR}"
sudo -u "${REAL_USER}" install -m 0644 "${SRC_ICON}" "${TARGET_ICON}"

# 4) Create .desktop launcher (Applications menu)
echo "==> Creating launcher: ${DESKTOP_FILE}"
sudo -u "${REAL_USER}" mkdir -p "${USER_APPS_DIR}"

# Use WorkingDirectory so app can resolve relative paths if needed
# Pass CONFIG path explicitly (recommended): app should read argv or env if you support it
# If your app doesn't support args, you can remove the config argument.
EXEC_LINE="${TARGET_BIN}"

# Optional watchdog: chạy python watchdog_service.py trước rồi chạy app
# (nếu bạn copy SRC_DIR vào /opt/app/src và file watchdog tồn tại)
WATCHDOG_ABS="${INSTALL_DIR}/${WATCHDOG_REL}"
if [[ -f "${WATCHDOG_ABS}" ]]; then
  # Launch watchdog in background, then app
  # NOTE: uses bash -lc so background works; stdout/stderr are not shown.
  EXEC_LINE="bash -lc 'python3 \"${WATCHDOG_ABS}\" --port 43999 --log-dir \"${TARGET_LOGS}\" >/dev/null 2>&1 & exec \"${TARGET_BIN}\"'"
fi

sudo -u "${REAL_USER}" tee "${DESKTOP_FILE}" >/dev/null <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=${APP_NAME}
StartupWMClass=${APP_NAME}
Comment=Fixture GUI (PyInstaller)
Exec=${EXEC_LINE}
Terminal=false
Categories=Utility;Development;
Icon=${TARGET_ICON}
Path=${INSTALL_DIR}
StartupNotify=true
EOF

sudo -u "${REAL_USER}" chmod 0644 "${DESKTOP_FILE}"

# 5) Desktop shortcut
if [[ -d "${REAL_HOME}/Desktop" ]]; then
  echo "==> Creating Desktop shortcut: ${DESKTOP_SHORTCUT}"
  sudo -u "${REAL_USER}" cp -f "${DESKTOP_FILE}" "${DESKTOP_SHORTCUT}"
  sudo -u "${REAL_USER}" chmod 0755 "${DESKTOP_SHORTCUT}" || true
  if command -v gio >/dev/null 2>&1; then
    sudo -u "${REAL_USER}" gio set "${DESKTOP_SHORTCUT}" metadata::trusted true >/dev/null 2>&1 || true
  fi
fi

# 6) Update desktop database (optional)
if command -v update-desktop-database >/dev/null 2>&1; then
  echo "==> Updating desktop database"
  sudo update-desktop-database "${USER_APPS_DIR}" >/dev/null 2>&1 || true
fi

echo "✅ Done."
echo "Installed binary : ${TARGET_BIN}"
echo "Installed config : ${TARGET_CONFIG}"
echo "Logs directory   : ${TARGET_LOGS}"
echo "Launcher         : ${DESKTOP_FILE}"
echo "Desktop shortcut : ${DESKTOP_SHORTCUT}"

sudo install -m 0755 "${SRC_BIN}" "${TARGET_BIN}"
sudo install -m 0664 "${SRC_CONFIG}" "${TARGET_CONFIG}"

sudo mkdir -p "${INSTALL_DIR}/LOGS"
sudo chmod 0775 "${INSTALL_DIR}/LOGS"

sudo mkdir -p "${INSTALL_DIR}/logs"
sudo chmod 0775 "${INSTALL_DIR}/logs"

sudo mkdir -p "${INSTALL_DIR}"
sudo chown -R "${REAL_USER}:${REAL_USER}" "${INSTALL_DIR}"
sudo chmod 775 "${INSTALL_DIR}"

sudo chmod +x "${TARGET_BIN}"