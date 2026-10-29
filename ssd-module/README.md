# ThoxOS Ginux external SSD host integration

This module installs the experimental THOX Ginux **QEMU guest** on an already
booted x86-64 Linux host. The external SSD boots Linux. Ginux runs inside QEMU
using its own Rust kernel. Native Ginux boot, NVIDIA acceleration inside Ginux,
and physical KnightHub acceptance are not established.

**Your AI. Your Data. Your Rules.™**

## Install on the booted SSD

Verify the complete downloaded kit against its delivery SHA-256 before running
any included program. Keep the module and `module-ginux` directories together.
The expected build-receipt hash comes from the authenticated delivery receipt or
your own successful source build. Do not substitute a hash printed by an
unverified download.

Run this as your desktop user first:

```bash
python3 ssd-module/preflight.py --json
```

The inventory reads CPU, installed RAM, NVIDIA name/memory/driver, KVM access,
firmware presence and block-device topology. It does not collect environment
variables, passwords, BitLocker keys, disk labels, serial numbers or file data.
`usb_nonrotational_root_candidate` identifies the current root's USB disk
ancestry, including common encrypted/LVM layouts. It is an inventory result,
not physical hardware certification.

After booting the existing Linux installation on the external USB SSD:

```bash
sudo python3 ssd-module/install_host.py \
  --kit ./module-ginux \
  --expected-receipt-sha256 '<authenticated build-receipt SHA-256>' \
  --install-dependencies \
  --require-usb-root
```

The installer supports Debian/Ubuntu `apt-get` and Arch/NiceC0re `pacman`. The
explicit dependency option installs QEMU x86, OVMF and util-linux. A package
manager may need network access. If they are already installed, omit that
option. Python 3.9+ is needed for installation and inventory, and the VM
launcher uses Bash and standard host tools.

The installer verifies the pinned build receipt, all four SHA256SUMS entries,
the EFI payload and preserved upstream attribution. It copies ordinary files
to `/opt/thox/ginux`, `/usr/local/bin/thox-ginux` and
`/usr/share/applications/thox-ginux.desktop`. It refuses an existing installation
instead of overwriting it. Its local receipt records installed hashes. It does
not start a VM, touch partitions, write firmware or reboot the host.

Launch **ThoxOS Ginux research VM** from the desktop applications menu, or run:

```bash
thox-ginux
```

Run it as the desktop user. Guest state belongs to that user's
`${XDG_STATE_HOME:-$HOME/.local/state}/thox/ginux`. The serial console is the
actual running kernel surface. TCG is the default; KVM acceleration is an
explicit launcher option when the current user has `/dev/kvm` access:

```bash
QEMU_ACCEL=kvm thox-ginux
```

Guest storage persists as an ordinary file in that state directory. The launcher
recreates firmware variables from the OVMF template at each boot. Shut down the
VM before disconnecting the SSD. No GPU device is
passed through to this research guest. Linux on KnightHub retains responsibility
for the RTX 4060 Ti, CUDA and the normal THOX desktop.

## Prepare a Linux external SSD

Use the existing guarded host image and writer path in
[EXTERNAL_SSD.md](docs/EXTERNAL_SSD.md). This package supplies a guest integration
installer and a concrete source overlay builder for the established Linux image
lane. It does not supply an accepted Linux host image. Current host build, media
admission and physical acceptance are separate gates. The unchanged guarded
Windows writer source is included under `vendor/windows-writer/`, with original
readme and exact Git-blob/SHA-256 provenance. Its image format differs from the
dual-arch builder's output. Do not use it on that output or weaken its refusal.

For an ordinary-file installation staging area, without package installation or
host qualification:

```bash
python3 ssd-module/install_host.py \
  --kit ./module-ginux \
  --expected-receipt-sha256 '<authenticated build-receipt SHA-256>' \
  --stage-root ./staged-root
```

Staging does not install a running host or prove it boots.

## Verify and maintain

```bash
python3 -m unittest discover -s ssd-module/tests -v
cat /opt/thox/ginux/host-install-receipt.json
```

The tests use tiny EFI fixtures and disposable directories; they do not boot a
kernel or exercise native Windows storage. Runtime boot evidence must bind to
the exact built EFI, not the test fixture.

An update preserves the existing installation. Stop the VM, retain the current
installation and user state, review the new receipt and replace the three known
installation paths through the administrator's normal package workflow. State
files are not removed by this installer. Do not put the guest's private state in
a public source archive.

Original integration code: Copyright 2026 THOX.ai LLC, Apache-2.0. Upstream
Ginux copyright and Apache-2.0 attribution travel in the artifact bundle.
