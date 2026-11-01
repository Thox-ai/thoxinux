# ARM64 Scoping for ThoxInux (v1.1 Scoping Document)

Scoping date: 2026-10-31. Author: ThoxInux Wave 5, Lane B (THOX.ai).
Status: scoping only. This document makes no commitment and names no
dates. Effort is given in relative sizes (small, medium, large) backed
by the counts measured below.

All upstream counts are measured at upstream main
`759cf2e221b459b0195c3fa7ed909688b755e74e` (2026-10-31) unless a pin
figure is stated; the pin is `36503bda2d87465765e1b94e65f9d100f27ed5be`.
The upstream tree is https://github.com/gmkurtzer/ginux. ThoxInux
counts are from `kernel/ginux/patches/` in this repository.

## 1. Headline findings

- Upstream has exactly one architecture. `kernel/src/arch/` contains
  only `x86_64`, and `kernel/src/arch.rs` gates it with
  `#[cfg(target_arch = "x86_64")]`. No aarch64 module, stub, or
  in-progress port exists upstream to inherit. The only aarch64
  mention in the codebase is in `crates/oci` (OCI image architecture
  naming), not kernel support.
- The arch tree is the majority of the kernel: 18 files, 60,224 lines
  at main `759cf2e2`, out of 111,281 lines in `kernel/src` (54
  percent). At the pin it was 7 files, 52,646 lines. Whole-repo Rust
  is 173,276 lines at main.
- On top of the Rust arch tree sit 20 x86-64 assembly files, 14,673
  lines (`kernel/*.S`), none of which carries over to aarch64.
- The toolchain is not a blocker: Rust 1.99.0 (the pinned toolchain)
  lists `aarch64-unknown-uefi` and `aarch64-unknown-none` in
  `rustc --print target-list` (verified on KnightHub, 2026-10-31).
  What is missing is all build wiring: `rust-toolchain.toml` requests
  only `x86_64-unknown-uefi`, and the Makefile builds the boot image
  for `x86_64-unknown-uefi` and every service for
  `x86_64-unknown-none`.
- The test story exists on the shelf today: KnightHub already has
  `qemu-system-aarch64` and AAVMF firmware (package
  `qemu-efi-aarch64` 2025.11-3ubuntu7.3, `AAVMF_CODE.fd` and
  `AAVMF_VARS.fd` under `/usr/share/AAVMF/`), the direct analogue of
  the x86-64 QEMU plus OVMF setup the lifecycle suite uses.

## 2. What the x86-64 ABI layer actually is

The Linux ABI ThoxInux implements is defined against the x86-64
machine at every layer, not just in the syscall numbers:

- Syscall entry: the `SYSCALL` instruction, entry state programmed
  through MSRs (for example LSTAR, `0xc000_0082`, in
  `kernel/src/arch/x86_64/cpu.rs`), a dedicated syscall vector, and
  register conventions (number in `rax`, arguments in `rdi` and
  successors, `rcx` and `r11` clobbered by hardware). The aarch64
  analogue is the `svc` instruction and the EL0 to EL1 exception
  model, with the number in `x8` and arguments in `x0` and
  successors. Nothing about the entry trampoline is shared.
- The syscall table itself differs. The x86-64 table implemented here
  has 375 dispatched numbers (0 to 462 with gaps). Linux on aarch64
  uses the generic (asm-generic) syscall table: different numbers,
  some calls absent (there is no `open`, only `openat`), some present
  that x86-64 lacks. A port re-derives the constants table and the
  audit ledger from the aarch64 table; the 375 figure does not
  transfer. The handler logic behind most numbers (files, sockets,
  memory, processes) is arch-independent in intent and largely shared
  in code, but each number must be re-mapped and re-audited.
