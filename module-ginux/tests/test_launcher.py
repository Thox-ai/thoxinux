"""Guard tests using inert EFI/firmware fixtures; these never boot a VM."""
import hashlib
import os
import pathlib
import shlex
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.artifacts = self.root / "artifacts"
        self.artifacts.mkdir()
        self.state = self.root / "state"
        self.qemu = self.root / "qemu-fixture"
        self.qemu.write_text("#!/bin/sh\nexit 99\n")
        self.qemu.chmod(0o755)
        for name in ("GINUX.EFI", "build-receipt.json", "GINUX_LICENSE", "GINUX_NOTICE"):
            (self.artifacts / name).write_bytes(b"inert test fixture\n")
        (self.artifacts / "SHA256SUMS").write_text("".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
            for path in sorted(self.artifacts.iterdir())
        ))
        self.code = self.root / "CODE.fd"
        self.vars = self.root / "VARS.fd"
        self.code.write_bytes(b"inert firmware")
        self.vars.write_bytes(b"inert firmware")
        self.env = {**os.environ, "QEMU_SYSTEM_X86_64": str(self.qemu),
                    "OVMF_CODE": str(self.code), "OVMF_VARS": str(self.vars),
                    "QEMU_ACCEL": "tcg", "GINUX_MEMORY": "2G"}

    def run_launcher(self, *extra):
        return subprocess.run([str(ROOT / "scripts/run-vm.sh"),
                               "--artifact-dir", str(self.artifacts),
                               "--state-dir", str(self.state), *extra],
                              env=self.env, text=True, capture_output=True)

    def test_dry_command_preserves_validated_hardware_and_creates_no_state(self):
        result = self.run_launcher("--print-command")
        self.assertEqual(result.returncode, 0, result.stderr)
        args = shlex.split(result.stdout)
        self.assertIn("q35,accel=tcg", args)
        self.assertIn("max,+smep,+smap,+umip", args)
        self.assertIn("intel-iommu,intremap=off,aw-bits=48", args)
        self.assertIn("virtio-blk-pci,drive=ginux-volume,disable-legacy=on,iommu_platform=on,serial=ginux-volume", args)
        self.assertIn("virtio-net-pci,netdev=ginux-net,disable-legacy=on,iommu_platform=on,mac=52:54:00:12:34:56,addr=0x3", args)
        self.assertEqual(args[args.index("-smp") + 1], "1")
        self.assertFalse(any("hostfwd" in arg or "/dev/sd" in arg or "vfio" in arg for arg in args))
        self.assertFalse(self.state.exists())

    def test_tampered_efi_rejected_before_launch(self):
        (self.artifacts / "GINUX.EFI").write_bytes(b"tampered")
        result = self.run_launcher("--print-command")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAILED", result.stderr)
        self.assertFalse(self.state.exists())

    def test_missing_efi_checksum_rejected(self):
        manifest = self.artifacts / "SHA256SUMS"
        manifest.write_text("".join(line for line in manifest.read_text().splitlines(keepends=True)
                                    if not line.rstrip().endswith("GINUX.EFI")))
        result = self.run_launcher("--print-command")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must cover", result.stderr)

    def test_duplicate_checksum_rejected(self):
        manifest = self.artifacts / "SHA256SUMS"
        manifest.write_text(manifest.read_text() + manifest.read_text().splitlines(keepends=True)[0])
        result = self.run_launcher("--print-command")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate", result.stderr)

    def test_manifest_traversal_rejected(self):
        manifest = self.artifacts / "SHA256SUMS"
        manifest.write_text(manifest.read_text().replace("  GINUX.EFI", "  ../GINUX.EFI"))
        result = self.run_launcher("--print-command")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsafe entry", result.stderr)

    def test_unknown_accelerator_rejected(self):
        self.env["QEMU_ACCEL"] = "kvm,dirty-ring-size=4096"
        self.assertEqual(self.run_launcher("--print-command").returncode, 2)

    def test_qemu_path_option_injection_rejected(self):
        result = self.run_launcher("--state-dir", str(self.root / "bad,readonly=on"), "--print-command")
        self.assertEqual(result.returncode, 2)

    def test_mismatched_firmware_configuration_rejected(self):
        self.env["OVMF_VARS"] = "/missing/vars.fd"
        result = self.run_launcher("--print-command")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("matching pair", result.stderr)

    def test_invalid_memory_rejected(self):
        self.env["GINUX_MEMORY"] = "4G,slots=12"
        self.assertEqual(self.run_launcher("--print-command").returncode, 2)

    def test_high_memory_profile_rejected(self):
        for value in ("4G", "2049M", "99999999999999999999999999G"):
            with self.subTest(value=value):
                self.env["GINUX_MEMORY"] = value
                result = self.run_launcher("--print-command")
                self.assertEqual(result.returncode, 2)
                self.assertIn("at most 2G", result.stderr)

if __name__ == "__main__":
    unittest.main()
