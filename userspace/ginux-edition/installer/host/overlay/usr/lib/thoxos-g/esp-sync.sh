#!/usr/bin/env bash
# ThoxOS Ginux Edition: copy the newest host kernel and initrd to the ESP.
#
# systemd-boot reads /thoxos/vmlinuz and /thoxos/initrd.img from the EFI system
# partition. Debian installs kernels into /boot, so this runs from the kernel
# postinst and initramfs post-update hooks after every kernel or initrd change.
# A missing or unmounted ESP is reported and skipped, never guessed.
set -euo pipefail

readonly esp=/boot/efi
readonly target="$esp/thoxos"

log() {
    printf 'thoxos-g-esp-sync: %s\n' "$*" >&2
}

if ! mountpoint -q "$esp"; then
    log "$esp is not mounted; kernel not copied to the ESP"
    exit 0
fi

kernel_version="$(find /boot -maxdepth 1 -name 'vmlinuz-*' -printf '%f\n' | sed 's/^vmlinuz-//' | sort -V | tail -1)"
if [[ -z "$kernel_version" ]]; then
    log "no kernel in /boot"
    exit 1
fi
initrd="/boot/initrd.img-$kernel_version"
if [[ ! -s "$initrd" ]]; then
    log "initrd for $kernel_version not built yet; the initramfs hook will copy it"
    exit 0
fi

mkdir -p "$target"
# Write to temporary names first so a power loss never leaves a half kernel.
install -m 0644 "/boot/vmlinuz-$kernel_version" "$target/vmlinuz.new"
install -m 0644 "$initrd" "$target/initrd.img.new"
sync
mv -f "$target/vmlinuz.new" "$target/vmlinuz"
mv -f "$target/initrd.img.new" "$target/initrd.img"
sync
log "ESP now boots kernel $kernel_version"
