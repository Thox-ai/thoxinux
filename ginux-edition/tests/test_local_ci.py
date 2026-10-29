"""Tests for scripts/local-ci.sh: the no-Actions CI runner and its commit status."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "local-ci.sh"

pytestmark = pytest.mark.skipif(shutil.which("git") is None or shutil.which("make") is None,
                                reason="needs git and make")


def module(tmp_path: Path, recipe: str = "echo '5 passed, 1 skipped in 0.1s'") -> Path:
    """A throwaway git checkout holding the script and a stand-in Makefile."""
    mod = tmp_path / "module"
    (mod / "scripts").mkdir(parents=True)
    shutil.copy(SCRIPT, mod / "scripts" / "local-ci.sh")
    (mod / "Makefile").write_text(f"test:\n\t{recipe}\n")
    (mod / ".gitignore").write_text("build/\n")
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
    for argv in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "commit", "-q", "-m", "init"],
                 ["git", "remote", "add", "origin", "https://github.com/acme/widget.git"]):
        subprocess.run(argv, cwd=mod, check=True, env=env)
    return mod


def gh_stub(tmp_path: Path) -> tuple[dict, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "gh.log"
    stub = bin_dir / "gh"
    stub.write_text(f'#!/bin/bash\nprintf "%s\\n" "$@" >> {log}\n')
    stub.chmod(0o755)
    return dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}"), log


def run(mod: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", "scripts/local-ci.sh", *args], cwd=mod, capture_output=True, text=True,
                          env=env or dict(os.environ))


def head(mod: Path) -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=mod, capture_output=True, text=True,
                          check=True).stdout.strip()


def test_dry_run_names_the_status_call(tmp_path):
    mod = module(tmp_path)
    r = run(mod, "--dry-run", "--report", "--full")
    assert r.returncode == 0, r.stderr
    assert f"repos/acme/widget/statuses/{head(mod)}" in r.stdout
    assert "context=thox/local-ci" in r.stdout
    assert "desktop theme generation" in r.stdout
    assert not (mod / "build").exists()  # nothing ran


def test_passing_run_writes_its_result(tmp_path):
    mod = module(tmp_path)
    r = run(mod)
    assert r.returncode == 0, r.stdout + r.stderr
    result = json.loads((mod / "build" / "local-ci" / f"{head(mod)[:12]}.json").read_text())
    assert result["state"] == "success"
    assert result["description"].startswith("5 passed, 1 skipped; shellcheck clean (local, ")


def test_failing_checks_fail_the_run(tmp_path):
    mod = module(tmp_path, recipe="exit 3")
    r = run(mod)
    assert r.returncode == 1
    result = json.loads((mod / "build" / "local-ci" / f"{head(mod)[:12]}.json").read_text())
    assert result["state"] == "failure"


def test_report_posts_the_status_for_head(tmp_path):
    mod = module(tmp_path)
    env, log = gh_stub(tmp_path)
    r = run(mod, "--report", env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    call = log.read_text().splitlines()
    assert call[:4] == ["api", f"repos/acme/widget/statuses/{head(mod)}", "--method", "POST"]
    assert "state=success" in call and "context=thox/local-ci" in call


def test_report_refuses_a_dirty_tree(tmp_path):
    mod = module(tmp_path)
    (mod / "Makefile").write_text("test:\n\techo changed\n")
    env, log = gh_stub(tmp_path)
    r = run(mod, "--report", env=env)
    assert r.returncode == 1 and "clean tree" in r.stderr
    assert not log.exists()


def test_unknown_option_is_a_usage_error(tmp_path):
    assert run(module(tmp_path), "--bogus").returncode == 2


def test_missing_shellcheck_is_not_reported_as_clean(tmp_path):
    mod = module(tmp_path, recipe="echo '5 passed in 0.1s'; echo 'shellcheck not installed; skipped'")
    assert run(mod).returncode == 0
    result = json.loads((mod / "build" / "local-ci" / f"{head(mod)[:12]}.json").read_text())
    assert "shellcheck not installed" in result["description"] and "clean" not in result["description"]


# ------------------------------------------------------------ pre-push gate

HOOK_INSTALLER = ROOT / "scripts" / "install-pre-push-hook.sh"


def repo_with_module(tmp_path: Path, recipe: str) -> tuple[Path, Path, dict]:
    """A repository whose module lives in ginux-edition/, plus a bare remote."""
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
    top = tmp_path / "repo"
    mod = top / "ginux-edition"
    (mod / "scripts").mkdir(parents=True)
    shutil.copy(SCRIPT, mod / "scripts" / "local-ci.sh")
    shutil.copy(HOOK_INSTALLER, mod / "scripts" / "install-pre-push-hook.sh")
    (mod / "Makefile").write_text(f"test:\n\t{recipe}\n")
    (top / ".gitignore").write_text("build/\n")
    (top / "other.txt").write_text("outside the module\n")
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    for argv in (["git", "init", "-q", "-b", "main"], ["git", "add", "-A"], ["git", "commit", "-q", "-m", "init"],
                 ["git", "remote", "add", "origin", str(remote)]):
        subprocess.run(argv, cwd=top, check=True, env=env)
    return top, mod, env


def test_gate_blocks_a_red_push_and_lets_a_green_one_through(tmp_path):
    top, mod, env = repo_with_module(tmp_path, "exit 3")
    r = subprocess.run(["bash", "scripts/install-pre-push-hook.sh"], cwd=mod, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "thoxos-ginux local CI gate" in (top / ".git" / "hooks" / "pre-push").read_text()
    push = subprocess.run(["git", "push", "-q", "origin", "main"], cwd=top, capture_output=True, text=True, env=env)
    assert push.returncode != 0 and "FAIL make test" in push.stdout + push.stderr
    (mod / "Makefile").write_text("test:\n\techo '3 passed in 0.1s'\n")
    subprocess.run(["git", "commit", "-qam", "green"], cwd=top, check=True, env=env)
    push = subprocess.run(["git", "push", "-q", "origin", "main"], cwd=top, capture_output=True, text=True, env=env)
    assert push.returncode == 0, push.stdout + push.stderr


def test_gate_skips_pushes_outside_the_module(tmp_path):
    top, mod, env = repo_with_module(tmp_path, "echo '3 passed in 0.1s'")
    subprocess.run(["bash", "scripts/install-pre-push-hook.sh"], cwd=mod, check=True, capture_output=True)
    subprocess.run(["git", "push", "-q", "origin", "main"], cwd=top, check=True, capture_output=True, env=env)
    (mod / "Makefile").write_text("test:\n\texit 3\n")  # red, but committed only in the next push's base
    subprocess.run(["git", "commit", "-qam", "red module"], cwd=top, check=True, env=env)
    subprocess.run(["git", "push", "-q", "--no-verify", "origin", "main"], cwd=top, check=True, env=env)
    (top / "other.txt").write_text("changed outside\n")
    subprocess.run(["git", "commit", "-qam", "outside"], cwd=top, check=True, env=env)
    push = subprocess.run(["git", "push", "-q", "origin", "main"], cwd=top, capture_output=True, text=True, env=env)
    assert push.returncode == 0, push.stdout + push.stderr  # module untouched by this push: no gate


def test_installer_leaves_a_foreign_hook_alone(tmp_path):
    top, mod, _env = repo_with_module(tmp_path, "true")
    hook = top / ".git" / "hooks" / "pre-push"
    hook.write_text("#!/bin/sh\necho mine\n")
    r = subprocess.run(["bash", "scripts/install-pre-push-hook.sh"], cwd=mod, capture_output=True, text=True)
    assert r.returncode == 1 and hook.read_text() == "#!/bin/sh\necho mine\n"
