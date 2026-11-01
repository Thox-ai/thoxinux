#!/usr/bin/env bash
# Copyright (c) 2026 THOX.ai LLC. Licensed under the Apache License, Version 2.0.
# ThoxOS Ginux Edition: convert a raw host image into an Azure-ready VHD.
#
# Azure accepts only fixed-size VHDs whose virtual size is a whole number of
# MiB (VHDX and dynamic VHDs are rejected). The raw image from
# installer/assemble-disk.sh is already MiB-aligned; this converts it with
# qemu-img (subformat=fixed,force_size keeps the exact size) and verifies the
# footer, the size and the checksum with vhd_check.py before writing .sha256.
#
# Usage: build-vhd.sh RAW_IMAGE OUT_VHD
set -euo pipefail

fail() {
    echo "build-vhd: $*" >&2
    exit 1
}

[[ $# -eq 2 ]] || fail "usage: $0 RAW_IMAGE OUT_VHD"
raw="$1"
vhd="$2"
[[ -s "$raw" ]] || fail "missing $raw"
command -v qemu-img >/dev/null 2>&1 || fail "qemu-img is required (qemu-utils)"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
checker="$here/vhd_check.py"
[[ -f "$checker" ]] || fail "missing $checker"

size=$(stat -c %s "$raw")
mib=$((1024 * 1024))
((size % mib == 0)) || fail "raw size $size is not a whole number of MiB"
((size <= 1023 * 1024 * mib)) || fail "raw size exceeds Azure's 1023 GiB OS disk limit"

rm -f "$vhd"
qemu-img convert -f raw -O vpc -o subformat=fixed,force_size "$raw" "$vhd"
python3 "$checker" "$vhd" --expect-size "$size"
(cd "$(dirname "$vhd")" && sha256sum "$(basename "$vhd")" >"$(basename "$vhd").sha256")
echo "build-vhd: $vhd ready ($((size / mib)) MiB virtual, $(du -h "$vhd" | cut -f1) on disk)"
