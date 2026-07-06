#!/usr/bin/env bash
# ATANOR Environment — Stage 1 installer.
# Turns a stock Ubuntu 22.04/24.04 into an ATANOR machine: the engine and web shell run
# as bounded systemd services from boot, data lives in /var/lib/atanor, and (optionally)
# the machine boots straight into the ATANOR shell in kiosk mode.
#
#   sudo bash install.sh                 # services only (reach it at http://localhost:3000)
#   sudo bash install.sh --kiosk         # + boot into full-screen ATANOR shell
#
# Idempotent: safe to re-run for updates (git pull + rebuild + restart).
# Honest boundaries: no kernel/driver work here — Ubuntu LTS carries that. Ctrl+Alt+F2
# always remains a normal TTY; we never lock the user in.
set -euo pipefail

REPO_URL="${ATANOR_REPO:-https://github.com/Cozystone/ATANOR-Demo.git}"
BRANCH="${ATANOR_BRANCH:-demo}"
APP_DIR=/opt/atanor
DATA_DIR=/var/lib/atanor
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KIOSK=0
[ "${1:-}" = "--kiosk" ] && KIOSK=1

[ "$(id -u)" -eq 0 ] || { echo "run with sudo"; exit 1; }

echo "[1/6] packages"
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  git python3 python3-venv python3-pip nodejs npm curl
if [ "$KIOSK" -eq 1 ]; then
  DEBIAN_FRONTEND=noninteractive apt-get install -y cage chromium-browser || \
  DEBIAN_FRONTEND=noninteractive apt-get install -y cage chromium
fi

echo "[2/6] atanor system user + directories"
id -u atanor >/dev/null 2>&1 || useradd --system --create-home --home-dir /var/lib/atanor-home atanor
mkdir -p "$DATA_DIR"
chown -R atanor:atanor "$DATA_DIR"

echo "[3/6] code -> $APP_DIR"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch origin && git -C "$APP_DIR" checkout "$BRANCH" && git -C "$APP_DIR" pull --ff-only origin "$BRANCH"
else
  git clone --branch "$BRANCH" --depth 1 "$REPO_URL" "$APP_DIR"
fi
chown -R atanor:atanor "$APP_DIR"

echo "[4/6] python venv + node build"
sudo -u atanor python3 -m venv "$APP_DIR/.venv"
sudo -u atanor "$APP_DIR/.venv/bin/pip" install --upgrade pip -q
sudo -u atanor "$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/deploy/requirements-cloud.txt"
( cd "$APP_DIR/apps/web" && sudo -u atanor npm install --no-audit --no-fund && sudo -u atanor npm run build )

echo "[5/6] systemd services"
install -m 0644 "$HERE/atanor-engine.service" /etc/systemd/system/atanor-engine.service
install -m 0644 "$HERE/atanor-web.service" /etc/systemd/system/atanor-web.service
systemctl daemon-reload
systemctl enable --now atanor-engine.service atanor-web.service

if [ "$KIOSK" -eq 1 ]; then
  echo "[6/6] kiosk shell (boots into ATANOR; Ctrl+Alt+F2 stays a normal TTY)"
  install -m 0644 "$HERE/atanor-shell.service" /etc/systemd/system/atanor-shell.service
  systemctl enable atanor-shell.service
  systemctl set-default graphical.target
else
  echo "[6/6] no kiosk requested — open http://localhost:3000"
fi

echo
echo "ATANOR Environment installed."
echo "  engine : systemctl status atanor-engine   (health: curl http://127.0.0.1:8502/health)"
echo "  shell  : http://localhost:3000"
echo "  data   : $DATA_DIR   (backup = copy this directory)"
