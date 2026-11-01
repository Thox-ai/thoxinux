#!/usr/bin/env python3
"""Boot the KnightHub SSD image in QEMU as a USB disk and check the host path.

Simulates the KnightHub boot: UEFI (OVMF) firmware, the image attached as a
USB mass-storage device behind an xHCI controller, an Intel e1000e NIC. The
test copy carries one extra kernel argument (console=ttyS0) so systemd's
progress is observable on the serial port; the shipped image is unchanged.

The outer VM exposes no SVM/VMX, so the host's thoxos-g runs Ginux with TCG
(KnightHub itself uses KVM).

Checks, in order, against the serial log:
  1. systemd-boot hands off to the host kernel (kernel banner)
  2. the root file system on the USB disk mounts (systemd reaches basic.target)
  3. thoxos-g-growroot grows the root partition to the larger test disk
  4. thoxos-g-registry and thoxos-g-dns start
  5. thoxos-g-console starts on tty1
Then it captures tty1 (VGA) to PNG for the documentation.

Usage (inside the demo image, which has QEMU 11 and OVMF):
  python3 -I boot_ssd_image.py DISK_IMAGE OUT_DIR [TIMEOUT_SECONDS]
"""

from __future__ import annotations

import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import time
import zlib

MARKERS = [
    ("kernel", b"Linux version"),
    ("root mounted", b"Reached target basic.target"),
    ("growroot", b"thoxos-g-growroot: root file system on"),
    ("registry", b"Started thoxos-g-registry.service"),
    ("dns", b"Started thoxos-g-dns.service"),
    ("console", b"Started thoxos-g-console.service"),
]


ANSI = re.compile(rb"\x1b\[[0-9;?]*[A-Za-z]")


def serial_text(path: str) -> bytes:
    """Serial output with SGR colour codes removed (systemd colours unit names)."""
    try:
        with open(path, "rb") as handle:
            return ANSI.sub(b"", handle.read())
    except FileNotFoundError:
        return b""


def ppm_to_png(ppm_path: str, png_path: str) -> None:
    """Convert a binary P6 PPM (QEMU screendump) to PNG with the stdlib only."""
    with open(ppm_path, "rb") as handle:
        data = handle.read()
    parts = data.split(b"\n", 3)
    if parts[0] != b"P6":
        raise ValueError("not a P6 PPM")
    width, height = (int(v) for v in parts[1].split())
    pixels = parts[3]
    rows = b"".join(
        b"\x00" + pixels[y * width * 3:(y + 1) * width * 3] for y in range(height)
    )

    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(
            ">I", zlib.crc32(kind + body) & 0xFFFFFFFF
        )

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(rows, 9))
    png += chunk(b"IEND", b"")
    with open(png_path, "wb") as handle:
        handle.write(png)


def monitor_command(path: str, command: str) -> None:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as monitor:
        monitor.connect(path)
        monitor.settimeout(10)
        monitor.recv(4096)  # banner
        monitor.sendall(command.encode() + b"\n")
        time.sleep(2)
        monitor.recv(4096)


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    disk, out = sys.argv[1], sys.argv[2]
    timeout = float(sys.argv[3]) if len(sys.argv) > 3 else 1800
    os.makedirs(out, exist_ok=True)
    serial_log = os.path.join(out, "ssd-serial.log")
    monitor_path = os.path.join(out, "monitor.sock")
    variables = os.path.join(out, "ovmf-vars.fd")
    shutil.copyfile("/usr/share/OVMF/OVMF_VARS_4M.fd", variables)
    for stale in (serial_log, monitor_path):
        if os.path.exists(stale):
            os.remove(stale)

    argv = [
        "qemu-system-x86_64",
        "-machine", "q35,accel=tcg",
        # No nested virtualization: QEMU 11.1 TCG asserts (bql_locked) when the
        # guest starts KVM on emulated SVM. Inside, thoxos-g falls back to TCG.
        "-cpu", "max,-svm,-vmx",
        "-smp", "2",
        "-m", "4G",
        "-drive", "if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd",
        "-drive", f"if=pflash,format=raw,file={variables}",
        "-device", "qemu-xhci,id=xhci",
        "-drive", f"if=none,id=ssd,format=raw,file={disk}",
        "-device", "usb-storage,bus=xhci.0,drive=ssd,bootindex=1",
        "-netdev", "user,id=lan",
        "-device", "e1000e,netdev=lan",
        "-vga", "std",
        "-display", "none",
        "-serial", f"file:{serial_log}",
        "-monitor", f"unix:{monitor_path},server,nowait",
        "-no-reboot",
    ]
    qemu = subprocess.Popen(argv)
    deadline = time.monotonic() + timeout
    reached: list[str] = []
    try:
        for label, marker in MARKERS:
            while True:
                if qemu.poll() is not None:
                    print(f"ssd-boot: QEMU exited before '{label}'", file=sys.stderr)
                    return 1
                text = serial_text(serial_log)
                if b"Failed to start thoxos-g" in text:
                    print("ssd-boot: FAIL a thoxos-g service failed to start", file=sys.stderr)
                    return 1
                if marker in text:
                    reached.append(label)
                    print(f"ssd-boot: ok  {label}", file=sys.stderr)
                    break
                if time.monotonic() > deadline:
                    print(f"ssd-boot: FAIL timed out waiting for '{label}'", file=sys.stderr)
                    return 1
                time.sleep(2)
        # Give the console service time to draw the Ginux boot on tty1.
        time.sleep(float(os.environ.get("SSD_SCREENSHOT_DELAY", "90")))
        ppm = os.path.join(out, "ssd-tty1.ppm")
        monitor_command(monitor_path, f"screendump {ppm}")
        for _ in range(10):
            if os.path.exists(ppm) and os.path.getsize(ppm) > 0:
                break
            time.sleep(1)
        ppm_to_png(ppm, os.path.join(out, "ssd-tty1.png"))
        os.remove(ppm)
        print("ssd-boot: all checks passed; tty1 captured", file=sys.stderr)
        return 0
    finally:
        qemu.terminate()
        try:
            qemu.wait(timeout=20)
        except subprocess.TimeoutExpired:
            qemu.kill()


if __name__ == "__main__":
    sys.exit(main())
