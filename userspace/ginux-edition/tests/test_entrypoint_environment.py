"""Execute the entrypoint with service/privilege stubs, without Docker or QEMU.

The privilege stub records argv, then uses a genuinely empty child environment.
This checks shell argument forwarding, not actual setpriv or container isolation.
"""

from __future__ import annotations

import importlib.util
import json
import os
import pty
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "docker" / "entrypoint.sh"
SPEC = importlib.util.spec_from_file_location("entrypoint_runtime", ROOT / "runtime" / "thoxos_g.py")
assert SPEC and SPEC.loader
RUNTIME = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNTIME
SPEC.loader.exec_module(RUNTIME)

PROBE = (
    "import json,os,sys; "
    "print('CHILD:' + json.dumps({'environment':dict(os.environ),'command':sys.argv[1:]}))"
)


def executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(0o755)


@pytest.fixture
def harness(tmp_path: Path) -> dict[str, str]:
    binaries = tmp_path / "bin"
    binaries.mkdir()
    for name in ("dnsmasq", "registry", "chown", "python3"):
        executable(binaries / name, "#!/bin/sh\nexit 0\n")
    # setpriv itself is stubbed; execute env -i to observe the child's real
    # environment rather than deriving an expected result from the allowlist.
    executable(
        binaries / "setpriv",
        f"#!{sys.executable}\n"
        "import json,subprocess,sys\n"
        "arguments=sys.argv[1:]\n"
        "print('BOUNDARY:' + json.dumps(arguments), flush=True)\n"
        "boundary=arguments.index('--')\n"
        "assert '--reset-env' in arguments[:boundary]\n"
        "assert arguments[boundary+1]=='env'\n"
        "remaining=arguments[boundary+2:]\n"
        "assignments=[]\n"
        "while remaining and '=' in remaining[0]:\n"
        "    assignments.append(remaining.pop(0))\n"
        "assert remaining\n"
        "if remaining[0]=='/usr/bin/thoxos-g':\n"
        f"    remaining=[{sys.executable!r}, '-c', {PROBE!r}, *remaining]\n"
        "sys.exit(subprocess.run(['/usr/bin/env','-i',*assignments,*remaining]).returncode)\n",
    )
    # ttyd starts its configured child later. Execute exactly that suffix here
    # so web mode exercises the same shell-created argument vector.
    executable(
        binaries / "ttyd",
        f"#!{sys.executable}\n"
        "import subprocess,sys\n"
        "arguments=sys.argv[1:]\n"
        "sys.exit(subprocess.run(arguments[arguments.index('setpriv'):]).returncode)\n",
    )
    env = {key: value for key, value in os.environ.items() if not key.startswith("THOXOS_G_")}
    env.update(
        PATH=f"{binaries}:{os.environ['PATH']}",
        THOXOS_G_STATE_DIR=str(tmp_path / "state with spaces"),
        THOXOS_G_WEB_CREDENTIAL="web-user:web-password",
        THOXOS_G_UNSUPPORTED="must-not-cross",
        AWS_SECRET_ACCESS_KEY="unrelated-test-secret",
        TERM="test-terminal",
    )
    return env


def run_entrypoint(mode: str, env: dict[str, str]) -> tuple[dict, list[str]]:
    arguments = ["bash", str(ENTRYPOINT), mode]
    if mode == "exec":
        arguments.extend([sys.executable, "-c", PROBE, "exec argument with spaces"])
    master, slave = pty.openpty()
    try:
        result = subprocess.run(
            arguments, stdin=slave, capture_output=True, text=True, env=env, timeout=10
        )
    finally:
        os.close(slave)
        os.close(master)
    assert result.returncode == 0, result.stdout + result.stderr
    child = next(line[6:] for line in result.stdout.splitlines() if line.startswith("CHILD:"))
    boundary = next(
        line[9:] for line in result.stdout.splitlines() if line.startswith("BOUNDARY:")
    )
    return json.loads(child), json.loads(boundary)


@pytest.mark.parametrize("mode", ["console", "shell", "web", "selftest", "doctor", "qemu", "exec"])
def test_all_modes_forward_supported_settings_without_container_secrets(
    mode: str, harness: dict[str, str]
) -> None:
    configured = dict(RUNTIME.CONFIG_DEFAULTS)
    configured.update(
        THOXOS_G_STATE_DIR=harness["THOXOS_G_STATE_DIR"],
        THOXOS_G_MODE="shell",
        THOXOS_G_DOMAIN="configured-domain",
        THOXOS_G_DNS="10.0.2.9",
        THOXOS_G_IMAGE="registry.thoxos.internal/thoxos/userspace:configured",
        THOXOS_G_OVMF_CODE="/mounted firmware/code.fd",
        THOXOS_G_CPU="",  # An explicit empty setting must remain empty.
    )
    child, boundary = run_entrypoint(mode, dict(harness, **configured))
    actual = child["environment"]
    assert {key: actual.get(key) for key in configured} == configured
    assert actual["HOME"] == "/home/thoxos"
    assert actual["TERM"] == "test-terminal"
    assert actual["LANG"] == "C.UTF-8"
    assert "THOXOS_G_WEB_CREDENTIAL" not in actual
    assert "THOXOS_G_UNSUPPORTED" not in actual
    assert "AWS_SECRET_ACCESS_KEY" not in actual
    assert boundary[:4] == [
        "--reuid=thoxos", "--regid=thoxos", "--init-groups", "--inh-caps=-all"
    ]
    assert boundary[4:7] == ["--reset-env", "--", "env"]
    if mode == "shell":
        assert child["command"] == ["/usr/bin/thoxos-g", "console", "--shell"]
    if mode == "exec":
        assert child["command"] == ["exec argument with spaces"]


def test_unset_settings_are_left_to_runtime_defaults(harness: dict[str, str]) -> None:
    child, _ = run_entrypoint("exec", harness)
    forwarded = {
        key: value for key, value in child["environment"].items() if key.startswith("THOXOS_G_")
    }
    assert forwarded == {"THOXOS_G_STATE_DIR": harness["THOXOS_G_STATE_DIR"]}
