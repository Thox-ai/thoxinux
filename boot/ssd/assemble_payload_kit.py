#!/usr/bin/env python3
"""Assemble a current module-ginux payload kit from Payload U.

Source line: unified. The EFI, license and notice are copied byte for byte
from a unified build output directory (Payload U, the v0.9.0 release asset
source). The launcher is the unified tree launcher from this repository
(kernel/ginux/scripts/run-vm.sh).

No build-time build-receipt.json exists for Payload U: the unified build
copied the EFI and then its receipt step failed on a legacy patch filename
(write-build-receipt.py looked for patches/thox-banner.patch, which the
unified patch series does not carry; recorded in the build log of the
unified build). This script therefore generates the receipt at assembly
time. The receipt binds only the measured artifact hashes, states its own
kind plainly, and claims no build-time provenance it does not have.

Kit format, as enforced by install_host.verify_kit in this directory:
  kit/artifacts/GINUX.EFI          PE executable, SHA-256 pinned by receipt
  kit/artifacts/GINUX_LICENSE      non-empty upstream license text
  kit/artifacts/GINUX_NOTICE       non-empty upstream notice text
  kit/artifacts/build-receipt.json JSON object; its artifacts map binds the
                                   EFI, license and notice hashes exactly
  kit/artifacts/SHA256SUMS         covers all four artifacts exactly, one
                                   "<sha256>  <name>" line per artifact
  kit/scripts/run-vm.sh            ordinary file starting with a shebang
The assembled kit is far too large for git (the EFI alone is 12,507,648
bytes and is already published as the v0.9.0 release asset), so the kit
itself is assembled on disk and only this script is committed.
"""
import argparse
import datetime
import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install_host

EXPECTED_EFI_SHA256 = "85722bd41426491bf86f810bbdd25f951c53afc49e1bf32ad5b34c63ab4420ae"
UPSTREAM_COMMIT = "36503bda2d87465765e1b94e65f9d100f27ed5be"
PAYLOAD_NAMES = ("GINUX.EFI", "GINUX_LICENSE", "GINUX_NOTICE")


def read_sums(path):
    entries = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        digest, _, name = line.partition("  ")
        entries[name.strip().lstrip("*")] = digest.strip().lower()
    return entries


def assemble(efi_dir, launcher, out, expected_efi_sha256=EXPECTED_EFI_SHA256):
    efi_dir = Path(efi_dir)
    launcher = Path(launcher)
    out = Path(out)
    if out.exists() or out.is_symlink():
        raise ValueError("Kit output path must not exist; existing kits are preserved")
    for name in PAYLOAD_NAMES:
        path = efi_dir / name
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Missing or non-regular payload file: {path}")
    if launcher.is_symlink() or not launcher.is_file() or not launcher.read_bytes().startswith(b"#!"):
        raise ValueError("Missing ordinary launcher with a shebang line")
    hashes = {name: install_host.sha256(efi_dir / name) for name in PAYLOAD_NAMES}
    if hashes["GINUX.EFI"] != expected_efi_sha256.lower():
        raise ValueError(
            f"Payload EFI digest mismatch: got {hashes['GINUX.EFI']}, "
            f"expected the pinned Payload U digest {expected_efi_sha256.lower()}"
        )
    with (efi_dir / "GINUX.EFI").open("rb") as image:
        if image.read(2) != b"MZ":
            raise ValueError("GINUX.EFI is not a PE executable")
    for name in ("GINUX_LICENSE", "GINUX_NOTICE"):
        if (efi_dir / name).stat().st_size == 0:
            raise ValueError(f"Empty attribution file: {name}")
    sums_path = efi_dir / "SHA256SUMS"
    if sums_path.is_file():
        recorded = read_sums(sums_path)
        for name in PAYLOAD_NAMES:
            if recorded.get(name) != hashes[name]:
                raise ValueError(f"Source SHA256SUMS does not match measured payload: {name}")
    receipt = {
        "edition": "ThoxOS Ginux Research Edition",
        "stage": "engineering-preview",
        "version": "0.9.0",
        "variant": "unified (Payload U)",
        "source_line": "unified",
        "upstream_repository": "https://github.com/gmkurtzer/ginux",
        "upstream_commit": UPSTREAM_COMMIT,
        "efi_sha256": hashes["GINUX.EFI"],
        "efi_size_bytes": (efi_dir / "GINUX.EFI").stat().st_size,
        "artifacts": hashes,
        "receipt_kind": "wave5-kit-assembly",
        "receipt_note": (
            "Generated at kit assembly time in Wave 5. No build-time receipt "
            "exists for Payload U: the unified build receipt step failed after "
            "the EFI was copied, on a legacy patch filename. This receipt "
            "binds only the measured artifact hashes in this file."
        ),
        "assembled_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "physical_hardware_test": "not_run",
    }
    artifacts_dir = out / "artifacts"
    scripts_dir = out / "scripts"
    try:
        artifacts_dir.mkdir(parents=True)
        scripts_dir.mkdir(parents=True)
        for name in PAYLOAD_NAMES:
            shutil.copyfile(efi_dir / name, artifacts_dir / name)
        (artifacts_dir / "build-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        receipt_hash = install_host.sha256(artifacts_dir / "build-receipt.json")
        sums = {name: install_host.sha256(artifacts_dir / name) for name in sorted(install_host.REQUIRED)}
        (artifacts_dir / "SHA256SUMS").write_text(
            "".join(f"{sums[name]}  {name}\n" for name in sorted(install_host.REQUIRED))
        )
        shutil.copyfile(launcher, scripts_dir / "run-vm.sh")
        (scripts_dir / "run-vm.sh").chmod(0o755)
        manifest = {
            "schema": "thox.ginux.payload-kit.wave5.v1",
            "kit": "module-ginux",
            "build_receipt_sha256": receipt_hash,
            "components": {
                "artifacts/GINUX.EFI": {"source_line": "unified", "sha256": hashes["GINUX.EFI"]},
                "artifacts/GINUX_LICENSE": {"source_line": "unified", "sha256": hashes["GINUX_LICENSE"]},
                "artifacts/GINUX_NOTICE": {"source_line": "unified", "sha256": hashes["GINUX_NOTICE"]},
                "artifacts/build-receipt.json": {"source_line": "wave5-assembly", "sha256": receipt_hash},
                "scripts/run-vm.sh": {
                    "source_line": "unified",
                    "sha256": install_host.sha256(scripts_dir / "run-vm.sh"),
                    "origin": "kernel/ginux/scripts/run-vm.sh in Thox-ai/thoxinux",
                },
            },
            "physical_write": False,
        }
        (out / "KIT-MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
        install_host.verify_kit(out, receipt_hash)
    except Exception:
        if out.exists():
            shutil.rmtree(out)
        raise
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--efi-dir", required=True, type=Path, help="Unified build output directory holding GINUX.EFI, GINUX_LICENSE, GINUX_NOTICE")
    parser.add_argument("--launcher", required=True, type=Path, help="run-vm.sh launcher, unified source line")
    parser.add_argument("--out", required=True, type=Path, help="New kit directory to create (module-ginux layout)")
    parser.add_argument("--expected-efi-sha256", default=EXPECTED_EFI_SHA256)
    args = parser.parse_args()
    try:
        manifest = assemble(args.efi_dir, args.launcher, args.out, args.expected_efi_sha256)
    except (ValueError, OSError) as error:
        parser.exit(2, f"Stopped: {error}\n")
    print(json.dumps(manifest, indent=2))
    print("Kit assembled and verified by install_host.verify_kit. No physical disk write was performed.")


if __name__ == "__main__":
    main()
