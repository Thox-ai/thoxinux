import importlib.util
import pathlib
import subprocess
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts/prepare_source.py"
spec = importlib.util.spec_from_file_location("prepare_source", SCRIPT)
prepare_source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare_source)


class SourcePreparationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name) / "source"
        self.root.mkdir()
        self.patches = pathlib.Path(self.tmp.name) / "patches"
        self.patches.mkdir()
        def git(*args):
            return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.DEVNULL).decode().strip()
        self.git = git
        git("init", "-q")
        git("config", "user.name", "Fixture")
        git("config", "user.email", "fixture@example.invalid")
        (self.root / "kernel.rs").write_text("guarded original\n")
        (self.root / "other.rs").write_text("untouched\n")
        git("add", ".")
        git("commit", "-qm", "fixture")
        self.commit = git("rev-parse", "HEAD")
        (self.root / "kernel.rs").write_text("guarded corrected\n")
        (self.patches / "fix.patch").write_bytes(subprocess.check_output(["git", "-C", str(self.root), "diff"]))
        git("checkout", "--", "kernel.rs")
        (self.patches / "series").write_text("fix.patch\n")

    def prepare(self):
        return prepare_source.prepare(self.root, self.commit, self.patches)

    def test_pristine_apply_and_idempotent_repeat(self):
        self.assertEqual(self.prepare(), ["fix.patch"])
        self.assertEqual((self.root / "kernel.rs").read_text(), "guarded corrected\n")
        self.assertEqual(self.prepare(), ["fix.patch"])

    def test_unrelated_edit_is_rejected_without_overwriting_it(self):
        (self.root / "other.rs").write_text("operator work\n")
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertEqual((self.root / "other.rs").read_text(), "operator work\n")

    def test_missing_guarded_source_is_rejected(self):
        (self.root / "kernel.rs").unlink()
        with self.assertRaises(ValueError):
            self.prepare()

    def test_untracked_source_is_rejected(self):
        (self.root / "unreviewed.rs").write_text("unexpected\n")
        with self.assertRaises(ValueError):
            self.prepare()

    def test_patch_path_traversal_is_rejected(self):
        (self.patches / "series").write_text("../fix.patch\n")
        with self.assertRaises(ValueError):
            self.prepare()

    def test_source_revision_mismatch_is_rejected(self):
        with self.assertRaises(ValueError):
            prepare_source.prepare(self.root, "0" * 40, self.patches)

    def test_generated_boot_catalog_is_only_allowed_regenerated_file(self):
        p = self.root / "boot/efi/src/generated_boot.rs"
        p.parent.mkdir(parents=True)
        p.write_text("generated original\n")
        self.git("add", ".")
        self.git("commit", "-qm", "generated fixture")
        self.commit = self.git("rev-parse", "HEAD")
        p.write_text("regenerated output\n")
        self.prepare()
        self.assertEqual(p.read_text(), "regenerated output\n")


if __name__ == "__main__":
    unittest.main()
