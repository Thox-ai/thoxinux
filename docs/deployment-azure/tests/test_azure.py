"""Focused offline safety/packaging contracts; no Azure resource is contacted."""
import base64
import io
import json
import pathlib
import shutil
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

AZURE = pathlib.Path(__file__).resolve().parents[1]
SOURCE = AZURE.parent
sys.path.insert(0, str(AZURE))
import bootstrap
import cloud_init
import deploy
import generate_template
import package_release


def public_key():
    fields = (b"ssh-ed25519", bytes(range(32)))
    data = b"".join(len(field).to_bytes(4, "big") + field for field in fields)
    return "ssh-ed25519 " + base64.b64encode(data).decode() + " offline-fixture"


def fixture_release(root):
    for relative in package_release.REQUIRED:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if relative in ("ssd-module/install_host.py", "ssd-module/preflight.py"):
            shutil.copyfile(SOURCE / relative, path)
        elif relative.endswith("GINUX.EFI"):
            path.write_bytes(b"MZ" + b"offline fixture, not a kernel" * 8)
        elif relative.endswith("run-vm.sh"):
            path.write_text("#!/bin/bash\nprintf 'offline fixture only\\n'\n")
        elif relative.endswith("SOURCE_MANIFEST.json"):
            path.write_text('{}\n')
        else:
            path.write_text("offline fixture only\n")
    artifacts = root / "module-ginux/artifacts"
    payload = {name: package_release.digest((artifacts / name).read_bytes()) for name in ("GINUX.EFI", "GINUX_LICENSE", "GINUX_NOTICE")}
    patch_name = "thox-banner.patch"
    patch = root / "module-ginux/patches" / patch_name
    patch.write_text("offline fixture patch\n")
    (patch.parent / "series").write_text("# offline test fixture\n" + patch_name + "\n")
    patches = {patch_name: package_release.digest(patch.read_bytes())}
    source_manifest = {"source_patches": patches, "upstream": {"commit": "2" * 40, "cargo_lock_sha256": "3" * 64}}
    (root / "module-ginux/SOURCE_MANIFEST.json").write_text(json.dumps(source_manifest) + "\n")
    (artifacts / "build-receipt.json").write_text(json.dumps({"artifacts": payload, "source_patches": patches, "upstream_commit": "2" * 40, "cargo_lock_sha256": "3" * 64, "banner_patch_sha256": patches[patch_name]}) + "\n")
    (artifacts / "SHA256SUMS").write_text("".join(package_release.digest((artifacts / name).read_bytes()) + "  " + name + "\n" for name in ("GINUX.EFI", "build-receipt.json", "GINUX_LICENSE", "GINUX_NOTICE")))


def rewrite_zip(data, mutate):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        files = {info.filename: archive.read(info) for info in archive.infolist()}
    mutate(files)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return output.getvalue()


class AzureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.source = self.root / "source"
        fixture_release(self.source)
        self.artifact = self.root / "release.zip"
        self.info = package_release.package(self.source, self.artifact, "1" * 40)
        self.data = self.artifact.read_bytes()
        self.key = self.root / "public.pub"
        self.key.write_text(public_key())
        self.config = json.loads((AZURE / "deployment.example.json").read_text())
        self.config.update(subscription_id="11111111-2222-4333-8444-555555555555", image_version="24.04.202610010", ssh_public_key_path=str(self.key))
        self.config_path = self.root / "deployment.json"
        self.write_config()

    def write_config(self):
        self.config_path.write_text(json.dumps(self.config))

    def test_release_is_deterministic_and_bounded(self):
        other = self.root / "other.zip"
        info = package_release.package(self.source, other, "1" * 40)
        self.assertEqual(info["sha256"], self.info["sha256"])
        self.assertLess(info["bytes"], bootstrap.MAX_DOWNLOAD)

    def test_release_refuses_overwrite(self):
        with self.assertRaisesRegex(ValueError, "already exists"):
            package_release.package(self.source, self.artifact, "1" * 40)

    def test_release_refuses_unrelated_payload_changes(self):
        (self.source / "module-ginux/artifacts/GINUX.EFI").write_bytes(b"MZchanged")
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            package_release.package(self.source, self.root / "bad.zip", "1" * 40)

    def test_release_refuses_patch_map_missing_stale_or_extra_entries(self):
        for relative in ("module-ginux/SOURCE_MANIFEST.json", "module-ginux/artifacts/build-receipt.json"):
            path = self.source / relative
            original = json.loads(path.read_text())
            for patches in ({}, {"thox-banner.patch": "0" * 64}, {**original["source_patches"], "extra.patch": "0" * 64}):
                changed = {**original, "source_patches": patches}
                path.write_text(json.dumps(changed))
                with self.subTest(relative=relative, patches=patches), self.assertRaisesRegex(ValueError, "source_patches"):
                    package_release.package(self.source, self.root / "bad.zip", "1" * 40)
            path.write_text(json.dumps(original))

    def test_release_refuses_changed_patch_bytes_and_unlisted_patch(self):
        patch = self.source / "module-ginux/patches/thox-banner.patch"
        original = patch.read_bytes()
        patch.write_text("changed patch\n")
        with self.assertRaisesRegex(ValueError, "source_patches"):
            package_release.package(self.source, self.root / "bad.zip", "1" * 40)
        patch.write_bytes(original)
        (patch.parent / "unlisted.patch").write_text("unlisted\n")
        with self.assertRaisesRegex(ValueError, "exactly match"):
            package_release.package(self.source, self.root / "bad.zip", "1" * 40)

    def test_release_refuses_unsafe_or_duplicate_patch_series(self):
        series = self.source / "module-ginux/patches/series"
        for content in ("../escape.patch\n", "thox-banner.patch\nthox-banner.patch\n", "# empty\n", "missing.patch\n"):
            series.write_text(content)
            with self.subTest(series=content), self.assertRaisesRegex(ValueError, "series"):
                package_release.package(self.source, self.root / "bad.zip", "1" * 40)

    def test_release_refuses_upstream_or_cargo_lock_provenance_mismatch(self):
        path = self.source / "module-ginux/SOURCE_MANIFEST.json"
        original = json.loads(path.read_text())
        for field, value in (("commit", "4" * 40), ("cargo_lock_sha256", "5" * 64)):
            changed = json.loads(json.dumps(original))
            changed["upstream"][field] = value
            path.write_text(json.dumps(changed))
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "does not match build receipt"):
                package_release.package(self.source, self.root / "bad.zip", "1" * 40)
        path.write_text(json.dumps(original))

    def test_release_refuses_optional_stale_banner_digest(self):
        path = self.source / "module-ginux/artifacts/build-receipt.json"
        changed = json.loads(path.read_text())
        changed["banner_patch_sha256"] = "0" * 64
        path.write_text(json.dumps(changed))
        with self.assertRaisesRegex(ValueError, "banner patch digest"):
            package_release.package(self.source, self.root / "bad.zip", "1" * 40)

    def test_release_extracts_only_verified_manifest_files(self):
        out = self.root / "verified"
        manifest = bootstrap.extract_release(self.data, out, self.info["build_receipt_sha256"])
        self.assertEqual(manifest["source_commit"], "1" * 40)
        self.assertTrue((out / "module-ginux/artifacts/GINUX.EFI").is_file())
        self.assertFalse((out / ".agents").exists())

    def test_release_refuses_path_traversal(self):
        data = rewrite_zip(self.data, lambda files: files.update({"../escape": b"no"}))
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            bootstrap.extract_release(data, self.root / "out", self.info["build_receipt_sha256"])
        self.assertFalse((self.root / "escape").exists())

    def test_release_refuses_unhashed_extra_file(self):
        data = rewrite_zip(self.data, lambda files: files.update({"surprise.sh": b"no"}))
        with self.assertRaisesRegex(ValueError, "coverage"):
            bootstrap.extract_release(data, self.root / "out", self.info["build_receipt_sha256"])

    def test_release_refuses_missing_efi(self):
        data = rewrite_zip(self.data, lambda files: files.pop("module-ginux/artifacts/GINUX.EFI"))
        with self.assertRaisesRegex(ValueError, "coverage"):
            bootstrap.extract_release(data, self.root / "out", self.info["build_receipt_sha256"])

    def test_release_refuses_tampered_script(self):
        data = rewrite_zip(self.data, lambda files: files.update({"module-ginux/scripts/run-vm.sh": b"bad"}))
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            bootstrap.extract_release(data, self.root / "out", self.info["build_receipt_sha256"])

    def test_release_refuses_symlinks(self):
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            info = zipfile.ZipInfo("release-manifest.json")
            info.external_attr = 0o120777 << 16
            archive.writestr(info, b"/etc/passwd")
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            bootstrap.extract_release(output.getvalue(), self.root / "out", self.info["build_receipt_sha256"])

    def test_release_refuses_duplicate_members(self):
        output = io.BytesIO(self.data)
        with zipfile.ZipFile(output, "a") as archive:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                archive.writestr("release-manifest.json", b"{}")
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            bootstrap.extract_release(output.getvalue(), self.root / "out", self.info["build_receipt_sha256"])

    def test_release_binds_the_selected_receipt(self):
        with self.assertRaisesRegex(ValueError, "receipt mismatch"):
            bootstrap.extract_release(self.data, self.root / "out", "0" * 64)

    def test_artifact_url_refuses_sas_and_offsite_credentials(self):
        for url in ("http://a.blob.core.windows.net/c/x", "https://evil.example/c/x", "https://user:pass@abc.blob.core.windows.net/c/x", "https://abc.blob.core.windows.net/c/x?sig=secret", "https://abc.blob.core.windows.net/c/%2e%2e/x"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                bootstrap.validate_url(url)

    def test_authorization_redirect_is_not_followed(self):
        self.assertIsNone(bootstrap.NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://evil.example"))

    def test_config_rejects_default_subscription_and_latest_image(self):
        for field, value in (("subscription_id", "00000000-0000-0000-0000-000000000000"), ("image_version", "latest")):
            config = self.config.copy()
            config[field] = value
            self.config_path.write_text(json.dumps(config))
            with self.subTest(field=field), self.assertRaises(ValueError):
                deploy.load_config(self.config_path)

    def test_private_ssh_cannot_open_to_internet_or_broad_vnet(self):
        for cidr in ("0.0.0.0/0", "10.0.0.0/8", "192.168.0.0/16"):
            self.config.update(enable_private_ssh=True, admin_source_cidr=cidr)
            self.write_config()
            with self.subTest(cidr=cidr), self.assertRaises(ValueError):
                deploy.load_config(self.config_path)

    def test_bastion_requires_distinct_subnet_and_matching_ssh_rule(self):
        self.config.update(enable_bastion=True)
        self.write_config()
        with self.assertRaisesRegex(ValueError, "requires private SSH"):
            deploy.load_config(self.config_path)
        self.config.update(enable_private_ssh=True, bastion_subnet_prefix="10.42.1.0/26")
        self.write_config()
        with self.assertRaisesRegex(ValueError, "distinct"):
            deploy.load_config(self.config_path)
        self.config.update(bastion_subnet_prefix="10.42.0.0/26")
        self.write_config()
        self.assertTrue(deploy.load_config(self.config_path)["enable_bastion"])

    def test_public_key_rejects_private_and_truncated_material(self):
        for key in ("-----BEGIN PRIVATE KEY-----", "ssh-ed25519 " + base64.b64encode(b"x" * 40).decode()):
            with self.subTest(key=key), self.assertRaises(ValueError):
                deploy.validate_public_key(key)
        self.assertEqual(deploy.validate_public_key(public_key()), public_key())

    def test_prepare_is_local_and_pins_all_plan_bytes(self):
        out = self.root / "plan"
        with mock.patch.object(deploy, "command", side_effect=AssertionError("No Azure calls during prepare")):
            result = deploy.prepare(self.config_path, self.artifact, out)
        self.assertEqual(result["status"], "prepared-not-deployed")
        self.assertEqual(result["source_artifact"]["sha256"], self.info["sha256"])
        self.assertIn("sha256/" + self.info["sha256"], result["artifact_url"])
        deploy.check_plan(out)
        (out / "parameters.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "Plan file changed"):
            deploy.check_plan(out)

    def test_cloud_init_has_no_sas_or_token_and_fits_custom_data(self):
        out = self.root / "plan"
        deploy.prepare(self.config_path, self.artifact, out)
        cloud = (out / "cloud-init.txt").read_text()
        config = json.loads(cloud.split("\n", 1)[1])
        self.assertFalse(config["ssh_pwauth"])
        self.assertTrue(config["disable_root"])
        self.assertNotIn("?sig=", cloud)
        self.assertNotIn("Bearer ", cloud)
        self.assertIn("__IDENTITY_CLIENT_ID__", cloud)
        self.assertLessEqual(len(base64.b64encode(cloud.encode())), 65535)

    def test_deploy_refuses_unowned_resources_and_inventory_errors(self):
        with mock.patch.object(deploy, "command", return_value=[{"name": "existing-vm", "tags": {}}]):
            with self.assertRaisesRegex(ValueError, "ownership"):
                deploy.check_target_ownership(self.config)
        with mock.patch.object(deploy, "command", return_value=None):
            with self.assertRaisesRegex(ValueError, "inventory"):
                deploy.check_target_ownership(self.config)
        with mock.patch.object(deploy, "command", side_effect=OSError("inventory failed")):
            with self.assertRaises(OSError):
                deploy.check_target_ownership(self.config)
        for resources in ([], [{"tags": {"thox-project": "thoxos-ginux", "thox-deployment": self.config["vm_name"]}}]):
            with mock.patch.object(deploy, "command", return_value=resources):
                deploy.check_target_ownership(self.config)

    def test_arm_checked_in_file_matches_generator(self):
        self.assertEqual(json.loads((AZURE / "azuredeploy.json").read_text()), generate_template.template())

    def test_arm_keeps_vm_private_and_explicit_outbound(self):
        template = generate_template.template()
        resources = template["resources"]
        nic = next(x for x in resources if x["type"] == "Microsoft.Network/networkInterfaces")
        self.assertNotIn("publicIPAddress", json.dumps(nic))
        self.assertTrue(nic["properties"]["enableAcceleratedNetworking"])
        self.assertFalse(template["variables"]["hostSubnets"][0]["properties"]["defaultOutboundAccess"])
        self.assertIn("natGateway", template["variables"]["hostSubnets"][0]["properties"])
        self.assertEqual(template["variables"]["denyRule"][0]["properties"]["access"], "Deny")

    def test_arm_trusted_launch_and_container_scoped_reader(self):
        template = generate_template.template()
        vm = next(x for x in template["resources"] if x["type"] == "Microsoft.Compute/virtualMachines")
        nested = next(x for x in template["resources"] if x["type"] == "Microsoft.Resources/deployments")
        role = nested["properties"]["template"]["resources"][0]
        self.assertEqual(vm["properties"]["securityProfile"]["securityType"], "TrustedLaunch")
        self.assertTrue(vm["properties"]["securityProfile"]["uefiSettings"]["secureBootEnabled"])
        self.assertEqual(nested["resourceGroup"], "[parameters('artifactStorageResourceGroup')]")
        self.assertIn("storageAccounts/blobServices/containers", role["scope"])
        self.assertEqual(nested["properties"]["expressionEvaluationOptions"]["scope"], "inner")
        self.assertEqual(template["variables"]["blobReaderRoleId"], "2a2b9908-6ea1-4ae2-8e65-a410df84e7d1")
        self.assertIn("artifactStorageResourceGroup", " ".join(vm["dependsOn"]))

    def test_azure_cli_always_selects_explicit_subscription(self):
        with mock.patch.object(deploy.shutil, "which", return_value="/fixture/az"), mock.patch.object(deploy.subprocess, "run", return_value=mock.Mock(stdout="{}")) as run:
            deploy.command(["account", "show"], self.config)
        command = run.call_args.args[0]
        self.assertIn("--subscription", command)
        self.assertEqual(command[command.index("--subscription") + 1], self.config["subscription_id"])
        self.assertFalse(run.call_args.kwargs.get("shell", False))

    def test_storage_checks_do_not_disable_firewall_or_public_access(self):
        with mock.patch.object(deploy, "command", return_value={"publicNetworkAccess": "Disabled"}):
            with self.assertRaisesRegex(ValueError, "network-disabled"):
                deploy.check_storage(self.config)
        with mock.patch.object(deploy, "command", side_effect=[{}, {"properties": {"publicAccess": "blob"}}]):
            with self.assertRaisesRegex(ValueError, "container is public"):
                deploy.check_storage(self.config)
        with mock.patch.object(deploy, "command", return_value={"publicNetworkAccess": "Enabled", "networkRuleSet": {"defaultAction": "Deny"}}):
            with self.assertRaisesRegex(ValueError, "firewall denies"):
                deploy.check_storage(self.config)


if __name__ == "__main__":
    unittest.main()
