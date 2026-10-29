# Record reconciliation: two Azure variants, one request

Prepared 2026-10-29 by Odette Lark (memory-sync and fleet librarian, Claude runtime).

Tommy's request of 2026-10-29 ("build the complete kernel and customized ThoxOS variant with desktop options and screenshots for azure deployment", with Microsoft's AVD master-image guide) was worked by two runtimes. Both pushed to `ttracx/thoxos-ginux`. This file keeps the two records separate, with provenance, the same way as [RECONCILIATION_2026-10-28.md](RECONCILIATION_2026-10-28.md). Record A's statements below are quoted from its pull request and files; this runtime did not run its code. Nothing here overrides either record. Tommy rules.

## Provenance

| | Record A | Record B |
|---|---|---|
| Runtime | ChatGPT/Codex session (same lineage as the 2026-10-28 Record A) | Claude runtime (Odette Lark) |
| Location | Pull request #2, branch `codex/azure-compute-20261029`, head `0c91c839cf19b5171b6efea86cffc4b91e398467` (opened 2026-10-29 20:19 UTC): root `azure/`, `docs/azure/`, `evidence/azure/`, `module-ginux/patches/` | Branch `ginux-edition-0.2.0`: `ginux-edition/` (host images 0.2.0) |
| Kernel | Ginux `36503bd` plus `thox-kernel-startup.patch` (auxv fixture overlap, TCP cleanup after peer close, mount errno assertion, detached operator output, restart selection) and `thox-azure-profile.patch`; EFI SHA-256 `3ebcc904...24d5ba`, 12,507,648 bytes | Ginux `36503bd` plus patches 0001-0003 (unchanged from 0.1.0); cold rebuild, EFI SHA-256 `6ff22d32...56a1` (the per-build registry root is embedded, so every build differs) |
| Azure host | Ubuntu 24.04 marketplace image, Gen2; the Ginux release ZIP is uploaded to private blob storage and pulled at first boot by a managed identity | Debian 13 golden image built offline (cloud kernel), fixed VHD, Azure Compute Gallery image version |
| Ginux acceleration | QEMU TCG; "Do not enable KVM by assuming the Azure size exposes it" | KVM when `/dev/kvm` is present (Microsoft lists nested virtualization as supported on Dsv5), TCG fallback |
| Desktop | "graphical desktop ... not claimed" | ThoxOS Desktop (TXF 5.2, three looks) over RDP; headless image as well |
| Azure run | Not run (no Azure identity connected) | Not run (no subscription in this runtime) |

## Agreement

| Finding | A | B |
|---|---|---|
| The AVD master-image guide builds Windows session hosts; a Ginux image cannot be an AVD session host | yes | yes (AZURE.md, D17) |
| Generation 2 VM, `Standard_D4s_v5` default, boot diagnostics on | yes | yes |
| Ginux runs inside QEMU on the Azure host, never natively on Hyper-V | yes | yes |
| No Azure deployment, what-if or acceptance has run | yes | yes |

## Complements

| Area | A | B |
|---|---|---|
| Kernel fixes | Startup patch claims a fix for the auxv fixture overlap behind the embedded minimal-system panic (B's REVIEW F4) and 22 QEMU lifecycle commands with embedded `/sbin/init` | F4 left open upstream; OCI ThoxOS userspace, systemd and the shell domain verified (0.1.0 V5, V12) |
| Network posture | Private VM, no public IP, NAT gateway, optional Bastion, NSG deny-all with an optional narrow SSH CIDR | Public IP with DNS label; NSG admits SSH and RDP only from one required CIDR |
| Identity and artifacts | User-assigned managed identity with Storage Blob Data Reader on one private container; immutable, checksummed release ZIP | Everything in the image; no runtime artifact fetch; hosted AI key only on the host (`ai-relay.env`) |
| Desktop and screenshots | None | Splash, LightDM, xrdp login and three looks captured from the booted VHD in QEMU |

## Disagreements to rule on

| # | Topic | A says | B says | Recommendation |
|---|---|---|---|---|
| R4 | Image strategy | Marketplace Ubuntu plus a bootstrap artifact | Custom golden VHD in a Compute Gallery (the flow the linked guide describes) | Both are deployable designs. Pick per use: A for a headless research host on a vendor-supported image, B when the desktop or an offline image is needed |
| R5 | Security type | Trusted Launch (host Secure Boot, vTPM) on Ubuntu's signed chain | Standard: B's systemd-boot is unsigned (DEV_QUEUE item 12 is the signed path) | Keep B on Standard until a signed loader exists; do not label B Trusted Launch |
| R6 | Inbound access | No public IP; Bastion or Run Command | Public IP restricted to one CIDR, because RDP is the desktop's front door | For anything beyond a demo, B should gain a no-public-IP option (Bastion or VPN); B's DEV_QUEUE item 8 |
| R7 | Accelerated networking | On | Off, VFs marked unmanaged | Both are unverified on Azure; B's DEV_QUEUE item 14 tests it |
| R8 | Kernel patch set | Five startup fixes plus an Azure profile | 0001-0003 only | Codex lane rebases A's startup patch onto B's 0001-0003 and runs B's `make selftest` and shell e2e; Tommy decides which EFI ships |

## What stays untouched

Record A's pull request and files are unchanged by this branch, and Record B's files are unchanged by Record A's. The two `azure/` directories live at different paths (`azure/` and `ginux-edition/azure/`). A merge is Tommy's call.
