#!/usr/bin/env bash
# Copyright (c) 2026 THOX.ai LLC. Licensed under the Apache License, Version 2.0.
# Boot-test the Azure VHD in QEMU with a NoCloud seed and capture the desktop
# over RDP (tests/e2e/azure/boot_azure_image.py inside thoxos-g/azure-bench:1).
#
# Usage: tests/e2e/boot-azure-image.sh build/azure/thoxos-ginux-azure-desktop-0.2.0.vhd OUT_DIR [GINUX_WAIT_S]
#   A VHD named *-headless-* runs the headless checks: console capture and a
#   systemd boot of ThoxOS on Ginux for the administrator.
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
vhd="${1:?VHD path}"
out="${2:?output directory}"
ginux_wait="${3:-0}"
[[ -s "$vhd" ]] || { echo "boot-azure-image: missing $vhd" >&2; exit 1; }
mkdir -p "$out"
out="$(cd "$out" && pwd)"
vhd_dir="$(cd "$(dirname "$vhd")" && pwd)"
mode=()
if [[ "$(basename "$vhd")" == *-headless-* ]]; then mode=(--headless); fi
docker build -q -t thoxos-g/azure-bench:1 "$repo_root/tests/e2e/azure" >/dev/null
docker run --rm -v "$vhd_dir:/in:ro" -v "$out:/out" -v "$repo_root/tests/e2e/azure:/bench:ro" \
    thoxos-g/azure-bench:1 python3 -I /bench/boot_azure_image.py \
    --vhd "/in/$(basename "$vhd")" --out /out --boot-timeout "${AZURE_BOOT_TIMEOUT:-2400}" --ginux-wait "$ginux_wait" "${mode[@]}"
