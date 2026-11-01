"""Unit and integration tests for runtime/thoxos_g.py (no QEMU required)."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))

import thoxos_g  # noqa: E402  (path set above)
from thoxos_g import (  # noqa: E402
    Config,
    EscapeFilter,
    SingleInstance,
    ThoxosGError,
    boot_commands,
    build_qemu_argv,
    controller_error,
    iommu_device,
    listed_domains,
    load_config,
    memory_mib,
    prepare_state,
    read_config_file,
    resolve_accel,
    resolve_cpu,
)

FAKE_QEMU = ROOT / "tests" / "fake_qemu.py"


def config(**overrides: str) -> Config:
    env = {key: value for key, value in overrides.items()}
    return load_config(env, config_file="/nonexistent/thoxos-g.conf")


class TestConfig:
    def test_defaults_are_valid(self) -> None:
        cfg = config()
        assert cfg.domain == "thoxos"
        assert cfg.image == "registry.thoxos.internal/thoxos/userspace:0.1.0"
        assert cfg.dns == "10.0.2.2"
        assert cfg.domain_memory_mib == 2048

    @pytest.mark.parametrize(
        ("key", "value"),
        [
            ("THOXOS_G_MEMORY", "4T"),
            ("THOXOS_G_MEMORY", "0G"),
            ("THOXOS_G_VOLUME_SIZE", "lots"),
            ("THOXOS_G_DOMAIN", "Thox OS"),
            ("THOXOS_G_DOMAIN", "x;shutdown"),
            ("THOXOS_G_DOMAIN", "a" * 26),
            ("THOXOS_G_IMAGE", "a b"),
            ("THOXOS_G_INIT", "sbin/init"),
            ("THOXOS_G_ACCEL", "hvf"),
            ("THOXOS_G_DNS", "registry.thoxos.internal"),
            ("THOXOS_G_DOMAIN_MEMORY_MIB", "64"),
            ("THOXOS_G_BOOT_TIMEOUT", "1"),
            ("THOXOS_G_CPU", "host;rm"),
            ("THOXOS_G_MODE", "desktop"),
        ],
    )
    def test_rejects_invalid_values(self, key: str, value: str) -> None:
        with pytest.raises(ThoxosGError):
            config(**{key: value})

    @pytest.mark.parametrize("memory", ["3G", "4G", "8G", "512M"])
    def test_vm_memory_stays_inside_identity_map(self, memory: str) -> None:
        with pytest.raises(ThoxosGError, match="identity-maps"):
            config(THOXOS_G_MEMORY=memory)

    def test_largest_identity_mapped_memory_accepted(self) -> None:
        assert config(THOXOS_G_MEMORY="2816M").memory == "2816M"

    def test_environment_overrides_file(self, tmp_path: Path) -> None:
        conf = tmp_path / "thoxos-g.conf"
        conf.write_text('# comment\nTHOXOS_G_MEMORY="2560M"\nTHOXOS_G_DOMAIN=lab\n')
        cfg = load_config({"THOXOS_G_DOMAIN": "demo"}, str(conf))
        assert cfg.memory == "2560M"
        assert cfg.domain == "demo"

    def test_unknown_setting_is_an_error(self, tmp_path: Path) -> None:
        conf = tmp_path / "thoxos-g.conf"
        conf.write_text("THOXOS_G_MEMRY=8G\n")
        with pytest.raises(ThoxosGError, match="unknown or malformed"):
            read_config_file(str(conf))

    def test_memory_mib(self) -> None:
        assert memory_mib("4G") == 4096
        assert memory_mib("512M") == 512


class TestHardwareProfile:
    def test_accel_auto(self) -> None:
        cfg = config()
        assert resolve_accel(cfg, lambda: True) == "kvm"
        assert resolve_accel(cfg, lambda: False) == "tcg"

    def test_forced_kvm_without_device_fails(self) -> None:
        with pytest.raises(ThoxosGError, match="/dev/kvm"):
            resolve_accel(config(THOXOS_G_ACCEL="kvm"), lambda: False)

    def test_cpu_keeps_required_features(self) -> None:
        assert resolve_cpu(config(), "kvm") == "host,+smep,+smap,+umip"
        assert resolve_cpu(config(), "tcg") == "max,+smep,+smap,+umip"
        assert resolve_cpu(config(THOXOS_G_CPU="Skylake-Client"), "kvm") == "Skylake-Client"

    def test_iommu_requests_48_bit_width(self) -> None:
        assert iommu_device("aw-bits=<uint8> - (default: 39)") == (
            "intel-iommu,intremap=off,aw-bits=48"
        )
        assert iommu_device("caching-mode=<bool>") == "intel-iommu,intremap=off"

    def test_argv_matches_validated_profile(self) -> None:
        cfg = config(THOXOS_G_STATE_DIR="/state")
        argv = build_qemu_argv(cfg, "kvm", "host", "/fw/code.fd", "intel-iommu,aw-bits=48")
        joined = " ".join(argv)
        assert "-machine q35,accel=kvm" in joined
        assert "-smp 1" in joined
        assert "virtio-blk-pci,drive=ginux-volume,disable-legacy=on,iommu_platform=on" in joined
        assert "virtio-net-pci,netdev=ginux-net,disable-legacy=on,iommu_platform=on" in joined
        assert "file=/state/volume.raw" in joined
        assert "fat:rw:/state/esp" in joined
        assert "readonly=on,file=/fw/code.fd" in joined
        assert "signal=off" in joined
        # No host port forwarding: nothing inside the guest is exposed.
        assert "hostfwd" not in joined


class TestControllerProtocol:
    def test_boot_commands_first_boot(self) -> None:
        cmds = boot_commands(config(), domain_exists=False)
        assert cmds == [
            "network set eth0 dns 10.0.2.2",
            "domain new thoxos",
            "domain set thoxos image=registry.thoxos.internal/thoxos/userspace:0.1.0 "
            "init=/sbin/init memory-mib=2048",
            "domain start thoxos --attach",
        ]

    def test_boot_commands_shell_domain(self) -> None:
        cmds = boot_commands(config(), domain_exists=False, shell=True)
        assert cmds[1] == "domain new thoxos-shell"
        assert "init=/usr/local/bin/thox-shell" in cmds[2]
        assert cmds[-1] == "domain start thoxos-shell --attach"

    def test_boot_commands_existing_domain(self) -> None:
        cmds = boot_commands(config(), domain_exists=True)
        assert "domain new thoxos" not in cmds
        assert cmds[-1] == "domain start thoxos --attach"

    def test_listed_domains_parses_table(self) -> None:
        output = (
            b"domain list\r\n"
            b"NAME            STATE       PERSONALITY  INIT        CPU  IMAGE\r\n"
            b"demo            configured  linux        /sbin/init  1    embedded://x\r\n"
            b"thoxos          running     linux        /sbin/init  1    registry.thoxos.internal/x\r\n"
        )
        assert listed_domains(output) == {"demo", "thoxos"}

    def test_listed_domains_empty_and_echo_ignored(self) -> None:
        assert listed_domains(b"domain list\r\ndomains: 0 configured\r\n") == set()

    def test_controller_error_detection(self) -> None:
        assert controller_error(b"domain set x a=1\r\ndomain: duplicate setting\r\n") == (
            "domain: duplicate setting"
        )
        assert controller_error(b"network set eth0 dns 1.2.3.4\r\neth0: DNS configured\r\n") is None
        assert controller_error(b"domains: 0 configured\r\n") is None


class TestEscapeFilter:
    def test_plain_bytes_pass_through(self) -> None:
        assert EscapeFilter().feed(b"ls -la\r") == (b"ls -la\r", False)

    def test_ctrl_a_x_quits(self) -> None:
        assert EscapeFilter().feed(b"ab\x01x") == (b"ab", True)

    def test_ctrl_a_twice_sends_one(self) -> None:
        assert EscapeFilter().feed(b"\x01\x01") == (b"\x01", False)

    def test_prefix_split_across_reads(self) -> None:
        escape = EscapeFilter()
        assert escape.feed(b"\x01") == (b"", False)
        assert escape.feed(b"X") == (b"", True)

    def test_ctrl_bracket_reaches_ginux(self) -> None:
        # Ctrl-] is Ginux's own detach key and must not be swallowed.
        assert EscapeFilter().feed(b"\x1d") == (b"\x1d", False)

    def test_unknown_follower_is_forwarded(self) -> None:
        assert EscapeFilter().feed(b"\x01a") == (b"\x01a", False)


class TestState:
    def test_prepare_state(self, tmp_path: Path) -> None:
        efi = tmp_path / "GINUX.EFI"
        efi.write_bytes(b"MZ-test")
        variables = tmp_path / "vars.fd"
        variables.write_bytes(b"\0" * 4096)
        cfg = config(
            THOXOS_G_EFI=str(efi),
            THOXOS_G_STATE_DIR=str(tmp_path / "state"),
            THOXOS_G_VOLUME_SIZE="2G",
        )
        os.makedirs(cfg.state_dir)
        prepare_state(cfg, str(variables))
        assert (Path(cfg.esp_dir) / "EFI" / "BOOT" / "BOOTX64.EFI").read_bytes() == b"MZ-test"
        assert Path(cfg.vars_path).read_bytes() == variables.read_bytes()
        volume = Path(cfg.volume_path)
        assert volume.stat().st_size == 2 * 1024**3
        assert stat.S_IMODE(volume.stat().st_mode) == 0o600

    def _stamp_setup(self, tmp_path: Path) -> tuple[Config, Path, Path]:
        efi = tmp_path / "GINUX.EFI"
        efi.write_bytes(b"MZ-test")
        variables = tmp_path / "vars.fd"
        variables.write_bytes(b"\0" * 4096)
        manifest = tmp_path / "userspace-manifest.json"
        manifest.write_bytes(b'{"layers": ["a"]}')
        cfg = config(
            THOXOS_G_EFI=str(efi),
            THOXOS_G_STATE_DIR=str(tmp_path / "state"),
            THOXOS_G_VOLUME_SIZE="1G",
            THOXOS_G_USERSPACE_MANIFEST=str(manifest),
        )
        os.makedirs(cfg.state_dir)
        return cfg, variables, manifest

    def test_new_volume_records_userspace(self, tmp_path: Path) -> None:
        cfg, variables, _ = self._stamp_setup(tmp_path)
        assert prepare_state(cfg, str(variables)) is False
        assert Path(cfg.volume_stamp_path).read_text().startswith("sha256:")

    def test_same_userspace_keeps_volume(self, tmp_path: Path) -> None:
        cfg, variables, _ = self._stamp_setup(tmp_path)
        prepare_state(cfg, str(variables))
        volume = Path(cfg.volume_path)
        with open(volume, "r+b") as handle:
            handle.write(b"cache")
        assert prepare_state(cfg, str(variables)) is False
        assert volume.read_bytes()[:5] == b"cache"

    def test_changed_userspace_replaces_volume(self, tmp_path: Path) -> None:
        cfg, variables, manifest = self._stamp_setup(tmp_path)
        prepare_state(cfg, str(variables))
        volume = Path(cfg.volume_path)
        with open(volume, "r+b") as handle:
            handle.write(b"cache")
        manifest.write_bytes(b'{"layers": ["b"]}')
        assert prepare_state(cfg, str(variables)) is True
        assert volume.read_bytes()[:5] == b"\0" * 5
        assert volume.stat().st_size == 1024**3
        assert stat.S_IMODE(volume.stat().st_mode) == 0o600

    def test_unstamped_volume_is_replaced(self, tmp_path: Path) -> None:
        cfg, variables, _ = self._stamp_setup(tmp_path)
        Path(cfg.volume_path).write_bytes(b"old cache from an earlier build")
        assert prepare_state(cfg, str(variables)) is True
        assert Path(cfg.volume_stamp_path).exists()

    def test_missing_manifest_keeps_volume(self, tmp_path: Path) -> None:
        cfg, variables, manifest = self._stamp_setup(tmp_path)
        manifest.unlink()
        Path(cfg.volume_path).write_bytes(b"cache")
        assert prepare_state(cfg, str(variables)) is False
        assert Path(cfg.volume_path).read_bytes() == b"cache"
        assert not Path(cfg.volume_stamp_path).exists()

    def test_prepare_state_requires_efi(self, tmp_path: Path) -> None:
        cfg = config(THOXOS_G_EFI=str(tmp_path / "missing.efi"), THOXOS_G_STATE_DIR=str(tmp_path))
        with pytest.raises(ThoxosGError, match="GINUX.EFI|missing.efi"):
            prepare_state(cfg, str(tmp_path / "vars"))

    def test_single_instance_lock(self, tmp_path: Path) -> None:
        lock = str(tmp_path / "console.lock")
        with SingleInstance(lock):
            with pytest.raises(ThoxosGError, match="already running"):
                with SingleInstance(lock):
                    pass
        with SingleInstance(lock):
            pass


class TestConsoleEndToEnd:
    """Drive the real console path against tests/fake_qemu.py over a pty."""

    def run_console(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        until: tuple[str, ...] = ("Welcome to ThoxOS", "login:"),
        extra_args: tuple[str, ...] = (),
        **env: str,
    ) -> tuple[int, list[str]]:
        efi = tmp_path / "GINUX.EFI"
        efi.write_bytes(b"MZ")
        code = tmp_path / "code.fd"
        code.write_bytes(b"\0" * 16)
        variables = tmp_path / "vars.fd"
        variables.write_bytes(b"\0" * 16)
        log = tmp_path / "qemu.log"
        settings = {
            "THOXOS_G_QEMU": str(FAKE_QEMU),
            "THOXOS_G_EFI": str(efi),
            "THOXOS_G_STATE_DIR": str(tmp_path / "state"),
            "THOXOS_G_OVMF_CODE": str(code),
            "THOXOS_G_OVMF_VARS": str(variables),
            "THOXOS_G_ACCEL": "tcg",
            "THOXOS_G_VOLUME_SIZE": "1G",
            "THOXOS_G_BOOT_TIMEOUT": "20",
            "FAKE_QEMU_LOG": str(log),
            **env,
        }
        for key, value in settings.items():
            monkeypatch.setenv(key, value)
        args = ["--config", str(tmp_path / "none.conf"), "console", "--quiet", *extra_args]
        for pattern in until:
            args += ["--until", pattern]
        status = thoxos_g.main(args)
        lines = log.read_text().splitlines() if log.exists() else []
        return status, lines

    def test_first_boot_creates_and_starts_domain(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        status, lines = self.run_console(tmp_path, monkeypatch)
        assert status == 0
        commands = [line[4:] for line in lines if line.startswith("CMD ")]
        assert commands == [
            "domain list",
            "network set eth0 dns 10.0.2.2",
            "domain new thoxos",
            "domain set thoxos image=registry.thoxos.internal/thoxos/userspace:0.1.0 "
            "init=/sbin/init memory-mib=2048",
            "domain start thoxos --attach",
        ]
        argv = next(line for line in lines if line.startswith("ARGV "))
        assert "aw-bits=48" in argv and "accel=tcg" in argv

    def test_existing_domain_is_reused(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        status, lines = self.run_console(tmp_path, monkeypatch, FAKE_EXISTING_DOMAIN="thoxos")
        assert status == 0
        assert "CMD domain new thoxos" not in lines

    def test_controller_refusal_fails_cleanly(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        status, _ = self.run_console(tmp_path, monkeypatch, FAKE_REJECT="domain set")
        assert status == 1
        assert "controller refused" in capsys.readouterr().err


class TestAnsiStripper:
    def test_systemd_welcome_line(self) -> None:
        stripper = thoxos_g.AnsiStripper()
        raw = (
            b"\x1b[0;1;39mWelcome to \x1b[0m\x1b[38;2;5;164;81mThoxOS 0.1.0 Ginux Edition"
            b"\x1b[0m\x1b[0;1;39m!\x1b[0m"
        )
        assert stripper.feed(raw) == b"Welcome to ThoxOS 0.1.0 Ginux Edition!"

    def test_sequences_split_across_reads(self) -> None:
        stripper = thoxos_g.AnsiStripper()
        pieces = [b"ok \x1b", b"[0;3", b"2m green\x1b[0", b"m done"]
        assert b"".join(stripper.feed(piece) for piece in pieces) == b"ok  green done"

    def test_osc_and_two_byte_escapes(self) -> None:
        stripper = thoxos_g.AnsiStripper()
        assert stripper.feed(b"a\x1b]0;title\x07b\x1b]2;t\x1b\\c\x1b=d") == b"abcd"


class TestShellMode:
    def test_shell_domain_reaches_prompt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        status, lines = TestConsoleEndToEnd().run_console(
            tmp_path, monkeypatch, until=("ThoxOS 0.1.0 Ginux Edition", "]# "), extra_args=("--shell",)
        )
        assert status == 0
        commands = [line[4:] for line in lines if line.startswith("CMD ")]
        assert "domain new thoxos-shell" in commands
        assert commands[-1] == "domain start thoxos-shell --attach"


    def test_mode_setting_selects_shell_domain(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        status, lines = TestConsoleEndToEnd().run_console(
            tmp_path, monkeypatch, until=("]# ",), THOXOS_G_MODE="shell"
        )
        assert status == 0
        assert "CMD domain start thoxos-shell --attach" in lines
