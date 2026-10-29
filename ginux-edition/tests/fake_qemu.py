#!/usr/bin/env python3
"""Test double for qemu-system-x86_64 used by tests/test_thoxos_g.py.

Answers the two capability queries thoxos-g makes, and otherwise emulates the
Ginux controller console on stdin/stdout closely enough to exercise the boot
driver: banner, prompt, `domain list`, `network set`, `domain new/set/start`.
Every received command is appended to $FAKE_QEMU_LOG so tests can assert the
exact sequence. $FAKE_EXISTING_DOMAIN pre-populates `domain list`.
$FAKE_REJECT makes the controller refuse commands that contain that text.
"""

import os
import sys

PROMPT = "ginux> "


def out(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


def main() -> int:
    args = sys.argv[1:]
    if args == ["--version"]:
        out("QEMU emulator version 11.1.2 (fake)\n")
        return 0
    if args == ["-device", "intel-iommu,help"]:
        out(os.environ.get("FAKE_IOMMU_HELP", "  aw-bits=<uint8>  -  (default: 48)\n"))
        return 0

    log_path = os.environ["FAKE_QEMU_LOG"]
    existing = os.environ.get("FAKE_EXISTING_DOMAIN", "")
    reject = os.environ.get("FAKE_REJECT", "")
    with open(log_path, "a", encoding="utf-8") as log:
        log.write("ARGV " + " ".join(args) + "\n")
    out("Ginux booted\r\nGinux controller v0 (ring 3)\r\n")
    out("ThoxOS Ginux Edition 0.1.0 | THOX.ai | research preview\r\n")
    out("Type 'help' for commands.\r\n" + PROMPT)
    for raw in sys.stdin:
        line = raw.strip()
        with open(log_path, "a", encoding="utf-8") as log:
            log.write("CMD " + line + "\n")
        out(line + "\r\n")  # the controller echoes input
        if reject and reject in line:
            out("domain: settings rejected\r\n" + PROMPT)
        elif line == "domain list":
            if existing:
                out("NAME            STATE       PERSONALITY  INIT        IMAGE\r\n")
                out(f"{existing:<16}configured  linux        /sbin/init  x\r\n")
            else:
                out("domains: 0 configured\r\n")
            out(PROMPT)
        elif line.startswith("network set eth0 dns "):
            out("eth0: DNS configured\r\n" + PROMPT)
        elif line.startswith("domain new "):
            out(f"{line.split()[2]}: created (image required)\r\n" + PROMPT)
        elif line.startswith("domain set "):
            out(f"{line.split()[2]}: settings accepted; configured\r\n" + PROMPT)
        elif line.startswith("domain start ") and line.split()[2].endswith("-shell"):
            out("\r\nThoxOS 0.1.0 Ginux Edition  (Rocky Linux 10 userspace on the Ginux kernel)\r\n")
            out("[root@ginux ~]# ")
        elif line.startswith("domain start ") and line.endswith("--attach"):
            out("\r\nWelcome to ThoxOS 0.1.0 Ginux Edition!\r\n")
            out("\r\nThoxOS 0.1.0 Ginux Edition  (Rocky Linux 10 userspace on the Ginux kernel)\r\n")
            out("ginux login: ")
        else:
            out("ginux: unknown command\r\n" + PROMPT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
