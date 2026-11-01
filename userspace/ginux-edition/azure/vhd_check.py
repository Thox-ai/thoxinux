#!/usr/bin/env python3
# Copyright (c) 2026 THOX.ai LLC. Licensed under the Apache License, Version 2.0.
"""vhd_check: verify a VHD meets Azure's upload rules before it leaves the build.

Azure takes fixed VHDs only, with a virtual size that is a whole number of MiB
and at most 1023 GiB. A fixed VHD is the raw disk followed by a 512-byte
footer; this reads that footer and checks the cookie, the disk type, the data
offset, the sizes, the file length and the footer checksum.

Usage: vhd_check.py IMAGE.vhd [--expect-size BYTES]
Exit code 0 when every check passes; 1 with the failed checks otherwise.
"""

from __future__ import annotations

import argparse
import os
import struct
import sys
from dataclasses import dataclass
from typing import Optional, Sequence

FOOTER_SIZE = 512
MIB = 1024 * 1024
MAX_BYTES = 1023 * 1024 * MIB
DISK_TYPE_FIXED = 2


@dataclass(frozen=True)
class Footer:
    cookie: bytes
    features: int
    version: int
    data_offset: int
    creator_app: bytes
    original_size: int
    current_size: int
    cylinders: int
    heads: int
    sectors: int
    disk_type: int
    checksum: int
    computed_checksum: int


def footer_checksum(raw: bytes) -> int:
    """One's complement of the byte sum with the checksum field (64..67) as zero."""
    total = sum(raw[:64]) + sum(raw[68:])
    return (~total) & 0xFFFFFFFF


def parse_footer(raw: bytes) -> Footer:
    if len(raw) != FOOTER_SIZE:
        raise ValueError(f"footer must be {FOOTER_SIZE} bytes, got {len(raw)}")
    (cookie, features, version, data_offset, _timestamp, creator_app, _creator_version, _creator_os,
     original_size, current_size, cylinders, heads, sectors, disk_type, checksum) = struct.unpack(
        ">8sIIQI4sII QQ HBB II".replace(" ", ""), raw[:68])
    return Footer(cookie, features, version, data_offset, creator_app, original_size, current_size,
                  cylinders, heads, sectors, disk_type, checksum, footer_checksum(raw))


def check(path: str, expect_size: Optional[int] = None) -> list[str]:
    """Return the list of failed checks (empty when the VHD is acceptable)."""
    problems: list[str] = []
    try:
        length = os.path.getsize(path)
        with open(path, "rb") as handle:
            if length < FOOTER_SIZE:
                return [f"{path} is shorter than a VHD footer"]
            handle.seek(length - FOOTER_SIZE)
            footer = parse_footer(handle.read(FOOTER_SIZE))
    except OSError as error:
        return [f"cannot read {path}: {error.strerror}"]
    if footer.cookie != b"conectix":
        problems.append(f"footer cookie is {footer.cookie!r}, expected b'conectix'")
    if footer.disk_type != DISK_TYPE_FIXED:
        problems.append(f"disk type {footer.disk_type} is not fixed (2); Azure rejects dynamic VHDs")
    if footer.data_offset != 0xFFFFFFFFFFFFFFFF:
        problems.append("data offset is set; a fixed VHD has none")
    if footer.checksum != footer.computed_checksum:
        problems.append(f"footer checksum {footer.checksum:#010x} != computed {footer.computed_checksum:#010x}")
    if footer.current_size % MIB:
        problems.append(f"virtual size {footer.current_size} is not a whole number of MiB")
    if footer.current_size > MAX_BYTES:
        problems.append("virtual size exceeds 1023 GiB")
    if length != footer.current_size + FOOTER_SIZE:
        problems.append(f"file length {length} != virtual size {footer.current_size} + {FOOTER_SIZE}")
    if expect_size is not None and footer.current_size != expect_size:
        problems.append(f"virtual size {footer.current_size} != expected {expect_size}")
    return problems


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Check a VHD against Azure's upload rules")
    parser.add_argument("vhd")
    parser.add_argument("--expect-size", type=int, default=None)
    args = parser.parse_args(argv)
    problems = check(args.vhd, args.expect_size)
    if problems:
        for problem in problems:
            print(f"vhd_check: FAIL {problem}", file=sys.stderr)
        return 1
    size = os.path.getsize(args.vhd) - FOOTER_SIZE
    print(f"vhd_check: ok {args.vhd}: fixed VHD, {size // MIB} MiB, footer checksum valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
