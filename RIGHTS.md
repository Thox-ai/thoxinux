# Rights and license ledger

Every component in this repository, its license, and its notice obligations. If a component is not listed here, it does not ship.

| Component | Origin | License | Obligations |
|---|---|---|---|
| Ginux kernel, controller, services, tools | gmkurtzer/ginux @ 36503bda | Apache-2.0 | Preserve LICENSE and NOTICE from upstream; state changes (the patch series in kernel/ginux/patches/ is the change record); Ginux name used as attribution only |
| THOX patch series (kernel startup, identity, QEMU tools, registry anchor) | THOX.ai LLC, consolidated 2026-10-31 from the thoxos-ginux module-ginux and ginux-edition lanes | Apache-2.0 | THOX copyright headers where the stack supports them |
| ThoxOS userspace (ginux-edition tree: desktop, installer, rootfs, runtime, shell) | THOX.ai LLC | Apache-2.0 for THOX code | Bundled third-party components keep their own licenses; the Debian 13 base system in built images is governed by the licenses of its packages, enumerated in the image build manifests, not by this ledger |
| Agent supervisor (userspace/agentos) | THOX.ai LLC | Apache-2.0 | Rust crate dependencies are listed in its Cargo.lock with their upstream licenses (MIT or Apache-2.0 family); no copyleft dependency is admitted without a ledger entry here |
| SSD installer (boot/ssd) | THOX.ai LLC, vendored components under boot/ssd/vendor | Apache-2.0 for THOX code; vendored items keep their own LICENSE/NOTICE files in place | Do not strip vendored notices |
| Documentation, whitepaper and guides | THOX.ai LLC | Apache-2.0 (code-adjacent docs in this repository) | Captures and recordings keep their real vs synthetic labels from the evidence records |
| Rocky Linux 10 and Alpine Linux userspaces (runtime payloads, not source in this repo) | Rocky Enterprise Software Foundation; Alpine Linux | GPL family and per-package licenses of those distributions | They are validation payloads assembled from OCI images at runtime; ThoxInux does not relicense them, and built images must carry the distributions' own notices |
| OVMF / EDK II firmware (test harness) | TianoCore | BSD-2-Clause-Patent | Test tooling only; not redistributed as a ThoxInux component |
| QEMU (test harness) | QEMU project | GPL-2.0 | Test tooling only; not linked into or redistributed with ThoxInux artifacts |

## Explicitly not in this repository (proprietary, no license granted)

- MeshStack (proprietary THOX technology). Only its interface surface is documented, in thoxbeam/ and docs/THREAT-MODEL.md.
- ThoxKey firmware, secure boot keys, device identity and attestation material.
- ThoxWork, and distilled device models that are not Apache-2.0 clean. The allowlist policy and eval gates are open; the weights are not.

## Trademark posture

ThoxInux and ThoxOS are THOX.ai product names. Ginux is named only to credit the upstream project and state the fork, per UPSTREAM.md. Nothing in the Apache-2.0 grant licenses THOX trademarks.
