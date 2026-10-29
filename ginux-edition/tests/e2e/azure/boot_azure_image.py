#!/usr/bin/env python3
# Copyright (c) 2026 THOX.ai LLC. Licensed under the Apache License, Version 2.0.
"""Boot-test the ThoxOS Ginux Edition Azure VHD in QEMU and capture its desktop.

Runs inside the thoxos-g/azure-bench image (tests/e2e/azure/Dockerfile):

1. Boots the VHD through a 20 GiB qcow2 overlay (so first-boot root growth is
   exercised) on QEMU q35 + OVMF, virtio disk and network, standard VGA.
2. Provisions it like Azure would, with cloud-init: a NoCloud seed (vfat,
   label CIDATA) creates the default administrator "thox" with a password.
   The image's datasource list is [Azure, NoCloud]; Azure itself is not here.
3. Checks the host over SSH: identity, services, cloud-init, groups, root
   growth, per-machine keys, the TXF looks.
4. Captures the boot splash and the LightDM greeter from the VGA console, the
   xrdp login screen, and one RDP desktop session per look (TXF Slate,
   Porcelain, Console Pro) with an RDP client on a virtual X display.
5. Optionally opens "ThoxOS on Ginux" inside the desktop and types commands.

With --headless (the headless image) steps 4 and 5 are replaced by a capture
of the VGA console and a full systemd boot of ThoxOS on Ginux for the
administrator, run headless until the ThoxOS welcome line and login prompt.

Writes report.json and PNG captures to OUT. Exit 0 only if every check passed.

Usage: boot_azure_image.py --vhd IMAGE.vhd --out OUT [--boot-timeout S] [--ginux-wait S] [--headless]
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

USER = "thox"
PASSWORD = "Thoxos-e2e-2026"
OVMF_CODE = "/usr/share/OVMF/OVMF_CODE_4M.fd"
OVMF_VARS = "/usr/share/OVMF/OVMF_VARS_4M.fd"
RDP_SIZE = (1600, 1000)
LOOKS = ("slate", "porcelain", "console-pro")


class Bench:
    def __init__(self, out: Path, headless: bool = False) -> None:
        self.out = out
        self.headless = headless
        self.vm_uuid = str(uuid.uuid4())
        self.report: dict = {"checks": {}, "captures": [], "notes": []}
        self.qemu: Optional[subprocess.Popen] = None
        self.xvfb: Optional[subprocess.Popen] = None
        self.started = time.monotonic()

    # ------------------------------------------------------------- utilities
    def log(self, message: str) -> None:
        print(f"azure-boot [{time.monotonic() - self.started:7.1f}s] {message}", flush=True)

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        self.report["checks"][name] = {"ok": bool(ok), "detail": detail.strip()[:2000]}
        self.log(f"{'ok  ' if ok else 'FAIL'} {name}{': ' + detail.strip().splitlines()[0] if detail.strip() else ''}")
        return ok

    def run(self, argv, timeout: float = 60, **kw) -> subprocess.CompletedProcess:
        return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, **kw)

    def ssh(self, command: str, timeout: float = 120) -> subprocess.CompletedProcess:
        argv = ["sshpass", "-p", PASSWORD, "ssh", "-p", "2222", "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=10", "-o", "LogLevel=ERROR",
                f"{USER}@127.0.0.1", command]
        try:
            return self.run(argv, timeout=timeout)
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(argv, 124, "", "timeout")

    def monitor(self, command: str) -> None:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(10)
            sock.connect(str(self.out / "monitor.sock"))
            sock.recv(4096)
            sock.sendall(command.encode() + b"\n")
            time.sleep(0.6)
            try:
                sock.recv(65536)
            except socket.timeout:
                pass

    def screendump(self, name: str) -> Optional[Path]:
        ppm = self.out / f"{name}.ppm"
        try:
            self.monitor(f"screendump {ppm}")
        except OSError as error:
            self.log(f"screendump {name} failed: {error}")
            return None
        for _ in range(20):
            if ppm.exists() and ppm.stat().st_size > 0:
                break
            time.sleep(0.5)
        png = self.out / f"{name}.png"
        result = self.run(["convert", str(ppm), str(png)])
        ppm.unlink(missing_ok=True)
        return png if result.returncode == 0 else None

    def x_capture(self, name: str) -> Path:
        png = self.out / f"{name}.png"
        self.run(["import", "-display", ":99", "-window", "root", str(png)], timeout=30)
        self.report["captures"].append(png.name)
        return png

    # ----------------------------------------------------------------- setup
    def make_seed(self) -> Path:
        seed_dir = self.out / "seed"
        seed_dir.mkdir(exist_ok=True)
        (seed_dir / "meta-data").write_text("instance-id: thoxos-e2e-1\nlocal-hostname: thoxos-e2e\n")
        (seed_dir / "user-data").write_text(
            "#cloud-config\n"
            f"password: {PASSWORD}\n"
            "chpasswd: {expire: false}\n"
            "ssh_pwauth: true\n")
        image = self.out / "seed.img"
        image.unlink(missing_ok=True)
        self.run(["mkfs.vfat", "-n", "CIDATA", "-C", str(image), "4096"], check=True)
        env = dict(os.environ, MTOOLS_SKIP_CHECK="1")
        for name in ("meta-data", "user-data"):
            self.run(["mcopy", "-i", str(image), str(seed_dir / name), f"::/{name}"], check=True, env=env)
        return image

    def start_vm(self, vhd: Path) -> None:
        overlay = self.out / "azure-test.qcow2"
        overlay.unlink(missing_ok=True)
        self.run(["qemu-img", "create", "-f", "qcow2", "-F", "vpc", "-b", str(vhd), str(overlay), "20G"], check=True)
        vars_fd = self.out / "ovmf-vars.fd"
        shutil.copyfile(OVMF_VARS, vars_fd)
        seed = self.make_seed()
        argv = [
            "qemu-system-x86_64", "-machine", "q35", "-accel", "tcg", "-cpu", "max,-svm,-vmx",
            "-smp", "2", "-m", "4096",
            # A fresh SMBIOS UUID per run, as every Azure VM has: systemd derives
            # the machine-id from it, so the per-machine check means something.
            "-uuid", self.vm_uuid,
            "-drive", f"if=pflash,format=raw,readonly=on,file={OVMF_CODE}",
            "-drive", f"if=pflash,format=raw,file={vars_fd}",
            "-drive", f"file={overlay},format=qcow2,if=virtio",
            "-drive", f"file={seed},format=raw,if=virtio,readonly=on",
            "-netdev", "user,id=n0,hostfwd=tcp:127.0.0.1:2222-:22,hostfwd=tcp:127.0.0.1:3389-:3389",
            "-device", "virtio-net-pci,netdev=n0",
            "-vga", "std", "-display", "none",
            "-serial", f"file:{self.out / 'serial.log'}",
            "-monitor", f"unix:{self.out / 'monitor.sock'},server,nowait",
        ]
        self.log("starting QEMU: " + " ".join(shlex.quote(a) for a in argv))
        self.qemu = subprocess.Popen(argv, stdout=open(self.out / "qemu.log", "wb"), stderr=subprocess.STDOUT)
        for _ in range(50):
            if (self.out / "monitor.sock").exists():
                return
            time.sleep(0.2)
        raise RuntimeError("QEMU monitor socket did not appear")

    def serial(self) -> str:
        try:
            return (self.out / "serial.log").read_text(errors="replace")
        except OSError:
            return ""

    # ------------------------------------------------------------------ boot
    def watch_boot(self, timeout: float) -> bool:
        """Grab the splash while waiting for SSH."""
        deadline = time.monotonic() + timeout
        frame = 0
        best_splash: Optional[Path] = None
        while time.monotonic() < deadline:
            if self.qemu and self.qemu.poll() is not None:
                return self.check("qemu running", False, f"QEMU exited with {self.qemu.returncode}")
            if not self.headless and frame < 60 and best_splash is None:
                png = self.screendump(f"boot-{frame:02d}")
                frame += 1
                if png and self.is_splash(png):
                    best_splash = png.rename(self.out / "boot-splash.png")
                    self.report["captures"].append("boot-splash.png")
                elif png:
                    png.unlink(missing_ok=True)
            if self.ssh("true", timeout=20).returncode == 0:
                self.check("ssh reachable", True, f"after {time.monotonic() - self.started:.0f} s")
                if not self.headless:
                    self.check("boot splash captured", best_splash is not None,
                               "Plymouth ThoxOS splash on the VGA console" if best_splash else "no splash frame seen")
                return True
            time.sleep(3)
        return self.check("ssh reachable", False, "timed out; see serial.log")

    @staticmethod
    def is_splash(png: Path) -> bool:
        """Mostly TXF canvas with brand-green pixels near the center."""
        result = subprocess.run(["convert", str(png), "-resize", "64x40!", "-depth", "8", "txt:-"],
                                capture_output=True, text=True)
        if result.returncode != 0:
            return False
        dark = green = total = 0
        for line in result.stdout.splitlines()[1:]:
            if "#" not in line:
                continue
            hexv = line.split("#", 1)[1][:6]
            r, g, b = int(hexv[0:2], 16), int(hexv[2:4], 16), int(hexv[4:6], 16)
            total += 1
            if r < 20 and g < 20 and b < 24:
                dark += 1
            if g > 90 and r < 60 and b < 120 and g > r * 2:
                green += 1
        return total > 0 and dark / total > 0.85 and green >= 2

    # ---------------------------------------------------------------- checks
    def host_checks(self) -> None:
        r = self.ssh("cloud-init status --wait --long", timeout=900)
        self.check("cloud-init finished", "status: done" in r.stdout, r.stdout + r.stderr)
        r = self.ssh("timeout 600 systemctl is-system-running --wait; systemctl --failed --no-legend", timeout=660)
        self.check("systemd running", r.stdout.split("\n")[0].strip() in ("running", "degraded"), r.stdout)
        self.check("no failed units", r.stdout.strip() == "running", r.stdout)
        r = self.ssh(". /etc/os-release; echo \"$PRETTY_NAME|$VARIANT\"; uname -r; cat /usr/share/thoxos-g/IMAGE_FLAVOR")
        flavor = "desktop=headless" if self.headless else "desktop=desktop"
        identity = "target=azure" in r.stdout and flavor in r.stdout and "cloud-amd64" in r.stdout
        if not self.headless:
            identity = identity and "ThoxOS Desktop on Debian 13 (Trixie)|Ginux Edition" in r.stdout
        self.check("identity", identity, r.stdout)
        units = ["thoxos-g-registry", "thoxos-g-dns", "ssh"] + ([] if self.headless else ["xrdp", "lightdm"])
        r = self.ssh(f"systemctl is-active {' '.join(units)} walinuxagent chrony")
        states = r.stdout.split()
        self.check("desktop and runtime services active" if not self.headless else "runtime services active",
                   states[:len(units)] == ["active"] * len(units), r.stdout)
        self.report["notes"].append(f"walinuxagent and chrony outside Azure: {states[len(units):]}")
        r = self.ssh("id")
        self.check("admin groups", all(g in r.stdout for g in ("(sudo)", "(kvm)")), r.stdout)
        r = self.ssh("findmnt -bno SIZE /; cat /var/lib/thoxos-g/growroot.done 2>/dev/null || true")
        size = int(r.stdout.split()[0]) if r.stdout.split() and r.stdout.split()[0].isdigit() else 0
        self.check("root grown to the disk", size > 15 * 1024 ** 3, r.stdout)
        desktop_keys = "" if self.headless else \
            " && test -s /var/lib/thoxos-desktop/firstboot.done && sudo test -s /etc/xrdp/rsakeys.ini"
        r = self.ssh(f"test -s /etc/ssh/ssh_host_ed25519_key.pub{desktop_keys} && cat /etc/machine-id && "
                     "readlink -f /var/lib/dbus/machine-id")
        lines = r.stdout.split()
        machine_id = lines[0] if lines else ""
        # A machine ID copied from the image (D-Bus's build-time ID, VALIDATION D-16)
        # would repeat on every VM; systemd says where it took the ID from.
        from_image = "machine ID from D-Bus machine ID" in self.serial()
        self.check("per-machine keys and machine-id",
                   r.returncode == 0 and len(machine_id) == 32 and lines[-1:] == ["/etc/machine-id"] and not from_image,
                   f"{machine_id} (VM UUID {self.vm_uuid}; "
                   f"{'from the image: D-Bus ID' if from_image else 'generated at first boot'})\n{r.stderr}")
        self.report["notes"].append(f"machine-id {machine_id}, VM UUID {self.vm_uuid}")
        if not self.headless:
            r = self.ssh("thoxos-look list")
            self.check("three looks installed", all(l in r.stdout for l in LOOKS), r.stdout)
            # GTK trusts the icon cache over the directory: a stale cache hides the launcher icons.
            r = self.ssh("for i in thoxos-ginux thoxos-ask thoxos-looks thoxos-about thoxos-system thoxos-doctor; do "
                         "grep -q $i /usr/share/icons/hicolor/icon-theme.cache && echo $i; done")
            self.check("launcher icons in the icon cache", len(r.stdout.split()) == 6, r.stdout)
        chip = "" if self.headless else "; thoxos-ai-chip"
        r = self.ssh(f"systemctl is-enabled thox-ai-relay; systemctl is-active thox-ai-relay || true{chip}")
        self.check("AI relay off until configured",
                   "inactive" in r.stdout and (self.headless or "AI OFF" in r.stdout), r.stdout)
        r = self.ssh("thoxos-ginux doctor")
        self.check("Ginux doctor for the administrator", r.returncode == 0 and "ok   ginux efi" in r.stdout,
                   r.stdout + r.stderr)
        r = self.ssh("sudo grep -E '^(Provisioning.Agent|ResourceDisk.Format|ResourceDisk.EnableSwap)=' /etc/waagent.conf; "
                     "lsinitramfs /boot/initrd.img-$(uname -r) | grep -cE '/hv_(vmbus|storvsc|netvsc)\\.ko'")
        self.check("Azure agent settings and Hyper-V initrd", "Provisioning.Agent=cloud-init" in r.stdout
                   and r.stdout.strip().endswith("3"), r.stdout)

    def headless_checks(self, timeout: float) -> None:
        """Console capture, then ThoxOS on Ginux for the administrator, headless."""
        png = self.screendump("headless-console")
        if png:
            self.report["captures"].append(png.name)
        command = (f"THOXOS_G_STATE_DIR=$HOME/.local/state/thoxos-g THOXOS_G_MODE=system "
                   f"THOXOS_G_BOOT_TIMEOUT={int(timeout)} timeout {int(timeout) + 60} /usr/bin/thoxos-g console "
                   "--quiet --until 'Welcome to ThoxOS' --until 'login:' > ~/ginux-boot.log 2>&1; "
                   "echo rc=$?; tail -c 1500 ~/ginux-boot.log")
        self.log(f"booting ThoxOS on Ginux inside the VM (nested software emulation, up to {timeout:.0f} s)")
        begun = time.monotonic()
        r = self.ssh(command, timeout=timeout + 120)
        self.check("ThoxOS on Ginux boots for the administrator", "rc=0" in r.stdout,
                   f"in {time.monotonic() - begun:.0f} s; " + r.stdout[-1200:])
        log = self.ssh("cat ~/ginux-boot.log", timeout=60)
        (self.out / "ginux-boot.log").write_text(log.stdout)

    # ------------------------------------------------------------------- RDP
    def start_xvfb(self) -> None:
        w, h = RDP_SIZE
        self.xvfb = subprocess.Popen(["Xvfb", ":99", "-screen", "0", f"{w}x{h}x24", "-nolisten", "tcp"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)

    def rdp(self, credentials: bool) -> subprocess.Popen:
        w, h = RDP_SIZE
        argv = ["xfreerdp3", "/v:127.0.0.1:3389", "/cert:ignore", f"/size:{w}x{h}", "/bpp:24",
                "/log-level:ERROR", "+fonts"]  # no -wallpaper: xrdp then hides its login background
        if credentials:
            argv += [f"/u:{USER}", f"/p:{PASSWORD}"]
        else:
            # Empty credentials on stdin: FreeRDP connects over TLS and xrdp
            # shows its own (ThoxOS branded) login screen.
            argv += ["/sec:tls", "/from-stdin:force"]
        env = dict(os.environ, DISPLAY=":99")
        client = subprocess.Popen(argv, env=env, stdin=subprocess.PIPE,
                                  stdout=open(self.out / "xfreerdp.log", "ab"), stderr=subprocess.STDOUT)
        if client.stdin:
            if not credentials:
                client.stdin.write(b"\n\n\n")
            client.stdin.close()
        return client

    def session_display(self) -> Optional[str]:
        r = self.ssh("pgrep -u thox -a Xorg | grep -oE ' :[0-9]+' | head -1")
        value = r.stdout.strip()
        return value or None

    def remote_x(self, display: str, command: str) -> None:
        self.ssh(f"export DISPLAY={display} XAUTHORITY=$HOME/.Xauthority; setsid -f {command} >/dev/null 2>&1",
                 timeout=30)

    def end_session(self, client: Optional[subprocess.Popen]) -> None:
        if client and client.poll() is None:
            client.terminate()
            try:
                client.wait(10)
            except subprocess.TimeoutExpired:
                client.kill()
        self.ssh("pkill -u thox -x Xorg; sleep 3; pkill -KILL -u thox -x Xorg; true", timeout=30)
        time.sleep(8)

    def wait_for_desktop(self, timeout: float = 600) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            r = self.ssh("pgrep -u thox -x xfce4-panel >/dev/null && pgrep -u thox -x plank >/dev/null && echo up")
            if "up" in r.stdout:
                return True
            time.sleep(5)
        return False

    def desktop_captures(self, ginux_wait: float) -> None:
        self.start_xvfb()
        client = self.rdp(credentials=False)
        time.sleep(25)
        self.x_capture("rdp-login")
        self.end_session(client)

        for look in LOOKS:
            self.ssh(f"mkdir -p ~/.config/thoxos && echo {look} > ~/.config/thoxos/look")
            client = self.rdp(credentials=True)
            up = self.wait_for_desktop()
            if not self.check(f"rdp session ({look})", up, "xfce4-panel and plank running" if up else "no desktop"):
                self.x_capture(f"rdp-{look}-failed")
                self.end_session(client)
                continue
            time.sleep(25)  # look applied at session start, then a settle
            display = self.session_display() or ":10"
            r = self.ssh(f"DISPLAY={display} XAUTHORITY=$HOME/.Xauthority xfconf-query -c xsettings -p /Net/ThemeName")
            expected = {"slate": "ThoxOS-Slate", "porcelain": "ThoxOS-Porcelain", "console-pro": "ThoxOS-ConsolePro"}[look]
            self.check(f"look applied ({look})", r.stdout.strip() == expected, r.stdout + r.stderr)
            self.x_capture(f"rdp-{look}-desktop")
            if look == "slate":
                self.remote_x(display, "xfce4-terminal --title='About this system' --hide-menubar --geometry=100x24 -x thoxos-hold fastfetch")
                time.sleep(20)
                self.x_capture("rdp-slate-about")
            elif look == "porcelain":
                self.remote_x(display, "thunar /usr/share/thox")
                time.sleep(20)
                self.x_capture("rdp-porcelain-files")
            elif look == "console-pro" and ginux_wait > 0:
                self.remote_x(display, "xfce4-terminal --title='ThoxOS on Ginux' --hide-menubar --geometry=112x34 -x thoxos-ginux shell")
                self.log(f"waiting {ginux_wait:.0f} s for ThoxOS on Ginux (nested software emulation)")
                time.sleep(ginux_wait)
                self.x_capture("rdp-console-pro-ginux-boot")
                env = dict(os.environ, DISPLAY=":99")
                for text in ("uname -srm", "thox status"):
                    subprocess.run(["xdotool", "type", "--delay", "120", text], env=env, check=False)
                    subprocess.run(["xdotool", "key", "Return"], env=env, check=False)
                    time.sleep(150)  # nested software emulation: allow each command its output
                self.x_capture("rdp-console-pro-ginux")
                r = self.ssh("pgrep -u thox -a qemu-system-x86 | head -1")
                self.check("Ginux VM running for the desktop user", "GINUX" in r.stdout or "qemu" in r.stdout, r.stdout)
            self.end_session(client)

    # -------------------------------------------------------------- shutdown
    def stop(self) -> None:
        if self.qemu and self.qemu.poll() is None:
            self.ssh("sudo systemctl poweroff", timeout=20)
            try:
                self.qemu.wait(120)
            except subprocess.TimeoutExpired:
                self.qemu.send_signal(signal.SIGTERM)
                self.qemu.wait(20)
        if self.xvfb and self.xvfb.poll() is None:
            self.xvfb.terminate()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--vhd", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--boot-timeout", type=float, default=1800)
    parser.add_argument("--ginux-wait", type=float, default=0)
    parser.add_argument("--headless", action="store_true", help="the headless image: no desktop checks")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    bench = Bench(args.out, headless=args.headless)
    try:
        bench.start_vm(args.vhd)
        if bench.watch_boot(args.boot_timeout):
            bench.host_checks()
            if args.headless:
                bench.headless_checks(max(args.ginux_wait, 600))
                return finish(bench, args.out)
            r = bench.ssh("for i in $(seq 1 60); do pgrep -x lightdm-gtk-gre >/dev/null && break; sleep 5; done; "
                          "pgrep -x lightdm-gtk-gre >/dev/null && loginctl show-seat seat0 -p CanGraphical", timeout=330)
            bench.check("console greeter (LightDM)", "CanGraphical=yes" in r.stdout,
                        "lightdm-gtk-greeter on seat0" if "CanGraphical=yes" in r.stdout else r.stdout + r.stderr)
            time.sleep(10)
            png = bench.screendump("lightdm-greeter")
            if png:
                bench.report["captures"].append(png.name)
            bench.desktop_captures(args.ginux_wait)
    except Exception as error:  # report, then shut down cleanly
        bench.check("harness", False, f"{type(error).__name__}: {error}")
    return finish(bench, args.out)


def finish(bench: Bench, out: Path) -> int:
    """Shut the VM down, write report.json, return the exit status."""
    try:
        bench.stop()
    except Exception as error:  # still write the report
        bench.check("clean shutdown", False, f"{type(error).__name__}: {error}")
    bench.report["elapsed_seconds"] = round(time.monotonic() - bench.started)
    bench.report["serial_tail"] = bench.serial()[-4000:]
    (out / "report.json").write_text(json.dumps(bench.report, indent=2) + "\n")
    failed = [name for name, c in bench.report["checks"].items() if not c["ok"]]
    print(f"azure-boot: {len(bench.report['checks']) - len(failed)} passed, {len(failed)} failed: {failed}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
