#!/usr/bin/env python3
"""Apply a reviewed patch series only to a pristine or exact known checkout."""
import pathlib
import re
import subprocess
import tempfile


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args])


def paths(root):
    return [p.decode() for p in git(root, "ls-files", "-z").split(b"\0") if p]


def patch_paths(patch_dir):
    series = patch_dir / "series"
    names = series.read_text().splitlines() if series.exists() else ["thox-banner.patch"]
    names = [n.strip() for n in names if n.strip() and not n.lstrip().startswith("#")]
    if not names or len(names) != len(set(names)):
        raise ValueError("Patch series must be nonempty and unique")
    for name in names:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.patch", name):
            raise ValueError("Unsafe patch-series entry")
        p = patch_dir / name
        if not p.is_file() or p.is_symlink():
            raise ValueError("Missing ordinary patch: " + name)
    return [patch_dir / n for n in names]


def prepare(root, commit, patch_dir):
    root, patch_dir = root.resolve(), patch_dir.resolve()
    if git(root, "rev-parse", "HEAD").decode().strip() != commit:
        raise ValueError("Source commit mismatch")
    patches = patch_paths(patch_dir)
    generated = "boot/efi/src/generated_boot.rs"
    tracked = paths(root)
    with tempfile.TemporaryDirectory(prefix="thox-reviewed-source-") as directory:
        expected = pathlib.Path(directory) / "expected"
        subprocess.run(["git", "clone", "-q", "--shared", "--no-checkout", str(root), str(expected)], check=True)
        subprocess.run(["git", "-C", str(expected), "checkout", "-q", "--detach", commit], check=True)
        originals = {p: (expected / p).read_bytes() for p in tracked if p != generated}
        for patch in patches:
            subprocess.run(["git", "-C", str(expected), "apply", "--index", str(patch)], check=True)
        expected_paths = set(paths(expected))
        if set(originals) - expected_paths:
            raise ValueError("This build profile does not remove tracked source files")
        expected_bytes = {p: (expected / p).read_bytes() for p in expected_paths if p != generated}
        unknown = git(root, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0")
        unknown = {p.decode() for p in unknown if p}
        if unknown - expected_paths:
            raise ValueError("Refusing untracked source files")
        if any((root / p).is_symlink() for p in expected_bytes):
            raise ValueError("Refusing symlinked source files")
        pristine = not unknown and all((root / p).is_file() and (root / p).read_bytes() == b for p, b in originals.items())
        if pristine:
            for patch in patches:
                subprocess.run(["git", "-C", str(root), "apply", str(patch)], check=True)
        for p, expected_data in expected_bytes.items():
            if not (root / p).is_file() or (root / p).read_bytes() != expected_data:
                raise ValueError("Source differs from reviewed patch series: " + p)
        actual_paths = set(paths(root)) | {p.decode() for p in git(root, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0") if p}
        if actual_paths != expected_paths:
            raise ValueError("Tracked source inventory differs from reviewed patch series")
    return [p.name for p in patches]


if __name__ == "__main__":
    import sys
    try:
        applied = prepare(pathlib.Path(sys.argv[1]), sys.argv[2], pathlib.Path(sys.argv[3]))
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit("Refused source preparation: " + str(error))
    print("Verified reviewed source patches: " + ", ".join(applied))
