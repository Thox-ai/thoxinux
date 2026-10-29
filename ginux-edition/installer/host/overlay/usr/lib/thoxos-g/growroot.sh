#!/usr/bin/env bash
# ThoxOS Ginux Edition: grow the root partition and file system to fill the
# SSD once, on first boot. The flashed image is small; the SSD is not.
#
# Also moves the backup GPT header to the real end of the disk, which a raw
# image written to a larger device leaves in the middle.
set -euo pipefail

readonly marker=/var/lib/thoxos-g/.root-grown

log() {
    printf 'thoxos-g-growroot: %s\n' "$*"
}

root_source="$(findmnt -n -o SOURCE /)"
[[ -b "$root_source" ]] || { log "root $root_source is not a block device; nothing to do"; exit 0; }

disk="/dev/$(lsblk -n -o PKNAME "$root_source" | head -1)"
partition_number="$(cat "/sys/class/block/$(basename "$root_source")/partition")"
[[ -b "$disk" && "$partition_number" =~ ^[0-9]+$ ]] || {
    log "cannot identify the disk under $root_source"
    exit 1
}

# sfdisk relocates the backup GPT header when asked to rewrite the table.
if ! sfdisk --relocate gpt-bak-std "$disk" >/dev/null 2>&1; then
    log "backup GPT relocation not needed or not supported"
fi

output="$(growpart "$disk" "$partition_number" 2>&1)" || {
    if grep -q NOCHANGE <<<"$output"; then
        log "partition $partition_number already fills $disk"
    else
        log "growpart failed: $output"
        exit 1
    fi
}
resize2fs "$root_source"
touch "$marker"
log "root file system on $root_source now spans $(lsblk -n -o SIZE "$root_source" | head -1 | tr -d ' ')"
