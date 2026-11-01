#!/usr/bin/env python3
"""Install the verified Ginux VM kit as ordinary files on a Linux host."""
import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import preflight

REQUIRED = {"GINUX.EFI", "build-receipt.json", "GINUX_LICENSE", "GINUX_NOTICE"}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_kit(kit, receipt_hash):
    if not re.fullmatch(r"[0-9a-fA-F]{64}", receipt_hash):
        raise ValueError("Expected receipt SHA-256 must be exactly 64 hexadecimal characters")
    artifact_dir = kit / "artifacts"
    if not artifact_dir.is_dir() or artifact_dir.is_symlink():
        raise ValueError("Missing ordinary artifacts directory")
    files = REQUIRED | {"SHA256SUMS"}
    for name in files:
        path = artifact_dir / name
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Missing or non-regular artifact: {name}")
    receipt = artifact_dir / "build-receipt.json"
    if sha256(receipt) != receipt_hash.lower():
        raise ValueError("Build receipt digest mismatch")
    receipt_data = json.loads(receipt.read_text())
    if not isinstance(receipt_data, dict):
        raise ValueError("Build receipt must be a JSON object")
    checksums = {}
    for line in (artifact_dir / "SHA256SUMS").read_text().splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r"([0-9a-fA-F]{64}) [ *]([^/\\]+)", line)
        if not match or match[2] not in REQUIRED or match[2] in checksums:
            raise ValueError("SHA256SUMS contains an unsafe, duplicate or unexpected entry")
        checksums[match[2]] = match[1].lower()
    if set(checksums) != REQUIRED:
        raise ValueError("SHA256SUMS must cover EFI, build receipt, license and notice exactly")
    payload_hashes = receipt_data.get("artifacts")
    payload_names = REQUIRED - {"build-receipt.json"}
    if not isinstance(payload_hashes, dict) or set(payload_hashes) != payload_names:
        raise ValueError("Pinned build receipt must identify EFI, license and notice hashes")
    for name in payload_names:
        if payload_hashes[name] != checksums[name]:
            raise ValueError(f"Checksum is not bound to pinned build receipt: {name}")
    for name, expected in checksums.items():
        if sha256(artifact_dir / name) != expected:
            raise ValueError(f"Artifact digest mismatch: {name}")
    with (artifact_dir / "GINUX.EFI").open("rb") as image:
        if image.read(2) != b"MZ":
            raise ValueError("GINUX.EFI is not a PE executable")
    for name in ("GINUX_LICENSE", "GINUX_NOTICE"):
        if (artifact_dir / name).stat().st_size == 0:
            raise ValueError(f"Empty attribution file: {name}")
    launcher = kit / "scripts" / "run-vm.sh"
    if launcher.is_symlink() or not launcher.is_file() or not launcher.read_bytes().startswith(b"#!/"):
        raise ValueError("Missing ordinary scripts/run-vm.sh launcher")
    return artifact_dir, launcher, checksums


def install_dependencies():
    if shutil.which("apt-get"):
        subprocess.run(["apt-get", "update"], check=True)
        subprocess.run(["apt-get", "install", "-y", "--no-install-recommends", "qemu-system-x86", "ovmf", "util-linux"], check=True)
    elif shutil.which("pacman"):
        subprocess.run(["pacman", "-S", "--needed", "--noconfirm", "qemu-system-x86", "edk2-ovmf", "util-linux"], check=True)
    else:
        raise ValueError("Install QEMU x86, OVMF and util-linux with this host's package manager, then rerun without --install-dependencies")


