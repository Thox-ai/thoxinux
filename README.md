# ThoxOS Ginux Edition

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE) [![Stage: Engineering preview](https://img.shields.io/badge/stage-engineering_preview-orange.svg)](docs/continuation/README.md)

ThoxOS Ginux Edition combines a Linux host with Gregory Kurtzer's independent Rust Ginux kernel running in QEMU. Choose a complete ThoxOS Desktop, an interactive browser shell, or the headless kernel lifecycle research path below. The host supplies real hardware drivers; Ginux runs the tested userspace inside its VM.

**Your AI. Your Data. Your Rules.™**

## Choose your experience

| Experience | Start here | Demonstrated behavior | Remaining acceptance |
| --- | --- | --- | --- |
| **ThoxOS Desktop** | [Desktop guide](ginux-edition/docs/DESKTOP.md) · [Azure image guide](ginux-edition/docs/AZURE.md) | Debian 13/XFCE desktop, TXF 5.2 three looks, RDP, and a per-user Ginux shell, captured from a VHD in QEMU by the image team | Real Azure deployment, nested KVM, hosted inference and KnightHub physical boot |
| **Browser or terminal shell** | [QuickStart](ginux-edition/docs/QUICKSTART.md) · [User guide](ginux-edition/docs/USER_GUIDE.md) | Docker systemd boot and interactive OCI ThoxOS shell; authenticated browser console with image-team captures and logs | Fresh Docker execution in this continuation environment; Windows writer and physical SSD acceptance |
| **Headless kernel lifecycle** | [Azure Compute Start Here](docs/azure/START_HERE.md) · [Kernel module](module-ginux/README.md) | Patched EFI, embedded `/sbin/init`, detached status, restart, recovery, shutdown and saved configuration under QEMU TCG | Azure host deployment and broader Linux workload compatibility |

The implementations have separate patch sets and binary identities. [The reconciliation record](docs/RECONCILIATION_2026-10-29.md) preserves both. [The continuation note](docs/continuation/README.md) distinguishes prior-team image validation from checks rerun for this source change.

![ThoxOS Desktop with TXF Slate and About, captured over RDP from a VHD booted in QEMU](ginux-edition/docs/previews/azure/rdp-slate-about.png)

*Authentic image-team capture: ThoxOS Desktop on Debian 13, reached over RDP in QEMU software emulation. The Ginux VM inside this Linux host desktop has a console. This is not an Azure deployment capture.*

![Console Pro desktop with ThoxOS running on Ginux in a terminal, captured in QEMU](ginux-edition/docs/previews/azure/rdp-console-pro-ginux.png)

## Start with the interactive shell

On an x86-64 Linux build host with Docker Engine/Desktop and the documented prerequisites:

```bash
cd ginux-edition
make test
make demo-image
make selftest
make demo-shell
```

Try `uname -srm`, `thox version` and `thox status`. `make demo` instead reaches the systemd login prompt; interactive use uses `make demo-shell` because the upstream getty path does not complete login. The Docker demo runs QEMU and keeps Docker's Linux host kernel.

For a browser shell after building the image:

```bash
docker run --rm -e THOXOS_G_MODE=shell -p 127.0.0.1:7681:7681 \
  -v thoxos-g-state:/var/lib/thoxos-g/state thoxos-g/demo:0.1.0 web
```

Open `http://127.0.0.1:7681` and use the generated credential in the container log. Keep the bind address on loopback. The [user guide](ginux-edition/docs/USER_GUIDE.md) covers configuration, persistence and troubleshooting.

## Desktop and external-SSD images

The image implementation is under `ginux-edition/`. Host images use version `0.2.0`; its Ginux guest/userspace is `0.1.0`. The image team's [validation record](ginux-edition/docs/VALIDATION.md) and [raw evidence](ginux-edition/docs/evidence/0.2.0/) document a cold kernel build, Docker checks, desktop VHD bench (23 checks), headless VHD bench (13 checks), and SSD image QEMU USB-disk bench (6 checks). These are separate from physical hardware tests and new continuation checks.

Follow the [QuickStart](ginux-edition/docs/QUICKSTART.md) to build the Azure desktop/headless VHD or KnightHub SSD image. The 0.2.0 image fixes per-machine identity initialization found in the earlier 0.1.0 image. Physical writing needs a clearly identified spare target; the protected THOXOS/Vibe disk is not a default target. No physical SSD was selected or written in this continuation.

The desktop VHD has an unsigned boot loader and uses **Standard** Azure security with restricted-source SSH/RDP and a public IP. The separate root `azure/` variant uses an Ubuntu 24.04 Gen2 marketplace host, **Trusted Launch**, private NIC, explicit NAT, container-scoped managed identity and SHA-256-pinned artifact. Preserve those differences. Both designs are Linux Azure VMs; neither is a Windows Azure Virtual Desktop session host. Azure deployment and Gallery publication remain unrun.

## Headless Azure Compute kernel

Version `0.2.0-azure-candidate` under root `module-ginux/` and `azure/` has a separate complete EFI: 12,507,648 bytes, SHA-256 `3ebcc9043ef9dc8b7e75abc15b113a5810c8d39c0ad47143476a41caed24d5ba`. Build-receipt SHA-256: `c4ac916269f053a689801af6a9214b6613090a35bd0a247eeb3e2d10d6ccf31b`.

The [kernel lifecycle receipt](evidence/azure/lifecycle-results.json) records 22 actual QEMU commands across cold and recovered boots. [The Azure validation summary](evidence/azure/VALIDATION_SUMMARY.json) records the original 120 unit checks across kernel, upstream libraries, launchers, SSD and Azure tooling. These are payload-bound historical results, not a claim that every check was rerun for this continuation. The strict Microsoft.Resources schema failure and 13 adapted local checks remain separate in [the schema receipt](azure/ARM_SCHEMA_VALIDATION.json).

Git contains source, patches, receipts and attribution. Compiled EFI and full host images are separate payloads; a source ZIP is not an installation image. The root [Azure guide](docs/azure/START_HERE.md), [PDF](docs/azure/THOX_Ginux_Azure_Deployment_Guide.pdf), [HTML](docs/azure/html/THOX_Ginux_Azure_Deployment_Guide.html), [deployment commands](azure/README.md) and [manual capture procedure](azure/CAPTURE_MASTER_IMAGE.md) cover this path.

## Evidence and boundaries

[Recorded demos](docs/azure/media/README.md) include actual Ginux screen recordings and separately labeled synthetic user scenes. The image team's [desktop capture inventory](ginux-edition/docs/DESKTOP.md#screenshots) identifies splash, login, three looks and the working Ginux console. Current source-change evidence belongs to [the continuation record](docs/continuation/README.md).

No established MeshStack or ThoxWork integration runs inside this Ginux variant. Ginux and desktop captures do not prove distributed inference. Native Ginux Hyper-V boot, a Ginux graphical desktop, qualified NVIDIA/CUDA, native USB/NVMe drivers and general Linux application compatibility remain unestablished. Hosted-model relay tests use a local stub; real hosted inference remains unrun. No stable GitHub Release or physical acceptance is claimed.

## Historical kit

The [October 28 kit guide](START_HERE.md), [PDF](docs/THOX_Ginux_Research_Guide.pdf), [HTML](docs/html/THOX_Ginux_Research_Guide.html) and [original validation](evidence/VALIDATION_SUMMARY.json) remain predecessor evidence, including that payload's embedded-domain panic. The original `ssd-module/` installer copies files onto an existing accepted Linux host; it does not flash, repartition or reboot. Its image/writer mismatch is historical to that path and does not negate the separate image bench.

## Source, license and development

Ginux upstream is `gmkurtzer/ginux` commit `36503bda2d87465765e1b94e65f9d100f27ed5be`, Apache-2.0. THOX work preserves upstream authorship and notices; see [LICENSE](LICENSE), [NOTICE.md](NOTICE.md), [module provenance](module-ginux/SOURCE_MANIFEST.json) and [image-lane notice](ginux-edition/NOTICE.md). The root research module originated in `ttracx/thoxos-desktop-debian` at `1390b8a18334e91d03725b177c813760f4b38579`.

Use [local CI](ginux-edition/docs/DEVELOPMENT.md#continuous-integration) for the image implementation; GitHub Actions is retired under the existing cost decision. Local checks do not establish Azure or physical acceptance. See [Releases](https://github.com/ttracx/thoxos-ginux/releases) for actual issued releases.

Internal continuity: [agent entry](AGENTS.md), [continuation handoff](.agents/CONTINUATION_HANDOFF.md), [root handoff](.agents/HANDOFF.md) and [image-lane handoff](ginux-edition/.agents/HANDOFF.md). Keep agent instructions out of user installation packages and public output.

Copyright 2026 THOX.ai LLC for original THOX work. Private engineering repository; public publication and production qualification are separate states.
