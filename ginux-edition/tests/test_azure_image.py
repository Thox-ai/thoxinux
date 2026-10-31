"""Tests for the Azure deliverables: VHD checks, the ARM template and its first-boot script."""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "azure"))

import vhd_check  # noqa: E402

TEMPLATE = ROOT / "azure" / "azuredeploy.json"
MIB = 1024 * 1024


def fixed_footer(size: int, disk_type: int = 2, cookie: bytes = b"conectix") -> bytes:
    head = struct.pack(">8sIIQI4sIIQQHBBI", cookie, 2, 0x00010000, 0xFFFFFFFFFFFFFFFF, 0, b"qemu",
                       0x00050003, 0x5769326B, size, size, 1024, 16, 63, disk_type)
    body = head + b"\0\0\0\0" + b"\x11" * 16 + b"\0" + b"\0" * 427  # checksum, id, saved state, reserved
    checksum = vhd_check.footer_checksum(body)
    return head + struct.pack(">I", checksum) + body[68:]


def write_vhd(path: Path, size: int, **kwargs) -> Path:
    with open(path, "wb") as handle:
        handle.truncate(size)
        handle.seek(size)
        handle.write(fixed_footer(size, **kwargs))
    return path


def test_fixed_aligned_vhd_passes(tmp_path):
    assert vhd_check.check(str(write_vhd(tmp_path / "a.vhd", 4 * MIB)), 4 * MIB) == []


def test_dynamic_and_misaligned_vhds_fail(tmp_path):
    problems = vhd_check.check(str(write_vhd(tmp_path / "d.vhd", 4 * MIB, disk_type=3)))
    assert any("not fixed" in p for p in problems)
    odd = 4 * MIB + 512
    problems = vhd_check.check(str(write_vhd(tmp_path / "o.vhd", odd)))
    assert any("whole number of MiB" in p for p in problems)


def test_corrupt_footer_fails(tmp_path):
    path = write_vhd(tmp_path / "c.vhd", 2 * MIB)
    with open(path, "r+b") as handle:
        handle.seek(2 * MIB + 100)
        handle.write(b"\xff")
    assert any("checksum" in p for p in vhd_check.check(str(path)))
    assert any("cookie" in p for p in vhd_check.check(str(write_vhd(tmp_path / "k.vhd", MIB, cookie=b"notavhd!"))))


@pytest.mark.skipif(shutil.which("qemu-img") is None, reason="qemu-img not installed")
def test_qemu_img_fixed_conversion_passes(tmp_path):
    raw = tmp_path / "disk.raw"
    with open(raw, "wb") as handle:
        handle.truncate(16 * MIB)
    vhd = tmp_path / "disk.vhd"
    subprocess.run(["qemu-img", "convert", "-f", "raw", "-O", "vpc", "-o", "subformat=fixed,force_size",
                    str(raw), str(vhd)], check=True)
    assert vhd_check.check(str(vhd), 16 * MIB) == []


# --------------------------------------------------------------- ARM template

def template():
    return json.loads(TEMPLATE.read_text())


def expressions(node):
    if isinstance(node, dict):
        for value in node.values():
            yield from expressions(value)
    elif isinstance(node, list):
        for value in node:
            yield from expressions(value)
    elif isinstance(node, str) and node.startswith("[") and node.endswith("]"):
        yield node


def test_template_references_resolve():
    doc = template()
    params, variables = set(doc["parameters"]), set(doc["variables"])
    for expr in expressions(doc):
        for name in re.findall(r"parameters\('([^']+)'\)", expr):
            assert name in params, f"unknown parameter {name}"
        for name in re.findall(r"variables\('([^']+)'\)", expr):
            assert name in variables, f"unknown variable {name}"
    declared = {r["name"] for r in doc["resources"]}
    assert len(declared) == len(doc["resources"])
    for resource in doc["resources"]:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", resource["apiVersion"])


def test_template_never_opens_ports_to_everyone():
    doc = template()
    for rule in doc["variables"]["sshRule"] + doc["variables"]["rdpRule"]:
        assert rule["properties"]["sourceAddressPrefix"] == "[parameters('allowedSourceCidr')]"
    assert "defaultValue" not in doc["parameters"]["allowedSourceCidr"]
    nic = next(r for r in doc["resources"] if r["type"].endswith("networkInterfaces"))
    assert nic["properties"]["enableAcceleratedNetworking"] is False
    vm = next(r for r in doc["resources"] if r["type"].endswith("virtualMachines"))
    assert "securityProfile" not in vm["properties"]  # standard security: unsigned boot loader


