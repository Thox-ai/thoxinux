#!/usr/bin/env python3
"""thoxos-g: launcher and console driver for ThoxOS Ginux Edition.

ThoxOS Ginux Edition runs the Ginux kernel (GINUX.EFI) inside QEMU with the
exact hardware profile Ginux validates (Q35, OVMF, Intel IOMMU, virtio block
and network). This module owns that profile in one place and drives the Ginux
controller console so a ThoxOS domain boots with no typing:

    network set eth0 dns <THOXOS_G_DNS>
    domain new <domain>            (first boot only)
    domain set <domain> image=... init=/sbin/init memory-mib=...
    domain start <domain> --attach

After that the console belongs to the user. Ctrl-] stays with Ginux (it
detaches from the domain back to the controller, as upstream defines).
Ctrl-A then X leaves thoxos-g and powers the virtual machine off; Ctrl-A
Ctrl-A sends one literal Ctrl-A.

Subcommands
-----------
console        Boot and attach (interactive). --shell boots the `<domain>-shell`
               domain instead: same image, init /usr/local/bin/thox-shell, a
               ThoxOS shell on the console with no systemd.
               With one or more --until PATTERN
               it runs headless, exits 0 once every PATTERN has appeared in
               the console output in order, and is used by self-tests.
doctor         Check QEMU, firmware, acceleration, GINUX.EFI and the local
               registry/DNS services, and report each finding.
print-qemu     Print the QEMU command line that `console` would run.

Configuration: /etc/thoxos-g/thoxos-g.conf (KEY=VALUE), overridden by
environment variables of the same name. See CONFIG_DEFAULTS.

Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import errno
import fcntl
import hashlib
import ipaddress
import os
import pty
import re
import select
import shutil
import signal
import socket
import subprocess
import sys
import termios
import time
import tty
from dataclasses import dataclass
from typing import Callable, Iterable, Mapping, Optional, Sequence

CONFIG_FILE = "/etc/thoxos-g/thoxos-g.conf"

CONFIG_DEFAULTS: dict[str, str] = {
    "THOXOS_G_EFI": "/usr/lib/thoxos-g/GINUX.EFI",
    "THOXOS_G_STATE_DIR": "/var/lib/thoxos-g",
    "THOXOS_G_QEMU": "qemu-system-x86_64",
    "THOXOS_G_MEMORY": "2G",
    "THOXOS_G_VOLUME_SIZE": "64G",
    "THOXOS_G_ACCEL": "auto",
    "THOXOS_G_CPU": "",
    "THOXOS_G_OVMF_CODE": "",
    "THOXOS_G_OVMF_VARS": "",
    "THOXOS_G_IMAGE": "registry.thoxos.internal/thoxos/userspace:0.1.0",
    "THOXOS_G_DOMAIN": "thoxos",
    "THOXOS_G_DOMAIN_MEMORY_MIB": "2048",
    "THOXOS_G_INIT": "/sbin/init",
    "THOXOS_G_SHELL_INIT": "/usr/local/bin/thox-shell",
    "THOXOS_G_MODE": "system",
    "THOXOS_G_DNS": "10.0.2.2",
    "THOXOS_G_BOOT_TIMEOUT": "300",
    # Manifest of the userspace image this build serves. The Ginux OCI cache
    # is keyed by reference, so a changed manifest means a stale cache.
    "THOXOS_G_USERSPACE_MANIFEST": "/usr/share/thoxos-g/userspace-manifest.json",
}

OVMF_CODE_CANDIDATES = (
    "/usr/share/OVMF/OVMF_CODE_4M.fd",
    "/usr/share/OVMF/OVMF_CODE.fd",
    "/usr/share/edk2/ovmf/OVMF_CODE.fd",
    "/usr/share/edk2/x64/OVMF_CODE.4m.fd",
    "/usr/share/edk2/x64/OVMF_CODE.fd",
    "/usr/share/qemu/edk2-x86_64-code.fd",
)
OVMF_VARS_CANDIDATES = (
    "/usr/share/OVMF/OVMF_VARS_4M.fd",
    "/usr/share/OVMF/OVMF_VARS.fd",
    "/usr/share/edk2/ovmf/OVMF_VARS.fd",
    "/usr/share/edk2/x64/OVMF_VARS.4m.fd",
    "/usr/share/edk2/x64/OVMF_VARS.fd",
    "/usr/share/qemu/edk2-i386-vars.fd",
)

CONTROLLER_PROMPT = b"ginux> "
CONTROLLER_READY = b"Type 'help' for commands."
ESCAPE_PREFIX = 0x01  # Ctrl-A, then x/X quits; Ctrl-A Ctrl-A sends Ctrl-A
CONTROLLER_ERROR_PREFIXES = (b"domain: ", b"network: ")
# QEMU q35 keeps all guest RAM below 4 GiB only up to 0xB0000000 bytes.
MAX_VM_MEMORY_MIB = 2816
SIZE_PATTERN = re.compile(r"^[1-9][0-9]{0,5}[MG]$")
# 25 characters max so the "-shell" companion domain stays within 31.
DOMAIN_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,24}$")
IMAGE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._:/@-]{2,254}$")
INIT_PATTERN = re.compile(r"^/[A-Za-z0-9._/-]{1,254}$")
# QEMU 10.0.x was observed to fail Ginux virtio-net initialization (10.0.13).
KNOWN_BAD_QEMU = re.compile(r"^10\.0\.")


class ThoxosGError(Exception):
    """A failure the user can act on. Printed without a traceback."""


@dataclass(frozen=True)
class Config:
    """Validated runtime configuration."""

    efi: str
    state_dir: str
    qemu: str
    memory: str
    volume_size: str
    accel: str
    cpu: str
    ovmf_code: str
    ovmf_vars: str
    image: str
    domain: str
    domain_memory_mib: int
    init: str
    shell_init: str
    mode: str
    dns: str
    boot_timeout: float
    userspace_manifest: str = ""

    @property
    def esp_dir(self) -> str:
        return os.path.join(self.state_dir, "esp")

    @property
    def vars_path(self) -> str:
        return os.path.join(self.state_dir, "ovmf-vars.fd")

    @property
    def volume_path(self) -> str:
        return os.path.join(self.state_dir, "volume.raw")

    @property
    def lock_path(self) -> str:
        return os.path.join(self.state_dir, "console.lock")

    @property
    def volume_stamp_path(self) -> str:
        """Records which userspace manifest the volume's OCI cache was filled from."""
        return os.path.join(self.state_dir, "volume.userspace")


