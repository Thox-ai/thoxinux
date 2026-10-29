# Decision log

Decisions made under Autonomous Ship Mode for ThoxOS Ginux Edition 0.1.0. Each one stands until Tommy rules otherwise.

| # | Date | Decision | Why | Reversible by |
|---|---|---|---|---|
| D1 | 2026-10-28 | KnightHub boots a Debian 13 host from the SSD and runs Ginux under KVM; bare-metal Ginux is only an experimental boot entry | Ginux drives only QEMU virtio devices and a serial console (REVIEW F-table, hardware profile). Bare metal cannot reach NVMe, USB or the NIC | A Ginux release with physical drivers |
| D2 | 2026-10-28 | ThoxOS userspace = Rocky 10 UBI init (upstream-validated digest) plus a file-only overlay and one demo user | The only userspace upstream boots through `multi-user.target`; adding packages risks units Ginux cannot run | Upstream validating other bases |
| D3 | 2026-10-28 | Serve the userspace from a local, read-only TLS registry trusted through a per-build root scoped to one host name (patch 0003) | Ginux pulls only over HTTPS from pinned roots; publishing to Docker Hub would need an account decision and public exposure | Tommy choosing a public Docker Hub namespace |
| D4 | 2026-10-28 | Destroy the local root key right after signing the registry leaf | A trusted root that cannot sign anything new cannot be abused later | None needed |
| D5 | 2026-10-28 | Pin QEMU 11.1 from trixie-backports in the demo and on the host | QEMU 10.0.13 fails Ginux virtio-net init; 10.2.2 and 11.1.2 pass (F3) | Upstream fix for F3 |
| D6 | 2026-10-28 | Cap VM RAM at 2816 MiB, default 2 GiB | Ginux identity-maps 4 GiB; q35 moves RAM high above 2.75 GiB (F5) | Ginux mapping all RAM |
| D7 | 2026-10-28 | Ship patches 0001-0003 only; hold the partial fix for F4 | A fix that still fails its own check is not shippable; ThoxOS never uses the embedded minimal system | Completing the F4 fix |
| D8 | 2026-10-28 | thoxos-g quits on Ctrl-A then X, not Ctrl-] | Ctrl-] is Ginux's own detach key | None needed |
| D9 | 2026-10-28 | Browser console: one client, credential generated per container unless set, bound by `make demo-web` to 127.0.0.1 | Each connection boots a VM on the same volume; no default password on a network port | None needed |
| D10 | 2026-10-28 | SSD installer refuses a disk carrying a THOXOS label unless `--erase-existing-thoxos` | The ThoxOS Vibe Desktop plan uses a 500 GB SSD labeled THOXOS; never erase it silently | Tommy choosing the target disk |
| D11 | 2026-10-28 | systemd-boot, Secure Boot off | Simplest UEFI path from an offline build; KnightHub already boots an external Linux SSD for ThoxOS Vibe (assumption stated in the user guide) | Signed shim path in the dev queue |
| D12 | 2026-10-28 | Repository license Apache-2.0, THOX trademarks reserved in NOTICE.md | Matches upstream Ginux so patches and tooling combine cleanly; trademarks are outside Apache grants | Tommy ruling a different license for THOX-authored files |
| D13 | 2026-10-28 | No AI model ships in the image; `thox ask` targets the host endpoint at 10.0.2.2:11434 and needs `THOX_AI_MODEL` set | The KnightHub model endpoint is planned, not confirmed; a guessed model name would be invented data | Tommy naming the served model |
| D14 | 2026-10-29 | Interactive ThoxOS runs in a second domain whose init is `thox-shell`, a small line editor that reads the console byte by byte and runs each line with `bash -c`; KnightHub tty1 defaults to it | Measured: getty login never reaches a password prompt and bash as init exits at its first read (V9); `thox-shell` passes the e2e session (V12). Upstream itself validates shells as domain init | Upstream console line discipline |
| D15 | 2026-10-29 | Replace the Ginux volume when the served userspace manifest changes | Ginux answers from its OCI cache by tag (F12); the volume holds only that cache and the domain table, which the boot sequence recreates | Ginux checking the registry digest before a cache hit |
