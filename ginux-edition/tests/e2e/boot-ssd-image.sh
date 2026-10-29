#!/usr/bin/env bash
# Boot-test the KnightHub SSD image in QEMU (USB disk, OVMF, e1000e NIC).
#
# Makes a sparse 12G copy (so first-boot root growth is exercised). On that
# copy's boot entry only, it adds console=ttyS0, visible systemd status, journal
# forwarding to the console and no serial getty, then runs
# tests/e2e/boot_ssd_image.py inside the demo image.
#
# Usage: tests/e2e/boot-ssd-image.sh build/ssd/thoxos-ginux-knighthub-0.1.0.img OUT_DIR
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
image="${1:?image path}"
out="${2:?output directory}"
version="$(cat "$repo_root/VERSION")"
mkdir -p "$out"
out="$(cd "$out" && pwd)"
test_disk="$out/ssd-test.img"

cp --sparse=always "$image" "$test_disk"
truncate -s 12G "$test_disk"

docker run --rm -v "$out:/out" thoxos-g/disk-tools:1 bash -euc '
    export MTOOLS_SKIP_CHECK=1
    mcopy -i /out/ssd-test.img@@1M ::/loader/entries/thoxos-g.conf /tmp/entry.conf
    sed -i "s/ quiet loglevel=3 / systemd.show_status=1 systemd.journald.forward_to_console=1 systemd.mask=serial-getty@ttyS0.service /; s/console=tty1/console=tty1 console=ttyS0,115200/" /tmp/entry.conf
    mcopy -o -i /out/ssd-test.img@@1M /tmp/entry.conf ::/loader/entries/thoxos-g.conf
    cat /tmp/entry.conf'

docker run --rm --entrypoint python3 \
    -v "$out:/out" -v "$repo_root/tests/e2e:/e2e:ro" \
    "thoxos-g/demo:$version" -I /e2e/boot_ssd_image.py /out/ssd-test.img /out "${SSD_BOOT_TIMEOUT:-2400}"
