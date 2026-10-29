# Ginux review for ThoxOS

Reviewed: gmkurtzer/ginux at `36503bda2d87465765e1b94e65f9d100f27ed5be` (2026-10-26), built and booted on 2026-10-28.
Reviewer: Odette Lark, THOX.ai. Evidence lives in `docs/VALIDATION.md`.

## Verdict

Ginux is real and it runs. We built `GINUX.EFI` from source, and it booted a ThoxOS userspace (Rocky Linux 10 UBI init plus a ThoxOS identity overlay) through systemd `multi-user.target` to a login prompt, pulling the image over its own TLS stack from a local registry. It is a research prototype: QEMU-only hardware, a 4 GiB identity map, a development signing key, and no security audit. ThoxOS uses it as a demo kernel inside a VM, never as the kernel of a THOX product.

## What Ginux is

| Area | Finding |
|---|---|
| Shape | Independent Rust-first x86-64 kernel. One UEFI image (`GINUX.EFI`, 12.5 MB in our build) holds the kernel, boot catalog and an embedded ring-3 controller |
| Isolation model | Kernel-native domains own processes, address spaces, mounts, capabilities and lifecycle. Linux x86-64 is a personality inside a domain |
| Userspace delivery | The kernel's network service pulls OCI images (manifest, config, gzip layers, at most 16) and unpacks them into domain roots; the cache persists on a virtio volume |
| Size | 154,583 lines across tracked `.rs` files in our checkout (upstream reports about 139,000 retained implementation and test lines; counting methods differ) |
| License | Apache-2.0 |
| Toolchain | Rust 1.99.0 (pinned in `rust-toolchain.toml`), clang for assembly fixtures; builds cleanly on Ubuntu 24.04 and Debian 13 |

## Hardware profile (hard limits for KnightHub)

| Limit | Source | Consequence |
|---|---|---|
| Devices: virtio-blk and virtio-net only (PCI vendor 0x1af4, devices 0x1041/0x1042) | `kernel/src/arch/x86_64/pci.rs` | No NVMe, AHCI, USB or physical NIC. Bare-metal boot on KnightHub cannot reach storage or network |
| Console: COM1 serial (0x3F8) | `boot/efi/src/main.rs` | No GPU or framebuffer console after early boot; KnightHub has no serial header in use |
| Intel IOMMU with 48-bit address width required | `kernel/src/arch/x86_64/iommu.rs` | QEMU before 9.1 defaults to 39 bits and the kernel panics |
| Identity map covers the first 4 GiB | `kernel/src/arch/x86_64/paging.rs` | VM RAM above 2.75 GiB moves into high memory on q35 and the kernel panics |
| One vCPU | `tools/qemu/run.sh` (`-smp 1`) | No SMP |

## Findings

