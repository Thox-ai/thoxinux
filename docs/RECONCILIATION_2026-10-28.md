# Record reconciliation: two runtimes, one request

Prepared 2026-10-28 by Odette Lark (memory-sync and fleet librarian, Claude runtime).

Tommy's request ("review Ginux, spin up a customized ThoxOS, a Docker VM demo, and an installation package for an external SSD that boots on KnightHub") was worked by two runtimes the same evening. Both pushed to `ttracx/thoxos-ginux`. This file keeps the two records separate, with provenance, and lists where they agree, where they complement each other, and where they disagree. Nothing here overrides either record. Tommy rules.

## Provenance

| | Record A | Record B |
|---|---|---|
| Runtime | ChatGPT/Codex session (per its `.agents/HANDOFF.md`) | Claude runtime (Odette Lark) |
| Location | `main` at `e88662bdc7e975753a5a049eb4b664bcee0db7e5`: `module-ginux/`, `ssd-module/`, `evidence/`, `docs/` | Branch `ginux-edition-0.1.0`: `ginux-edition/` |
| Ginux base | `gmkurtzer/ginux` `36503bd` | same |
| EFI tested | SHA-256 `4fd25157...e69e8` (banner patch) | SHA-256 `0a7c68a4...a5fd27` (patches 0001-0003) |
| QEMU used | 8.2.2 (Ubuntu packages), TCG | 8.2.2, 10.0.13, 10.2.2, 11.1.2, TCG; product pins 11.1.2 |
| Docker | Not available in that session | Docker 29.9, images built and run |

## Agreement (independent confirmation)

| Finding | A | B |
|---|---|---|
| Ginux needs `intel-iommu,intremap=off,aw-bits=48` on QEMU 8.2 | yes | yes (patch 0001) |
| 4 GiB guest RAM fails with the identity-map error; 2 GiB works | yes | yes (cap 2816 MiB) |
| `embedded://minimal-system-v0` domain start panics in both THOX and pristine upstream | yes | yes, plus a source trace (REVIEW F4) |
| KnightHub keeps a Linux host for real hardware; Ginux has no NVMe, USB or physical NIC | yes | yes |
| No byte-reproducible build claim | yes | yes (generated_boot.rs rewritten each build) |

## Complements (each record covers what the other left open)

| Area | A | B |
|---|---|---|
| Linux userspace in a domain | Not reached (embedded path only) | ThoxOS userspace pulled over OCI from a local TLS registry, systemd `multi-user.target`, `login:` (VALIDATION V5) |
| Docker demo | Recipe written, not run | Built and run; selftest exit 0 |
| SSD install | Post-boot installer onto an existing Linux host on the SSD (no flashing) | Fresh 8 GiB GPT image (Debian 13 host, systemd-boot, KVM launcher) plus guarded writers |
| Controller persistence and recovery | Tested and passed | Not separately tested |
| Upstream unit tests | 53 library tests passed | Not rerun; 80 ThoxOS-side tests |

## Disagreements to rule on

| # | Topic | A says | B says | Recommendation |
|---|---|---|---|---|
| R1 | Linux domain execution | `linux_domain_execution: failed` (summary field) | OCI domain execution passed; only the embedded minimal path fails | Narrow A's field to "embedded minimal-system domain: failed" and record B's OCI pass beside it |
| R2 | Fresh SSD media | Blocked: Vibe layout and NiceC0re writer mismatch; do not bypass | New image and writers with their own guards; refuses a THOXOS-labeled disk unless `--erase-existing-thoxos` | Tommy picks the disk. Spare USB SSD: use B. The 500 GB THOXOS SSD (ThoxOS Vibe): use A's post-boot installer, never B's writer |
| R3 | Scope of THOX patching | Banner only | Banner, QEMU portability, and one scoped registry trust anchor | Keep both visible; B's registry anchor is required for its offline OCI path |

## What stays untouched

Record A's files on `main` are unchanged by this branch. Record B lives under `ginux-edition/` and this file. A merge is Tommy's call.