def install(kit, receipt_hash, stage_root=None, dependencies=False, require_usb=False):
    artifacts, launcher, hashes = verify_kit(kit, receipt_hash)
    if stage_root is None:
        if platform.system() != "Linux" or platform.machine() not in ("x86_64", "amd64"):
            raise ValueError("The native host installer requires x86-64 Linux")
        if os.geteuid() != 0:
            raise ValueError("System installation requires sudo; no VM is started by this installer")
        if require_usb and not preflight.collect()["usb_nonrotational_root_candidate"]:
            raise ValueError("Running root was not identified on USB nonrotational storage; no installation made")
        root = Path("/")
    else:
        if dependencies or require_usb:
            raise ValueError("--stage-root packages ordinary files only and cannot install packages or qualify external storage")
        root = stage_root.resolve()
        if root == Path("/"):
            raise ValueError("--stage-root cannot be the running system root")
        root.mkdir(parents=True, exist_ok=True)
    destination = root / "opt/thox/ginux"
    wrapper = root / "usr/local/bin/thox-ginux"
    desktop = root / "usr/share/applications/thox-ginux.desktop"
    for path in (destination, wrapper, desktop):
        if path.exists() or path.is_symlink():
            raise ValueError(f"Existing path preserved: {path}. Review and remove the prior installation explicitly before reinstalling")
        for parent in path.parents:
            if parent.is_symlink():
                raise ValueError(f"Refusing symlinked installation parent: {parent}")
    if dependencies:
        install_dependencies()
    if stage_root is None and not shutil.which("qemu-system-x86_64"):
        raise ValueError("QEMU is missing; rerun with --install-dependencies or install it with the system package manager")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix=".ginux-install-", dir=destination.parent))
    created = []
    try:
        staged.chmod(0o755)
        (staged / "artifacts").mkdir()
        for name in sorted(REQUIRED | {"SHA256SUMS"}):
            shutil.copyfile(artifacts / name, staged / "artifacts" / name)
            (staged / "artifacts" / name).chmod(0o644)
        shutil.copyfile(launcher, staged / "run-vm.sh")
        (staged / "run-vm.sh").chmod(0o755)
        for name, expected in hashes.items():
            if sha256(staged / "artifacts" / name) != expected:
                raise ValueError(f"Installed byte verification failed: {name}")
        installed = {"schema": "thox.ginux.host-install.v1", "build_receipt_sha256": receipt_hash.lower(), "artifacts": hashes, "launcher_sha256": sha256(staged / "run-vm.sh"), "physical_write": False, "vm_started": False, "staging_only": stage_root is not None}
        (staged / "host-install-receipt.json").write_text(json.dumps(installed, indent=2) + "\n")
        staged.rename(destination)
        created.append(destination)
        wrapper.parent.mkdir(parents=True, exist_ok=True)
        with wrapper.open("x") as target:
            target.write('#!/bin/sh\nexec /opt/thox/ginux/run-vm.sh --artifact-dir /opt/thox/ginux/artifacts "$@"\n')
        wrapper.chmod(0o755)
        created.append(wrapper)
        desktop.parent.mkdir(parents=True, exist_ok=True)
        with desktop.open("x") as target:
            target.write("[Desktop Entry]\nType=Application\nName=ThoxOS Ginux research VM\nComment=Experimental Ginux kernel in a local QEMU guest\nExec=/usr/local/bin/thox-ginux\nTerminal=true\nIcon=utilities-terminal\nCategories=System;Development;\n")
        created.append(desktop)
        return installed
    except Exception:
        for path in reversed(created):
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)
        raise
    finally:
        if staged.exists():
            shutil.rmtree(staged)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit", required=True, type=Path, help="Local module-ginux folder from the reviewed kit")
    parser.add_argument("--expected-receipt-sha256", required=True)
    parser.add_argument("--install-dependencies", action="store_true", help="Install QEMU/OVMF/util-linux through apt or pacman")
    parser.add_argument("--require-usb-root", action="store_true", help="Refuse unless running root is on a detected USB nonrotational disk")
    parser.add_argument("--stage-root", type=Path, help="Package ordinary files under this directory; no dependency or hardware action")
    args = parser.parse_args()
    try:
        result = install(args.kit.resolve(), args.expected_receipt_sha256, args.stage_root, args.install_dependencies, args.require_usb_root)
    except (ValueError, OSError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        parser.exit(2, f"Refused: {error}\n")
    print(json.dumps(result, indent=2))
    if args.stage_root is None:
        print("Installed. Run thox-ginux as your desktop user. No VM has been started.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