def render_first_boot(params: dict) -> str:
    """Evaluate the template's format(...) for firstBootScript the way ARM does."""
    expr = template()["variables"]["firstBootScript"]
    match = re.fullmatch(r"\[format\('(.*)', (base64\(.*\))\)\]", expr, flags=re.S)
    assert match, "firstBootScript is not a format() expression"
    fmt = match.group(1).replace("''", "'")
    args = re.findall(r"base64\(parameters\('([^']+)'\)\)", match.group(2))
    values = [base64.b64encode(params[a].encode()).decode() for a in args]
    return re.sub(r"\{(\d)\}", lambda m: values[int(m.group(1))], fmt)


@pytest.mark.skipif(shutil.which("bash") is None or shutil.which("base64") is None, reason="needs bash")
def test_first_boot_script_sets_look_without_writing_credentials(tmp_path):
    look = "porcelain'; touch PWNED; echo '$(id)`whoami`"
    secret = "test-key-must-never-enter-custom-data"
    script = render_first_boot({"desktopLook": look, "aiApiKey": secret})
    assert secret not in script
    assert base64.b64encode(secret.encode()).decode() not in script
    assert "THOX_RELAY_API_KEY" not in script
    etc = tmp_path / "etc"
    (etc / "thoxos").mkdir(parents=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.log"
    tool = bin_dir / "thoxos-look"
    tool.write_text(f"#!/bin/bash\nprintf '%s\\n' \"$@\" >> {log}\n")
    tool.chmod(0o755)
    path = tmp_path / "firstboot.sh"
    path.write_text(script.replace("/etc/thoxos/", f"{etc}/thoxos/"))
    subprocess.run(["bash", "-n", str(path)], check=True)
    env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}")
    subprocess.run(["bash", str(path)], check=True, env=env, cwd=tmp_path)
    assert log.read_text().splitlines() == ["system-default", look]
    assert not (tmp_path / "PWNED").exists()
    assert not (etc / "thoxos" / "ai-relay.env").exists()


def test_template_cannot_put_ai_credentials_in_custom_data():
    doc = template()
    for name in ("aiUpstream", "aiAuth", "aiApiKey", "aiModel"):
        assert name not in doc["parameters"]
    script = doc["variables"]["firstBootScript"]
    assert "parameters('adminPasswordOrKey')" not in script
    assert "THOX_RELAY" not in script
    assert "ai-relay.env" not in script
    assert re.findall(r"parameters\('([^']+)'\)", script) == ["desktopLook"]


# --------------------------------------------------------------- chrony PTP

PTP_SCRIPT = ROOT / "azure" / "overlay" / "usr" / "lib" / "thoxos-g" / "chrony-azure-ptp.sh"


def run_ptp(tmp_path: Path, device_exists: bool) -> Path:
    """Run a copy of the script with its fixed paths moved under tmp_path."""
    device = tmp_path / "ptp_hyperv"
    if device_exists:
        device.touch()
    conf_dir = tmp_path / "chrony"
    script = PTP_SCRIPT.read_text().replace("/dev/ptp_hyperv", str(device)) \
        .replace("/run/thoxos-g/chrony", str(conf_dir)).replace("/sys/bus/vmbus/devices", str(tmp_path / "no-vmbus"))
    copy = tmp_path / "ptp.sh"
    copy.write_text(script)
    subprocess.run(["bash", str(copy)], check=True, capture_output=True)
    return conf_dir / "azure-ptp.conf"


def test_ptp_refclock_written_only_when_the_device_exists(tmp_path):
    conf = run_ptp(tmp_path, device_exists=True)
    assert conf.read_text().startswith(f"refclock PHC {tmp_path / 'ptp_hyperv'} poll 3")
    (tmp_path / "ptp_hyperv").unlink()
    assert not run_ptp(tmp_path, device_exists=False).exists()  # removed again off Azure


def test_chrony_includes_the_runtime_refclock_only():
    conf = (ROOT / "azure" / "overlay" / "etc" / "chrony" / "conf.d" / "azure-ptp.conf").read_text()
    active = [l for l in conf.splitlines() if l.strip() and not l.startswith("#")]
    assert active == ["include /run/thoxos-g/chrony/*.conf"]  # a static refclock line fails chronyd off Azure


def test_ptp_step_runs_privileged_before_chronyd():
    dropin = (ROOT / "azure" / "overlay" / "etc" / "systemd" / "system" / "chrony.service.d"
              / "50-thoxos-azure-ptp.conf").read_text()
    # chrony.service sets User=_chrony; without "+" the step cannot write /run (VALIDATION D-10).
    assert "ExecStartPre=+/usr/lib/thoxos-g/chrony-azure-ptp.sh" in dropin