def read_config_file(path: str) -> dict[str, str]:
    """Parse KEY=VALUE lines. Missing file yields {}; malformed lines raise."""
    values: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.readlines()
    except FileNotFoundError:
        return values
    except OSError as error:
        raise ThoxosGError(f"cannot read {path}: {error.strerror}") from error
    for number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or key not in CONFIG_DEFAULTS:
            raise ThoxosGError(f"{path}:{number}: unknown or malformed setting {key!r}")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


def memory_mib(size: str) -> int:
    """Convert a validated size such as '4G' or '512M' to MiB."""
    number = int(size[:-1])
    return number * 1024 if size.endswith("G") else number


def load_config(env: Mapping[str, str], config_file: str = CONFIG_FILE) -> Config:
    """Merge defaults, the config file and the environment, then validate."""
    merged = dict(CONFIG_DEFAULTS)
    merged.update(read_config_file(config_file))
    merged.update({key: value for key, value in env.items() if key in CONFIG_DEFAULTS})

    def require(key: str, pattern: re.Pattern[str], what: str) -> str:
        value = merged[key].strip()
        if not pattern.fullmatch(value):
            raise ThoxosGError(f"{key}={value!r} is not a valid {what}")
        return value

    memory = require("THOXOS_G_MEMORY", SIZE_PATTERN, "size (e.g. 4G)")
    volume_size = require("THOXOS_G_VOLUME_SIZE", SIZE_PATTERN, "size (e.g. 64G)")
    domain = require("THOXOS_G_DOMAIN", DOMAIN_PATTERN, "domain name")
    image = require("THOXOS_G_IMAGE", IMAGE_PATTERN, "OCI image reference")
    init = require("THOXOS_G_INIT", INIT_PATTERN, "absolute init path")
    shell_init = require("THOXOS_G_SHELL_INIT", INIT_PATTERN, "absolute init path")
    mode = merged["THOXOS_G_MODE"].strip()
    if mode not in ("system", "shell"):
        raise ThoxosGError(f"THOXOS_G_MODE must be system or shell, got {mode!r}")

    accel = merged["THOXOS_G_ACCEL"].strip()
    if accel not in ("auto", "kvm", "tcg"):
        raise ThoxosGError(f"THOXOS_G_ACCEL must be auto, kvm or tcg, got {accel!r}")

    try:
        dns = str(ipaddress.IPv4Address(merged["THOXOS_G_DNS"].strip()))
    except ValueError as error:
        raise ThoxosGError(f"THOXOS_G_DNS must be an IPv4 address: {error}") from error

    try:
        domain_memory = int(merged["THOXOS_G_DOMAIN_MEMORY_MIB"])
    except ValueError as error:
        raise ThoxosGError("THOXOS_G_DOMAIN_MEMORY_MIB must be an integer") from error
    if not 256 <= domain_memory <= 65536:
        raise ThoxosGError("THOXOS_G_DOMAIN_MEMORY_MIB must be between 256 and 65536")
    if not 1024 <= memory_mib(memory) <= MAX_VM_MEMORY_MIB:
        raise ThoxosGError(
            f"THOXOS_G_MEMORY={memory} must be between 1G and {MAX_VM_MEMORY_MIB}M: Ginux "
            "identity-maps only the first 4 GiB, and QEMU q35 moves RAM above 4 GiB once a "
            "guest has more than 2.75 GiB, where Ginux stops with 'loaded EFI image is "
            "outside the identity map'"
        )

    try:
        boot_timeout = float(merged["THOXOS_G_BOOT_TIMEOUT"])
    except ValueError as error:
        raise ThoxosGError("THOXOS_G_BOOT_TIMEOUT must be a number of seconds") from error
    if not 10 <= boot_timeout <= 7200:
        raise ThoxosGError("THOXOS_G_BOOT_TIMEOUT must be between 10 and 7200 seconds")

    cpu = merged["THOXOS_G_CPU"].strip()
    if cpu and not re.fullmatch(r"[A-Za-z0-9_.,+=-]{1,128}", cpu):
        raise ThoxosGError(f"THOXOS_G_CPU={cpu!r} contains unsupported characters")

    return Config(
        efi=merged["THOXOS_G_EFI"].strip(),
        state_dir=merged["THOXOS_G_STATE_DIR"].strip(),
        qemu=merged["THOXOS_G_QEMU"].strip(),
        memory=memory,
        volume_size=volume_size,
        accel=accel,
        cpu=cpu,
        ovmf_code=merged["THOXOS_G_OVMF_CODE"].strip(),
        ovmf_vars=merged["THOXOS_G_OVMF_VARS"].strip(),
        image=image,
        domain=domain,
        domain_memory_mib=domain_memory,
        init=init,
        shell_init=shell_init,
        mode=mode,
        dns=dns,
        boot_timeout=boot_timeout,
        userspace_manifest=merged["THOXOS_G_USERSPACE_MANIFEST"].strip(),
    )


