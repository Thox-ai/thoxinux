#!/usr/bin/env python3
"""Record actual compiled bytes, pinned base, patch and lockfile provenance."""
import datetime
import hashlib
import json
import pathlib
import subprocess
import sys

source, out = map(pathlib.Path, sys.argv[1:])
module = pathlib.Path(__file__).resolve().parent.parent
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
patch_names = [line.strip() for line in (module / "patches/series").read_text().splitlines() if line.strip() and not line.lstrip().startswith("#")]
receipt = {
    "edition": "ThoxOS Ginux Research Edition",
    "stage": "engineering-preview",
    "version": "0.2.0-azure-candidate",
    "variant": "THOX Azure Compute Edition",
    "built_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "upstream_repository": "https://github.com/gmkurtzer/ginux",
    "upstream_commit": subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip(),
    "rustc": subprocess.check_output(["rustc", "--version"], cwd=source, text=True).strip(),
    "identity_patch_sha256": sha(module / "patches/thox-identity.patch"),
    "source_patches": {name: sha(module / "patches" / name) for name in patch_names},
    "clang": subprocess.check_output(["clang", "--version"], text=True).splitlines()[0],
    "cargo_lock_sha256": sha(source / "Cargo.lock"),
    "efi_sha256": sha(out / "GINUX.EFI"),
    "efi_size_bytes": (out / "GINUX.EFI").stat().st_size,
    "artifacts": {name: sha(out / name) for name in ("GINUX.EFI", "GINUX_LICENSE", "GINUX_NOTICE")},
    "physical_hardware_test": "not_run",
}
(out / "build-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
