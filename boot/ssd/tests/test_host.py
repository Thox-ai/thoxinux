import contextlib
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE))
import install_host
import preflight
import build_external_ssd


class HostTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.kit = self.root / "kit"
        (self.kit / "artifacts").mkdir(parents=True)
        (self.kit / "scripts").mkdir()
        (self.kit / "scripts/run-vm.sh").write_text("#!/bin/bash\nprintf 'fixture only\\n'\n")
        files = {"GINUX.EFI": b"MZfixture only", "GINUX_LICENSE": b"Apache fixture", "GINUX_NOTICE": b"Attribution fixture"}
        for name, value in files.items():
            (self.kit / "artifacts" / name).write_bytes(value)
        hashes = {name: hashlib.sha256(value).hexdigest() for name, value in files.items()}
        (self.kit / "artifacts/build-receipt.json").write_text(json.dumps({"artifacts": hashes}))
        self.receipt_hash = install_host.sha256(self.kit / "artifacts/build-receipt.json")
        self.refresh_checksums()

    def tearDown(self):
        self.temp.cleanup()

    def refresh_checksums(self):
        artifacts = self.kit / "artifacts"
        (artifacts / "SHA256SUMS").write_text("".join(f"{install_host.sha256(artifacts / name)}  {name}\n" for name in sorted(install_host.REQUIRED)))

    def test_stage_installs_readable_files_without_launch_or_packages(self):
        stage = self.root / "stage"
        with patch.object(install_host, "install_dependencies", side_effect=AssertionError("No package action")), patch.object(preflight, "collect", side_effect=AssertionError("No host qualification")):
            result = install_host.install(self.kit, self.receipt_hash, stage)
        self.assertTrue(result["staging_only"])
        self.assertFalse(result["physical_write"])
        self.assertFalse(result["vm_started"])
        self.assertIn('"$@"', (stage / "usr/local/bin/thox-ginux").read_text())
        self.assertIn("Terminal=true", (stage / "usr/share/applications/thox-ginux.desktop").read_text())
        self.assertEqual((stage / "opt/thox/ginux").stat().st_mode & 0o777, 0o755)
        self.assertEqual((stage / "opt/thox/ginux/artifacts/GINUX.EFI").read_bytes(), b"MZfixture only")

    def test_wrong_receipt_refuses_before_creating_target(self):
        stage = self.root / "stage"
        with self.assertRaisesRegex(ValueError, "receipt digest mismatch"):
            install_host.install(self.kit, "0" * 64, stage)
        self.assertFalse(stage.exists())

    def test_corrupted_artifact_refuses(self):
        (self.kit / "artifacts/GINUX.EFI").write_bytes(b"MZcorrupted")
        with self.assertRaisesRegex(ValueError, "Artifact digest mismatch"):
            install_host.verify_kit(self.kit, self.receipt_hash)

    def test_rewritten_checksums_cannot_override_pinned_receipt(self):
        (self.kit / "artifacts/GINUX.EFI").write_bytes(b"MZattacker bytes")
        self.refresh_checksums()
        with self.assertRaisesRegex(ValueError, "not bound to pinned build receipt"):
            install_host.verify_kit(self.kit, self.receipt_hash)

    def test_symlink_payload_refuses(self):
        path = self.kit / "artifacts/GINUX_NOTICE"
        path.unlink()
        path.symlink_to(self.root / "elsewhere")
        with self.assertRaisesRegex(ValueError, "non-regular"):
            install_host.verify_kit(self.kit, self.receipt_hash)

    def test_checksum_traversal_refuses(self):
        with (self.kit / "artifacts/SHA256SUMS").open("a") as target:
            target.write("0" * 64 + "  ../../unsafe\n")
        with self.assertRaisesRegex(ValueError, "unsafe"):
            install_host.verify_kit(self.kit, self.receipt_hash)

    def test_existing_install_is_preserved(self):
        stage = self.root / "stage"
        install_host.install(self.kit, self.receipt_hash, stage)
        marker = stage / "opt/thox/ginux/keep-me"
        marker.write_text("owner data")
        with self.assertRaisesRegex(ValueError, "Existing path preserved"):
            install_host.install(self.kit, self.receipt_hash, stage)
        self.assertEqual(marker.read_text(), "owner data")

    def test_stage_refuses_system_actions(self):
        with self.assertRaisesRegex(ValueError, "ordinary files only"):
            install_host.install(self.kit, self.receipt_hash, self.root / "stage", dependencies=True)

    def test_symlinked_destination_parent_refuses(self):
        stage = self.root / "stage"
        stage.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        (stage / "opt").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlinked installation parent"):
            install_host.install(self.kit, self.receipt_hash, stage)
        self.assertEqual(list(outside.iterdir()), [])

    def test_encrypted_root_finds_usb_disk(self):
        blocks = [{"path": "/dev/sdb", "type": "disk", "tran": "usb", "rota": False, "children": [{"type": "part", "children": [{"type": "crypt", "maj:min": "253:0"}]}]}]
        self.assertEqual(preflight.root_disks(blocks, "253:0")[0]["tran"], "usb")

    def test_unknown_root_does_not_qualify(self):
        self.assertEqual(preflight.root_disks([], "0:1"), [])

    def test_read_only_preflight_with_command_stubs(self):
        def fake(args):
            if args[0] == "lsblk":
                return {"available": True, "exit_code": 0, "output": json.dumps({"blockdevices": [{"path": "/dev/sdb", "type": "disk", "tran": "usb", "rota": False, "maj:min": "8:16"}]})}
            if args[0] == "findmnt":
                return {"available": True, "exit_code": 0, "output": "8:16"}
            return {"available": False, "exit_code": None, "output": ""}
        with patch.object(preflight, "command", side_effect=fake):
            result = preflight.collect()
        self.assertTrue(result["usb_nonrotational_root_candidate"])
        self.assertEqual(result["mutations"], [])

    def test_image_package_overlay_is_additive_and_requires_unique_marker(self):
        original = "[Content]\nPackages=\n    base\n[Validation]\nChecksum=no\n"
        changed = build_external_ssd.add_guest_packages(original)
        self.assertIn("    qemu-system-x86\n    edk2-ovmf\n", changed)
        self.assertIn("    base\n[Validation]\nChecksum=no\n", changed)
        with self.assertRaisesRegex(ValueError, "package section changed"):
            build_external_ssd.add_guest_packages(original + "Packages=\n")

    def test_vendored_writer_matches_original_git_blobs(self):
        root = MODULE / "vendor/windows-writer"
        manifest = json.loads((root / "SOURCE-MANIFEST.json").read_text())
        self.assertFalse(manifest["modified"])
        for item in manifest["files"]:
            path = root / item["name"]
            self.assertEqual(build_external_ssd.git_blob(path), item["git_blob_sha"])
            self.assertEqual(install_host.sha256(path), item["sha256"])

    def test_isolated_build_checkout_gets_payload_without_changing_source(self):
        source = self.root / "source"
        source.mkdir()
        def git(*args):
            return subprocess.run(["git", "-C", str(source), *args], text=True, capture_output=True, check=True).stdout.strip()
        git("init")
        original = "[Content]\nPackages=\n    base\n[Validation]\nChecksum=no\n"
        config = source / "image/x86_64/mkosi.conf"
        config.parent.mkdir(parents=True)
        config.write_text(original)
        git("add", ".")
        git("-c", "user.name=THOX fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "isolated fixture only")
        commit = git("rev-parse", "HEAD")
        with patch.object(build_external_ssd, "HOST_COMMIT", commit), patch.object(build_external_ssd, "SOURCE_BLOBS", {"image/x86_64/mkosi.conf": build_external_ssd.git_blob(config)}):
            record, receipt = build_external_ssd.prepare(source, self.root / "worktree", self.kit, self.receipt_hash)
        self.assertEqual(git("status", "--porcelain"), "")
        self.assertEqual(config.read_text(), original)
        self.assertEqual(record["status"], "prepared-not-built")
        self.assertIn("blocked-layout-mismatch", record["windows_writer_admission"])
        self.assertTrue((self.root / "worktree/image/common/overlay/opt/thox/ginux/artifacts/GINUX.EFI").is_file())
        self.assertTrue(receipt.is_file())
        self.assertTrue((self.root / "worktree/.git").is_dir())
        cloned_config = (self.root / "worktree/.git/config").read_text()
        self.assertIn(str(source), cloned_config)
        self.assertNotIn("fixture@example.invalid", cloned_config)


if __name__ == "__main__":
    unittest.main()
