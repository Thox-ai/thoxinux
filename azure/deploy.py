#!/usr/bin/env python3
"""Prepare, upload, validate, preview or deploy the explicit Azure research host."""
import argparse
import base64
import hashlib
import ipaddress
import json
import pathlib
import re
import shutil
import subprocess
import tempfile
import urllib.parse
import uuid
import zipfile

import bootstrap
import cloud_init

DIRECTORY = pathlib.Path(__file__).resolve().parent
REQUIRED_CONFIG = {"subscription_id", "resource_group", "location", "vm_name", "admin_username", "ssh_public_key_path", "storage_account", "storage_resource_group", "container", "image_version"}
OPTIONAL_CONFIG = {"enable_private_ssh", "admin_source_cidr", "vnet_address_prefix", "subnet_address_prefix", "enable_bastion", "bastion_subnet_prefix"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_config(path, require_image=True):
    config = json.loads(path.read_text())
    if not isinstance(config, dict) or not REQUIRED_CONFIG <= set(config) or set(config) - REQUIRED_CONFIG - OPTIONAL_CONFIG:
        raise ValueError("Configuration fields do not match deployment.example.json")
    if uuid.UUID(config["subscription_id"]).int == 0:
        raise ValueError("Set an actual explicit Azure subscription ID")
    for field in ("resource_group", "storage_resource_group"):
        if not re.fullmatch(r"[A-Za-z0-9_.()-]{1,90}", config[field]) or config[field].endswith("."):
            raise ValueError(f"Invalid {field}")
    if not re.fullmatch(r"[a-z0-9]{3,24}", config["storage_account"]):
        raise ValueError("Invalid storage_account")
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])", config["container"]) or "--" in config["container"]:
        raise ValueError("Invalid artifact container")
    if not re.fullmatch(r"[a-z][a-z0-9-]{2,31}", config["vm_name"]):
        raise ValueError("vm_name must be a lowercase DNS-style name of 3–32 characters")
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,31}", config["admin_username"]) or config["admin_username"] in {"root", "admin", "administrator", "thoxginux", "ubuntu"}:
        raise ValueError("Choose a nonreserved admin_username distinct from the guest account")
    if not re.fullmatch(r"[a-z0-9]+", config["location"]):
        raise ValueError("Use an Azure location identifier such as eastus")
    if require_image and not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", config["image_version"]):
        raise ValueError("image_version must be an explicitly resolved Marketplace version, never latest")
    for field, default in (("vnet_address_prefix", "10.42.0.0/16"), ("subnet_address_prefix", "10.42.1.0/24"), ("admin_source_cidr", "10.42.0.0/24"), ("bastion_subnet_prefix", "10.42.0.0/26")):
        network = ipaddress.ip_network(config.get(field, default), strict=True)
        if network.version != 4 or not any(network.subnet_of(ipaddress.ip_network(private)) for private in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")):
            raise ValueError(f"{field} must be an explicit RFC1918 IPv4 network")
        config[field] = str(network)
    if not ipaddress.ip_network(config["subnet_address_prefix"]).subnet_of(ipaddress.ip_network(config["vnet_address_prefix"])):
        raise ValueError("Subnet is outside the VNet")
    config.setdefault("enable_private_ssh", False)
    config.setdefault("enable_bastion", False)
    if not isinstance(config["enable_private_ssh"], bool):
        raise ValueError("enable_private_ssh must be boolean")
    if config["enable_private_ssh"] and ipaddress.ip_network(config["admin_source_cidr"]).prefixlen < 24:
        raise ValueError("Private SSH source must be /24 or narrower")
    if not isinstance(config["enable_bastion"], bool):
        raise ValueError("enable_bastion must be boolean")
    if config["enable_bastion"]:
        bastion = ipaddress.ip_network(config["bastion_subnet_prefix"])
        if bastion.prefixlen > 26 or not bastion.subnet_of(ipaddress.ip_network(config["vnet_address_prefix"])) or bastion.overlaps(ipaddress.ip_network(config["subnet_address_prefix"])):
            raise ValueError("Bastion requires a distinct VNet subnet of /26 or larger")
        if not config["enable_private_ssh"] or not bastion.subnet_of(ipaddress.ip_network(config["admin_source_cidr"])):
            raise ValueError("Bastion requires private SSH enabled from a narrow network covering its subnet")
    return config


def command(args, config):
    # Explicit subscription selectors on every Azure CLI invocation prevent an
    # accidental deployment in a different account's default subscription.
    if not shutil.which("az"):
        raise ValueError("Azure CLI is unavailable; use an authenticated Azure CLI/Cloud Shell environment")
    result = subprocess.run(["az", *args, "--subscription", config["subscription_id"], "--only-show-errors", "--output", "json"], check=True, text=True, stdout=subprocess.PIPE)
    return json.loads(result.stdout) if result.stdout.strip() else None


def artifact_info(path):
    if not path.is_file() or path.is_symlink() or path.stat().st_size > bootstrap.MAX_DOWNLOAD:
        raise ValueError("Artifact must be a regular Azure release ZIP below 100 MiB")
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("release-manifest.json"))
    if manifest.get("schema") != "thox.ginux.azure.release.v1":
        raise ValueError("Use azure/package_release.py output")
    artifact_hash = sha(path)
    receipt_hash = manifest.get("build_receipt_sha256", "")
    with tempfile.TemporaryDirectory(prefix="thox-azure-verify-") as temp:
        bootstrap.extract_release(path.read_bytes(), pathlib.Path(temp), receipt_hash)
    return {"sha256": artifact_hash, "bytes": path.stat().st_size, "build_receipt_sha256": receipt_hash, "blob_name": f"sha256/{artifact_hash}/THOX_Ginux_Azure_Release.zip", "source_commit": manifest["source_commit"]}