- Context switch and execution state: saved register frames, FS base
  handling (`arch_prctl`, TLS), and the vDSO (an x86-64 ELF serving
  `clock_gettime` from the TSC) are all x86-64 specific. Aarch64 needs
  its own frame layout, `TPIDR_EL0` TLS handling, and a vDSO built on
  the generic timer registers.
- Page tables: `kernel/src/arch/x86_64/paging.rs` (1,837 lines at
  main) implements the x86-64 four-level format, accessed and dirty
  bits, and NX handling. Aarch64 translation tables have a different
  descriptor format, granule choice, and attribute encoding
  (MAIR, UXN/PXN). The address-space policy above paging is shared;
  the table walker is new work.
- Interrupts, timers, and DMA: `apic.rs` (229 lines), `timer.rs`
  (824), `iommu.rs` (666, Intel VT-d), `smp.rs` (643), `acpi.rs`
  (492), and `pci.rs` (4,536) at main encode x86 platform hardware:
  APIC, HPET and TSC, VT-d. The aarch64 platform equivalents are the
  GIC interrupt controller, the generic timer, and an SMMU, plus
  either ACPI (on server-class hardware) or device tree (on boards).
  This is the least portable layer in the tree.

Measured split at main `759cf2e2`:

| Layer | Files | Lines | Portability |
|---|---|---|---|
| Arch tree `kernel/src/arch/x86_64/` (incl. `cpu/` submodules) | 18 | 60,224 | Arch-bound by definition |
| Assembly `kernel/*.S` | 20 | 14,673 | Arch-bound, x86-64 syntax |
| Shared kernel `kernel/src/` outside the arch tree | about 51,000 lines | - | Mostly portable; 15 files still reference `x86_64` |
| Services, control plane, crates | rest of 173,276 | - | Portable except build targets; `boot/efi/src/main.rs`, the controller, and one OCI file reference `x86_64` |

In total, 17 files outside the arch tree reference `x86_64` at main,
so the arch boundary leaks and a port must audit those files, not
just add a sibling arch directory.

## 3. The THOX patch series under a port

Series measured in this repository (`kernel/ginux/patches/`):

| Patch | Arch-bound or portable | Basis |
|---|---|---|
| `thox-identity.patch` (1 file, 1 hunk) | Portable | Controller banner text in `control-plane/runtime/src/main.rs`; no arch content |
| `thox-registry-anchor.patch` (1 file, 2 hunks) | Portable | TLS trust selection in the network service; no arch content |
| `thox-qemu-tools.patch` (2 files, 4 hunks) | Portable in intent, x86 in detail | Host tooling; its firmware discovery names x86 OVMF files, so an aarch64 variant needs the AAVMF paths and `qemu-system-aarch64` selection added |
| `thox-kernel-startup.patch` (8 files, 34 hunks) | Mixed | Makefile, `lib.rs`, `linux_stack.rs`, and `linux_socket.rs` hunks express behavior that must hold on any arch; the `cpu.rs` hunks and the two assembly files (`linux-probe.S`, `linux-system-init.S`) are x86-64 only and would need aarch64 counterparts or arch-conditional structure |

So of the four patches, two carry over as-is, one needs a tooling
variant, and one splits into a portable part and an arch-bound part.

## 4. Effort drivers, sized relatively

Sizes are relative to each other, grounded in the counts above. They
are planning inputs, not estimates of calendar time.