def first_existing(candidates: Iterable[str]) -> Optional[str]:
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None


def resolve_firmware(config: Config) -> tuple[str, str]:
    """Return (code, vars) firmware paths or raise with what was searched."""
    code = config.ovmf_code or first_existing(OVMF_CODE_CANDIDATES)
    variables = config.ovmf_vars or first_existing(OVMF_VARS_CANDIDATES)
    if not code or not os.path.isfile(code):
        raise ThoxosGError("OVMF code firmware not found; install ovmf or set THOXOS_G_OVMF_CODE")
    if not variables or not os.path.isfile(variables):
        raise ThoxosGError("OVMF variable store not found; install ovmf or set THOXOS_G_OVMF_VARS")
    return code, variables


def kvm_usable() -> bool:
    return os.uname().machine == "x86_64" and os.access("/dev/kvm", os.R_OK | os.W_OK)


def resolve_accel(config: Config, kvm_available: Callable[[], bool] = kvm_usable) -> str:
    if config.accel == "kvm":
        if not kvm_available():
            raise ThoxosGError("THOXOS_G_ACCEL=kvm but /dev/kvm is not usable by this user")
        return "kvm"
    if config.accel == "tcg":
        return "tcg"
    return "kvm" if kvm_available() else "tcg"


def resolve_cpu(config: Config, accel: str) -> str:
    """Ginux requires SMEP, SMAP and UMIP; mirror upstream's CPU choice."""
    if config.cpu:
        return config.cpu
    base = "host" if accel == "kvm" else "max"
    return f"{base},+smep,+smap,+umip"


