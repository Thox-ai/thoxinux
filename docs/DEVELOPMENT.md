# Development

## Architecture in one page

ThoxInux is a monorepo with one kernel identity:

- `kernel/ginux/` is the build profile for the fork: it pins upstream Ginux (UPSTREAM.md), prepares a pristine checkout, applies the unified patch series with byte-exact verification, builds the single EFI release unit, and launches it under QEMU. The kernel, the ring-3 controller and the native services come from upstream plus the series.
- `boot/ssd/` builds the external SSD image and the host installer, with target-identity refusal guards that must never be weakened to make a test pass.
- `userspace/ginux-edition/` is the ThoxOS userspace line: desktop, installer, rootfs assembly, runtime, Docker demo and its benches.
- `userspace/agentos/` is the agent layer in Rust: thox-agentd supervisor, signed agent identity (ed25519), tool broker with capability grants, append-only audit log, and the user-swappable model slot.
- `thoxbeam/` documents the ThoxBeam runtime interface and the MeshStack plugin boundary. Interfaces only; proprietary logic is never committed here.
- `evidence/` preserves the predecessor lanes' validation records. Numbers in this repository cite a payload and an environment; never merge numbers across payloads (docs/RECONCILIATION-2026-10-31.md).

## Dev environment

x86-64 Linux, rustup (the upstream tree pins Rust 1.99.0 with x86_64-unknown-uefi and x86_64-unknown-none targets), clang, make, python3 with pytest, QEMU 8.2 or newer with OVMF, Docker for the userspace demo. Stage everything on a volume with room: a full host image build wants about 125 GiB.

## Build and test commands

| What | Command | Where |
|---|---|---|
| Build the EFI | `scripts/build-native.sh` | kernel/ginux/ |
| Boot the EFI | `scripts/run-vm.sh` | kernel/ginux/ |
| Kernel profile tests | `python3 -m pytest tests/` | kernel/ginux/ |
| SSD tests | `python3 -m pytest tests/` | boot/ssd/ |
| Userspace tests and demo | `make test`, `make demo-image`, `make selftest`, `make demo-shell` | userspace/ginux-edition/ |
| Agent layer tests | `cargo test` | userspace/agentos/ |

Local CI is the THOX pattern (no GitHub Actions): run the suites above and record results in the change description. A result counts only with the exact source revision and a log.

## Branching and commits

- `main` is the consolidated line. Work lands on short-lived branches named `lane/<topic>` and merges with a summary of tests run.
- Commits are small, imperative, and signed off (DCO style: `Signed-off-by`).
- Patch discipline: changes to upstream Ginux files exist ONLY as entries in kernel/ginux/patches/series, regenerated as patches, never as silent in-tree edits. If you change a patch, the build receipt and the compatibility audit are re-run.
- Secrets, keys and credentials are never committed. Run a secret scan before every push.

## Work log

- 2026-10-31: monorepo created by transforming ttracx/thoxos-ginux (private archive of record, untouched). Two predecessor patch sets converged into the unified series; reconciliation closed in docs/RECONCILIATION-2026-10-31.md. thox-agentos adopted into userspace/agentos. v0.9.0 staged as a draft release, repository private, public flip is a founder decision.

## Known limitations

- Builds are being made byte-reproducible; until two clean builds produce identical SHA-256, release notes must say so.
- The embedded minimal Linux domain start failure from the Oct 28 record is under diagnosis; see the evidence report for the current root-cause state.
- Docker daemon availability varies by host; the EFI build path is native and does not need Docker.

## Roadmap

Phase 1 (this staging): v0.9 public flip on founder order. Phase 2: agent domains with allowlist enforcement on by default in the guest, ThoxBeam interface implementation, model slot in the guest, Secure Boot signing. Phase 3: independent security review and hardware validation beyond QEMU, the gate for any production-device use.

## Governance note

Public publishing of anything from this repository (public flip, announcements, store listings, registries, campaigns) requires explicit founder approval: Craig Ross's explicit approval via craig@thox.ai, CC tommy@thox.ai, and for the public flip and the thox.ai website, the standing founder rules in the repository standard apply. Repository Creation Standard v1.0 governs this repository's shape.
