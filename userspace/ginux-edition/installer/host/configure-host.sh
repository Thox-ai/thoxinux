#!/bin/bash
# Copyright (c) 2026 THOX.ai LLC. Licensed under the Apache License, Version 2.0.
# ThoxOS Ginux Edition: configure the host root inside the image build.
#
# Runs once in installer/host/Dockerfile after the packages, the ThoxOS runtime
# and the overlays are in place. Every choice depends on two values:
#   TARGET   knighthub | azure
#   DESKTOP  headless  | desktop
# and on HOST_VERSION / THOXOS_VERSION for the identity files. The KnightHub
# admin password comes from the BuildKit secret at /run/secrets/admin_password.
set -euo pipefail

: "${TARGET:?}" "${DESKTOP:?}" "${HOST_VERSION:?}" "${THOXOS_VERSION:?}"
log() { echo "configure-host: $*"; }
fail() { echo "configure-host: $*" >&2; exit 1; }

case "$TARGET" in knighthub | azure) ;; *) fail "TARGET must be knighthub or azure" ;; esac
case "$DESKTOP" in headless | desktop) ;; *) fail "DESKTOP must be headless or desktop" ;; esac

enable_units() {
    local unit
    for unit in "$@"; do
        systemctl enable "$unit" >/dev/null 2>&1 || fail "cannot enable $unit"
        log "enabled $unit"
    done
}

require_enabled() {
    local unit state
    for unit in "$@"; do
        state="$(systemctl is-enabled "$unit" 2>/dev/null || true)"
        case "$state" in enabled | enabled-runtime | static | alias | indirect) ;;
        *) fail "$unit is not enabled (state: ${state:-missing})" ;; esac
    done
}

# ----------------------------------------------------------------- overlays
if [[ "$TARGET" == azure ]]; then cp -a /tmp/thoxos-overlay-azure/. /; fi
if [[ "$DESKTOP" == desktop ]]; then cp -a /tmp/thoxos-overlay-desktop/. /; fi
rm -rf /tmp/thoxos-overlay-azure /tmp/thoxos-overlay-desktop
chmod 0755 /usr/local/bin/thox /usr/local/bin/thoxos-ginux /usr/lib/thoxos-g/thox_ai_relay.py

# ---------------------------------------------------------------- initramfs
echo 'MODULES=most' >/etc/initramfs-tools/conf.d/thoxos-g-modules
if [[ "$TARGET" == azure ]]; then
    # Azure requires the Hyper-V storage and network drivers in the initrd.
    printf '%s\n' hv_vmbus hv_storvsc hv_netvsc hv_utils nvme nvme_core ext4 vfat >>/etc/initramfs-tools/modules
else
    printf '%s\n' uas usb_storage xhci_pci xhci_hcd nvme ext4 vfat >>/etc/initramfs-tools/modules
fi

