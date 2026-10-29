# NOTICE

ThoxOS Ginux Edition
Copyright (c) 2026 THOX.ai LLC. All rights reserved.

## THOX.ai LLC intellectual property

THOX, THOX.ai, ThoxOS and "Your AI. Your Data. Your Rules." are trademarks of
THOX.ai LLC. The ThoxOS identity files, the `thox` command, the `thoxos-g`
launcher, the build, packaging and installer tooling, the documentation and the
patch series in this repository are works of THOX.ai LLC, licensed under the
Apache License, Version 2.0 (see LICENSE) so they combine cleanly with the
upstream Ginux kernel. The Apache License does not grant rights to THOX.ai LLC
trademarks (Section 6). Use of the marks requires written permission from
THOX.ai LLC.

## Upstream and third-party attributions

| Component | Origin | License | How it is used |
|---|---|---|---|
| Ginux kernel and controller | https://github.com/gmkurtzer/ginux at 36503bda2d87465765e1b94e65f9d100f27ed5be, Copyright 2026 Ginux contributors | Apache-2.0 | Fetched at build time and modified by `patches/0001` to `0003`; distributed as `GINUX.EFI` |
| Rocky Linux 10 UBI init image | docker.io/rockylinux/rockylinux:10-ubi-init (digest in `upstream.lock`), Rocky Enterprise Software Foundation | Per-package licenses inside the image | Base of the ThoxOS userspace image |
| Debian 13 "trixie" and trixie-backports | https://www.debian.org | Per-package licenses (DFSG and non-free-firmware) | Demo container base and KnightHub host root |
| QEMU 11.1 | https://www.qemu.org via Debian trixie-backports | GPL-2.0 and others | Runs Ginux with the validated hardware profile |
| OVMF (EDK II) | Debian `ovmf` package | BSD-2-Clause-Patent | UEFI firmware for the Ginux VM |
| CNCF Distribution registry v2 | docker.io/library/registry:2 (digest in `docker/Dockerfile`) | Apache-2.0 | Read-only local registry for the ThoxOS image |
| ttyd 1.7.7 | https://github.com/tsl0922/ttyd (binary SHA-256 pinned) | MIT | Browser console in the demo image |
| dnsmasq | Debian `dnsmasq-base` | GPL-2.0 or GPL-3.0 | DNS forwarder for the Ginux guest |
| systemd-boot | Debian `systemd-boot-efi` | LGPL-2.1-or-later | UEFI boot manager on the KnightHub SSD |
| Linux kernel | Debian `linux-image-amd64` | GPL-2.0 | KnightHub host kernel (hardware drivers, KVM) |
| skopeo | Debian `skopeo` | Apache-2.0 | Seeds the registry at build time (not shipped) |

The upstream Ginux NOTICE reads: "Ginux. Copyright 2026 Ginux contributors.
This product includes software developed by Ginux contributors."

Ginux is a research prototype. Its author states that no security audit has
been completed. ThoxOS Ginux Edition inherits that status.
