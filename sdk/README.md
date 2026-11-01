# SDK and toolchain

## Pinned toolchain

| Tool | Pin | Source of truth |
|---|---|---|
| Rust | 1.99.0, targets x86_64-unknown-uefi and x86_64-unknown-none | rust-toolchain.toml in the prepared upstream tree; kernel/ginux/upstream.env (GINUX_RUST_VERSION) |
| Upstream source | gmkurtzer/ginux @ 36503bda2d87465765e1b94e65f9d100f27ed5be | UPSTREAM.md |
| Build | cargo + make (`make build` in the prepared tree) | kernel/ginux/scripts/build-native.sh |
| Test harness | QEMU (validated 8.2.2 TCG in predecessor evidence; 10.2.1 on the current build host), OVMF | kernel/ginux/scripts/run-vm.sh |
| Agent layer | Rust workspace, stable channel of the host | userspace/agentos/Cargo.toml |

## Building against ThoxInux

- Kernel and controller work: start from docs/QUICKSTART.md step 1 and 2. Changes to upstream files are patches in kernel/ginux/patches/ (see docs/DEVELOPMENT.md, patch discipline).
- Agent development: userspace/agentos is the reference implementation of the agent contract (manifest, signed identity, capability grants, broker, audit). Its README and docs are the SDK for agent authors.
- Interface integration (closed or open components): thoxbeam/README.md defines the only supported boundary.

## Contribution

Contribution guide: docs/DEVELOPMENT.md (branching, commits, DCO sign-off, test evidence). License for contributions: Apache-2.0, per LICENSE. By contributing you agree your contribution is licensed under the same terms.
