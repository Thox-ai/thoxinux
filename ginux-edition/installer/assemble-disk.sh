#!/usr/bin/env bash
# ThoxOS Ginux Edition: assemble the KnightHub external-SSD disk image.
#
# Runs as root inside the disk-tools container (no loop devices, no mounts):
# the root file system is created with `mkfs.ext4 -d` from an exported host
# root tree, the ESP with mtools, and both are placed into a GPT image.
#
# Usage: assemble-disk.sh ROOTFS_TAR OUT_DIR SIZE VERSION
#   SIZE accepts G or M suffixes (minimum 6G). The first boot grows the root
#   partition to fill the SSD, so a small image works on any larger drive.
# Outputs (OUT_DIR): thoxos-ginux-knighthub-VERSION.img, .img.sha256, manifest.json
set -euo pipefail

fail() {
    echo "assemble-disk: $*" >&2
    exit 1
}

[[ $# -eq 4 ]] || fail "usage: $0 ROOTFS_TAR OUT_DIR SIZE VERSION"
rootfs_tar="$1"
out="$2"
size="$3"
version="$4"
[[ -s "$rootfs_tar" ]] || fail "missing $rootfs_tar"
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail "version must be semver, got $version"
for tool in mkfs.ext4 mkfs.vfat mmd mcopy sfdisk uuidgen tar sha256sum; do
    command -v "$tool" >/dev/null 2>&1 || fail "missing tool: $tool"
done

case "$size" in
*G) size_mib=$((${size%G} * 1024)) ;;
*M) size_mib=${size%M} ;;
*) fail "size must end in G or M, got $size" ;;
esac
((size_mib >= 6144)) || fail "image size must be at least 6G"

readonly esp_mib=512
readonly esp_start_mib=1
readonly root_start_mib=$((esp_start_mib + esp_mib))
# Leave 1 MiB at the end for the backup GPT.
readonly root_mib=$((size_mib - root_start_mib - 1))

work="$(mktemp -d /tmp/thoxos-disk.XXXXXX)"
trap 'rm -rf "$work"' EXIT
root="$work/root"
mkdir -p "$root" "$out"

echo "assemble-disk: unpacking host root"
tar --numeric-owner -xpf "$rootfs_tar" -C "$root"
rm -f "$root/.dockerenv"

kernel_version="$(find "$root/boot" -maxdepth 1 -name 'vmlinuz-*' -printf '%f\n' | sed 's/^vmlinuz-//' | sort -V | tail -1)"
[[ -n "$kernel_version" ]] || fail "no kernel in the host root"
[[ -s "$root/boot/initrd.img-$kernel_version" ]] || fail "no initrd for $kernel_version"
systemd_boot="$root/usr/lib/systemd/boot/efi/systemd-bootx64.efi"
[[ -s "$systemd_boot" ]] || fail "systemd-boot EFI binary missing from the host root"
ginux_efi="$root/usr/lib/thoxos-g/GINUX.EFI"
[[ -s "$ginux_efi" ]] || fail "GINUX.EFI missing from the host root"

esp_partuuid="$(uuidgen)"
root_partuuid="$(uuidgen)"
root_fs_uuid="$(uuidgen)"
esp_volume_id="$(od -An -N4 -tx4 /dev/urandom | tr -d ' ' | tr 'a-f' 'A-F')"

# Identity files Docker manages at run time are rewritten for a real machine.
rm -f "$root/etc/hostname" "$root/etc/hosts" "$root/etc/resolv.conf"
echo "thoxos-knighthub" >"$root/etc/hostname"
printf '127.0.0.1\tlocalhost\n127.0.1.1\tthoxos-knighthub\n::1\tlocalhost ip6-localhost ip6-loopback\n' >"$root/etc/hosts"
ln -s ../run/systemd/resolve/stub-resolv.conf "$root/etc/resolv.conf"
: >"$root/etc/machine-id"
cat >"$root/etc/fstab" <<EOF
# ThoxOS Ginux Edition KnightHub SSD
PARTUUID=$root_partuuid  /          ext4  defaults,noatime,errors=remount-ro  0 1
PARTUUID=$esp_partuuid   /boot/efi  vfat  umask=0077,nofail                   0 2
EOF

