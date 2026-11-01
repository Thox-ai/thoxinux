#!/usr/bin/env python3
"""Prepare/build a Ginux-equipped candidate through the existing THOX image lane.

No physical-device argument exists. Output is an ordinary image build only.
"""
import argparse
import datetime
import hashlib
import json
import subprocess
from pathlib import Path

import install_host

HOST_COMMIT = "e912d82ad9d8e3475a945039b5f16228c9a4bf56"
SOURCE_BLOBS = {
    "image/build-image.sh": "129e0de55888514fb6cfa84671a09866fecaaa03",
    "image/scripts/build-x86.sh": "4473c642469962a5fe07ef3a2643a8b9ee2500bd",
    "image/scripts/stage-extra.sh": "aac0543260c275be5eaa4b28d3cc1e47914015e7",
    "image/x86_64/mkosi.conf": "8fe83ece16c5801c54ce681ef0652ed918b9b154",
}


def git_blob(path):
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def add_guest_packages(text):
    marker = "Packages=\n"
    if text.count(marker) != 1:
        raise ValueError("Pinned mkosi package section changed; do not patch a different source")
    return text.replace(marker, marker + "    # THOX Ginux research guest dependencies\n    qemu-system-x86\n    edk2-ovmf\n    util-linux\n", 1)


def prepare(source, worktree, kit, receipt_hash):
    if worktree.exists() or worktree.is_symlink():
        raise ValueError("Worktree path must not exist; existing source is preserved")
    install_host.verify_kit(kit, receipt_hash)
    subprocess.run(["git", "-C", str(source), "cat-file", "-e", HOST_COMMIT + "^{commit}"], check=True)
    # A linked Git worktree's .git points outside the Docker /src mount. Use a
    # self-contained local clone so the existing builder can read source HEAD.
    subprocess.run(["git", "clone", "--no-hardlinks", "--no-checkout", str(source), str(worktree)], check=True)
    subprocess.run(["git", "-C", str(worktree), "checkout", "--detach", HOST_COMMIT], check=True)
    for relative, expected in SOURCE_BLOBS.items():
        if git_blob(worktree / relative) != expected:
            raise ValueError("Pinned source blob mismatch: " + relative)
    configuration = worktree / "image/x86_64/mkosi.conf"
    configuration.write_text(add_guest_packages(configuration.read_text()))
    overlay = worktree / "image/common/overlay"
    overlay.mkdir(parents=True, exist_ok=True)
    installation = install_host.install(kit, receipt_hash, stage_root=overlay)
    added = {}
    for base in (overlay / "opt/thox/ginux", overlay / "usr/local/bin/thox-ginux", overlay / "usr/share/applications/thox-ginux.desktop"):
        files = base.rglob("*") if base.is_dir() else [base]
        for path in files:
            if path.is_file():
                added[str(path.relative_to(overlay))] = install_host.sha256(path)
    record = {
        "schema": "thox.ginux.external-ssd-source.v1", "status": "prepared-not-built",
        "host_repository": "ttracx/thoxos-vibe-rust", "host_commit": HOST_COMMIT,
        "source_blobs": SOURCE_BLOBS, "modified_mkosi_sha256": install_host.sha256(configuration),
        "guest_build_receipt_sha256": receipt_hash.lower(), "overlay_sha256": added,
        "image_variant": "x86_64-dual", "installed_guest_stage": installation,
        "physical_write": False, "native_boot": "not_run", "vm_gate": "not_run",
        "windows_writer_admission": "blocked-layout-mismatch: existing NiceC0re writer admits two-part ext images; this dual-arch host uses a different layout",
        "created_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    record_path = worktree / "ginux-integration-source.json"
    record_path.write_text(json.dumps(record, indent=2) + "\n")
    return record, record_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="Existing authorized clone of thoxos-vibe-rust")
    parser.add_argument("--worktree", required=True, type=Path, help="New isolated source worktree on the approved build volume")
    parser.add_argument("--kit", required=True, type=Path)
    parser.add_argument("--expected-receipt-sha256", required=True)
    parser.add_argument("--out", required=True, type=Path, help="New ordinary-file artifact directory")
    parser.add_argument("--build", action="store_true", help="Run workspace tests and the existing privileged Docker image build")
    parser.add_argument("--run-vm-gate", action="store_true", help="After build, execute the existing VM harness on this host")
    args = parser.parse_args()
    if args.run_vm_gate and not args.build:
        parser.error("--run-vm-gate requires --build")
    output = args.out.absolute()
    if output.exists() or output.is_symlink() or any(part in ("/dev", "/sys", "/proc") for part in [str(output), *map(str, output.parents)]):
        parser.error("--out must be a new ordinary-file directory outside device/kernel filesystems")
    try:
        worktree = args.worktree.absolute()
        record, record_path = prepare(args.source.resolve(), worktree, args.kit.resolve(), args.expected_receipt_sha256)
        output.mkdir(parents=True)
        commands = [
            ["cargo", "test", "--workspace"],
            ["bash", "image/build-image.sh", "--variant", "x86_64-dual", "--version", "0.1.0-ginux-host", "--out", str(output), "--min-free-gib", "125"],
        ]
        vm_command = ["bash", "image/vm/loop.sh", "--variant", "x86_64-dual", "--artifact-dir", str(output), "--skip-build"]
        record["planned_commands"] = commands + [vm_command]
        record["executed_commands"] = []
        if args.build:
            for index, command in enumerate(commands + ([vm_command] if args.run_vm_gate else [])):
                log_path = output / f"integration-command-{index + 1}.log"
                with log_path.open("x") as log:
                    result = subprocess.run(command, cwd=worktree, stdout=log, stderr=subprocess.STDOUT, check=False)
                record["executed_commands"].append({"command": command, "exit_code": result.returncode, "log": log_path.name})
                record["status"] = "failed" if result.returncode else "candidate-command-passed-acceptance-pending"
                record_path.write_text(json.dumps(record, indent=2) + "\n")
                (output / "ginux-integration-source.json").write_text(json.dumps(record, indent=2) + "\n")
                if result.returncode:
                    raise ValueError(f"Command failed with exit {result.returncode}; retained {log_path}")
            if args.run_vm_gate:
                record["vm_gate"] = "command_passed-review-receipts-required"
        record_path.write_text(json.dumps(record, indent=2) + "\n")
        (output / "ginux-integration-source.json").write_text(json.dumps(record, indent=2) + "\n")
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(2, f"Stopped: {error}\n")
    print(json.dumps(record, indent=2))
    print("Candidate source prepared. No physical disk write is available or performed by this builder.")


if __name__ == "__main__":
    main()
