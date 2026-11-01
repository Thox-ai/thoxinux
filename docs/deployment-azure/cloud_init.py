"""Produce secret-free cloud-init using JSON, which is valid YAML."""
import base64
import json
from pathlib import Path


def render(config):
    directory = Path(__file__).resolve().parent
    host_config = {
        "artifact_url": config["artifact_url"],
        "artifact_sha256": config["artifact_sha256"],
        "build_receipt_sha256": config["build_receipt_sha256"],
        "identity_client_id": "__IDENTITY_CLIENT_ID__",
        "run_guest_smoke": True,
    }
    files = [{"path": "/etc/thox-ginux-azure.json", "permissions": "0644", "owner": "root:root", "content": json.dumps(host_config, indent=2) + "\n"}]
    for name in ("bootstrap.py", "smoke_guest.py"):
        files.append({"path": "/usr/local/lib/thox-ginux/" + name, "permissions": "0755", "owner": "root:root", "encoding": "b64", "content": base64.b64encode((directory / name).read_bytes()).decode()})
    data = {"package_update": True, "package_upgrade": False, "packages": ["qemu-system-x86", "ovmf", "util-linux", "python3", "ca-certificates"], "ssh_pwauth": False, "disable_root": True, "write_files": files, "runcmd": [["python3", "/usr/local/lib/thox-ginux/bootstrap.py", "--config", "/etc/thox-ginux-azure.json"]]}
    result = "#cloud-config\n" + json.dumps(data, indent=2) + "\n"
    if len(base64.b64encode(result.encode())) > 65535:
        raise ValueError("cloud-init exceeds the conservative encoded custom-data size limit")
    return result