| Component | Size | Driver |
|---|---|---|
| Build wiring (targets, Makefile, toolchain, boot image packaging for `aarch64-unknown-uefi` and `aarch64-unknown-none`) | Small | Targets exist in Rust 1.99.0; the wiring pattern already exists for x86-64 and is copied, not designed |
| Boot and early init (UEFI entry, memory map, EL transition, initial page tables) | Medium | Small code volume but first-of-kind in this tree; the x86-64 boot path offers a shape, not reusable code |
| Page tables and address space (`paging.rs` analogue, 1,837 lines, plus the arch parts of `address_space.rs`) | Medium | Well-specified hardware format; the shared policy layer above it carries over |
| Syscall entry, dispatcher re-mapping, context switch, signals, TLS, vDSO | Large | The constants table and ledger are re-derived for the asm-generic table; entry and frame code is new; correctness is audit-critical and touches the 42,752-line `cpu.rs` problem space even though much handler logic is shared |
| Interrupt, timer, IOMMU, SMP platform layer (GIC, generic timer, SMMU in place of APIC, HPET/TSC, VT-d; about 2,300 lines of direct analogues plus `pci.rs` interactions) | Large | Different hardware model, no upstream start, and behavior only provable under emulation or hardware |
| Assembly suite (`kernel/*.S`, 14,673 lines: probe, interpreter, exec target, system init) | Large | These files encode the Linux process-start contract in x86-64 assembly; each needs an aarch64 re-implementation or a Rust replacement, and they gate whether any Linux binary starts at all |
| Userspace and services (controller, network, protocol, volume services; OCI handling) | Small | Rust services retarget; `crates/oci` already names aarch64 images; Rocky Linux 10 and Alpine both publish aarch64 userspace images, so the guest side needs selection, not creation |
| Test and proof (QEMU plus AAVMF lifecycle suite port, fresh syscall audit at the aarch64 table, reproducibility controls) | Medium | The suite structure and the audit method transfer; the expected outputs, banners, and the entire audit table are new |

## 5. Open unknowns

- Whether upstream Ginux ever intends an aarch64 port. There is no
  signal in the tree (no arch abstraction beyond the single
  `#[cfg(target_arch = "x86_64")]` gate, no aarch64 issue or branch
  evidence in the code). If upstream later ports, a THOX-first port
  could face a second reconciliation; if upstream never ports, THOX
  owns the arch layer permanently.
- Device model on real aarch64 hardware: virtio coverage, PCI versus
  platform devices, and ACPI versus device tree differ sharply by
  target class, and none of it is exercised by the QEMU story.
- Whether the x86-64 assembly contract files can be replaced by Rust
  on aarch64 (a design choice with performance and audit
  consequences) or must be re-written in aarch64 assembly.
- The aarch64 audit baseline: the asm-generic table's size and status
  distribution under the same scoring rules used for x86-64 are
  unknown until someone does the count; no number in this document
  should be read as predicting it.

## 6. Decision inputs Tommy would need to supply

1. Target hardware class: emulation only (QEMU plus AAVMF), a server
   class platform (ACPI, GIC, SMMU, virtio and PCI), or a specific
   board family (device tree). This choice sizes the platform layer
   in section 4 more than any other input.
2. Whether UEFI-only boot is acceptable on aarch64, matching the
   current x86-64 posture, or whether a second boot path is required.
3. The purpose of the port: a THOX device requirement (which device,
   which SoC), upstream-contribution positioning, or exploratory
   coverage. Purpose decides whether the full syscall audit at the
   aarch64 table is part of the work or a later phase.
4. Timeline class (exploratory, next-major-version, or committed
   roadmap item), stated as a class only. This scoping document
   deliberately attaches no dates.
5. Whether the port is THOX-only (a downstream arch layer carried in
   the patch series) or intended for upstreaming, which changes how
   the arch boundary in section 2 should be refactored first.

## 7. Bottom line

An ARM64 port is a new architecture bring-up inside an existing
kernel, not a retarget: the shared services, userspace, and most
handler logic carry over, but roughly 75,000 lines of arch and
assembly surface (60,224 arch Rust lines plus 14,673 assembly lines,
measured at main `759cf2e2`) define the machine contract and must be
re-created for aarch64, with a different syscall table audited from
zero. The prerequisites that usually block such ports are absent:
the Rust targets exist, QEMU and AAVMF are already installed on the
build host, and aarch64 userspace images are published by both
distributions ThoxInux uses. The decision therefore turns on the
inputs in section 6, above all the target hardware class, not on
feasibility.
