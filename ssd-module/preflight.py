#!/usr/bin/env python3
"""Read-only KnightHub host inventory. No disk writes or firmware changes."""
import argparse
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path


def command(args):
    try:
        result = subprocess.run(args, text=True, capture_output=True, timeout=15, check=False)
        return {"available": True, "exit_code": result.returncode, "output": result.stdout.strip()}
    except (OSError, subprocess.TimeoutExpired):
        return {"available": False, "exit_code": None, "output": ""}


def root_disks(blocks, root_major_minor):
    """Find root's physical ancestors, including dm-crypt/LVM nesting."""
    found = []

    def visit(node, ancestors):
        chain = ancestors + [node]
        if str(node.get("maj:min", "")) == root_major_minor:
            for ancestor in chain:
                if ancestor.get("type") == "disk":
                    identity = ancestor.get("path") or ancestor.get("name")
                    if not any(item.get("path") == identity for item in found):
                        found.append({key: ancestor.get(key) for key in ("path", "size", "tran", "rm", "ro", "rota")})
        for child in node.get("children", []):
            visit(child, chain)

    for block in blocks:
        visit(block, [])
    return found


def collect():
    cpu = "Unknown"
    memory_bytes = None
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                memory_bytes = int(line.split()[1]) * 1024
                break
    except (OSError, ValueError, IndexError):
        pass
    inventory = command(["lsblk", "--json", "--bytes", "--output", "NAME,PATH,TYPE,SIZE,TRAN,RM,RO,ROTA,MAJ:MIN"])
    blocks = []
    try:
        if inventory["exit_code"] == 0:
            blocks = json.loads(inventory["output"])["blockdevices"]
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    root = command(["findmnt", "--noheadings", "--output", "MAJ:MIN", "/"])
    ancestors = root_disks(blocks, root["output"]) if root["exit_code"] == 0 else []
    candidate = bool(ancestors) and all(item["tran"] == "usb" and item["rota"] in (False, 0) for item in ancestors)
    gpu = command(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"])
    firmware = "UEFI" if Path("/sys/firmware/efi").is_dir() else "Legacy or unavailable"
    return {
        "schema": "thox.ginux.host-preflight.v1",
        "scope": "Read-only inventory; this does not prove physical boot, driver compatibility, Secure Boot or workload acceptance.",
        "platform": platform.system(), "architecture": platform.machine(), "cpu": cpu,
        "memory_bytes": memory_bytes, "firmware": firmware,
        "kvm_accessible": os.access("/dev/kvm", os.R_OK | os.W_OK),
        "qemu_available": shutil.which("qemu-system-x86_64") is not None,
        "nvidia": {"probe_available": gpu["available"], "exit_code": gpu["exit_code"], "summary": gpu["output"]},
        "root_physical_disks": ancestors, "usb_nonrotational_root_candidate": candidate,
        "block_devices": blocks, "storage_inventory_available": bool(blocks),
        "mutations": [],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = collect()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("ThoxOS Ginux host preflight (read only)")
        print(f"CPU: {result['cpu']}")
        ram = result['memory_bytes']
        print(f"RAM: {ram / 1024**3:.1f} GiB" if ram else "RAM: unavailable")
        print(f"Host: {result['platform']} {result['architecture']}; firmware: {result['firmware']}")
        print(f"KVM access: {result['kvm_accessible']}; QEMU: {result['qemu_available']}")
        print("NVIDIA: " + (result['nvidia']['summary'] or "unavailable"))
        print(f"Running root on USB nonrotational candidate: {result['usb_nonrotational_root_candidate']}")
        print("Root disks: " + json.dumps(result['root_physical_disks']))
        print(result['scope'])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