def query_qemu(qemu: str, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            [qemu, *arguments], capture_output=True, text=True, timeout=30, check=False
        )
    except FileNotFoundError as error:
        raise ThoxosGError(f"{qemu} not found; install qemu-system-x86") from error
    except subprocess.TimeoutExpired as error:
        raise ThoxosGError(f"{qemu} {' '.join(arguments)} did not answer in 30 s") from error
    return completed.stdout + completed.stderr


def qemu_version(qemu: str) -> str:
    match = re.search(r"version (\d+\.\d+\.\d+)", query_qemu(qemu, "--version"))
    if not match:
        raise ThoxosGError(f"cannot read the QEMU version from {qemu} --version")
    return match.group(1)


def iommu_device(iommu_help: str) -> str:
    """Ginux needs 48-bit DMA remapping; QEMU before 9.1 defaults to 39."""
    if "aw-bits" in iommu_help:
        return "intel-iommu,intremap=off,aw-bits=48"
    return "intel-iommu,intremap=off"


def build_qemu_argv(
    config: Config, accel: str, cpu: str, ovmf_code: str, iommu: str
) -> list[str]:
    """The validated Ginux hardware profile, plus ThoxOS state paths."""
    return [
        config.qemu,
        "-machine", f"q35,accel={accel}",
        "-cpu", cpu,
        "-smp", "1",
        "-m", config.memory,
        "-display", "none",
        "-monitor", "none",
        "-chardev", "stdio,id=thoxos-console,signal=off",
        "-serial", "chardev:thoxos-console",
        "-no-reboot",
        "-net", "none",
        "-rtc", "base=utc",
        "-device", iommu,
        "-device", "virtio-blk-pci,drive=ginux-volume,disable-legacy=on,"
                   "iommu_platform=on,serial=ginux-volume",
        "-netdev", "user,id=ginux-net,restrict=off",
        "-device", "virtio-net-pci,netdev=ginux-net,disable-legacy=on,"
                   "iommu_platform=on,mac=52:54:00:12:34:56,addr=0x3",
        "-drive", f"if=none,id=ginux-volume,format=raw,file={config.volume_path}",
        "-drive", f"if=pflash,format=raw,readonly=on,file={ovmf_code}",
        "-drive", f"if=pflash,format=raw,file={config.vars_path}",
        "-drive", f"if=none,id=ginux-esp,format=raw,file=fat:rw:{config.esp_dir}",
        "-device", "ide-hd,drive=ginux-esp,bootindex=1",
    ]


def userspace_stamp(config: Config) -> Optional[str]:
    """sha256 of the served userspace manifest, or None when no manifest is installed."""
    if not config.userspace_manifest:
        return None
    try:
        with open(config.userspace_manifest, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
    except FileNotFoundError:
        return None
    except OSError as error:
        raise ThoxosGError(f"cannot read {config.userspace_manifest}: {error.strerror}") from error
    return f"sha256:{digest}"


def read_stamp(path: str) -> Optional[str]:
    try:
        with open(path, encoding="ascii") as handle:
            return handle.read().strip() or None
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError):
        return None


def write_stamp(path: str, stamp: str) -> None:
    temporary = f"{path}.tmp"
    with open(temporary, "w", encoding="ascii") as handle:
        handle.write(stamp + "\n")
    os.replace(temporary, path)


