# ThoxOS Ginux Research Edition

THOX-branded Ginux research guest with a Docker/QEMU demo and a standalone Linux host launcher. This is an engineering preview. It is a serial-console operating-system prototype, and it does not provide a graphical ThoxOS desktop or NVIDIA acceleration.

The independent Ginux kernel executes inside QEMU. Docker packages the build and QEMU process; Docker itself does not replace its Linux host kernel with Ginux. The external SSD host remains Linux so it can support KnightHub's actual GPU, USB and storage hardware.

Your AI. Your Data. Your Rules.™

## Current acceptance

The delivered EFI compiled and passed a native QEMU TCG controller smoke test at 2 GiB: THOX banner, status, components, domain list, help and clean shutdown. Saved domain configuration survived a separate reboot. Starting the embedded minimal Linux domain triggered a kernel panic. The same failure reproduced with the unmodified pinned upstream EFI in this environment. Linux userspace execution, Docker runtime, KVM and physical KnightHub boot remain unqualified. Use this candidate for controller and architecture evaluation.

## Quick start

Run from this directory with Docker Engine/Desktop and Docker Compose v2 installed:

```bash
docker compose build
docker compose run --rm ginux
```

The first build downloads the pinned Ginux source, Rust toolchain components and Cargo dependencies. The guest starts without a Linux domain image. OCI root filesystems are fetched when you explicitly request an image through the controller. The demo exposes no incoming network ports and mounts no host disks or home directories. Its named Docker volume stores the sparse 64 GiB guest volume. OVMF firmware variables are recreated from the matching template on each launch. Do not run two guests against the same state.

For a managed build that uses an HTTPS inspection proxy, preserve the host's Docker proxy settings and pass its complete trusted CA bundle as a BuildKit secret. For example, `docker build --platform linux/amd64 --secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt --target runtime -t thoxos-ginux:0.1.0-candidate .`, followed by `docker compose run --no-build --rm ginux`. The secret is mounted only for networked Rust/Cargo/Git build steps and is not copied into image layers. Keep certificate verification enabled.

The QEMU serial console should reach the preserved `ginux>` prompt. Use `status`, `components`, `domain list` and `help`, then enter `shutdown` for a clean exit. The following upstream Linux ABI workflow requires outbound image download and has not passed qualification in this package:

```text
domain new alpine
domain set alpine image=alpine:latest init=/bin/sh
domain start alpine --attach
```

Press Control-] to detach from the domain back to Ginux. This Alpine tag is a demonstration input, not a pinned workload or a compatibility guarantee. Enter `shutdown` before closing the terminal. Control-C is an emergency stop and may lose recent guest state. Storage durability and arbitrary Linux application compatibility remain experimental.

TCG software emulation is the default and also works through Docker Desktop on Apple Silicon using an amd64 container. It will be considerably slower than KVM. On an x86-64 Linux host with accessible `/dev/kvm`, opt in:

```bash
KVM_GID=$(stat -c %g /dev/kvm) docker compose -f compose.yaml -f compose.kvm.yaml run --rm ginux
```

The KVM override grants only the KVM device. It uses no privileged container and grants no direct disk or GPU access.

## Export the installation payload

BuildKit can export the EFI and its receipt without starting a guest:

```bash
docker build --platform linux/amd64 --target artifacts --output type=local,dest=artifacts .
sha256sum artifacts/build-receipt.json
(cd artifacts && sha256sum --strict -c SHA256SUMS)
```

The output contains `GINUX.EFI`, `build-receipt.json`, `SHA256SUMS`, `GINUX_LICENSE` and `GINUX_NOTICE`. The receipt records the exact upstream commit, Rust version, patch, Cargo lockfile and compiled payload hashes. The SSD host installer uses the receipt digest as its explicit trusted input. A checksum establishes byte identity, not security review or successful physical boot.

## Native Linux build and launch

Install Git, Python 3, GNU Make, Clang, Rust 1.99.0, QEMU x86-64 and OVMF. Install both Rust targets:

```bash
rustup toolchain install 1.99.0 --profile minimal --component clippy --component rustfmt
rustup target add --toolchain 1.99.0 x86_64-unknown-uefi x86_64-unknown-none
./scripts/build-native.sh
./scripts/run-vm.sh --artifact-dir ./artifacts --state-dir "$HOME/.local/state/thox/ginux"
```

`GINUX_SOURCE_DIR` and `GINUX_ARTIFACT_DIR` can select dedicated build and output directories. The build script rejects unrelated tracked edits in the source checkout. The four-line THOX banner patch preserves the upstream controller banner, `ginux>` prompt and ABI identity. The boot catalog is regenerated as part of the build.

The native launcher runs as a regular user, verifies the artifact checksums, selects a matching OVMF CODE/VARS pair, locks the state directory and creates a sparse 64 GiB guest volume on first use. It never formats a host drive or resets an existing guest volume. `QEMU_ACCEL=kvm` opts into Linux KVM; `GINUX_MEMORY=2G` is the default and maximum memory allocation for this tested profile. Set both `OVMF_CODE` and `OVMF_VARS` when using nonstandard firmware locations. `--print-command` verifies artifacts and prints the command without creating guest state or launching QEMU.

The validated guest profile explicitly requests 48-bit IOMMU addressing with `intel-iommu,intremap=off,aw-bits=48`. QEMU 8.2 defaults to a 39-bit IOMMU, which fails Ginux's required 48-bit translation construction. The explicit capability retains the kernel's guard. An actual 4 GiB guest attempt failed because OVMF placed the EFI image outside Ginux's initial identity map. The package therefore caps only the research guest at 2 GiB. KnightHub's Linux host can still use its full installed memory and RTX GPU.

## Sources and scope

Ginux is pinned to [gmkurtzer/ginux commit 36503bda2d87465765e1b94e65f9d100f27ed5be](https://github.com/gmkurtzer/ginux/tree/36503bda2d87465765e1b94e65f9d100f27ed5be). It is an independent Rust x86-64 kernel with a Linux compatibility personality. Its validated target is Q35/OVMF with virtual IOMMU and modern virtio storage/network devices. Native KnightHub storage, RTX 4060 Ti/CUDA, graphical desktop, broad USB support and bare-metal boot are not established by this package.

THOX modifications are limited to the research banner and packaging. The Apache-2.0 upstream license and attribution remain intact. See `LICENSE`, `NOTICE`, and the exported Ginux license/notice payloads.

## Validation

Run the packaging guard checks:

```bash
python3 -m unittest discover -s tests -v
for script in scripts/*.sh; do bash -n "$script" || exit; done
```

These use inert fixtures to verify hardware arguments, integrity rejection and invalid-input handling. They do not boot a kernel. Real build, QEMU boot, Docker, KVM and KnightHub SSD results must be recorded separately in the delivered evidence.
