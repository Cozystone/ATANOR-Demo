#!/usr/bin/env bash
# ============================================================================
# ATANOR Linux v0 — stage 2a: keep ONLY the Linux kernel; drop every Ubuntu/
# GNOME layer. Debian minbase (debootstrap) + our engine + cage (kiosk Wayland
# compositor) + chromium. The machine boots straight into the ATANOR shell:
# no display manager, no desktop environment, no distro branding anywhere.
#
#   sudo bash build.sh rootfs    # phase 1: debootstrap + packages into ROOTFS
#   sudo bash build.sh atanor    # phase 2: engine + web build + services
#   sudo bash build.sh image     # phase 3: bootable GPT disk image (USB-flashable)
#   sudo bash build.sh all       # everything
#
# Output: $WORK/atanor-linux.img  (dd to USB, or boot in QEMU)
# Honest scope of v0: kiosk shell (the orb IS the screen; SPLATRA wallpaper
# field behind it). Multi-window desktop arrives with our own compositor (2b).
# ============================================================================
set -euo pipefail

WORK=${ATANOR_LINUX_WORK:-/opt/atanor-linux}
ROOTFS="$WORK/rootfs"
IMG="$WORK/atanor-linux.img"
MIRROR=${ATANOR_DEB_MIRROR:-http://deb.debian.org/debian}
SUITE=bookworm
REPO_URL=${ATANOR_REPO:-https://github.com/Cozystone/ATANOR-Demo.git}
BRANCH=${ATANOR_BRANCH:-demo}
IMG_SIZE_GB=${ATANOR_IMG_GB:-14}

[ "$(id -u)" -eq 0 ] || { echo "run with sudo"; exit 1; }
PHASE="${1:-all}"

in_chroot() { chroot "$ROOTFS" /usr/bin/env DEBIAN_FRONTEND=noninteractive bash -c "$1"; }

mount_binds() {
  mountpoint -q "$ROOTFS/proc" || mount -t proc proc "$ROOTFS/proc"
  mountpoint -q "$ROOTFS/sys" || mount -t sysfs sys "$ROOTFS/sys"
  mountpoint -q "$ROOTFS/dev" || mount --bind /dev "$ROOTFS/dev"
  mountpoint -q "$ROOTFS/dev/pts" || mount --bind /dev/pts "$ROOTFS/dev/pts"
  # the chroot resolves names with ITS OWN /etc/hosts + resolv.conf — inherit the
  # host's (incl. any DNS-outage /etc/hosts pinning) or apt dies while the host works
  cp /etc/resolv.conf "$ROOTFS/etc/resolv.conf" 2>/dev/null || true
  cp /etc/hosts "$ROOTFS/etc/hosts" 2>/dev/null || true
}
umount_binds() {
  for m in dev/pts dev sys proc; do umount -l "$ROOTFS/$m" 2>/dev/null || true; done
}
trap umount_binds EXIT

# ---------------------------------------------------------------- phase: rootfs
if [ "$PHASE" = rootfs ] || [ "$PHASE" = all ]; then
  echo "== [1/3] debootstrap $SUITE minbase =="
  mkdir -p "$ROOTFS"
  if [ ! -f "$ROOTFS/etc/debian_version" ]; then
    debootstrap --variant=minbase --arch=amd64 "$SUITE" "$ROOTFS" "$MIRROR"
  fi
  # non-free-firmware: real hardware (Wi-Fi/GPU microcode) needs blobs on USB boot
  cat > "$ROOTFS/etc/apt/sources.list" <<EOF
deb $MIRROR $SUITE main contrib non-free-firmware
deb $MIRROR ${SUITE}-updates main contrib non-free-firmware
deb http://security.debian.org/debian-security ${SUITE}-security main contrib non-free-firmware
EOF
  mount_binds
  in_chroot "apt-get update -qq"
  echo "== kernel + boot + session stack (NO desktop environment) =="
  in_chroot "apt-get install -y --no-install-recommends \
    linux-image-amd64 firmware-linux-free intel-microcode amd64-microcode \
    systemd systemd-sysv systemd-boot udev dbus \
    iproute2 iputils-ping systemd-resolved systemd-timesyncd \
    ca-certificates curl git sudo locales \
    python3 python3-venv python3-pip \
    xorg xinit openbox tint2 pcmanfm lxterminal chromium \
    libgl1-mesa-dri libegl-mesa0 \
    alsa-utils fonts-noto-cjk fonts-noto-color-emoji \
    xdotool x11-utils x11-xserver-utils wmctrl"
  echo "== node 20 (web shell) =="
  # pipefail matters: if the nodesource setup fails, plain 'apt install nodejs' would
  # silently install Debian's node 18 (too old for Next 16) — fail loudly instead
  in_chroot "set -o pipefail && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt-get install -y nodejs && node -v | grep -q '^v2[0-9]'"
  echo "== identity: this machine calls itself ATANOR Linux, kernel by Linux =="
  echo atanor > "$ROOTFS/etc/hostname"
  cat > "$ROOTFS/etc/os-release" <<'EOF'
PRETTY_NAME="ATANOR Linux 0.1"
NAME="ATANOR Linux"
VERSION_ID="0.1"
VERSION="0.1 (own desktop on a plain Linux kernel; package base: Debian bookworm)"
ID=atanor
ID_LIKE=debian
HOME_URL="https://atanor-liard.vercel.app"
EOF
  printf 'ATANOR Linux 0.1  \\n (\\l)\n\n' > "$ROOTFS/etc/issue"
  in_chroot "sed -i 's/^# *ko_KR.UTF-8/ko_KR.UTF-8/; s/^# *en_US.UTF-8/en_US.UTF-8/' /etc/locale.gen && locale-gen"
  echo 'LANG=ko_KR.UTF-8' > "$ROOTFS/etc/default/locale"
  in_chroot "id -u atanor >/dev/null 2>&1 || useradd -m -s /bin/bash -G sudo,video,render,audio,input atanor"
  in_chroot "echo 'atanor:Atanor!Dev2026' | chpasswd"
  echo "PHASE-ROOTFS-OK"
fi

# ---------------------------------------------------------------- phase: atanor
if [ "$PHASE" = atanor ] || [ "$PHASE" = all ]; then
  echo "== [2/3] ATANOR engine + shell =="
  mount_binds
  in_chroot "[ -d /opt/atanor/.git ] || git clone --branch $BRANCH --depth 1 $REPO_URL /opt/atanor"
  # root pulls a repo owned by atanor — git's ownership guard blocks it SILENTLY
  # under '|| true' (shipped a stale rootfs once). Allow-list + fail loudly.
  in_chroot "git config --global --add safe.directory /opt/atanor && git -C /opt/atanor pull --ff-only origin $BRANCH"
  in_chroot "python3 -m venv /opt/atanor/.venv && /opt/atanor/.venv/bin/pip install -q --upgrade pip"
  in_chroot "/opt/atanor/.venv/bin/pip install -q -r /opt/atanor/deploy/requirements-cloud.txt"
  # import-path contract (same lesson as the Ubuntu VM: encode as .pth, not env)
  in_chroot 'SITE=$(/opt/atanor/.venv/bin/python -c "import site;print(site.getsitepackages()[0])"); { echo /opt/atanor; echo /opt/atanor/apps/api; for d in /opt/atanor/packages/*/; do echo ${d%/}; done; } > "$SITE/atanor-paths.pth"'
  in_chroot "cd /opt/atanor/apps/web && npm install --no-audit --no-fund && npm run build"
  in_chroot "chown -R atanor:atanor /opt/atanor && mkdir -p /var/lib/atanor && chown atanor:atanor /var/lib/atanor"
  # ship the BRAIN: the curated triple store is data (untracked in git) — without
  # this the OS boots with an empty knowledge store. Copy from the build host's
  # working repo when present (WSL sees the Windows worktree under /mnt/c).
  HOST_KG=${ATANOR_KG_SOURCE:-"/mnt/c/0.ASKIM ALL-VIN/27., ATANOR DEMO/data/graph_scale/kg_triples"}
  if [ -d "$HOST_KG" ]; then
    mkdir -p "$ROOTFS/opt/atanor/data/graph_scale"
    rm -rf "$ROOTFS/opt/atanor/data/graph_scale/kg_triples"
    cp -r "$HOST_KG" "$ROOTFS/opt/atanor/data/graph_scale/kg_triples"
    in_chroot "chown -R atanor:atanor /opt/atanor/data"
    echo "  brain shipped: $(du -sh "$ROOTFS/opt/atanor/data/graph_scale/kg_triples" | cut -f1) curated triples"
  else
    echo "  WARNING: no host kg_triples found — image boots with an empty store"
  fi

  echo "== services: engine + web + shell-on-tty1 (no display manager at all) =="
  # source of truth is the repo ALREADY CLONED INSIDE the chroot — no host-side
  # sibling-directory assumptions (that path broke the first image build)
  install -m 0644 "$ROOTFS/opt/atanor/deploy/atanor-environment/atanor-engine.service" "$ROOTFS/etc/systemd/system/atanor-engine.service"
  install -m 0644 "$ROOTFS/opt/atanor/deploy/atanor-environment/atanor-web.service" "$ROOTFS/etc/systemd/system/atanor-web.service"
  # ---- the ATANOR desktop: our own X session, Windows-like by design ----
  mkdir -p "$ROOTFS/etc/atanor"
  install -m 0755 "$ROOTFS/opt/atanor/deploy/atanor-linux/xsession" "$ROOTFS/etc/atanor/xsession"
  install -m 0644 "$ROOTFS/opt/atanor/deploy/atanor-linux/tint2rc" "$ROOTFS/etc/atanor/tint2rc"
  install -m 0755 "$ROOTFS/opt/atanor/deploy/atanor-linux/orb-window.sh" "$ROOTFS/usr/local/bin/atanor-orb-window"
  install -m 0755 "$ROOTFS/opt/atanor/deploy/atanor-environment/orb-wallpaper.sh" "$ROOTFS/usr/local/bin/atanor-orb-wallpaper"
  # systemd session on tty1 needs the X wrapper to allow it
  printf 'allowed_users=anybody\nneeds_root_rights=yes\n' > "$ROOTFS/etc/X11/Xwrapper.config"
  cat > "$ROOTFS/etc/systemd/system/atanor-desktop.service" <<'EOF'
# ATANOR Linux: the machine boots into OUR desktop — openbox windows, tint2
# taskbar, SPLATRA living wallpaper, resident orb. Ctrl+Alt+F2 stays a TTY.
[Unit]
Description=ATANOR desktop (own X session)
After=systemd-user-sessions.service atanor-web.service getty@tty1.service
Wants=atanor-web.service
# tty1 belongs to the desktop — without this, getty grabs the console and the
# machine boots to a login prompt instead (first-boot lesson)
Conflicts=getty@tty1.service

[Service]
User=atanor
PAMName=login
TTYPath=/dev/tty1
StandardInput=tty
StandardOutput=journal
UtmpIdentifier=tty1
Environment=XDG_RUNTIME_DIR=/run/user/1000
ExecStartPre=/bin/sh -c 'mkdir -p /run/user/1000 && chown atanor:atanor /run/user/1000'
ExecStart=/usr/bin/startx /etc/atanor/xsession -- :0 vt1 -keeptty -nolisten tcp
Restart=always
RestartSec=3

[Install]
WantedBy=graphical.target
EOF
  in_chroot "systemctl disable atanor-shell 2>/dev/null; rm -f /etc/systemd/system/atanor-shell.service; systemctl enable atanor-engine atanor-web atanor-desktop systemd-resolved systemd-timesyncd && systemctl set-default graphical.target"
  # DHCP on every wired interface — a USB-booted machine must just get online
  cat > "$ROOTFS/etc/systemd/network/20-wired.network" <<'EOF'
[Match]
Name=en* eth*
[Network]
DHCP=yes
EOF
  in_chroot "systemctl enable systemd-networkd"
  echo "PHASE-ATANOR-OK"
fi

# ---------------------------------------------------------------- phase: image
if [ "$PHASE" = image ] || [ "$PHASE" = all ]; then
  echo "== [3/3] bootable image (GPT: ESP + ext4 root, systemd-boot) =="
  umount_binds
  rm -f "$IMG"
  truncate -s "${IMG_SIZE_GB}G" "$IMG"
  LOOP=$(losetup --show -fP "$IMG")
  # GPT: 512M ESP + rest root
  parted -s "$LOOP" mklabel gpt \
    mkpart ESP fat32 1MiB 513MiB set 1 esp on \
    mkpart root ext4 513MiB 100%
  mkfs.vfat -F32 -n ATANOR-EFI "${LOOP}p1"
  mkfs.ext4 -q -L atanor-root "${LOOP}p2"
  MNT="$WORK/mnt"; mkdir -p "$MNT"
  mount "${LOOP}p2" "$MNT"
  mkdir -p "$MNT/boot/efi"
  mount "${LOOP}p1" "$MNT/boot/efi"
  echo "  rsync rootfs -> image"
  rsync -aHAX --numeric-ids "$ROOTFS/" "$MNT/" --exclude proc --exclude sys --exclude dev
  mkdir -p "$MNT/proc" "$MNT/sys" "$MNT/dev"
  ROOT_UUID=$(blkid -s UUID -o value "${LOOP}p2")
  cat > "$MNT/etc/fstab" <<EOF
UUID=$ROOT_UUID / ext4 defaults 0 1
$(blkid -s UUID -o value "${LOOP}p1" | sed 's/^/UUID=/') /boot/efi vfat umask=0077 0 2
EOF
  # systemd-boot: tiny, no grub theming battles — our splash is the shell itself
  mount -t proc proc "$MNT/proc"; mount --bind /dev "$MNT/dev"; mount -t sysfs sys "$MNT/sys"
  chroot "$MNT" bootctl install --no-variables
  KVER=$(ls "$MNT/lib/modules" | head -1)
  cp "$MNT/boot/vmlinuz-$KVER" "$MNT/boot/efi/vmlinuz"
  cp "$MNT/boot/initrd.img-$KVER" "$MNT/boot/efi/initrd.img"
  mkdir -p "$MNT/boot/efi/loader/entries"
  cat > "$MNT/boot/efi/loader/loader.conf" <<'EOF'
default atanor.conf
timeout 0
editor no
EOF
  cat > "$MNT/boot/efi/loader/entries/atanor.conf" <<EOF
title ATANOR
linux /vmlinuz
initrd /initrd.img
options root=UUID=$ROOT_UUID rw quiet loglevel=3 vt.global_cursor_default=0
EOF
  umount -l "$MNT/proc" "$MNT/dev" "$MNT/sys" 2>/dev/null || true
  umount -l "$MNT/boot/efi" "$MNT"
  losetup -d "$LOOP"
  echo "PHASE-IMAGE-OK -> $IMG"
  echo "boot test: qemu-system-x86_64 -enable-kvm -m 4096 -smp 4 -drive file=$IMG,format=raw,if=virtio -bios /usr/share/ovmf/OVMF.fd"
fi