# ------------------------------------------------------------------ desktop
if [[ "$DESKTOP" == desktop ]]; then
    install -m 0644 /etc/os-release.thoxos-desktop /etc/os-release.new
    rm -f /etc/os-release /etc/os-release.thoxos-desktop
    mv /etc/os-release.new /etc/os-release
    # Console and Azure serial console login banner (agetty: \n host, \l tty).
    printf 'ThoxOS Desktop on Debian 13 (Trixie), Ginux Edition \\n \\l\n\n' >/etc/issue
    plymouth-set-default-theme thoxos
    update-alternatives --set x-session-manager /usr/bin/xfce4-session >/dev/null
    dconf update
    # The generated launcher icons land after apt's triggers built the hicolor
    # cache; GTK trusts a cache over the directory, so rebuild it (and give
    # the derived folder themes their own) or every ThoxOS launcher shows a
    # generic icon.
    command -v gtk-update-icon-cache >/dev/null || fail "gtk-update-icon-cache missing"
    for theme in /usr/share/icons/hicolor /usr/share/icons/ThoxOS-Papirus-Dark /usr/share/icons/ThoxOS-Papirus-Light; do
        [[ -d "$theme" ]] && gtk-update-icon-cache -f -q "$theme"
    done
    grep -q thoxos-ginux /usr/share/icons/hicolor/icon-theme.cache || fail "launcher icons missing from the hicolor cache"
    xrdp_ini=/etc/xrdp/xrdp.ini
    # The login box stays light (Porcelain values): xrdp draws its labels with
    # the "black" color, so a dark box would hide them. The page behind it is
    # the dark ThoxOS wallpaper.
    sed -i \
        -e 's/^#\?ls_title=.*/ls_title=ThoxOS Desktop/' \
        -e 's|^#\?ls_logo_filename=.*|ls_logo_filename=/usr/share/xrdp/thoxos-logo.bmp|' \
        -e 's/^#\?ls_logo_transform=.*/ls_logo_transform=none/' \
        -e 's|^#\?ls_background_image=.*|ls_background_image=/usr/share/xrdp/thoxos-login-bg.bmp|' \
        -e 's/^#\?ls_background_transform=.*/ls_background_transform=scale/' \
        -e 's/^ls_top_window_bg_color=.*/ls_top_window_bg_color=09090B/' \
        -e 's/^ls_bg_color=.*/ls_bg_color=FAFAFA/' \
        -e 's/^blue=.*/blue=047C3D/' \
        -e 's/^grey=.*/grey=E4E4E7/' \
        -e 's/^dark_grey=.*/dark_grey=A1A1AA/' \
        "$xrdp_ini"
    for key in 'ls_title=ThoxOS Desktop' 'ls_logo_filename=/usr/share/xrdp/thoxos-logo.bmp' \
        'ls_background_image=/usr/share/xrdp/thoxos-login-bg.bmp' 'blue=047C3D'; do
        grep -qx "$key" "$xrdp_ini" || fail "xrdp login branding did not apply ($key)"
    done
    # Per-machine keys are generated on first boot (thoxos-desktop-firstboot).
    rm -f /etc/xrdp/rsakeys.ini
    enable_units lightdm.service xrdp.service thoxos-desktop-firstboot.service
    systemctl set-default graphical.target >/dev/null
else
    systemctl set-default multi-user.target >/dev/null
fi

kernel="$(find /lib/modules -mindepth 1 -maxdepth 1 -printf '%f\n' | sort -V | tail -1)"
[[ -n "$kernel" ]] || fail "no kernel installed"
if ! update-initramfs -c -k "$kernel" >/tmp/update-initramfs.log 2>&1; then
    update-initramfs -u -k "$kernel" >>/tmp/update-initramfs.log 2>&1 || { cat /tmp/update-initramfs.log >&2; fail "update-initramfs failed"; }
fi
[[ -s "/boot/initrd.img-$kernel" ]] || fail "no initrd for $kernel"
rm -f /tmp/update-initramfs.log
[[ -s /usr/lib/systemd/boot/efi/systemd-bootx64.efi ]] || fail "systemd-boot EFI binary missing"
if [[ "$TARGET" == azure ]]; then
    # List once into a file: grep -q on a pipe would SIGPIPE lsinitramfs and
    # trip pipefail even when the module is there.
    lsinitramfs "/boot/initrd.img-$kernel" >/tmp/initrd.list
    for module in hv_vmbus hv_storvsc hv_netvsc; do
        grep -q "/$module\.ko" /tmp/initrd.list || fail "$module missing from the initrd"
    done
    rm -f /tmp/initrd.list
    log "initrd carries hv_vmbus, hv_storvsc, hv_netvsc"
fi

# /etc/hostname, /etc/hosts and /etc/resolv.conf are bind mounts during a
# Docker build; installer/assemble-disk.sh writes them into the disk image.
sed -i 's/^# *en_US.UTF-8/en_US.UTF-8/' /etc/locale.gen
locale-gen >/dev/null

