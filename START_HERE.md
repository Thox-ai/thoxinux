# ThoxOS Ginux Research Kit

> **Historical kit guide — October 28, 2026.** These instructions identify the original delivered payload and its limits. For the current desktop, browser shell or headless Azure Compute path, use the [repository experience selector](README.md#choose-your-experience). The separate `ginux-edition/` implementation has its own image and test evidence; do not apply this kit's embedded-domain failure or image/writer limitation to that implementation.

Internal engineering candidate, 2026-10-28. Prepared for Tommy Xaypanya.

The included THOX EFI was built and booted under QEMU TCG. Controller commands, clean shutdown and saved configuration recovery passed. Starting the embedded Linux domain panics in this environment; the same failure reproduced with pristine upstream. This is a controller and architecture demo. Docker execution, full Linux host-image construction, KVM and KnightHub hardware acceptance remain pending.

Your AI. Your Data. Your Rules.™

## Run the Docker demo

Install Docker Engine/Desktop and Compose v2, then open a terminal in the extracted kit:

```bash
cd module-ginux
docker compose build
docker compose run --rm ginux
```

At `ginux>` enter:

```text
status
components
domain list
help
shutdown
```

This builds from pinned Ginux source and starts QEMU inside the container. It does not replace Docker's Linux host kernel. The default uses one virtual CPU, 2 GiB RAM, a 48-bit virtual IOMMU and a persistent sparse 64 GiB guest volume. Real disk usage starts small and grows with stored data. No incoming ports, host drives, home directories or GPU are passed through.

## Run the supplied EFI without rebuilding

On x86-64 Linux, install QEMU x86, OVMF and util-linux with the host package manager. Run as your regular desktop user from the kit root:

```bash
bash module-ginux/scripts/run-vm.sh --artifact-dir module-ginux/artifacts
```

`module-ginux/artifacts/GINUX.EFI` is the actual tested payload, not a download placeholder. Its SHA-256 is `4fd25157b9f0348346a56fcb3e8d51d29414094f0f3aaa533ffddb52932e69e8`.

## Install on the existing external SSD Linux host

Boot an already accepted Linux installation on the external SSD first. From the kit root:

```bash
python3 ssd-module/preflight.py --json
sudo python3 ssd-module/install_host.py \
  --kit module-ginux \
  --expected-receipt-sha256 182dedf18e3e91468ef58f455010d8dfdf6920ae518b02eb18c8ec8f045b4977 \
  --install-dependencies --require-usb-root
```

Then launch `thox-ginux` as the desktop user. The installer copies ordinary files and installs QEMU dependencies when requested. It does not repartition, flash a drive, alter firmware or reboot.

For building a new Linux SSD host, read `ssd-module/docs/EXTERNAL_SSD.md`. The source-pinned build wrapper stages Ginux into the established THOX image pipeline. This session lacks Docker and the pipeline's required 125 GiB free build space. A new host image has not been built. Its Vibe disk layout is incompatible with the bundled NiceC0re writer. Do not use that writer on a Vibe image or bypass its refusal. A matched, tested host-image and writer pair is required before a fresh SSD can be prepared.

## Included material

- `docs/THOX_Ginux_Research_Guide.pdf` and `docs/html/THOX_Ginux_Research_Guide.html`: review, architecture, QuickStart and hardware acceptance steps.
- `module-ginux/`: actual EFI, pinned build recipe, source patch, Docker/QEMU launchers, attribution and guard tests.
- `ssd-module/`: host installer, read-only inventory, existing image-pipeline wrapper, guarded writer source and tests.
- `evidence/`: real build/test logs and separate successful and failed boot receipts.
- `SHA256SUMS`: file integrity inventory. Verify the complete ZIP hash from the delivery before trusting its scripts.

Ginux has no qualified NVIDIA/CUDA, graphical desktop, native USB/NVMe or KnightHub bare-metal profile. The Linux host supplies actual hardware support. This package does not establish deployed THOX AI, MeshStack or ThoxWork services inside Ginux.
