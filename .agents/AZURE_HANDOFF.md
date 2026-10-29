# Azure Compute kernel pickup

Current lane: THOX Azure Compute Edition `0.2.0-azure-candidate`, 2026-10-29. This is additive source continuity, not external runtime acknowledgement. The previous handoff remains historical.

Owner: `ttracx/thoxos-ginux`, private; remote baseline `e88662bdc7e975753a5a049eb4b664bcee0db7e5`. The restored local snapshot baseline `09c79c376938bff212d2b7c59469114feecadbb2` has identical file blobs but a separate history. The verified remote shipping SHA belongs in the post-push receipt, not this self-referencing commit. Upstream remains `gmkurtzer/ginux` `36503bda2d87465765e1b94e65f9d100f27ed5be`.

## Implemented and tested

The complete source-pinned EFI is 12,507,648 bytes, SHA-256 `3ebcc9043ef9dc8b7e75abc15b113a5810c8d39c0ad47143476a41caed24d5ba`. Build receipt SHA-256 `c4ac916269f053a689801af6a9214b6613090a35bd0a247eeb3e2d10d6ccf31b`. It is distributed in the runtime ZIP, not Git. `module-ginux/patches/series` binds three reviewed patches; the kernel patch is `ca19175faaec9e1037b82fc2bfa28dda1c2d6887548bab254af3059ac392afa0`.

Corrected auxv fixture layout, local TCP identity after peer close, stale mount-errno fixture, detached operator output routing and restart selection. Domain authority, W^X, ELF, frame, guard-page and IOMMU checks remain. Real local QEMU TCG passed 17 cold-boot commands and five recovered-boot commands: embedded `/sbin/init`, detached start/status/PID, stop/start/restart, failure recovery and clean shutdown; configuration recovered across a second boot. This proves minimal-system-v0, not arbitrary Linux workloads.

120 unit tests passed across kernel stack (5), nine upstream libraries (53), module (17), SSD (15), Azure (30). Root combined source passes fmt, Clippy with warnings denied, ShellCheck and exact patch preparation. `evidence/azure/VALIDATION_SUMMARY.json` and raw logs hold current proof. `evidence/azure/kernel-diagnosis` refers separately to the same kernel patch without final THOX Azure banners.

Azure deployment code prepares Ubuntu 24.04 Gen2/D4s_v5 with Trusted Launch, private NIC, explicit NAT, private Blob managed identity, nonroot QEMU and bounded controller smoke. Runtime ZIP includes compiled EFI and matched provenance. No Azure subscription/identity is connected: server validate, what-if, deployment, on-host acceptance and Gallery capture remain not_run. Native Ginux Hyper-V boot and Windows AVD are unsupported by this package. Strict Microsoft.Resources schema failures are preserved separately from 13 adapted local checks; do not call the adapted pass an untouched strict or cloud pass.

## Review and delivery state

Actual session colleagues: kernel_diagnosis, azure_implementation, azure_architecture and azure_docs. Independent kernel/Azure source reviews found no blockers. No external Claude/Sera/Hermes acknowledgement is implied. Current official guide is `docs/azure/`; original Oct28 docs/logs remain historical. Preserve all existing SSD writer and firmware safeguards. Docker/KVM/physical/full-host-image gates remain unrun.

Policy sources reloaded: thox-brain `f03e8d951dd12d7a4a916bd2ad51e4fa887b8332`; thox-handoffs `01aeb95b54ddd528b2966667f3d1b63aba486268`. Canonical gate is a separate supplied-evidence check; missing independent delivery/runtime proof must remain open. Source push, archive, Library and Outlook receipts are maintained outside the shipping commit to avoid recursive hashes. Native saved memory/live graph and external runtime loading are unavailable.

## Named next owners

| Lane | Inputs and task | Exit evidence / stop condition |
| --- | --- | --- |
| Codex / Nova | This exact branch, runtime ZIP, Azure guide; authorized subscription/identity and dedicated compute RG | ARM validate, what-if, deployment, cloud-init receipts and real host smoke; stop on ownership, network, quota, RBAC or integrity refusal |
| Claude / Sera | Immutable remote SHA, patch series, local proof and unrun-cloud list | Independent source/claims review; never remove guards or invent acceptance |
| Hermes | Source/payload hashes, archive and Sadie delivery receipts | Reconcile existing closeout; no alternative mailbox or duplicate unknown sends |
| Muse / Samuel / Julian / Clara | Current PDF/HTML and raw authentic CLI evidence | Maintain internal docs and exact THOX branding; no public publication or relabelled simulated/deployed screenshots |
| Kai | Prior KnightHub lane and untouched SSD safety gates | Hardware pickup only when device online and explicitly targeted; no physical write, firmware change or reboot from this Azure build |
| Sadie | Verified sender/archive, final source SHA and actual ZIP/PDF copies | One consolidated Outlook report to Tommy/Craig, Sent Items/attachment bytes readback; no invented external ACK |

All external assignments remain prepared/queued until their own runtime returns evidence. No consolidation-board mutation is implied.