# ------------------------------------------------------------------- users
useradd --system --no-create-home --shell /usr/sbin/nologin thoxos-registry
useradd --create-home --shell /bin/bash --groups kvm thoxos
chown thoxos-registry:thoxos-registry /etc/thoxos-g/tls/registry.key
chmod 0600 /etc/thoxos-g/tls/registry.key
mkdir -p /var/lib/thoxos-g/state /boot/efi
chown thoxos:thoxos /var/lib/thoxos-g/state
chmod 0750 /var/lib/thoxos-g/state
chmod 0755 /usr/lib/thoxos-g/*.sh /etc/kernel/postinst.d/zz-thoxos-g-esp /etc/initramfs/post-update.d/zz-thoxos-g-esp
passwd -l root >/dev/null

if [[ "$TARGET" == azure ]]; then
    useradd --system --no-create-home --shell /usr/sbin/nologin thoxos-ai
    sed -i \
        -e 's/^Provisioning.Agent=.*/Provisioning.Agent=cloud-init/' \
        -e 's/^ResourceDisk.Format=.*/ResourceDisk.Format=n/' \
        -e 's/^ResourceDisk.EnableSwap=.*/ResourceDisk.EnableSwap=n/' \
        /etc/waagent.conf
    grep -q '^Provisioning.Agent=cloud-init' /etc/waagent.conf || echo 'Provisioning.Agent=cloud-init' >>/etc/waagent.conf
    # The image is generalized: no SSH host keys, no machine-id, no accounts
    # with a password. cloud-init creates the administrator at deployment.
    rm -f /etc/ssh/ssh_host_*
    agent_unit=""
    for candidate in walinuxagent.service waagent.service; do
        if [[ -f "/usr/lib/systemd/system/$candidate" ]]; then agent_unit="$candidate"; break; fi
    done
    [[ -n "$agent_unit" ]] || fail "Azure Linux Agent unit not found"
    enable_units systemd-networkd.service systemd-resolved.service chrony.service "$agent_unit" \
        ssh.service serial-getty@ttyS0.service thoxos-g-hostkeys.service thox-ai-relay.service
    # cloud-init enables its own stages on install; the unit names changed
    # across releases (cloud-init-network.service replaced cloud-init.service).
    require_enabled cloud-init-local.service cloud-config.service cloud-final.service
    if [[ -f /usr/lib/systemd/system/cloud-init-network.service ]]; then
        require_enabled cloud-init-network.service
    else
        require_enabled cloud-init.service
    fi
    if getent passwd thox >/dev/null; then fail "Azure images must not carry the thox login account"; fi
else
    admin_password=thoxos
    if [[ -s /run/secrets/admin_password ]]; then admin_password="$(head -n1 /run/secrets/admin_password)"; fi
    useradd --create-home --shell /bin/bash --groups sudo,kvm,adm,systemd-journal thox
    printf 'thox:%s\n' "$admin_password" | chpasswd
    chage -d 0 thox
    enable_units systemd-networkd.service systemd-resolved.service systemd-timesyncd.service
fi

enable_units thoxos-g-dns.service thoxos-g-registry.service thoxos-g-growroot.service
if [[ "$DESKTOP" == desktop ]]; then
    # Desktop users run their own Ginux VM from the dock; tty1 stays a login.
    systemctl disable thoxos-g-console.service >/dev/null 2>&1 || true
else
    enable_units thoxos-g-console.service
    systemctl mask getty@tty1.service >/dev/null
fi

# ----------------------------------------------------------------- identity
if [[ "$DESKTOP" != desktop ]]; then
    printf 'ThoxOS Ginux Edition host on Debian 13 (Trixie) \\n \\l\n\n' >/etc/issue
fi
: >/etc/machine-id
# The dbus package wrote its own machine ID during the build, and systemd
# initializes an empty /etc/machine-id from it at first boot: every machine
# made from the image would share one ID (and one DHCP DUID). Link it to
# /etc/machine-id as a fresh Debian install does.
rm -f /var/lib/dbus/machine-id
ln -s /etc/machine-id /var/lib/dbus/machine-id
[[ -L /var/lib/dbus/machine-id ]] || fail "D-Bus machine ID is not a link to /etc/machine-id"
rm -f /var/lib/systemd/random-seed
printf '%s\n' "$HOST_VERSION" >/usr/share/thoxos-g/HOST_VERSION
mkdir -p /usr/share/thoxos
printf '%s\n' "$HOST_VERSION" >/usr/share/thoxos/VERSION
printf 'target=%s\ndesktop=%s\nhost_version=%s\nguest_version=%s\n' \
    "$TARGET" "$DESKTOP" "$HOST_VERSION" "$THOXOS_VERSION" >/usr/share/thoxos-g/IMAGE_FLAVOR
(cd /usr/lib/thoxos-g && sha256sum -c GINUX.EFI.sha256 >/dev/null) || fail "GINUX.EFI checksum mismatch"
log "done: $TARGET $DESKTOP host $HOST_VERSION (guest $THOXOS_VERSION), kernel $kernel"
