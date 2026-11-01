#!/usr/bin/env python3
"""Azure-only managed-identity fetch and installation; never accepts a SAS/token."""
import argparse
import hashlib
import json
import os
import pathlib
import pwd
import re
import shutil
import stat
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

MAX_DOWNLOAD = 100 * 1024 * 1024
MAX_EXPANDED = 128 * 1024 * 1024
REQUIRED = {
    "module-ginux/scripts/run-vm.sh", "module-ginux/artifacts/GINUX.EFI",
    "module-ginux/artifacts/build-receipt.json", "module-ginux/artifacts/SHA256SUMS",
    "module-ginux/artifacts/GINUX_LICENSE", "module-ginux/artifacts/GINUX_NOTICE",
    "module-ginux/SOURCE_MANIFEST.json", "module-ginux/patches/series", "ssd-module/install_host.py", "ssd-module/preflight.py",
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def validate_url(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not re.fullmatch(r"[a-z0-9]{3,24}\.blob\.core\.windows\.net", parsed.netloc):
        raise ValueError("Artifact URL must be an Azure public-cloud HTTPS Blob endpoint")
    if parsed.query or parsed.fragment or not parsed.path.startswith("/") or len(parsed.path.split("/")) < 3:
        raise ValueError("Artifact URL must identify one private blob without SAS/query/fragment")
    if any(part in (".", "..") for part in urllib.parse.unquote(parsed.path).split("/")):
        raise ValueError("Artifact URL contains unsafe path segments")
    return url


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_blob(config):
    validate_url(config["artifact_url"])
    if not re.fullmatch(r"[0-9a-f]{64}", config["artifact_sha256"]):
        raise ValueError("Artifact SHA-256 is invalid")
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", config["identity_client_id"]):
        raise ValueError("Managed identity client ID was not resolved by ARM")
    query = urllib.parse.urlencode({"api-version": "2018-02-01", "resource": "https://storage.azure.com/", "client_id": config["identity_client_id"]})
    imds = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    blob = urllib.request.build_opener(NoRedirect())
    # RBAC propagation can take several minutes. No error body, token, request
    # headers or URL query is printed during retry.
    for attempt in range(24):
        try:
            request = urllib.request.Request("http://169.254.169.254/metadata/identity/oauth2/token?" + query, headers={"Metadata": "true"})
            with imds.open(request, timeout=15) as response:
                token_data = response.read(65536)
            token = json.loads(token_data)["access_token"]
            request = urllib.request.Request(config["artifact_url"], headers={"Authorization": "Bearer " + token, "x-ms-version": "2023-11-03"})
            with blob.open(request, timeout=60) as response:
                data = response.read(MAX_DOWNLOAD + 1)
            del token
            if len(data) > MAX_DOWNLOAD:
                raise ValueError("Artifact exceeds download limit")
            if sha(data) != config["artifact_sha256"]:
                raise ValueError("Artifact SHA-256 mismatch")
            return data
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError):
            if attempt == 23:
                raise RuntimeError("Managed-identity artifact fetch failed after bounded retry") from None
            time.sleep(min(5 + attempt * 2, 30))
    raise RuntimeError("Artifact unavailable")


def extract_release(data, destination, receipt_sha):
    if not re.fullmatch(r"[0-9a-f]{64}", receipt_sha):
        raise ValueError("Build receipt SHA-256 is invalid")
    import io
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)) or len(names) > 40:
            raise ValueError("Duplicate or excessive release entries")
        if sum(info.file_size for info in infos) > MAX_EXPANDED:
            raise ValueError("Expanded release exceeds limit")
        for info in infos:
            path = pathlib.PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            if path.is_absolute() or ".." in path.parts or "\\" in info.filename or info.is_dir() or stat.S_ISLNK(mode):
                raise ValueError("Unsafe release member")
            if info.filename != path.as_posix():
                raise ValueError("Noncanonical release path")
        if "release-manifest.json" not in names:
            raise ValueError("Missing release manifest")
        manifest = json.loads(archive.read("release-manifest.json"))
        if not isinstance(manifest, dict) or manifest.get("schema") != "thox.ginux.azure.release.v1":
            raise ValueError("Unsupported release schema")
        files = manifest.get("files")
        if not isinstance(files, dict) or set(names) != set(files) | {"release-manifest.json"} or not REQUIRED <= set(files):
            raise ValueError("Release manifest coverage mismatch")
        for name in files:
            if name not in REQUIRED and not re.fullmatch(r"module-ginux/patches/[A-Za-z0-9_.-]+\.patch", name):
                raise ValueError("Unexpected release member")
        if manifest.get("build_receipt_sha256") != receipt_sha or sha(archive.read("module-ginux/artifacts/build-receipt.json")) != receipt_sha:
            raise ValueError("Pinned build receipt mismatch")
        for name, expected in files.items():
            content = archive.read(name)
            if not re.fullmatch(r"[0-9a-f]{64}", expected) or sha(content) != expected:
                raise ValueError("Release file hash mismatch")
            path = destination / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            path.chmod(0o755 if name.endswith(".sh") else 0o644)
    return manifest