def prepare_state(config: Config, ovmf_vars: str) -> bool:
    """Create the ESP, a fresh OVMF variable store and the sparse volume.

    Returns True when an existing volume was replaced. Ginux answers
    `domain start` from its OCI cache by image reference alone, so after the
    served userspace changes (same tag, new content) the old volume would boot
    the old userspace. The volume holds only that cache and the controller's
    domain table, which the boot sequence recreates, so it is replaced.
    """
    if not os.path.isfile(config.efi):
        raise ThoxosGError(f"{config.efi} not found; build GINUX.EFI or set THOXOS_G_EFI")
    boot_dir = os.path.join(config.esp_dir, "EFI", "BOOT")
    os.makedirs(boot_dir, mode=0o750, exist_ok=True)
    shutil.copyfile(config.efi, os.path.join(boot_dir, "BOOTX64.EFI"))
    # Fresh NVRAM each boot keeps the boot order on the ESP disk.
    shutil.copyfile(ovmf_vars, config.vars_path)
    stamp = userspace_stamp(config)
    replaced = False
    if stamp is not None and os.path.exists(config.volume_path):
        if read_stamp(config.volume_stamp_path) != stamp:
            os.remove(config.volume_path)
            replaced = True
    if not os.path.exists(config.volume_path):
        size = memory_mib(config.volume_size) * 1024 * 1024
        with open(config.volume_path, "wb") as handle:
            handle.truncate(size)
        os.chmod(config.volume_path, 0o600)
    if stamp is not None:
        write_stamp(config.volume_stamp_path, stamp)
    return replaced


def target_domain(config: Config, shell: bool) -> tuple[str, str]:
    """(domain name, init) for system mode (systemd) or shell mode."""
    if shell:
        return f"{config.domain}-shell", config.shell_init
    return config.domain, config.init


def boot_commands(config: Config, domain_exists: bool, shell: bool = False) -> list[str]:
    """Controller commands that bring the ThoxOS domain up."""
    name, init = target_domain(config, shell)
    commands = [f"network set eth0 dns {config.dns}"]
    if not domain_exists:
        commands.append(f"domain new {name}")
    commands.append(
        f"domain set {name} image={config.image} init={init} "
        f"memory-mib={config.domain_memory_mib}"
    )
    commands.append(f"domain start {name} --attach")
    return commands


class AnsiStripper:
    """Streaming removal of terminal escape sequences for pattern matching.

    systemd colours its output (the ThoxOS name arrives wrapped in SGR codes),
    so expect() searches text with CSI, OSC and two-byte ESC sequences removed.
    Sequences split across reads are held until complete.
    """

    def __init__(self) -> None:
        self.pending = bytearray()

    def feed(self, data: bytes) -> bytes:
        text = self.pending + data
        self.pending = bytearray()
        out = bytearray()
        index = 0
        length = len(text)
        while index < length:
            byte = text[index]
            if byte != 0x1B:
                out.append(byte)
                index += 1
                continue
            if index + 1 >= length:
                self.pending = text[index:]
                break
            kind = text[index + 1]
            if kind == ord("["):  # CSI: parameters then a final byte 0x40-0x7E
                end = index + 2
                while end < length and not 0x40 <= text[end] <= 0x7E:
                    end += 1
                if end >= length:
                    self.pending = text[index:]
                    break
                index = end + 1
            elif kind == ord("]"):  # OSC: terminated by BEL or ESC backslash
                end = index + 2
                while end < length and text[end] != 0x07 and not (
                    text[end] == 0x1B and end + 1 < length and text[end + 1] == ord("\\")
                ):
                    end += 1
                if end >= length:
                    self.pending = text[index:]
                    break
                index = end + (1 if text[end] == 0x07 else 2)
            else:  # two-byte escape such as ESC = or ESC c
                index += 2
        return bytes(out)