| ID | Severity | Finding | ThoxOS action |
|---|---|---|---|
| F1 | High (blocks boot) | QEMU 8.2 (Ubuntu 24.04) panics with `inactive IOMMU translation construction failed`: its intel-iommu defaults to `aw-bits=39` | Patch 0001 requests `aw-bits=48` when supported. Upstreamable |
| F2 | Low | `tools/qemu/common.sh` does not find Debian and Ubuntu firmware names (`OVMF_CODE_4M.fd`) | Patch 0001 adds them. Upstreamable |
| F3 | High (blocks boot) | QEMU 10.0.13 (Debian 13 default) panics with `virtio network initialization invariant failed`. QEMU 10.2.2 and 11.1.2 pass. Root cause not isolated | Demo and KnightHub host pin QEMU 11.1 (trixie-backports); `thoxos-g doctor` fails on 10.0.x |
| F4 | Medium | `domain start` of `embedded://minimal-system-v0` panics with `minimal system init execution failed` on QEMU 8.2, 10.2 and 11.1 (TCG). Traced to the fixture check in `address_space.rs`: since commit 070fb24 the auxiliary vector carries `AT_SYSINFO_EHDR` (40 words), but the check still expects `AT_NULL` at word 41 and places the stack so the vector overlaps the `AT_RANDOM` bytes. Correcting both moves the failure to the probe's exec result, so the fix is incomplete. Upstream's own `make test-c1` stops here in our environment | Not used by ThoxOS (OCI path). Reported as an upstream candidate; partial patch not shipped |
| F5 | Medium | VM memory above 2.75 GiB panics with `loaded EFI image is outside the identity map` | `thoxos-g` refuses `THOXOS_G_MEMORY` above 2816M with the reason |
| F6 | High (security) | The boot envelope that authenticates the controller payload is signed with a "development-only RFC test key", a public test vector | Treat the controller seal as an integrity check, not a security boundary |
| F7 | High (security) | Upstream states no security audit has been completed | ThoxOS Ginux Edition is labeled research preview; no inbound ports are forwarded to the guest |
| F8 | Info | Registry trust is two pinned roots (ISRG Root X1 for `auth.docker.io`, Starfield Services Root G2 for everything else), TLS 1.3 AES-128-GCM only, port 443 only. In practice only Docker Hub works | Patch 0003 adds a per-build ECDSA root accepted for exactly `registry.thoxos.internal` |
| F9 | Low | Hostname is fixed at `ginux` in the kernel, so the login prompt reads `ginux login:` | Documented; identity comes from os-release, issue and the controller banner |
| F10 | Low | `boot/efi/src/generated_boot.rs` is rewritten on every build, so a built tree is never clean | Builds happen in throwaway trees |
| F11 | Medium | The domain console has no line discipline (one byte per `read`, no echo, no newline translation). `login` never reaches a password prompt and an interactive bash as init exits at its first read | `thox-shell` line editor as the shell domain's init (VALIDATION V9, V12) |
| F12 | Medium | `domain start` answers from the OCI cache by image reference (`OCI cache hit (4 layers)`, no registry request), so a persisted volume keeps serving an earlier build's userspace under the same tag. Measured with one demo image: a volume filled by the previous build failed the shell domain right after `/etc/issue`; a fresh volume passed | `thoxos-g` stamps the volume with the SHA-256 of the served manifest and replaces the volume when it changes (VALIDATION V16) |
| F13 | Info | After a domain has run for 60 seconds Ginux prints one diagnostic block on the console (`Linux runtime exceeded sixty seconds; execution snapshot`, then recent syscall/result pairs). The domain keeps running | Documented in the user guide; visible in the shell preview |

## What works, measured

| Measurement (QEMU TCG, no KVM, 2 host cores) | Value |
|---|---|
| UEFI hand-off to controller prompt | 293 ms (kernel-reported) |
| OCI pull of the ThoxOS image, 4 layers, 109,774,305 bytes, verified | 19.2 s transfer, 38.5 s including unpack |
| Linux init to console | 6.5 to 7.6 s |
| Result, system domain | `Welcome to ThoxOS 0.1.0 Ginux Edition!`, `multi-user.target`, `login:` |
| Result, shell domain | `uname -srm` prints `Ginux 6.12.0-ginux.0.1 x86_64`; `thox status` runs (Python 3) on the Ginux kernel |

KVM numbers are not measured in this pass; KnightHub is the first KVM host.

## Fit for ThoxOS

- Demo value is high: "Linux userspace, no Linux kernel underneath" is visible on one console.
- Product value is low today: no real hardware, one CPU, 2.75 GiB, no audit. A THOX device kernel stays Linux.
- The method matters more than the kernel. Kurtzer's human-directed agentic engineering (architecture and acceptance criteria from the human, implementation and test loops from the agent) matches how the THOX fleet already splits work between Tommy and the coding lanes.

## Upstream contributions to offer

1. Patch 0001 (IOMMU width and firmware discovery) as a pull request to gmkurtzer/ginux.
2. An issue for F3 with the QEMU version matrix.
3. An issue for F4 with the auxiliary-vector trace and the partial fix.
4. An issue for F12 asking for a digest check against the registry before a cache hit is used.