def install(config):
    if os.geteuid() != 0:
        raise ValueError("Azure bootstrap must run as root through cloud-init")
    data = fetch_blob(config)
    home = pathlib.Path("/var/lib/thox-ginux")
    try:
        account = pwd.getpwnam("thoxginux")
    except KeyError:
        subprocess.run(["useradd", "--system", "--user-group", "--create-home", "--home-dir", str(home), "--shell", "/bin/bash", "thoxginux"], check=True)
        account = pwd.getpwnam("thoxginux")
    if account.pw_uid == 0 or account.pw_dir != str(home) or home.is_symlink():
        raise ValueError("Existing thoxginux identity does not match the dedicated account contract")
    home.chmod(0o700)
    marker = pathlib.Path("/opt/thox/ginux/azure-install-receipt.json")
    if marker.exists():
        old = json.loads(marker.read_text())
        if old.get("artifact_sha256") != config["artifact_sha256"]:
            raise ValueError("Different installed release preserved; use a fresh VM/image for upgrades")
        if config.get("run_guest_smoke", True) and old.get("guest_smoke") != "passed":
            raise ValueError("Prior matching install did not pass guest smoke; inspect preserved evidence before retry")
        print("Matching Azure release already installed; preserved existing guest state")
        return
    with tempfile.TemporaryDirectory(prefix="thox-azure-release-") as temp:
        stage = pathlib.Path(temp)
        manifest = extract_release(data, stage, config["build_receipt_sha256"])
        subprocess.run(["python3", str(stage / "ssd-module/install_host.py"), "--kit", str(stage / "module-ginux"), "--expected-receipt-sha256", config["build_receipt_sha256"]], check=True)
    result = {"schema": "thox.ginux.azure.install.v1", "artifact_sha256": config["artifact_sha256"], "build_receipt_sha256": config["build_receipt_sha256"], "source_commit": manifest["source_commit"], "host_route": "Ubuntu Azure Gen2 VM with QEMU TCG guest", "native_ginux_azure_boot": "not_claimed", "cloud_deployment_acceptance": "requires external readback", "guest_smoke": "not_run"}
    if config.get("run_guest_smoke", True):
        log_dir = pathlib.Path("/var/log/thox-ginux")
        log_dir.mkdir(mode=0o750, exist_ok=True)
        smoke = subprocess.run(["python3", "/usr/local/lib/thox-ginux/smoke_guest.py", "--output", str(log_dir)], check=False)
        result["guest_smoke"] = "passed" if smoke.returncode == 0 else "failed; inspect guest-smoke.json/log"
    marker.write_text(json.dumps(result, indent=2) + "\n")
    marker.chmod(0o644)
    print("THOX Ginux Azure release installed; inspect receipt and cloud-init status before acceptance")
    if result["guest_smoke"].startswith("failed"):
        raise RuntimeError("Guest controller smoke failed; deployment acceptance is blocked")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=pathlib.Path)
    args = parser.parse_args()
    try:
        install(json.loads(args.config.read_text()))
    except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError, zipfile.BadZipFile) as error:
        # Avoid printing HTTP error responses or authorization context.
        parser.exit(2, f"THOX Azure bootstrap stopped: {type(error).__name__}: {error}\n")


if __name__ == "__main__":
    main()