class ConsoleSession:
    """A child process on a pseudo-terminal with expect-style helpers.

    The user sees raw output (colours intact); matching runs on the same
    stream with escape sequences removed.
    """

    def __init__(self, argv: Sequence[str], echo: Callable[[bytes], None]) -> None:
        self.argv = list(argv)
        self.echo = echo
        self.buffer = bytearray()
        self.before = b""
        self.exit_status: Optional[int] = None
        self.stripper = AnsiStripper()
        self.pid, self.fd = pty.fork()
        if self.pid == 0:  # child
            try:
                os.execvp(self.argv[0], self.argv)
            except OSError as error:
                os.write(2, f"thoxos-g: cannot run {self.argv[0]}: {error}\n".encode())
            os._exit(127)
        attributes = termios.tcgetattr(self.fd)
        attributes[3] &= ~termios.ECHO  # the controller echoes input itself
        # Keep console bytes exact: Ginux already sends CRLF, and the pty's
        # output processing would turn every line ending into CR CR LF.
        attributes[1] &= ~termios.OPOST
        termios.tcsetattr(self.fd, termios.TCSANOW, attributes)

    def _read_once(self, timeout: float) -> bool:
        """Read available output; False when the child closed the terminal."""
        ready, _, _ = select.select([self.fd], [], [], timeout)
        if not ready:
            return True
        try:
            data = os.read(self.fd, 65536)
        except OSError as error:
            if error.errno == errno.EIO:
                return False
            raise
        if not data:
            return False
        self.buffer.extend(self.stripper.feed(data))
        self.echo(data)
        return True

    def expect(self, patterns: Sequence[bytes], timeout: float) -> int:
        """Wait for the first of patterns after the read cursor; return its index.

        The buffer is consumed up to the end of the match, so the next expect
        only sees newer output. Output preceding the match is kept in
        self.before for callers that parse command responses.
        """
        deadline = time.monotonic() + timeout
        while True:
            hits = [(self.buffer.find(pattern), index) for index, pattern in enumerate(patterns)]
            hits = [(position, index) for position, index in hits if position >= 0]
            if hits:
                position, index = min(hits)
                self.before = bytes(self.buffer[:position])
                del self.buffer[: position + len(patterns[index])]
                return index
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ThoxosGError(
                    "timed out waiting for " + " or ".join(repr(p.decode()) for p in patterns)
                )
            if not self._read_once(min(remaining, 0.5)):
                raise ThoxosGError("the virtual machine exited before the expected output")

    def send_line(self, line: str) -> None:
        self.send(line.encode() + b"\r")

    def send(self, data: bytes) -> None:
        view = memoryview(data)
        while view:
            written = os.write(self.fd, view)
            view = view[written:]

    def alive(self) -> bool:
        if self.exit_status is not None:
            return False
        pid, status = os.waitpid(self.pid, os.WNOHANG)
        if pid:
            self.exit_status = os.waitstatus_to_exitcode(status)
            return False
        return True

    def terminate(self, grace: float = 5.0) -> int:
        """Stop the child; return its exit status (or -signal). Idempotent."""
        if self.exit_status is not None:
            return self.exit_status
        try:
            os.kill(self.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + grace
        while time.monotonic() < deadline:
            pid, status = os.waitpid(self.pid, os.WNOHANG)
            if pid:
                self.exit_status = os.waitstatus_to_exitcode(status)
                return self.exit_status
            time.sleep(0.1)
        try:
            os.kill(self.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        _, status = os.waitpid(self.pid, 0)
        self.exit_status = os.waitstatus_to_exitcode(status)
        return self.exit_status


def listed_domains(domain_list_output: bytes) -> set[str]:
    """Domain names from `domain list` output (first column, header skipped)."""
    names: set[str] = set()
    in_table = False
    for raw in domain_list_output.replace(b"\r", b"").split(b"\n"):
        fields = raw.split()
        if not fields:
            continue
        if fields[0] == b"NAME":
            in_table = True  # rows only follow the header; skip the echoed command
            continue
        if in_table and len(fields) >= 2 and DOMAIN_PATTERN.fullmatch(
            fields[0].decode("ascii", "replace")
        ):
            names.add(fields[0].decode("ascii"))
    return names


def controller_error(response: bytes) -> Optional[str]:
    """Return the first controller error line in a command response, if any."""
    for raw in response.replace(b"\r", b"").split(b"\n"):
        line = raw.strip()
        if line.startswith(CONTROLLER_ERROR_PREFIXES):
            return line.decode("utf-8", "replace")
    return None


def run_command(session: ConsoleSession, command: str, timeout: float = 60) -> bytes:
    """Send one controller command and return its response, or raise on error."""
    session.send_line(command)
    session.expect([CONTROLLER_PROMPT], timeout)
    response = session.before
    error = controller_error(response)
    if error:
        raise ThoxosGError(f"controller refused {command!r}: {error}")
    return response


def run_boot_sequence(session: ConsoleSession, config: Config, shell: bool = False) -> None:
    """Wait for the controller, then configure and attach the ThoxOS domain."""
    session.expect([CONTROLLER_READY], config.boot_timeout)
    session.expect([CONTROLLER_PROMPT], config.boot_timeout)
    name, _ = target_domain(config, shell)
    exists = name in listed_domains(run_command(session, "domain list"))
    commands = boot_commands(config, exists, shell)
    for command in commands[:-1]:
        run_command(session, command)
    session.send_line(commands[-1])


class EscapeFilter:
    """Ctrl-A prefix handling: Ctrl-A x quits, Ctrl-A Ctrl-A sends Ctrl-A.

    Any other byte after Ctrl-A is forwarded together with the Ctrl-A, so a
    stray prefix never swallows input.
    """

    def __init__(self) -> None:
        self.pending = False

    def feed(self, data: bytes) -> tuple[bytes, bool]:
        forward = bytearray()
        for byte in data:
            if self.pending:
                self.pending = False
                if byte in (ord("x"), ord("X")):
                    return bytes(forward), True
                if byte == ESCAPE_PREFIX:
                    forward.append(ESCAPE_PREFIX)
                else:
                    forward.extend((ESCAPE_PREFIX, byte))
            elif byte == ESCAPE_PREFIX:
                self.pending = True
            else:
                forward.append(byte)
        return bytes(forward), False


def interact(session: ConsoleSession) -> int:
    """Bridge the user's terminal and the console until Ctrl-A x or VM exit."""
    escape_filter = EscapeFilter()
    stdin = sys.stdin.fileno()
    interactive = os.isatty(stdin)
    saved = termios.tcgetattr(stdin) if interactive else None
    if interactive:
        tty.setraw(stdin)
    try:
        while True:
            ready, _, _ = select.select([session.fd, stdin], [], [])
            if session.fd in ready and not session._read_once(0):
                break
            if stdin in ready:
                data = os.read(stdin, 1024)
                if not data:
                    break
                forward, quit_requested = escape_filter.feed(data)
                if forward:
                    session.send(forward)
                if quit_requested:
                    break
    finally:
        if saved is not None:
            termios.tcsetattr(stdin, termios.TCSADRAIN, saved)
    sys.stdout.write("\r\nthoxos-g: console closed, stopping the virtual machine\r\n")
    sys.stdout.flush()
    return session.terminate()


class SingleInstance:
    """Advisory lock so two consoles never share one volume."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.handle: Optional[int] = None

    def __enter__(self) -> "SingleInstance":
        self.handle = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            os.close(self.handle)
            self.handle = None
            raise ThoxosGError(
                "another ThoxOS console is already running on this state directory"
            ) from error
        return self

    def __exit__(self, *exc: object) -> None:
        if self.handle is not None:
            fcntl.flock(self.handle, fcntl.LOCK_UN)
            os.close(self.handle)


def raise_interrupt(signum: int, frame: object) -> None:
    raise KeyboardInterrupt


def write_stdout(data: bytes) -> None:
    os.write(sys.stdout.fileno(), data)


def assemble(config: Config) -> list[str]:
    """Resolve firmware, acceleration and IOMMU, then build the QEMU argv."""
    code, _ = resolve_firmware(config)
    accel = resolve_accel(config)
    cpu = resolve_cpu(config, accel)
    iommu = iommu_device(query_qemu(config.qemu, "-device", "intel-iommu,help"))
    return build_qemu_argv(config, accel, cpu, code, iommu)


def command_console(
    config: Config, until: Sequence[str], quiet: bool, shell: bool = False
) -> int:
    os.makedirs(config.state_dir, mode=0o750, exist_ok=True)
    with SingleInstance(config.lock_path):
        argv = assemble(config)
        _, variables = resolve_firmware(config)
        if prepare_state(config, variables):
            sys.stderr.write(
                "thoxos-g: the ThoxOS userspace changed since this volume was filled; "
                "starting with a fresh Ginux cache volume\n"
            )
        echo = (lambda data: None) if quiet else write_stdout
        session = ConsoleSession(argv, echo)
        # QEMU runs in its own session (pty), so container or service stop
        # signals reach only this process; turn them into a clean VM stop.
        previous = signal.signal(signal.SIGTERM, raise_interrupt)
        try:
            run_boot_sequence(session, config, shell)
            if not until:
                return interact(session)
            for pattern in until:
                session.expect([pattern.encode()], config.boot_timeout)
                sys.stderr.write(f"thoxos-g: reached {pattern!r}\n")
            return 0
        except KeyboardInterrupt:
            return 130
        finally:
            signal.signal(signal.SIGTERM, previous)
            if session.alive():
                session.terminate()


def tcp_reachable(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def command_doctor(config: Config) -> int:
    """Report every prerequisite; exit 1 if any required one is missing."""
    failures = 0

    def report(ok: bool, label: str, detail: str, required: bool = True) -> None:
        nonlocal failures
        state = "ok  " if ok else ("FAIL" if required else "warn")
        if not ok and required:
            failures += 1
        print(f"{state} {label:<22} {detail}")

    try:
        version = qemu_version(config.qemu)
        bad = bool(KNOWN_BAD_QEMU.match(version))
        report(not bad, "qemu", version + (" (10.0.x fails Ginux virtio-net; use 10.2+)" if bad else ""))
    except ThoxosGError as error:
        report(False, "qemu", str(error))
    try:
        code, variables = resolve_firmware(config)
        report(True, "ovmf", f"{code} + {variables}")
    except ThoxosGError as error:
        report(False, "ovmf", str(error))
    report(kvm_usable(), "kvm", "/dev/kvm usable" if kvm_usable() else
           "not usable; TCG works but boots far slower", required=config.accel == "kvm")
    report(os.path.isfile(config.efi), "ginux efi", config.efi)
    report(tcp_reachable("127.0.0.1", 443), "local registry", "127.0.0.1:443")
    report(tcp_reachable("127.0.0.1", 53), "dns forwarder", "127.0.0.1:53 (tcp probe)")
    report(os.access(os.path.dirname(config.state_dir) or "/", os.W_OK) or
           os.access(config.state_dir, os.W_OK), "state dir", config.state_dir)
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="thoxos-g", description=__doc__.split("\n")[0])
    parser.add_argument("--config", default=CONFIG_FILE, help="configuration file")
    commands = parser.add_subparsers(dest="command", required=True)
    console = commands.add_parser("console", help="boot ThoxOS and attach the console")
    console.add_argument(
        "--until",
        action="append",
        default=[],
        help="run headless until this text appears (repeat for an ordered list), then exit 0",
    )
    console.add_argument("--quiet", action="store_true", help="do not echo console output")
    console.add_argument(
        "--shell",
        action="store_true",
        help="boot the shell domain (ThoxOS shell, no systemd); same as THOXOS_G_MODE=shell",
    )
    commands.add_parser("doctor", help="check prerequisites")
    commands.add_parser("print-qemu", help="print the QEMU command line")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(os.environ, args.config)
        if args.command == "console":
            shell = args.shell or config.mode == "shell"
            return command_console(config, args.until, args.quiet, shell)
        if args.command == "doctor":
            return command_doctor(config)
        if args.command == "print-qemu":
            print(" ".join(assemble(config)))
            return 0
        return 2
    except ThoxosGError as error:
        print(f"thoxos-g: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
