# Embedded Ginux init recovery

Scope: pinned upstream `36503bda2d87465765e1b94e65f9d100f27ed5be`; source-only patch for THOX integration. The final patch contains no temporary diagnostics, generated manifests, signed development inputs, or binary files.

Patch SHA-256: `ca19175faaec9e1037b82fc2bfa28dda1c2d6887548bab254af3059ac392afa0`.

Clean unbranded test EFI SHA-256: `076b57d7cae092dea5b627b9cad82f7db463e5172b4229c6f5726bec0229ac41`.

## Causes and changes

1. The auxiliary vector grew to 40 words after AT_SYSINFO_EHDR was added. The static verifier still reserved a 50-word total startup layout, placed random bytes on the new AT_NULL pair, and asserted the previous terminator positions. The interpreted verifier similarly overlapped vector words with trailing strings. The patch derives both stack reservations from the current auxiliary-vector length, aligns the initial pointer to 16 bytes, rejects overflow/out-of-page layouts, and retains exact auxv guards including AT_SYSINFO_EHDR and both AT_NULL words. Assembly probes now assert the same complete tail. A shared compact assembly helper preserves the original strict five-page executable-fixture limit.
2. Local TCP transport was inferred from whether a peer slot still existed. Closing the client clears the accepted peer reference, after which closing the accepted socket incorrectly demanded a network socket handle and returned EBADF. A persistent local_tcp identity is assigned at successful local connect and accept, and used by close/send/receive/peek/readiness and the network-only shutdown/drain selectors. All reference counting, frame scrubbing, descriptor, and teardown checks remain in force.
3. The minimal-init fixture expected EPERM from mount(NULL,NULL,NULL,0). Upstream now permits a root process to administer its own domain mount namespace, so invalid pointers correctly produce EFAULT after authority validation. Only this fixture expectation is updated. Host-context, domain ownership, credential, pointer, and immutable-root enforcement are unchanged. Every successful boot also passes the existing linux_user::verify_contract gate, including denied privileged operations, stale-generation rejection, and unmapped IDs.
4. A detached embedded supervisor resumes the resident controller inside its Linux execution scope. The global background-output flag remained true and buffered all operator prompts into the domain console. An operator-console scope now restores operator output for the actual controller execution and restores previous domain routing afterward. A blind delayed status/shutdown experiment first proved that the controller was alive despite hidden output.
5. A requested embedded-domain restart lost its authorized selected slot when the old supervisor and execution were stopped. The next iteration consequently had no domain selection. The two teardown points now retain a selection only while an explicit restart request is pending. Active execution still resets to the host bank; the next begin_configured_container call performs the existing domain/limits/network validation before activation.

## Exact clean validation

Environment: Rust 1.99, clang 18, QEMU 8.2.2 TCG, q35, 1 vCPU, 2 GiB guest memory, OVMF 2024.02, Intel IOMMU aw-bits=48, persistent virtio block image. Hardware virtualization was not used.

Commands from the owned Ginux checkout, with the provided toolchain environment loaded:

```sh
make test-linux-stack
cargo fmt --all -- --check
make build
make architecture-check linux-compat-check abi-conformance
cargo clippy --package ginux-boot --target x86_64-unknown-uefi -- -D warnings
```

`lifecycle.py` is the exact QEMU regression script. It executes 17 controller commands on a fresh persistent volume, then 5 commands after rebooting the same volume. It verifies detached measured init start; running status and PID 100; stop/start; restart; contained injected failure and recovery; clean shutdown; recovered configuration; and another real init start/stop. Both boots exit QEMU with status 0 and GINUX_KERNEL_OK. Results: `lifecycle-results.json`; complete logs: `lifecycle-cold.log`, `lifecycle-recovered.log`.

`probe.py attached` additionally captures the clean final EFI running the actual minimal-init conformance sequence, GINUX_SYSTEM_INIT_V0 readiness, active execution, SUPERVISOR_SHUTDOWN and GINUX_KERNEL_OK. Complete log: `embedded-init-attached.log`.

Five host tests check stack/nonoverlap, full auxv-tail preservation after writing random bytes, interpreted payload separation, growth/alignment, oversized and overflowing layouts, and invalid page alignment. Source patch whitespace check and git apply --check against the pristine pinned clone also pass.

This evidence establishes the pinned embedded minimal-system-v0 fixture and controller lifecycle in QEMU. It does not establish Rocky/systemd compatibility, arbitrary Linux binary coverage, native Azure Hyper-V guest support, physical external-SSD boot, Azure cloud deployment, or KnightHub hardware compatibility.