def validate_public_key(public_key):
    if not re.fullmatch(r"ssh-(?:ed25519|rsa) [A-Za-z0-9+/]+={0,3}(?: [^\r\n]+)?", public_key) or "PRIVATE KEY" in public_key:
        raise ValueError("ssh_public_key_path must contain one supported OpenSSH public key")
    try:
        data = base64.b64decode(public_key.split()[1], validate=True)
        fields = []
        while data:
            if len(data) < 4:
                raise ValueError("Truncated key")
            size = int.from_bytes(data[:4], "big")
            if size == 0 or size > len(data) - 4:
                raise ValueError("Invalid key field")
            fields.append(data[4:4 + size])
            data = data[4 + size:]
        if fields[0].decode() != public_key.split()[0]:
            raise ValueError("Key type mismatch")
        if fields[0] == b"ssh-ed25519":
            if len(fields) != 2 or len(fields[1]) != 32:
                raise ValueError("Invalid Ed25519 key")
        elif len(fields) != 3 or int.from_bytes(fields[1], "big") < 3 or int.from_bytes(fields[2], "big").bit_length() < 2048:
            raise ValueError("RSA key must have at least 2048 bits")
    except (ValueError, IndexError, UnicodeDecodeError):
        raise ValueError("Invalid or insufficient OpenSSH public key encoding") from None
    return public_key


