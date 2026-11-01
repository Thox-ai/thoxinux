#!/usr/bin/env bash
# ThoxOS Ginux Edition: write the KnightHub disk image to an external SSD (Linux).
#
# This ERASES the target device. Guards, all enforced before a byte is written:
#   * target must be a whole-disk block device, not a partition
#   * target must not hold any mounted file system, swap, or the running root
#   * target must be USB/removable unless --allow-internal is given
#   * target must be at least as large as the image
#   * a disk already carrying a THOXOS file-system label (the ThoxOS Vibe SSD)
#     needs --erase-existing-thoxos as well
#   * the operator types the device name back (or passes --confirm NAME)
# After writing, the image checksum is verified against the device read-back.
#
# Usage:
#   sudo installer/install-to-ssd.sh --image build/ssd/thoxos-ginux-knighthub-0.1.0.img \
#        --device /dev/sdX [--confirm sdX] [--allow-internal] [--erase-existing-thoxos]
#        [--skip-verify]
#   The image may be .img or .img.xz.
set -euo pipefail

image=""
device=""
confirm=""
allow_internal=0
erase_thoxos=0
verify=1

fail() {
    echo "install-to-ssd: $*" >&2
    exit 1
}

while (($#)); do
    case "$1" in
    --image) image="${2:?}"; shift 2 ;;
    --device) device="${2:?}"; shift 2 ;;
    --confirm) confirm="${2:?}"; shift 2 ;;
    --allow-internal) allow_internal=1; shift ;;
    --erase-existing-thoxos) erase_thoxos=1; shift ;;
    --skip-verify) verify=0; shift ;;
    -h | --help) sed -n '2,22p' "$0"; exit 0 ;;
    *) fail "unknown argument: $1" ;;
    esac
done

[[ $EUID -eq 0 ]] || fail "run as root (sudo)"
[[ -n "$image" && -n "$device" ]] || fail "--image and --device are required"
[[ -f "$image" ]] || fail "image not found: $image"
for tool in lsblk blkid findmnt blockdev dd sha256sum sfdisk partprobe; do
    command -v "$tool" >/dev/null 2>&1 || fail "missing tool: $tool"
done

device="$(readlink -f "$device")"
[[ -b "$device" ]] || fail "$device is not a block device"
name="$(basename "$device")"
device_type="$(lsblk -dn -o TYPE "$device" | tr -d ' ')"
# Loop devices are accepted only with --allow-internal (rehearsals on an image file).
if [[ "$device_type" != "disk" ]] && ! [[ "$device_type" == "loop" && $allow_internal -eq 1 ]]; then
    fail "$device is a $device_type, not a whole disk (pass /dev/sdX, not a partition)"
fi

# Never the disk that holds the running system.
root_disk="$(lsblk -n -o PKNAME "$(findmnt -n -o SOURCE /)" 2>/dev/null | head -1 || true)"
[[ "$name" != "$root_disk" ]] || fail "$device holds the running root file system"
if lsblk -n -o MOUNTPOINTS "$device" | grep -q '[^[:space:]]'; then
    fail "$device has mounted file systems; unmount them first:
$(lsblk -o NAME,MOUNTPOINTS "$device")"
fi
if grep -q "^/dev/$name" /proc/swaps; then
    fail "$device is in use as swap"
fi

transport="$(lsblk -dn -o TRAN "$device" | tr -d ' ')"
removable="$(lsblk -dn -o RM "$device" | tr -d ' ')"
if [[ "$transport" != "usb" && "$removable" != "1" && $allow_internal -eq 0 ]]; then
    fail "$device is not a USB/removable disk (transport '$transport'); pass --allow-internal if you are certain"
fi

# Probe labels directly (blkid -p): lsblk reads them from udev, which can be
# stale or absent, and this guard must never fail open.
device_labels() {
    local part
    blkid -p -o value -s LABEL "$device" 2>/dev/null || true
    while read -r part; do
        blkid -p -o value -s LABEL "/dev/$part" 2>/dev/null || true
    done < <(lsblk -ln -o NAME "$device" | tail -n +2)
}
if device_labels | grep -qx 'THOXOS'; then
    ((erase_thoxos)) || fail "$device carries a THOXOS label (the ThoxOS Vibe SSD). Pass --erase-existing-thoxos to replace it"
fi

case "$image" in
*.xz)
    command -v xz >/dev/null 2>&1 || fail "xz is required for .xz images"
    image_bytes="$(xz --robot --list "$image" | awk '$1 == "totals" {print $5}')"
    reader=(xz -dc "$image")
    ;;
*)
    image_bytes="$(stat -c '%s' "$image")"
    reader=(cat "$image")
    ;;
esac
[[ "$image_bytes" =~ ^[0-9]+$ && "$image_bytes" -gt 0 ]] || fail "cannot determine the image size"
device_bytes="$(blockdev --getsize64 "$device")"
((device_bytes >= image_bytes)) || fail "$device ($device_bytes bytes) is smaller than the image ($image_bytes bytes)"

echo "Target:"
lsblk -d -o NAME,MODEL,SERIAL,SIZE,TRAN,RM "$device"
lsblk -o NAME,LABEL,FSTYPE,SIZE "$device" | tail -n +2 || true
echo
echo "Image:  $image ($((image_bytes / 1024 / 1024)) MiB)"
echo "Everything on $device will be destroyed."
if [[ -z "$confirm" ]]; then
    read -r -p "Type the device name ($name) to continue: " confirm
fi
[[ "$confirm" == "$name" ]] || fail "confirmation '$confirm' does not match '$name'; nothing was written"

# Clear old signatures so stale RAID/LVM metadata cannot confuse the new disk.
if command -v wipefs >/dev/null 2>&1; then
    wipefs --all --force "$device" >/dev/null
fi

echo "Writing..."
"${reader[@]}" | dd of="$device" bs=4M iflag=fullblock oflag=direct conv=fsync status=progress
sync

# The image's backup GPT sits at the image end; move it to the device end.
sfdisk --relocate gpt-bak-std "$device" >/dev/null 2>&1 || true
partprobe "$device" 2>/dev/null || true

# SHA-256 of the partition region [1 MiB, image end - 1 MiB) read from a
# command's stdout. dd stops after exactly that many blocks; the producer may
# then get SIGPIPE, which is expected and not an error, so pipefail is off here.
region_sha() {
    local blocks=$((image_bytes / 1048576 - 2))
    (
        set +o pipefail
        "$@" | dd bs=1M skip=1 count="$blocks" iflag=fullblock status=none | sha256sum | cut -d' ' -f1
    )
}

if ((verify)); then
    echo "Verifying..."
    # The GPT headers outside the region were rewritten on purpose when the
    # backup header moved to the end of the disk.
    expected="$(region_sha "${reader[@]}")"
    actual="$(region_sha cat "$device")"
    [[ -n "$expected" && "$expected" == "$actual" ]] || fail "verification failed: device contents differ from the image"
    echo "Partitions verified ($expected)."
fi

echo
echo "Done. On KnightHub: disable Secure Boot, plug in the SSD, press the boot-menu key"
echo "(F11 or F12 on most desktop boards), and choose the UEFI entry for this SSD."
echo "First boot grows the root partition to fill the SSD. Console: tty1. Admin: tty2, user thox."
