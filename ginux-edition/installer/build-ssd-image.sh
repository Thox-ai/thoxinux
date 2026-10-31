#!/usr/bin/env bash
# Copyright (c) 2026 THOX.ai LLC. Licensed under the Apache License, Version 2.0.
# ThoxOS Ginux Edition: build the KnightHub external-SSD disk image.
#
# Kept for the 0.1.0 command line. It calls installer/build-host-image.sh with
# --target knighthub; pass --desktop desktop for the ThoxOS Desktop variant.
#
# Usage:
#   installer/build-ssd-image.sh --demo-image thoxos-g/demo:0.1.0 \
#       --host-image thoxos-g/knighthub-host:0.2.0 --size 8G --out build/ssd \
#       [--desktop headless|desktop] [--admin-password-file FILE] [--extra-ca CA.pem] [--xz]
#
# Write the result to the SSD with installer/install-to-ssd.sh (Linux),
# installer/Install-ThoxOSGinux.ps1 (Windows), or Rufus/balenaEtcher (DD mode).
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$here/build-host-image.sh" --target knighthub "$@"
