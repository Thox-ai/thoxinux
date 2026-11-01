# Upstream: Ginux

ThoxInux is a fork of Ginux. This file is the fork record.

| Item | Value |
|---|---|
| Upstream repository | https://github.com/gmkurtzer/ginux |
| Upstream author | Gregory M. Kurtzer and contributors |
| Pinned upstream commit | `36503bda2d87465765e1b94e65f9d100f27ed5be` |
| Upstream license | Apache-2.0 (preserved in full in every derived file set) |
| Upstream Rust pin | 1.99.0 (rust-toolchain.toml in the upstream tree; targets x86_64-unknown-uefi and x86_64-unknown-none) |
| THOX source of the fork | ttracx/thoxos-ginux (private, archive of record, untouched by this repository's creation) |
| Research module origin | ttracx/thoxos-desktop-debian at `1390b8a18334e91d03725b177c813760f4b38579` (see kernel/ginux/SOURCE_MANIFEST.json) |

## Fork discipline

- THOX changes land as one reviewable patch series in `kernel/ginux/patches/` (file `series` is the order), applied to the pristine pinned tree by `kernel/ginux/scripts/prepare_source.py`, which verifies byte-exact results and refuses unknown or modified source. No silent edits to upstream files outside the series.
- The unified series (2026-10-31) converges the two predecessor patch sets. Convergence detail: docs/RECONCILIATION-2026-10-31.md.
- Upstream re-sync is reviewed monthly; security fixes are fast-tracked. A re-sync updates this file, re-runs the syscall audit (docs/COMPATIBILITY.md) and the evidence suites before any number in this repository changes.
- Upstream is experimental software and says so. ThoxInux inherits that posture: engineering preview until the Phase 3 independent security review and hardware validation land.

## What the fork changes

1. `thox-kernel-startup.patch`: kernel startup and Linux domain init work (Makefile, kernel/linux-probe.S, kernel/linux-system-init.S, address space, CPU, socket and stack code) from the Azure Compute lane.
2. `thox-identity.patch`: one unified ThoxInux identity block in the ring-3 controller. The upstream banner stays byte-identical; upstream ABI and prompt are retained.
3. `thox-qemu-tools.patch`: QEMU tooling support for Debian/Ubuntu 4M OVMF layouts (host tooling only).
4. `thox-registry-anchor.patch`: the controller's network service trusts a per-build ThoxOS local registry anchor (ginux-edition lane).

No upstream security guard, capability check or refusal is removed by any patch in the series.
