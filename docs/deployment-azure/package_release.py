#!/usr/bin/env python3
"""Build a deterministic, allowlisted Azure deployment ZIP from verified artifacts."""
import argparse
import hashlib
import json
import pathlib
import re
import zipfile

REQUIRED = (
    "module-ginux/scripts/run-vm.sh",
    "module-ginux/artifacts/GINUX.EFI",
    "module-ginux/artifacts/build-receipt.json",
    "module-ginux/artifacts/SHA256SUMS",
    "module-ginux/artifacts/GINUX_LICENSE",
    "module-ginux/artifacts/GINUX_NOTICE",
    "module-ginux/SOURCE_MANIFEST.json",
    "module-ginux/patches/series",
    "ssd-module/install_host.py",
    "ssd-module/preflight.py",
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify_provenance(files):
    """Bind the shipped patch set and upstream identity to the built receipt."""
    receipt = json.loads(files["module-ginux/artifacts/build-receipt.json"])
    source_manifest = json.loads(files["module-ginux/SOURCE_MANIFEST.json"])
    if not isinstance(receipt, dict) or not isinstance(source_manifest, dict):
        raise ValueError("Build receipt and source manifest must be JSON objects")
    series = []
    for raw in files["module-ginux/patches/series"].decode("utf-8").splitlines():
        name = raw.strip()
        if not name or name.startswith("#"):
            continue
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.patch", name) or name in series:
            raise ValueError("Patch series must contain safe unique patch filenames")
        series.append(name)
    if not series:
        raise ValueError("Patch series must identify the customized source patches")
    packaged = {path.removeprefix("module-ginux/patches/") for path in files if path.startswith("module-ginux/patches/") and path.endswith(".patch")}
    if packaged != set(series):
        raise ValueError("Packaged patch files do not exactly match patches/series")
    actual = {name: digest(files["module-ginux/patches/" + name]) for name in series}
    for record, label in ((receipt, "Build receipt"), (source_manifest, "Source manifest")):
        if record.get("source_patches") != actual:
            raise ValueError(label + " source_patches do not bind the exact packaged patch series")
        if "banner_patch_sha256" in record and record["banner_patch_sha256"] != actual.get("thox-banner.patch"):
            raise ValueError(label + " banner patch digest does not match packaged patch")
    upstream = source_manifest.get("upstream")
    if not isinstance(upstream, dict):
        raise ValueError("Source manifest has no upstream provenance")
    commit, cargo_lock = upstream.get("commit"), upstream.get("cargo_lock_sha256")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit) or receipt.get("upstream_commit") != commit:
        raise ValueError("Source manifest upstream commit does not match build receipt")
    if not isinstance(cargo_lock, str) or not re.fullmatch(r"[0-9a-f]{64}", cargo_lock) or receipt.get("cargo_lock_sha256") != cargo_lock:
        raise ValueError("Source manifest Cargo.lock digest does not match build receipt")


def package(source, output, source_commit):
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("source_commit must be a full Git SHA")
    files = {}
    selected = list(REQUIRED)
    selected += [p.relative_to(source).as_posix() for p in sorted((source / "module-ginux/patches").glob("*.patch"))]
    for relative in selected:
        path = source / relative
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Missing regular release input: {relative}")
        files[relative] = path.read_bytes()
    verify_provenance(files)
    # Reuse the existing installer verification, binding all artifact digests to
    # the build receipt before making a release archive.
    import importlib.util
    import sys
    sys.path.insert(0, str(source / "ssd-module"))
    spec = importlib.util.spec_from_file_location("thox_release_install", source / "ssd-module/install_host.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    receipt_hash = digest(files["module-ginux/artifacts/build-receipt.json"])
    module.verify_kit(source / "module-ginux", receipt_hash)
    manifest = {
        "schema": "thox.ginux.azure.release.v1",
        "edition": "ThoxOS Ginux Azure Research Edition",
        "source_commit": source_commit,
        "build_receipt_sha256": receipt_hash,
        "files": {name: digest(data) for name, data in sorted(files.items())},
        "claim_limits": ["Linux Azure host with QEMU TCG guest", "No native Azure Ginux or AVD session-host claim"],
    }
    files["release-manifest.json"] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ValueError("Output already exists; choose a new versioned release path")
    with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative, data in sorted(files.items()):
            info = zipfile.ZipInfo(relative, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = ((0o100755 if relative.endswith(".sh") else 0o100644) << 16)
            archive.writestr(info, data)
    result = {"artifact": output.name, "bytes": output.stat().st_size, "sha256": digest(output.read_bytes()), "build_receipt_sha256": receipt_hash, "source_commit": source_commit}
    output.with_suffix(output.suffix + ".json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parent.parent)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    try:
        result = package(args.source.resolve(), args.output.resolve(), args.source_commit)
    except (ValueError, OSError) as error:
        parser.exit(2, f"Refused: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
