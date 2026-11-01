"""Exercise source preparation against real local Git repositories, without network."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ginux-source.sh"


def git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=Source Test", "-c", "user.email=source@example.invalid",
         "-C", str(path), *args],
        text=True, capture_output=True, check=True,
    )
    return result.stdout.strip()


@pytest.fixture
def source(tmp_path: Path) -> dict:
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    git(upstream, "init", "-q")
    (upstream / "kernel.rs").write_text("fn kernel() { base(); }\n")
    git(upstream, "add", "kernel.rs")
    git(upstream, "commit", "-qm", "upstream base")
    commit = git(upstream, "rev-parse", "HEAD")
    (upstream / "kernel.rs").write_text("fn kernel() { patched(); }\n")
    patch = git(upstream, "diff", "--binary") + "\n"
    git(upstream, "checkout", "--", "kernel.rs")
    module = tmp_path / "module"
    (module / "scripts").mkdir(parents=True)
    shutil.copy2(SCRIPT, module / "scripts/ginux-source.sh")
    (module / "patches-legacy-edition").mkdir()
    (module / "patches-legacy-edition/0001-kernel.patch").write_text(patch)
    (module / "upstream.lock").write_text(
        f"GINUX_REPO='{upstream}'\nGINUX_COMMIT={commit}\n"
    )
    return {"module": module, "upstream": upstream, "commit": commit,
            "dest": tmp_path / "prepared"}


def prepare(source: dict) -> subprocess.CompletedProcess:
    environment = {**os.environ, "GIT_ALLOW_PROTOCOL": "file",
                   "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
    return subprocess.run(
        ["bash", str(source["module"] / "scripts/ginux-source.sh"), str(source["dest"])],
        text=True, capture_output=True, env=environment, timeout=15,
    )


def initial(source: dict) -> Path:
    result = prepare(source)
    assert result.returncode == 0, result.stderr
    return source["dest"]


def test_prepares_exact_patch_and_reuses_without_touching_user_index(source):
    dest = initial(source)
    assert (dest / "kernel.rs").read_text() == "fn kernel() { patched(); }\n"
    assert git(dest, "rev-parse", "HEAD") == source["commit"]
    before = (dest / ".git/index").read_bytes()
    result = prepare(source)
    assert result.returncode == 0, result.stderr
    assert "verified" in result.stdout
    assert (dest / ".git/index").read_bytes() == before


def test_foreign_repository_is_never_deleted(source):
    dest = source["dest"]
    dest.mkdir()
    git(dest, "init", "-q")
    sentinel = dest / "uncommitted-important-work.txt"
    sentinel.write_text("preserve me\n")
    result = prepare(source)
    assert result.returncode != 0
    assert "not an owned" in result.stderr
    assert sentinel.read_text() == "preserve me\n"
    assert (dest / ".git").is_dir()


def test_stale_patch_marker_preserves_existing_source(source):
    dest = initial(source)
    before = (dest / "kernel.rs").read_bytes()
    (source["module"] / "patches-legacy-edition/0001-kernel.patch").write_text("different patch bytes\n")
    result = prepare(source)
    assert result.returncode != 0
    assert "different patch set" in result.stderr
    assert (dest / "kernel.rs").read_bytes() == before


def test_matching_marker_does_not_hide_changed_source(source):
    dest = initial(source)
    (dest / "kernel.rs").write_text("local uncommitted work\n")
    result = prepare(source)
    assert result.returncode != 0
    assert "changed source bytes" in result.stderr
    assert (dest / "kernel.rs").read_text() == "local uncommitted work\n"


def test_matching_marker_does_not_hide_staged_changes(source):
    dest = initial(source)
    (dest / "kernel.rs").write_text("staged local work\n")
    git(dest, "add", "kernel.rs")
    index = (dest / ".git/index").read_bytes()
    result = prepare(source)
    assert result.returncode != 0
    assert "changed source bytes" in result.stderr
    assert (dest / ".git/index").read_bytes() == index
    assert (dest / "kernel.rs").read_text() == "staged local work\n"


def test_matching_marker_does_not_hide_changed_head(source):
    dest = initial(source)
    git(dest, "add", "kernel.rs")
    git(dest, "commit", "-qm", "local commit")
    head = git(dest, "rev-parse", "HEAD")
    result = prepare(source)
    assert result.returncode != 0
    assert "HEAD differs" in result.stderr
    assert git(dest, "rev-parse", "HEAD") == head


def test_matching_marker_does_not_hide_changed_origin(source):
    dest = initial(source)
    git(dest, "remote", "set-url", "origin", "/different/local/repository")
    result = prepare(source)
    assert result.returncode != 0
    assert "origin differs" in result.stderr
    assert git(dest, "remote", "get-url", "origin") == "/different/local/repository"


def test_untracked_source_is_refused_and_preserved(source):
    dest = initial(source)
    extra = dest / "extra.rs"
    extra.write_text("untracked local source\n")
    result = prepare(source)
    assert result.returncode != 0
    assert "untracked source" in result.stderr
    assert extra.read_text() == "untracked local source\n"


def test_per_build_public_registry_root_is_allowed(source):
    dest = initial(source)
    certificate = dest / "services/network/certs/thoxos-local-root.pem"
    certificate.parent.mkdir(parents=True)
    certificate.write_text("per-build public root fixture\n")
    result = prepare(source)
    assert result.returncode == 0, result.stderr
    assert certificate.read_text() == "per-build public root fixture\n"


def test_symlink_destination_is_refused(source):
    dest = initial(source)
    link = dest.parent / "source-link"
    link.symlink_to(dest, target_is_directory=True)
    source["dest"] = link
    result = prepare(source)
    assert result.returncode != 0
    assert link.is_symlink()
    assert (dest / "kernel.rs").read_text() == "fn kernel() { patched(); }\n"


def test_failed_patch_leaves_no_partial_destination(source):
    (source["module"] / "patches-legacy-edition/0001-kernel.patch").write_text("invalid patch\n")
    result = prepare(source)
    assert result.returncode != 0
    assert not source["dest"].exists()
    assert not list(source["dest"].parent.glob(".ginux-source.*"))