def prepare(config_path, artifact, output):
    config = load_config(config_path)
    info = artifact_info(artifact)
    if output.exists() or output.is_symlink():
        raise ValueError("Plan directory already exists; preserve it and choose a new directory")
    public_key = validate_public_key(pathlib.Path(config["ssh_public_key_path"]).expanduser().read_text().strip())
    artifact_url = f"https://{config['storage_account']}.blob.core.windows.net/{config['container']}/{info['blob_name']}"
    cloud = cloud_init.render({"artifact_url": artifact_url, "artifact_sha256": info["sha256"], "build_receipt_sha256": info["build_receipt_sha256"]})
    params = {
        "location": config["location"], "vmName": config["vm_name"], "adminUsername": config["admin_username"], "sshPublicKey": public_key,
        "ubuntuImageVersion": config["image_version"], "artifactStorageAccount": config["storage_account"], "artifactStorageResourceGroup": config["storage_resource_group"],
        "artifactContainer": config["container"], "cloudInit": cloud, "enablePrivateSsh": config["enable_private_ssh"], "adminSourceCidr": config["admin_source_cidr"],
        "vnetAddressPrefix": config["vnet_address_prefix"], "subnetAddressPrefix": config["subnet_address_prefix"],
        "enableBastion": config["enable_bastion"], "bastionSubnetPrefix": config["bastion_subnet_prefix"],
    }
    output.mkdir(parents=True)
    shutil.copyfile(DIRECTORY / "azuredeploy.json", output / "azuredeploy.json")
    (output / "cloud-init.txt").write_text(cloud)
    (output / "parameters.json").write_text(json.dumps({"$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#", "contentVersion": "1.0.0.0", "parameters": {name: {"value": value} for name, value in params.items()}}, indent=2) + "\n")
    (output / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    record = {"schema": "thox.ginux.azure.plan.v1", "status": "prepared-not-deployed", "source_artifact": info, "artifact_url": artifact_url, "resources": "private Ubuntu Gen2 VM, UAMI, container-scoped Blob Reader assignment, VNet/subnet/NSG, NAT gateway and outbound-only public IP", "files": {name: sha(output / name) for name in ("azuredeploy.json", "parameters.json", "cloud-init.txt", "config.json")}, "acceptance": {"arm_server_validation": "not_run", "deployment": "not_run", "guest_boot": "not_run", "native_ginux_azure": "not_claimed", "avd_session_host": "not_claimed"}}
    (output / "plan.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def check_plan(output):
    record = json.loads((output / "plan.json").read_text())
    if record.get("schema") != "thox.ginux.azure.plan.v1":
        raise ValueError("Invalid plan schema")
    for name, expected in record["files"].items():
        if pathlib.PurePosixPath(name).name != name or sha(output / name) != expected:
            raise ValueError("Plan file changed; prepare a new plan before deployment")
    return load_config(output / "config.json"), record


def check_storage(config):
    storage = command(["storage", "account", "show", "--name", config["storage_account"], "--resource-group", config["storage_resource_group"]], config)
    if storage.get("publicNetworkAccess") == "Disabled":
        raise ValueError("This default NAT deployment requires the Blob HTTPS endpoint; configure a reviewed private endpoint/DNS route before using a network-disabled storage account")
    if storage.get("networkRuleSet", {}).get("defaultAction") == "Deny":
        raise ValueError("Storage firewall denies the new NAT egress path; pre-provision and admit a reviewed network path or private endpoint instead. No firewall rule is changed")
    container = command(["storage", "container", "show", "--account-name", config["storage_account"], "--name", config["container"], "--auth-mode", "login"], config)
    if container.get("properties", {}).get("publicAccess") not in (None, "", "None", "none"):
        raise ValueError("Artifact container is public; choose a private container")


def verify_image(config):
    urn = "Canonical:ubuntu-24_04-lts:server:" + config["image_version"]
    image = command(["vm", "image", "show", "--location", config["location"], "--urn", urn], config)
    if image.get("hyperVGeneration") != "V2":
        raise ValueError("Resolved Ubuntu image is not Gen2")
    return image


def upload(config_path, artifact):
    config = load_config(config_path, require_image=False)
    info = artifact_info(artifact)
    check_storage(config)
    common = ["--account-name", config["storage_account"], "--container-name", config["container"], "--name", info["blob_name"], "--auth-mode", "login"]
    existing = command(["storage", "blob", "exists", *common], config)
    if not existing.get("exists"):
        command(["storage", "blob", "upload", *common, "--file", str(artifact), "--overwrite", "false", "--metadata", "sha256=" + info["sha256"]], config)
    with tempfile.TemporaryDirectory(prefix="thox-upload-readback-") as temp:
        target = pathlib.Path(temp) / "readback.zip"
        command(["storage", "blob", "download", *common, "--file", str(target)], config)
        if sha(target) != info["sha256"]:
            raise ValueError("Uploaded Blob payload does not match prepared bytes")
    return {"uploaded_or_reused": True, "payload_readback": "verified", **info}


def resolve_image(config_path):
    config = load_config(config_path, require_image=False)
    images = command(["vm", "image", "list", "--location", config["location"], "--publisher", "Canonical", "--offer", "ubuntu-24_04-lts", "--sku", "server", "--all"], config)
    candidates = [x for x in images if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", x.get("version", ""))]
    if not candidates:
        raise ValueError("No explicit Ubuntu image version returned for this region")
    latest = max(candidates, key=lambda x: tuple(map(int, x["version"].split("."))))
    config["image_version"] = latest["version"]
    verify_image(config)
    return {"location": config["location"], "image_version": latest["version"], "urn": latest["urn"], "hyper_v_generation": "V2", "action": "Copy image_version into your deployment config; no config or Azure resource was modified"}


def check_target_ownership(config):
    """Fail closed before mutation; names alone never establish ownership."""
    resources = command(["resource", "list", "--resource-group", config["resource_group"]], config)
    if not isinstance(resources, list):
        raise ValueError("Target resource-group inventory was not a resource list")
    expected = {"thox-project": "thoxos-ginux", "thox-deployment": config["vm_name"]}
    for resource in resources:
        tags = resource.get("tags") or {}
        if not isinstance(tags, dict) or any(tags.get(key) != value for key, value in expected.items()):
            raise ValueError("Target resource group contains resources without this deployment's ownership tags; use a dedicated empty resource group or review ownership before retrying")


def run_azure(action, output):
    config, record = check_plan(output)
    check_storage(config)
    verify_image(config)
    if action == "deploy":
        check_target_ownership(config)
    base = ["deployment", "group", {"deploy": "create"}.get(action, action), "--name", config["vm_name"] + "-ginux", "--resource-group", config["resource_group"], "--template-file", str(output / "azuredeploy.json"), "--parameters", "@" + str(output / "parameters.json")]
    result = command(base, config)
    (output / (action + "-result.json")).write_text(json.dumps(result, indent=2) + "\n")
    return {"action": action, "command_completed": True, "result_file": str(output / (action + "-result.json")), "acceptance": "Inspect cloud-init, installer receipt and real guest-smoke evidence; ARM success alone is not guest acceptance"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("prepare", "upload", "resolve-image"):
        child = sub.add_parser(action)
        child.add_argument("--config", required=True, type=pathlib.Path)
        if action != "resolve-image":
            child.add_argument("--artifact", required=True, type=pathlib.Path)
        if action == "prepare":
            child.add_argument("--out", required=True, type=pathlib.Path)
    for action in ("validate", "what-if", "deploy"):
        child = sub.add_parser(action)
        child.add_argument("--plan", required=True, type=pathlib.Path)
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            result = prepare(args.config, args.artifact, args.out)
        elif args.action == "upload":
            result = upload(args.config, args.artifact)
        elif args.action == "resolve-image":
            result = resolve_image(args.config)
        else:
            result = run_azure(args.action, args.plan.resolve())
    except (ValueError, OSError, KeyError, json.JSONDecodeError, zipfile.BadZipFile, subprocess.CalledProcessError) as error:
        parser.exit(2, f"Stopped: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