echo "assemble-disk: building the EFI system partition"
esp_img="$work/esp.img"
mkfs.vfat -F 32 -n THOXOS-ESP -i "$esp_volume_id" -C "$esp_img" $((esp_mib * 1024)) >/dev/null
export MTOOLS_SKIP_CHECK=1
mmd -i "$esp_img" ::/EFI ::/EFI/BOOT ::/EFI/systemd ::/loader ::/loader/entries ::/thoxos
mcopy -i "$esp_img" "$systemd_boot" ::/EFI/BOOT/BOOTX64.EFI
mcopy -i "$esp_img" "$systemd_boot" ::/EFI/systemd/systemd-bootx64.efi
mcopy -i "$esp_img" "$root/boot/vmlinuz-$kernel_version" ::/thoxos/vmlinuz
mcopy -i "$esp_img" "$root/boot/initrd.img-$kernel_version" ::/thoxos/initrd.img
mcopy -i "$esp_img" "$ginux_efi" ::/thoxos/GINUX.EFI
cat >"$work/loader.conf" <<'EOF'
default thoxos-g.conf
timeout 5
console-mode keep
editor no
EOF
cat >"$work/thoxos-g.conf" <<EOF
title    ThoxOS Ginux Edition $version (KnightHub host, Ginux under KVM)
linux    /thoxos/vmlinuz
initrd   /thoxos/initrd.img
options  root=PARTUUID=$root_partuuid rw quiet loglevel=3 module_blacklist=nouveau console=tty1
EOF
cat >"$work/ginux-baremetal.conf" <<'EOF'
title    Ginux bare-metal probe (experimental: no NVMe, USB or physical NIC drivers; expected to stop)
efi      /thoxos/GINUX.EFI
EOF
mcopy -i "$esp_img" "$work/loader.conf" ::/loader/loader.conf
mcopy -i "$esp_img" "$work/thoxos-g.conf" ::/loader/entries/thoxos-g.conf
mcopy -i "$esp_img" "$work/ginux-baremetal.conf" ::/loader/entries/ginux-baremetal.conf

echo "assemble-disk: building the ${root_mib} MiB root file system"
root_img="$work/root.img"
mkfs.ext4 -q -F -L THOXOS-G-ROOT -U "$root_fs_uuid" -d "$root" "$root_img" "${root_mib}M"

name="thoxos-ginux-knighthub-$version.img"
disk="$out/$name"
rm -f "$disk"
truncate -s "${size_mib}M" "$disk"
sfdisk --quiet "$disk" <<EOF
label: gpt
unit: sectors
first-lba: 2048
start=$((esp_start_mib * 2048)), size=$((esp_mib * 2048)), type=C12A7328-F81F-11D2-BA4B-00A0C93EC93B, uuid=$esp_partuuid, name="THOXOS-ESP"
start=$((root_start_mib * 2048)), size=$((root_mib * 2048)), type=4F68BCE3-E8CD-4DB1-96E7-FBCAF984B709, uuid=$root_partuuid, name="THOXOS-G-ROOT"
EOF
dd if="$esp_img" of="$disk" bs=1M seek="$esp_start_mib" conv=notrunc,sparse status=none
dd if="$root_img" of="$disk" bs=1M seek="$root_start_mib" conv=notrunc,sparse status=none

(cd "$out" && sha256sum "$name" >"$name.sha256")
ginux_sha="$(sha256sum "$ginux_efi" | cut -d' ' -f1)"
cat >"$out/manifest.json" <<EOF
{
  "product": "ThoxOS Ginux Edition",
  "target": "KnightHub external SSD",
  "version": "$version",
  "image": "$name",
  "image_sha256": "$(cut -d' ' -f1 "$out/$name.sha256")",
  "size_mib": $size_mib,
  "host_kernel": "$kernel_version",
  "ginux_efi_sha256": "$ginux_sha",
  "esp_partuuid": "$esp_partuuid",
  "root_partuuid": "$root_partuuid",
  "root_fs_uuid": "$root_fs_uuid",
  "secure_boot": "unsupported (unsigned systemd-boot); disable Secure Boot in firmware setup"
}
EOF
echo "assemble-disk: $out/$name ready ($(du -h --apparent-size "$disk" | cut -f1) apparent, $(du -h "$disk" | cut -f1) on disk)"
