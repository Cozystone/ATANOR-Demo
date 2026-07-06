#!/usr/bin/env bash
# Quick desktop-branding repair: reinstall the dconf keyfile + orb extension and
# VERIFY the db compiles (the failure mode that left the desktop looking stock).
# Safe to re-run; does not touch services or rebuild anything.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ "$(id -u)" -eq 0 ] || { echo "run with sudo"; exit 1; }

mkdir -p /etc/dconf/profile /etc/dconf/db/local.d
printf 'user-db:user\nsystem-db:local\n' > /etc/dconf/profile/user
install -m 0644 "$HERE/dconf/01-atanor" /etc/dconf/db/local.d/01-atanor

EXT_UUID=atanor-orb@atanor.ai
install -d /usr/share/gnome-shell/extensions/$EXT_UUID
cp "$HERE/gnome-extension/$EXT_UUID/"* /usr/share/gnome-shell/extensions/$EXT_UUID/

dconf update
dconf compile /tmp/atanor-dconf-test.db /etc/dconf/db/local.d
rm -f /tmp/atanor-dconf-test.db
echo "DCONF-COMPILE-OK"

# Dash-to-Panel lives in universe; a minimal install ships main-only
if [ ! -d /usr/share/gnome-shell/extensions/dash-to-panel@jderose9.github.com ]; then
  add-apt-repository -y universe >/dev/null 2>&1 || true
  apt-get update -qq || true
  DEBIAN_FRONTEND=noninteractive apt-get install -y gnome-shell-extension-dash-to-panel
fi

# Xorg session (xdotool active-window sensing is Xorg-only for now)
if [ -f /etc/gdm3/custom.conf ] && ! grep -q '^WaylandEnable=false' /etc/gdm3/custom.conf; then
  sed -i 's/^#\?WaylandEnable=.*/WaylandEnable=false/' /etc/gdm3/custom.conf
  grep -q '^WaylandEnable=false' /etc/gdm3/custom.conf || sed -i '/^\[daemon\]/a WaylandEnable=false' /etc/gdm3/custom.conf
fi

# perception daemon (user unit; OPT-IN — enabled per-user, not here)
mkdir -p /etc/systemd/user
install -m 0644 "$HERE/atanor-perception.service" /etc/systemd/user/atanor-perception.service
command -v xdotool >/dev/null 2>&1 || DEBIAN_FRONTEND=noninteractive apt-get install -y xdotool

echo "--- diagnostics ---"
ls /usr/share/gnome-shell/extensions/
command -v chromium chromium-browser firefox 2>/dev/null || true
[ -f /etc/xdg/autostart/atanor-orb.desktop ] && echo "AUTOSTART-OK" || echo "AUTOSTART-MISSING"
[ -f /usr/share/atanor/logo.png ] && echo "LOGO-OK" || echo "LOGO-MISSING"
echo "reboot (or log out/in) to apply"
