# Quick start

Every command here was run against this tree on KnightHub (WSL2, Ubuntu 26.04, x86-64) on 2026-10-31, unless a step is marked as a bench or a gate. Times and versions: Rust 1.99.0 (pinned by upstream rust-toolchain.toml), QEMU 10.2.1, OVMF 2025.11.

## Prerequisites

- x86-64 Linux host with git, cargo/rustc (rustup will select the pinned 1.99.0 toolchain inside the source tree), clang, make, python3.
- QEMU with OVMF for boot tests: `qemu-system-x86_64`, OVMF firmware files.
- About 125 GiB free for a full host image build; the kernel EFI build alone needs far less. Stage builds on a large volume.
- Docker only for the userspace demo path (step 3).

## 1. Build the ThoxInux EFI

```bash
cd kernel/ginux
scripts/build-native.sh
```

What this does: clones upstream Ginux at the pinned commit (UPSTREAM.md) into `kernel/ginux/.work/ginux`, applies the unified patch series with byte-exact verification (prepare_source.py refuses unknown or modified source), builds with `make build`, and writes `artifacts/GINUX.EFI` with a build receipt and SHA256SUMS. The artifact name stays GINUX.EFI in v0.9 because the upstream build system names it; the identity inside is ThoxInux (see the boot log).

## 2. Boot it in QEMU

```bash
cd kernel/ginux
scripts/run-vm.sh
```

Load-bearing configuration, learned from the predecessor evidence and enforced by the launcher: 2 GiB RAM, 1 vCPU, `intel-iommu,intremap=off,aw-bits=48`. QEMU defaults (39-bit address width) fail the kernel's 48-bit contract, and a 4 GiB attempt fails EFI identity-map placement. Do not "fix" these by changing the kernel; they are the tested profile.

> Annotation (2026-10-31, Wave 3 doc correction): one element of this
> profile is disputed by our own evidence. The claim that `aw-bits=48` is
> load-bearing comes from the predecessor handoff, but in the D14 evidence
> rerun the full 22-command lifecycle suite passed under both TCG and KVM
> in runs whose QEMU invocation (upstream `run.sh`) passes no `aw-bits`
> argument at all. The launcher profile above remains the tested
> configuration for `scripts/run-vm.sh`, and the 2 GiB memory limit,
> 1 vCPU, and `intremap=off` stand as documented. Whether `aw-bits=48` is
> strictly required has not been isolated; do not assert it as proven. Expected console: the ThoxInux identity block, the upstream "Ginux controller v0 (ring 3)" banner byte-identical, then the controller prompt. Try `help`, `status`, and the domain commands the prompt lists.

## 3. Run the userspace demo (Docker)

```bash
cd userspace/ginux-edition
make test
make demo-image
make selftest
make demo-shell
```

In the guest shell, `uname -srm`, `thox version` and `thox status` run against the real Ginux guest. The systemd login path has an upstream getty limitation; the documented interactive path is `make demo-shell`.

## 4. Run the agent supervisor (host development mode)

```bash
cd userspace/agentos
cargo test
cargo run --bin thox-agentd -- --help
```

See userspace/agentos/README.md for the manifest, identity and audit walkthrough.

## 5. SSD image (bench only in v0.9)

The external SSD image is built with boot/ssd tooling and validated in the QEMU USB-disk bench. Writing to a physical drive is a separate, explicitly authorized step on a named spare drive; the tooling refuses protected and ambiguous targets by design, and those refusals are features. See boot/ssd/README.md.

## Troubleshooting

- "Source differs from reviewed patch series": your upstream checkout is not pristine at the pinned commit, or a patch was edited. Start from a fresh `.work` directory; never edit the prepared source in place.
- Rust version errors: build inside the prepared source tree so rust-toolchain.toml selects 1.99.0, with the x86_64-unknown-uefi and x86_64-unknown-none targets installed for that toolchain.
- QEMU exits early or the EFI faults: check the IOMMU flags and memory size first (step 2). They are the two known-good-profile deviations that present as kernel faults.
