#!/bin/bash
# Copyright (c) 2026 THOX.ai LLC. Licensed under the Apache License, Version 2.0.
# ThoxOS Desktop first boot. The image is built once and booted on many
# machines, so key material created at package install time is replaced here:
# the snakeoil TLS certificate xrdp presents, and xrdp's RSA key pair.
set -euo pipefail
marker=/var/lib/thoxos-desktop/firstboot.done
mkdir -p "$(dirname "$marker")"
if command -v make-ssl-cert >/dev/null 2>&1; then
    make-ssl-cert generate-default-snakeoil --force-overwrite
fi
if command -v xrdp-keygen >/dev/null 2>&1; then
    xrdp-keygen xrdp /etc/xrdp/rsakeys.ini >/dev/null
    chmod 0600 /etc/xrdp/rsakeys.ini
fi
# xrdp reads the snakeoil key through the ssl-cert group.
if getent group ssl-cert >/dev/null && id xrdp >/dev/null 2>&1; then
    usermod -aG ssl-cert xrdp
fi
date -u +%FT%TZ >"$marker"
echo "thoxos-desktop-firstboot: RDP keys and TLS certificate generated"
